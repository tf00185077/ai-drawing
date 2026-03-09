"""
slack_notifier 單元測試
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.slack_notifier import notify_job_failed, notify_job_success


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


@patch("app.services.slack_notifier.get_settings")
def test_notify_job_success_uploads_files(mock_settings, tmp_path: Path) -> None:
    """有 token、有圖片時上傳至 Slack，附 id 與檔名"""
    mock_settings.return_value.slack_bot_token = "xoxb-test"
    img = tmp_path / "test.png"
    img.write_bytes(b"fake image")
    with patch("slack_sdk.WebClient") as mock_client:
        notify_job_success(
            channel_id="C123",
            job_id="job-abc",
            images=[(str(img), 42, "test.png")],
            thread_ts="123.456",
        )
        mock_client.return_value.files_upload_v2.assert_called_once()
        call_kw = mock_client.return_value.files_upload_v2.call_args[1]
        assert call_kw["channel"] == "C123"
        assert call_kw["thread_ts"] == "123.456"
        assert "id=42" in call_kw["initial_comment"]
        assert "test.png" in call_kw["initial_comment"]


@patch("app.services.slack_notifier.get_settings")
def test_notify_job_success_skips_when_no_token(mock_settings, tmp_path: Path) -> None:
    """無 token 時不發送、不拋錯"""
    mock_settings.return_value.slack_bot_token = ""
    img = tmp_path / "test.png"
    img.write_bytes(b"fake")
    with patch("slack_sdk.WebClient") as mock_client:
        notify_job_success("C123", "job-x", [(str(img), 1, "test.png")])
        mock_client.return_value.files_upload_v2.assert_not_called()
