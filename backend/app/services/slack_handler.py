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

logger = logging.getLogger(__name__)

# 支援指令格式：!generate <描述> [張數] 或 生圖 <描述> [張數]
_PATTERN_GENERATE = re.compile(
    r"^(?:!generate|生圖)\s+(.+?)(?:\s+(\d+))?\s*張?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _parse_command(text: str) -> tuple[str, int] | None:
    """
    解析生圖指令，回傳 (prompt, batch_size) 或 None。

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
            # ComfyUI 根路徑或 system_stats 皆可驗證連線
            r = client.get(f"{settings.comfyui_base_url.rstrip('/')}/system_stats")
            return r.status_code == 200
    except Exception as e:
        logger.debug("ComfyUI health check failed: %s", e)
        return False


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

    # 僅處理明確的指令前綴，避免對一般對話回覆
    stripped = text.strip()
    if not (
        stripped.lower().startswith("!generate")
        or stripped.startswith("生圖")
    ):
        return

    parsed = _parse_command(text)
    if not parsed:
        try:
            say(
                channel=channel,
                text="無法理解，請輸入生圖描述，例如：!generate 初音 5",
            )
        except Exception as e:
            logger.exception("Slack say failed (parse fail reply): %s", e)
        return

    prompt, batch_size = parsed

    # 可選：ComfyUI 可用性檢查
    if not _check_comfyui_available():
        try:
            say(channel=channel, text="生圖服務暫不可用")
        except Exception as e:
            logger.exception("Slack say failed (ComfyUI unavailable reply): %s", e)
        return

    params: GenerateParams = {
        "prompt": prompt,
        "batch_size": batch_size,
    }

    try:
        job_id = submit(params)
        try:
            say(channel=channel, text=f"已加入生圖佇列，job_id: {job_id}")
        except Exception as e:
            logger.exception("Slack say failed (success reply): %s", e)
    except QueueFullError:
        try:
            say(channel=channel, text="生圖佇列已滿，請稍後再試")
        except Exception as e:
            logger.exception("Slack say failed (queue full reply): %s", e)
        logger.warning("Slack user %s hit QueueFullError", user)
    except Exception as e:
        logger.exception("Slack handler unexpected error: %s", e)
        try:
            say(channel=channel, text="生圖服務暫不可用")
        except Exception as say_err:
            logger.exception("Slack say failed (error reply): %s", say_err)
