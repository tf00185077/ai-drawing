"""生圖 API 端點測試"""
from unittest.mock import patch

from app.core.queue import _reset_for_test


def setup_function() -> None:
    _reset_for_test()


def test_post_generate_returns_201_with_job_id(client) -> None:
    """POST /api/generate/ 回傳 201 與 job_id"""
    r = client.post(
        "/api/generate/",
        json={"prompt": "1girl, solo"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "已加入" in (data.get("message") or "")


def test_post_generate_returns_503_when_queue_full(client) -> None:
    """佇列已滿時 POST 回傳 503"""
    from app.core.queue import QueueFullError

    with patch("app.api.generate.submit", side_effect=QueueFullError("full")):
        r = client.post(
            "/api/generate/",
            json={"prompt": "test"},
        )
    assert r.status_code == 503


def test_get_queue_returns_valid_structure(client) -> None:
    """GET /api/generate/queue 回傳正確結構"""
    r = client.get("/api/generate/queue")
    assert r.status_code == 200
    data = r.json()
    assert "queue_running" in data
    assert "queue_pending" in data
    assert isinstance(data["queue_running"], list)
    assert isinstance(data["queue_pending"], list)
