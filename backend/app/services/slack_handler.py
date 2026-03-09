"""
Slack 訊息處理：解析指令、觸發生圖、回覆使用者

職責：解析 Slack message 事件，組成 GenerateParams，呼叫 queue.submit()，
並以 chat.postMessage 回覆。不直接呼叫 ComfyUI。

規範：.cursor/rules/slack-trigger.mdc
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.core.queue import GenerateParams, QueueFullError, submit
from app.services import slack_commands

logger = logging.getLogger(__name__)

# 支援指令格式：!generate <描述> [張數] 或 生圖 <描述> [張數]（legacy）
_PATTERN_GENERATE = re.compile(
    r"^(?:!generate|生圖)\s+(.+?)(?:\s+(\d+))?\s*張?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _is_slack_command(text: str) -> bool:
    """
    是否為本 handler 處理的指令（新 JSON 指令或 legacy !generate/生圖）。
    """
    stripped = text.strip()
    if not stripped:
        return False
    cmd_key, _ = slack_commands.parse_command(text)
    if cmd_key is not None:
        return True
    return (
        stripped.lower().startswith("!generate")
        or stripped.startswith("生圖")
    )


def _parse_legacy_command(text: str) -> tuple[str, int] | None:
    """
    解析 legacy 生圖指令，回傳 (prompt, batch_size) 或 None。

    支援格式：
    - !generate 初音 5
    - 生圖 初音 5
    - 生圖 1girl, solo
    """
    if not text or not text.strip():
        return None
    text = text.strip()
    m = _PATTERN_GENERATE.match(text)
    if not m:
        return None
    prompt = m.group(1).strip()
    count_str = m.group(2)
    batch_size = 1
    if count_str:
        try:
            n = int(count_str)
            batch_size = max(1, min(n, 8))
        except ValueError:
            pass
    if not prompt:
        return None
    return (prompt, batch_size)


def _check_comfyui_available() -> bool:
    """檢查 ComfyUI 是否可用（簡單 GET 到 base URL）"""
    settings = get_settings()
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{settings.comfyui_base_url.rstrip('/')}/system_stats")
            return r.status_code == 200
    except Exception as e:
        logger.debug("ComfyUI health check failed: %s", e)
        return False


def _safe_say(say: Any, channel: str, text: str) -> None:
    """安全回覆 Slack，錯誤僅 log"""
    try:
        say(channel=channel, text=text)
    except Exception as e:
        logger.exception("Slack say failed: %s", e)


# 白名單：與 COMMAND_SPECS["generate"] required + optional 對齊
_GENERATE_ALLOWED_KEYS = frozenset(
    {"prompt", "batch_size", "checkpoint", "lora", "negative_prompt", "seed", "steps", "cfg", "width", "height", "sampler_name", "scheduler"}
)


def _handle_generate_command(say: Any, channel: str, json_str: str | None, user: str, event: dict[str, Any] | None = None) -> None:
    """
    S3.2：!生圖片 → POST /api/generate/
    201→已加入佇列；503→佇列滿；400→參數錯誤
    """
    if json_str is None:
        _safe_say(say, channel, "參數格式錯誤，請用 !給我可用指令 查看")
        return
    data, parse_err = slack_commands.parse_json_safe(json_str)
    if parse_err:
        _safe_say(say, channel, f"參數格式錯誤：{parse_err}")
        return
    val_err = slack_commands.validate_params("generate", data)
    if val_err:
        _safe_say(say, channel, val_err)
        return
    body = {k: v for k, v in data.items() if k in _GENERATE_ALLOWED_KEYS and v is not None}
    if "prompt" not in body:
        _safe_say(say, channel, "缺少必填參數：prompt")
        return

    # 傳遞 Slack 頻道資訊，供任務失敗時通知
    body["slack_channel_id"] = channel
    if event and (ts := event.get("ts")):
        body["slack_thread_ts"] = ts

    base_url = get_settings().internal_api_base_url.rstrip("/")
    url = f"{base_url}/api/generate/"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=body)
    except Exception as e:
        logger.exception("Slack generate API call failed: %s", e)
        _safe_say(say, channel, "生圖服務暫不可用")
        return

    if r.status_code == 201:
        try:
            resp = r.json()
            job_id = resp.get("job_id", "unknown")
            _safe_say(say, channel, f"已加入生圖佇列，job_id: {job_id}")
        except Exception:
            _safe_say(say, channel, "已加入生圖佇列")
    elif r.status_code == 503:
        _safe_say(say, channel, "生圖佇列已滿")
        logger.warning("Slack user %s hit queue full (503)", user)
    elif r.status_code == 400:
        try:
            detail = r.json().get("detail", str(r.text))
            if isinstance(detail, list):
                detail = "; ".join(str(d.get("msg", d)) for d in detail)
        except Exception:
            detail = str(r.text) or "參數錯誤"
        _safe_say(say, channel, f"參數錯誤：{detail}")
    else:
        logger.warning("Slack generate API unexpected status %d: %s", r.status_code, r.text)
        _safe_say(say, channel, "生圖服務暫不可用")


def handle_message(event: dict[str, Any], say: Any, logger_instance: Any) -> None:
    """
    Slack message 事件處理：解析生圖指令、提交佇列、回覆使用者。

    簽名符合 Slack Bolt 的 message 事件 handler：(event, say, logger)。
    """
    # 過濾 bot 自身訊息，避免迴圈
    if event.get("bot_id"):
        return
    # 子類型（如 message_changed）略過
    if event.get("subtype") and event["subtype"] != "thread_broadcast":
        return

    text = event.get("text") or ""
    channel = event.get("channel")
    user = event.get("user", "unknown")

    if not _is_slack_command(text):
        return

    # 新指令（JSON 格式）
    cmd_key, json_str = slack_commands.parse_command(text)
    if cmd_key is not None:
        if cmd_key == "help":
            _safe_say(say, channel, slack_commands.build_help_message())
        elif cmd_key == "generate":
            _handle_generate_command(say, channel, json_str, user, event=event)
        else:
            _safe_say(say, channel, "此指令開發中，請稍後再試")
        return

    # Legacy：!generate / 生圖
    parsed = _parse_legacy_command(text)
    if not parsed:
        _safe_say(
            say,
            channel,
            "無法理解，請輸入生圖描述，例如：!generate 初音 5",
        )
        return

    prompt, batch_size = parsed

    if not _check_comfyui_available():
        _safe_say(say, channel, "生圖服務暫不可用")
        return

    params: GenerateParams = {
        "prompt": prompt,
        "batch_size": batch_size,
        "slack_channel_id": channel,
    }
    if ts := event.get("ts"):
        params["slack_thread_ts"] = ts

    try:
        job_id = submit(params)
        _safe_say(say, channel, f"已加入生圖佇列，job_id: {job_id}")
    except QueueFullError:
        _safe_say(say, channel, "生圖佇列已滿，請稍後再試")
        logger.warning("Slack user %s hit QueueFullError", user)
    except Exception as e:
        logger.exception("Slack handler unexpected error: %s", e)
        _safe_say(say, channel, "生圖服務暫不可用")
