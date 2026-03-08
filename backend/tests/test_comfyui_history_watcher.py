"""ComfyUI history watcher 單元測試"""
from unittest.mock import patch

import pytest

from app.services.comfyui_history_watcher import _should_skip_prompt_id


def test_should_skip_returns_true_when_prompt_id_is_ours() -> None:
    """本系統提交的 prompt_id 應略過"""
    with patch("app.core.queue.get_our_prompt_ids", return_value={"abc-123"}):
        with patch("app.core.queue.get_status", return_value={"queue_running": []}):
            assert _should_skip_prompt_id("abc-123") is True


def test_should_skip_returns_true_when_prompt_id_is_running() -> None:
    """正在執行的 prompt_id 應略過（由 queue 記錄）"""
    with patch("app.core.queue.get_our_prompt_ids", return_value=set()):
        with patch(
            "app.core.queue.get_status",
            return_value={"queue_running": [{"prompt_id": "running-456"}]},
        ):
            assert _should_skip_prompt_id("running-456") is True


def test_should_skip_returns_false_when_external() -> None:
    """外部（ComfyUI UI 直接生成）的 prompt_id 不應略過"""
    with patch("app.core.queue.get_our_prompt_ids", return_value=set()):
        with patch("app.core.queue.get_status", return_value={"queue_running": []}):
            assert _should_skip_prompt_id("external-789") is False
