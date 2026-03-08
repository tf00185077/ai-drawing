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
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ComfyUIError(Exception):
    """ComfyUI API 錯誤"""

    def __init__(self, message: str, node_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.node_errors = node_errors or {}


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


def get_output_images(history: dict[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    """
    從 history 中萃取出所有輸出圖片
    Returns: [{"filename": str, "subfolder": str, "type": str}, ...]
    """
    images: list[dict[str, Any]] = []
    prompt_data = history.get(prompt_id, {})
    outputs = prompt_data.get("outputs", {})

    for node_out in outputs.values():
        for img in node_out.get("images", []):
            images.append({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
    return images
