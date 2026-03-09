"""
Slack 指令定義：COMMAND_SPECS、parse_command、validate_params、build_help_message

供 slack_handler 使用，不直接呼叫 API。
規範：docs/slack-command-scheme.md、docs/slack-command-agent-tracker.md
"""
from __future__ import annotations

import json
import re
from typing import Any

# 指令定義：cmd_key, triggers, required, example, desc
# 觸發關鍵字依長度由長到短排序，避免「!用指定動作生圖片」被「!用文字生圖片」先匹配
COMMAND_SPECS: list[dict[str, Any]] = [
    {
        "cmd_key": "help",
        "triggers": ["!給我可用指令", "給我可用指令", "!help"],
        "required": [],
        "example": "!給我可用指令",
        "desc": "顯示此清單",
    },
    {
        "cmd_key": "generate_pose",
        "triggers": ["!用指定動作生圖片", "!用文字生圖片指定動作"],
        "required": ["prompt", "image_pose"],
        "example": '!用指定動作生圖片 {"prompt":"1girl", "image_pose":"2026-03-08/xxx.png"}',
        "desc": "生圖 + 姿態參考圖",
    },
    {
        "cmd_key": "generate",
        "triggers": ["!生圖片", "!用文字生圖片"],
        "required": ["prompt"],
        "example": '!生圖片 {"prompt":"1girl, miku", "batch_size":3}',
        "desc": "依 prompt 生圖",
    },
    {
        "cmd_key": "train_lora",
        "triggers": ["!訓練lora", "!進行lora訓練"],
        "required": ["folder"],
        "example": '!訓練lora {"folder":"my_char", "epochs":10}',
        "desc": "手動觸發 LoRA 訓練",
    },
    {
        "cmd_key": "query_gallery",
        "triggers": ["!查詢圖片", "!查詢圖片參數"],
        "required": [],
        "example": '!查詢圖片 {"limit":10}',
        "desc": "圖庫列表",
    },
    {
        "cmd_key": "rerun",
        "triggers": ["!重新生成圖片", "!重現圖片"],
        "required": ["image_id"],
        "example": '!重新生成圖片 {"image_id":123}',
        "desc": "用某張圖參數再產",
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

    # 預期 rest 為 JSON 物件
    if rest.startswith("{"):
        return (cmd_key, rest)
    return (cmd_key, None)


def validate_params(cmd_key: str, data: dict[str, Any]) -> str | None:
    """
    檢查必填欄位。缺必填回傳錯誤字串，否則回傳 None。
    """
    spec = next((s for s in COMMAND_SPECS if s["cmd_key"] == cmd_key), None)
    if not spec:
        return f"未知指令: {cmd_key}"
    required = spec.get("required", [])
    for field in required:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"缺少必填參數：{field}"

    # rerun 的 image_id 必須為整數
    if cmd_key == "rerun" and "image_id" in data:
        try:
            vid = data["image_id"]
            if isinstance(vid, str):
                int(vid)
            elif not isinstance(vid, int):
                return "image_id 必須為整數"
        except (ValueError, TypeError):
            return "image_id 必須為整數"

    return None


def build_help_message() -> str:
    """回傳「給我可用指令」的完整文案。"""
    lines = [
        "📋 可用指令：",
        "",
        "1. !生圖片 <JSON>",
        "   依 prompt 生圖。例：!生圖片 {\"prompt\":\"1girl, miku\", \"batch_size\":3}",
        "   參數：prompt(必填), batch_size, checkpoint, lora, negative_prompt, seed, steps, cfg, width, height",
        "",
        "2. !用指定動作生圖片 <JSON>",
        "   生圖 + 姿態參考圖。例：!用指定動作生圖片 {\"prompt\":\"1girl\", \"image_pose\":\"2026-03-08/xxx.png\"}",
        "   參數：prompt(必填), image_pose(必填), batch_size, checkpoint, lora, ...",
        "",
        "3. !訓練lora <JSON>",
        "   手動觸發 LoRA 訓練。例：!訓練lora {\"folder\":\"my_char\", \"epochs\":10}",
        "   參數：folder(必填), checkpoint, epochs, resolution, batch_size, ...",
        "",
        "4. !查詢圖片 <JSON>",
        "   圖庫列表。例：!查詢圖片 {\"limit\":10}",
        "   參數：limit, offset, checkpoint, lora, from_date, to_date",
        "",
        "5. !重新生成圖片 <JSON>",
        "   用某張圖參數再產。例：!重新生成圖片 {\"image_id\":123}",
        "",
        "輸入 !給我可用指令 可隨時查看此清單。",
    ]
    return "\n".join(lines)


def parse_json_safe(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    解析 JSON 字串。成功回傳 (data, None)，失敗回傳 (None, error_msg)。
    """
    if not raw or not raw.strip():
        return ({}, None)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return (None, "參數必須為 JSON 物件")
        return (data, None)
    except json.JSONDecodeError as e:
        return (None, f"JSON 解析失敗: {e}")
