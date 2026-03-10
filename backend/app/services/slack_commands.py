"""
Slack 指令定義：COMMAND_SPECS 為唯一資料來源

供 slack_handler 使用，不直接呼叫 API。
規範：docs/slack-command-scheme.md、docs/api-contract.md
"""
from __future__ import annotations

import json
from typing import Any

# =============================================================================
# 唯一資料來源：所有指令、參數、說明皆由此定義
# 與 docs/api-contract.md 對應：§1 生圖、§2 圖庫、§4 LoRA 訓練
# =============================================================================
COMMAND_SPECS: list[dict[str, Any]] = [
    {
        "cmd_key": "help",
        "triggers": ["!給我可用指令", "給我可用指令", "!help"],
        "required": [],
        "optional": [],
        "example": "!給我可用指令",
        "desc": "顯示此清單",
    },
    {
        "cmd_key": "generate_pose",
        "triggers": ["!用指定動作生圖片", "!用文字生圖片指定動作"],
        "required": ["prompt", "image_pose"],
        "optional": ["batch_size", "checkpoint", "lora", "negative_prompt", "seed", "steps", "cfg", "width", "height"],
        "example": '!用指定動作生圖片 {"prompt":"1girl", "image_pose":"2026-03-08/xxx.png"}',
        "desc": "生圖 + 姿態參考圖",
    },
    {
        "cmd_key": "generate",
        "triggers": ["!生圖片", "!用文字生圖片"],
        "required": ["prompt"],
        "optional": ["batch_size", "checkpoint", "lora", "negative_prompt", "seed", "steps", "cfg", "width", "height", "sampler_name", "scheduler"],
        "example": '!生圖片 {"prompt":"1girl, miku", "batch_size":3}',
        "desc": "依 prompt 生圖",
    },
    {
        "cmd_key": "train_lora",
        "triggers": ["!訓練lora", "!進行lora訓練"],
        "required": ["folder"],
        "optional": ["checkpoint", "epochs", "resolution", "batch_size", "learning_rate", "class_tokens", "keep_tokens", "num_repeats", "mixed_precision", "generate_after"],
        "example": '!訓練lora {"folder":"my_char", "epochs":10}',
        "desc": "手動觸發 LoRA 訓練",
    },
    {
        "cmd_key": "query_gallery",
        "triggers": ["!查詢圖片", "!查詢圖片參數"],
        "required": [],
        "optional": ["limit", "offset", "checkpoint", "lora", "from_date", "to_date", "image_id", "image_name"],
        "example": '!查詢圖片 {"limit":10} 或 {"image_id":123}',
        "desc": "圖庫列表，可用 image_id 或 image_name 查詢",
    },
    {
        "cmd_key": "rerun",
        "triggers": ["!重新生成圖片", "!重現圖片"],
        "required": ["image_id"],
        "optional": [],
        "example": '!重新生成圖片 {"image_id":123}',
        "desc": "用某張圖參數再產",
    },
    {
        "cmd_key": "list_resources",
        "triggers": ["!查可用資源", "!列出模型", "!查模型"],
        "required": [],
        "optional": [],
        "example": "!查可用資源",
        "desc": "列出 checkpoint、lora、workflow 清單",
    },
]


def _match_trigger(text: str) -> tuple[str, str] | None:
    """
    辨識訊息開頭是否為任一指令觸發，回傳 (cmd_key, rest)。
    rest 為觸發關鍵字之後的內容（已 strip）。
    若無匹配回傳 None。
    """
    stripped = text.strip()
    if not stripped:
        return None

    for spec in COMMAND_SPECS:
        for trigger in spec["triggers"]:
            if stripped.lower().startswith(trigger.lower()) or stripped.startswith(trigger):
                rest = stripped[len(trigger) :].strip()
                return (spec["cmd_key"], rest)
    return None


def parse_command(text: str) -> tuple[str | None, str | None]:
    """
    辨識訊息是否為指令，回傳 (cmd_key, json_str)。

    - 無匹配：(None, None)
    - help：(cmd_key, "{}")
    - 其他有 JSON：(cmd_key, json_str)
    - 其他無有效 JSON：(cmd_key, None) 表示格式無效
    """
    matched = _match_trigger(text)
    if not matched:
        return (None, None)

    cmd_key, rest = matched

    if cmd_key == "help":
        return (cmd_key, "{}")

    if not rest:
        return (cmd_key, "{}")

    if rest.startswith("{"):
        return (cmd_key, rest)
    return (cmd_key, None)


def validate_params(cmd_key: str, data: dict[str, Any]) -> str | None:
    """
    檢查必填欄位。缺必填回傳錯誤字串，否則回傳 None。
    必填欄位來源：COMMAND_SPECS
    """
    spec = _get_spec(cmd_key)
    if not spec:
        return f"未知指令: {cmd_key}"
    required = spec.get("required", [])
    for field in required:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"缺少必填參數：{field}"

    if cmd_key in ("rerun", "query_gallery") and "image_id" in data and data["image_id"] is not None:
        try:
            vid = data["image_id"]
            if isinstance(vid, str):
                int(vid)
            elif not isinstance(vid, int):
                return "image_id 必須為整數"
        except (ValueError, TypeError):
            return "image_id 必須為整數"

    return None


def _get_spec(cmd_key: str) -> dict[str, Any] | None:
    """依 cmd_key 取得 spec"""
    return next((s for s in COMMAND_SPECS if s["cmd_key"] == cmd_key), None)


def get_allowed_keys(cmd_key: str) -> frozenset[str]:
    """
    取得指令允許的參數鍵（required + optional），供 handler 白名單過濾。
    與 COMMAND_SPECS 對齊，單一來源。
    """
    spec = _get_spec(cmd_key)
    if not spec:
        return frozenset()
    required = spec.get("required", [])
    optional = spec.get("optional", [])
    return frozenset(required + optional)


def _format_params_line(spec: dict[str, Any]) -> str:
    """從 COMMAND_SPECS 產生參數說明字串"""
    required = spec.get("required", [])
    optional = spec.get("optional", [])
    parts = [f"{r}(必填)" for r in required]
    parts.extend(optional)
    return ", ".join(parts) if parts else "—"


def build_help_message() -> str:
    """
    從 COMMAND_SPECS 產生 help 文案（支援 Slack mrkdwn 排版）。
    唯一資料來源：COMMAND_SPECS
    """
    lines = ["*📋 可用指令*", ""]
    idx = 1
    for spec in COMMAND_SPECS:
        if spec["cmd_key"] == "help":
            continue
        trigger = spec["triggers"][0]
        params_line = _format_params_line(spec)
        lines.append(f"*{idx}. {trigger}*")
        lines.append(f"  {spec['desc']}")
        lines.append(f"  例：`{spec['example']}`")
        lines.append(f"  參數：{params_line}")
        lines.append("")
        idx += 1
    lines.append("_輸入 !給我可用指令 可隨時查看此清單_")
    return "\n".join(lines)


def parse_json_safe(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    解析 JSON 字串。成功回傳 (data, None)，失敗回傳 (None, error_msg)。
    錯誤訊息含解析失敗位置（行、欄）以便定位。
    """
    if not raw or not raw.strip():
        return ({}, None)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return (None, "參數必須為 JSON 物件")
        return (data, None)
    except json.JSONDecodeError as e:
        pos = f"第 {e.lineno} 行第 {e.colno} 欄" if getattr(e, "lineno", None) else "未知位置"
        return (None, f"JSON 解析失敗（{pos}）：{e.msg}")


def format_api_param_error(detail: Any, prefix: str = "參數錯誤") -> str:
    """
    解析 Backend API 回傳的驗證錯誤詳情，產出可讀的參數級錯誤訊息。
    支援 FastAPI/Pydantic 格式：detail 為 list 時，每項含 loc（路徑）、msg。
    例：detail=[{"loc":["body","batch_size"],"msg":"..."}] → "參數 batch_size 錯誤：..."
    """
    if isinstance(detail, str):
        return f"{prefix}：{detail}"
    if not isinstance(detail, list):
        return f"{prefix}：{detail}"

    parts: list[str] = []
    seen_params: set[str] = set()
    for item in detail:
        if not isinstance(item, dict):
            parts.append(str(item))
            continue
        loc = item.get("loc") or []
        msg = item.get("msg", "")
        # loc 如 ["body", "batch_size"] 或 ["query", "limit"]，取最後一項為參數名
        param = loc[-1] if isinstance(loc, (list, tuple)) and len(loc) > 0 else None
        if param is not None and param not in seen_params:
            seen_params.add(param)
            parts.append(f"參數 {param}：{msg}")
        elif msg:
            parts.append(msg)
    return f"{prefix}：{'; '.join(parts)}" if parts else f"{prefix}"
