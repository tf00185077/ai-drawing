"""
slack_notifier 單元測試
"""
from unittest.mock import patch

import pytest

from app.services.slack_notifier import notify_job_failed


@patch("app.services.slack_notifier.get_settings")
def test_notify_job_failed_posts_message(mock_settings) -> None:
    """有 token 時發送訊息"""
    mock_settings.return_value.slack_bot_token = "xoxb-test"
    with patch("slack_sdk.WebClient") as mock_client:
        notify_job_failed("C123", "job-abc", "ComfyUI 連線失敗")
        mock_client.return_value.chat_postMessage.assert_called_once()
        call_kw = mock_client.return_value.chat_postMessage.call_args[1]
        assert call_kw["channel"] == "C123"
        assert "job-abc" in call_kw["text"]
        assert "ComfyUI 連線失敗" in call_kw["text"]


@patch("app.services.slack_notifier.get_settings")
def test_notify_job_failed_with_thread_ts(mock_settings) -> None:
    """有 thread_ts 時以 thread 回覆"""
    mock_settings.return_value.slack_bot_token = "xoxb-test"
    with patch("slack_sdk.WebClient") as mock_client:
        notify_job_failed("C123", "job-xyz", "err", thread_ts="123.456")
        call_kw = mock_client.return_value.chat_postMessage.call_args[1]
        assert call_kw["thread_ts"] == "123.456"


@patch("app.services.slack_notifier.get_settings")
def test_notify_job_failed_skips_when_no_token(mock_settings) -> None:
    """無 token 時不發送、不拋錯"""
    mock_settings.return_value.slack_bot_token = ""
    with patch("slack_sdk.WebClient") as mock_client:
        notify_job_failed("C123", "job-x", "err")
        mock_client.return_value.chat_postMessage.assert_not_called()
