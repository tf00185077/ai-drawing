"""
Slack 非同步通知（佇列任務完成／失敗時發送）
使用 Web API 發送訊息，不依賴 Bolt 的 say 上下文
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


def notify_job_success(
    channel_id: str,
    job_id: str,
    images: list[tuple[str, int, str]],
    thread_ts: str | None = None,
) -> None:
    """
    生圖完成後，將生成的圖片上傳至指定 Slack 頻道，並附上 id、檔名供查詢。
    images: [(full_path, db_id, filename), ...]
    """
    if not images:
        return
    settings = get_settings()
    if not settings.slack_bot_token:
        logger.debug("Slack bot token not set, skip success notify")
        return
    try:
        from slack_sdk import WebClient

        client = WebClient(token=settings.slack_bot_token)
        for full_path, db_id, filename in images:
            path = Path(full_path)
            if not path.exists():
                logger.warning("Slack success notify: file not found %s", full_path)
                continue
            comment = f"id={db_id}, 檔名={filename}"
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "file": str(path),
                "initial_comment": comment,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            try:
                client.files_upload_v2(**kwargs)
            except Exception as e:
                logger.warning("Slack files_upload_v2 failed for %s: %s", filename, e)
        logger.info("Slack success notify sent for job %s, %d image(s)", job_id, len(images))
    except Exception as e:
        logger.warning("Slack success notify failed for job %s: %s", job_id, e)


def notify_job_failed(channel_id: str, job_id: str, error_msg: str, thread_ts: str | None = None) -> None:
    """
    發送任務失敗通知至指定 Slack 頻道。
    若 token 未設定或發送失敗，僅 log，不拋出。
    """
    settings = get_settings()
    if not settings.slack_bot_token:
        logger.debug("Slack bot token not set, skip notify")
        return
    try:
        from slack_sdk import WebClient

        client = WebClient(token=settings.slack_bot_token)
        text = f"生圖任務 {job_id} 執行失敗：{error_msg}"
        kwargs: dict[str, Any] = {"channel": channel_id, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        client.chat_postMessage(**kwargs)
        logger.info("Slack notify sent for failed job %s", job_id)
    except Exception as e:
        logger.warning("Slack notify failed for job %s: %s", job_id, e)
