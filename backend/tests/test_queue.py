"""批次生圖排程器單元測試"""
from unittest.mock import patch

import pytest

from app.core.queue import (
    QueueFullError,
    _reset_for_test,
    get_job_status,
    get_status,
    submit,
)


def setup_function() -> None:
    """每個測試前清空佇列"""
    _reset_for_test()


def test_submit_returns_job_id() -> None:
    """submit 回傳有效的 job_id"""
    job_id = submit({"prompt": "1girl"})
    assert isinstance(job_id, str)
    assert len(job_id) == 36


def test_submit_raises_when_full() -> None:
    """佇列已滿時 submit 拋出 QueueFullError"""
    with patch("app.core.queue.MAX_PENDING", 2):
        submit({"prompt": "a"})
        submit({"prompt": "b"})
        with pytest.raises(QueueFullError):
            submit({"prompt": "c"})


def test_get_status_empty_initially() -> None:
    """初始狀態下 get_status 回傳空佇列"""
    status = get_status()
    assert status["queue_running"] == []
    assert status["queue_pending"] == []


def test_get_status_after_submit() -> None:
    """submit 後 get_status 包含 pending 項目"""
    job_id = submit({"prompt": "test"})
    status = get_status()
    assert len(status["queue_pending"]) == 1
    assert status["queue_pending"][0]["job_id"] == job_id
    assert status["queue_pending"][0]["status"] == "queued"
    assert "submitted_at" in status["queue_pending"][0]


def test_get_job_status_returns_none_for_unknown() -> None:
    """未知 job_id 時 get_job_status 回傳 None"""
    assert get_job_status("nonexistent-id") is None


def test_get_job_status_returns_pending_job() -> None:
    """get_job_status 可取得 pending 任務狀態"""
    job_id = submit({"prompt": "x"})
    job = get_job_status(job_id)
    assert job is not None
    assert job["job_id"] == job_id
    assert job["status"] == "queued"
