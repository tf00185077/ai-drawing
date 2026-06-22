"""
ComfyUI API 串接
REST API 遠端觸發 workflow、取得佇列狀態、取回輸出圖片

=== 設計說明：DI 與 Protocol 的好處 ===

本模組採用 Dependency Injection (DI) 與 Protocol 抽象，主要考量如下。

【一】依賴注入 (Dependency Injection) 的好處

1. 可測性 (Testability)
   - 問題：若 ComfyUIClient 在建構時直接讀取 config、每次方法內 new httpx.Client，
     單元測試必須 patch 模組層級的 get_settings、httpx.Client，脆弱且難維護。
   - 解法：提供 get_comfy_client() 工廠，由 FastAPI Depends 注入。測試時可
     覆寫 Depends 傳入 FakeComfyUIClient，無須 patch 任何模組。
   - 結果：測試與真實依賴解耦，行為可預測。

2. 配置彈性 (Configuration Flexibility)
   - 問題：單一進程若需連多個 ComfyUI 實例（如 A/B 測試、多環境），硬綁 get_settings()
     無法切換。
   - 解法：get_comfy_client() 從 config 讀取；需要時可定義 get_comfy_client_staging()
     等額外工廠，依路由或情境注入不同實例。
   - 結果：同一介面、不同實作，由組合根（Application 啟動處）決定。

3. 關注點分離 (Separation of Concerns)
   - 問題：Route handler 若自己 new ComfyUIClient()，既處理 HTTP 又負責建立基礎設施。
   - 解法：handler 只宣告「需要 ImageGenerationClient」，由框架注入。建立與生命週期
     交給 Depends。
   - 結果：route 層更薄，職責單一。

【二】Protocol 抽象的好處

1. 替換實作 (Implementation Swapping)
   - 問題：generate、queue、lora_trainer 若直接依賴 ComfyUIClient，未來要換成
     WebSocket 版、或另一個生圖引擎（如 Replicate API），須改動所有呼叫端。
   - 解法：定義 ImageGenerationClient Protocol，只約定 submit_prompt、get_history
     等行為。呼叫端依賴 Protocol，不依賴具體類別。
   - 結果：新增 ComfyUIWebSocketClient、ReplicateAdapter 時，只需實作 Protocol，
     並在 DI 處替換，呼叫端零改動。

2. 介面契約明確 (Explicit Contract)
   - 問題：回傳 dict、接受 dict 時，呼叫端不清楚「到底需要哪些 key」。
   - 解法：Protocol 的方法簽名即為契約。IDE、型別檢查器可推導，文件即程式碼。
   - 結果：減少「猜錯格式」導致的 runtime 錯誤。

3. 易於 Mock (Easy Mocking)
   - 問題：測試業務邏輯時，不想真的打 ComfyUI。若依賴具體類別，mock 必須繼承或
     造出完整實例，麻煩。
   - 解法：依賴 Protocol 時，測試只需提供一個簡單的 class，實作同名方法、回傳
     固定值即可。符合 Protocol 即相容。
   - 結果：Fake 類別可極簡，測試更專注於被測邏輯。

【三】綜合效果

- 新增類似功能：在 1–2 處新增（新 Protocol 實作 + 新 Depends 工廠）。
- 換儲存/引擎：改 DI 綁定即可，業務層不動。
- 單獨測試：注入 Fake，無須起真實 ComfyUI。
- API 變了：只改 ComfyUIClient 內部，對外 Protocol 保持穩定。

詳細架構討論見：docs/comfyui-di-design.md
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import get_settings
from app.core.artifacts import get_output_images as _get_output_images

logger = logging.getLogger(__name__)

# /object_info 的程序內快取，以 base_url 為 key：{base_url: (fetched_at, object_info)}。
# get_comfy_client() 每次請求都會 new 一個 client，故快取放模組層級才能跨請求共用。
# TTL 逾時即重抓，讓 ComfyUI 重啟或新增 custom node 後的節點集合能被反映。
_object_info_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_object_info_cache() -> None:
    """清空 /object_info 快取（測試用，或在已知實例變動時主動失效）。"""
    _object_info_cache.clear()


class ComfyUIError(Exception):
    """ComfyUI API 錯誤"""

    def __init__(self, message: str, node_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.node_errors = node_errors or {}


def structure_node_errors(
    node_errors: Mapping[str, Any] | None,
    workflow: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    """
    把 ComfyUI /prompt 回傳的 node_errors 整理成 agent 易解析的清單
    [{node_id, class_type, reason}]，供自組 workflow 失敗時讓 agent 自我修正。
    ComfyUI 的 node_errors 值可能是 {errors:[{message,details}], class_type} 或純字串，皆相容。
    """
    out: list[dict[str, str]] = []
    wf = workflow or {}
    for node_id, info in (node_errors or {}).items():
        class_type = ""
        reason = ""
        if isinstance(info, Mapping):
            class_type = str(info.get("class_type", "") or "")
            errs = info.get("errors")
            if isinstance(errs, (list, tuple)):
                msgs = []
                for e in errs:
                    if isinstance(e, Mapping):
                        m = str(e.get("message", "") or "")
                        d = str(e.get("details", "") or "")
                        msgs.append(f"{m}: {d}" if d else m)
                    else:
                        msgs.append(str(e))
                reason = "; ".join(m for m in msgs if m)
            else:
                reason = str(info.get("message", "") or info)
        else:
            reason = str(info)
        if not class_type:
            node = wf.get(str(node_id)) or wf.get(node_id)
            if isinstance(node, Mapping):
                class_type = str(node.get("class_type", "") or "")
        out.append(
            {"node_id": str(node_id), "class_type": class_type, "reason": reason}
        )
    return sorted(out, key=lambda x: x["node_id"])


def structure_execution_error(history_status: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """
    從 ComfyUI history entry 的 status（含 messages 內的 execution_error）整理成
    [{node_id, class_type, reason}]，與 structure_node_errors 同形狀，供執行期失敗回報。
    """
    out: list[dict[str, str]] = []
    messages = (history_status or {}).get("messages") or []
    for m in messages:
        if isinstance(m, (list, tuple)) and len(m) >= 2 and m[0] == "execution_error":
            d = m[1] if isinstance(m[1], Mapping) else {}
            reason = (
                str(d.get("exception_message", "") or "")
                or str(d.get("exception_type", "") or "")
                or "execution error"
            )
            out.append(
                {
                    "node_id": str(d.get("node_id", "") or ""),
                    "class_type": str(d.get("node_type", "") or ""),
                    "reason": reason,
                }
            )
    return out


@runtime_checkable
class ImageGenerationClient(Protocol):
    """
    生圖引擎客戶端介面。
    業務邏輯依賴此 Protocol，可於測試或替換引擎時注入不同實作。
    """

    def submit_prompt(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> str:
        """提交 workflow，回傳 prompt_id"""
        ...

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        """取得指定 prompt 的執行結果"""
        ...

    def get_queue(self) -> dict[str, Any]:
        """取得目前佇列狀態"""
        ...

    def fetch_image(
        self,
        filename: str,
        *,
        subfolder: str = "",
        ftype: str = "output",
    ) -> bytes:
        """從引擎取回輸出圖片"""
        ...


class ComfyUIClient:
    """ComfyUI REST API 客戶端，實作 ImageGenerationClient Protocol"""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_submit: float | None = None,
        timeout_fetch: float | None = None,
        timeout_queue: float | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.comfyui_base_url).rstrip("/")
        self._timeout_submit = timeout_submit if timeout_submit is not None else settings.comfyui_timeout_submit
        self._timeout_fetch = timeout_fetch if timeout_fetch is not None else settings.comfyui_timeout_fetch
        self._timeout_queue = timeout_queue if timeout_queue is not None else settings.comfyui_timeout_queue

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def submit_prompt(
        self,
        prompt: dict[str, Any],
        *,
        client_id: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> str:
        """
        提交 workflow 至 ComfyUI 佇列
        Returns: prompt_id
        Raises: ComfyUIError on API error
        """
        payload: dict[str, Any] = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        if extra_data:
            payload["extra_data"] = extra_data

        with httpx.Client(timeout=self._timeout_submit) as client:
            r = client.post(self._url("/prompt"), json=payload)
            if not r.is_success:
                try:
                    err_body = r.json()
                    msg = err_body.get("error", r.text or r.reason_phrase)
                    node_errors = err_body.get("node_errors", {})
                    logger.error(
                        "ComfyUI /prompt %s: %s, node_errors=%s",
                        r.status_code,
                        msg,
                        node_errors,
                    )
                    raise ComfyUIError(str(msg), node_errors=node_errors)
                except ComfyUIError:
                    raise
                except Exception:
                    r.raise_for_status()
            data = r.json()

        if "error" in data:
            raise ComfyUIError(
                data["error"],
                node_errors=data.get("node_errors", {}),
            )
        return data["prompt_id"]

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        """
        取得指定 prompt 的執行結果
        Returns: { prompt_id: { "outputs": {...}, "status": {...} } }
        """
        with httpx.Client(timeout=self._timeout_fetch) as client:
            r = client.get(self._url(f"/history/{prompt_id}"))
            r.raise_for_status()
            return r.json()

    def get_full_history(self) -> dict[str, Any]:
        """
        取得 ComfyUI 完整執行歷史（所有已完成的 prompt）。
        用於監聽從 ComfyUI UI 直接生成的圖片，自動記錄至圖庫。
        Returns: { prompt_id: { "outputs": {...}, "prompt": [...], "status": {...} }, ... }
        """
        with httpx.Client(timeout=self._timeout_fetch) as client:
            r = client.get(self._url("/history"))
            r.raise_for_status()
            return r.json()

    def get_queue(self) -> dict[str, Any]:
        """
        取得目前佇列狀態
        Returns: { "queue_running": [...], "queue_pending": [...] }
        """
        with httpx.Client(timeout=self._timeout_queue) as client:
            r = client.get(self._url("/queue"))
            r.raise_for_status()
            return r.json()

    def upload_image(
        self,
        file_path: Path,
        *,
        overwrite: bool = True,
        subfolder: str = "",
        ftype: str = "input",
    ) -> dict[str, str]:
        """
        上傳圖片至 ComfyUI input 資料夾，供 LoadImage 使用。
        Returns: {"name": filename, "subfolder": subfolder, "type": ftype}
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")
        with httpx.Client(timeout=self._timeout_submit) as client:
            with file_path.open("rb") as f:
                files = {"image": (file_path.name, f, "image/png")}
                data = {
                    "overwrite": "true" if overwrite else "false",
                    "type": ftype,
                }
                if subfolder:
                    data["subfolder"] = subfolder
                r = client.post(self._url("/upload/image"), files=files, data=data)
        if not r.is_success:
            raise ComfyUIError(f"Upload failed: {r.text or r.reason_phrase}")
        result = r.json()
        return {
            "name": result.get("name", file_path.name),
            "subfolder": result.get("subfolder", subfolder),
            "type": result.get("type", ftype),
        }

    def fetch_image(
        self,
        filename: str,
        *,
        subfolder: str = "",
        ftype: str = "output",
    ) -> bytes:
        """
        從 ComfyUI 取回輸出圖片
        Returns: 圖片二進位內容
        """
        params = {"filename": filename, "subfolder": subfolder, "type": ftype}
        with httpx.Client(timeout=self._timeout_fetch) as client:
            r = client.get(self._url("/view"), params=params)
            r.raise_for_status()
            return r.content

    def clear_queue(
        self,
        *,
        clear_pending: bool = True,
        clear_running: bool = False,
    ) -> None:
        """
        清除佇列
        clear_pending: 清除等候中的項目
        clear_running: 中斷目前執行中的 workflow
        """
        payload: dict[str, bool] = {}
        if clear_pending:
            payload["clear"] = True
        if clear_running:
            payload["clear_running"] = True
        if not payload:
            return
        with httpx.Client(timeout=self._timeout_queue) as client:
            r = client.post(self._url("/queue"), json=payload)
            r.raise_for_status()

    def get_object_info(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """
        取得 ComfyUI 節點目錄（/object_info），描述本實例「實際裝了哪些 node」與其
        input/output 規格。結果以 base_url 為 key 做程序內 TTL 快取，逾時或 force_refresh
        時重抓，以反映 ComfyUI 重啟 / 新增 custom node 後的節點變動。
        Returns: { node_type: { "input": {...}, "output": [...], "output_name": [...], ... }, ... }
        """
        settings = get_settings()
        ttl = settings.comfyui_object_info_ttl
        now = time.monotonic()
        cached = _object_info_cache.get(self.base_url)
        if not force_refresh and cached is not None and (now - cached[0]) < ttl:
            return cached[1]
        with httpx.Client(timeout=self._timeout_fetch) as client:
            r = client.get(self._url("/object_info"))
            r.raise_for_status()
            data = r.json()
        _object_info_cache[self.base_url] = (now, data)
        return data


def get_comfy_client() -> ComfyUIClient:
    """
    FastAPI Depends 工廠：注入 ComfyUIClient 實例。
    使用範例：
        @router.post("/")
        async def trigger_generate(comfy: ComfyUIClient = Depends(get_comfy_client)):
            ...
    測試時可覆寫 app.dependency_overrides[get_comfy_client] 傳入 Fake 實作。
    """
    settings = get_settings()
    return ComfyUIClient(base_url=settings.comfyui_base_url)


def search_node_types(
    object_info: dict[str, Any], query: str = "", category: str = ""
) -> list[dict[str, str]]:
    """
    從 /object_info 篩出 node type，僅回 {name, category}（不回完整 schema），供 agent
    單點查時避免一次拉回整包目錄。兩個篩選條件皆大小寫不敏感、子字串比對、可組合（AND）：
    - query：比對節點「名稱」（如 "ksampler"）
    - category：比對節點「類別」（如 "loaders"、"conditioning"）
    皆為空時列出全部；無相符回空清單（非錯誤）。
    """
    q = query.strip().lower()
    cat = category.strip().lower()
    result: list[dict[str, str]] = []
    for name, spec in object_info.items():
        node_cat = (spec.get("category") or "") if isinstance(spec, dict) else ""
        if q and q not in name.lower():
            continue
        if cat and cat not in node_cat.lower():
            continue
        result.append({"name": name, "category": node_cat})
    return sorted(result, key=lambda r: r["name"])


def list_node_categories(object_info: dict[str, Any]) -> list[dict[str, Any]]:
    """
    列出 /object_info 中所有節點類別與其節點數量，供 agent 先瀏覽「有哪些功能分類」
    再用 search_node_types(category=...) 縮小範圍。依類別名稱排序。
    """
    counts: dict[str, int] = {}
    for spec in object_info.values():
        cat = (spec.get("category") or "") if isinstance(spec, dict) else ""
        counts[cat] = counts.get(cat, 0) + 1
    return [{"category": c, "count": n} for c, n in sorted(counts.items())]


def extract_node_schema(
    object_info: dict[str, Any], node_type: str
) -> dict[str, Any] | None:
    """
    從 /object_info 萃取單一 node type 的 input/output 規格。
    Returns: {"node_type", "display_name", "category",
              "inputs": {"required": [{"name","type"}], "optional": [...]},
              "outputs": [{"name","type"}]}
    若該 node type 不存在於本實例則回 None。
    """
    spec = object_info.get(node_type)
    if spec is None:
        return None

    def _parse_inputs(group: dict[str, Any]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for name, definition in group.items():
            # ComfyUI input 定義為 [type, opts?]；type 可能是字串或 enum 清單
            if isinstance(definition, (list, tuple)) and definition:
                raw_type = definition[0]
            else:
                raw_type = definition
            type_name = "COMBO" if isinstance(raw_type, list) else str(raw_type)
            result.append({"name": name, "type": type_name})
        return result

    input_def = spec.get("input", {}) or {}
    outputs_types = spec.get("output", []) or []
    output_names = spec.get("output_name", []) or []
    outputs: list[dict[str, str]] = []
    for idx, otype in enumerate(outputs_types):
        oname = output_names[idx] if idx < len(output_names) else str(otype)
        outputs.append({"name": str(oname), "type": str(otype)})

    return {
        "node_type": node_type,
        "display_name": spec.get("display_name", node_type),
        "category": spec.get("category", ""),
        "inputs": {
            "required": _parse_inputs(input_def.get("required", {}) or {}),
            "optional": _parse_inputs(input_def.get("optional", {}) or {}),
        },
        "outputs": outputs,
    }


def get_output_images(history: dict[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    """
    從 history 中萃取出所有輸出圖片
    Returns: [{"filename": str, "subfolder": str, "type": str}, ...]
    """
    return _get_output_images(history, prompt_id)
