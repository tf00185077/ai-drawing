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


def test_post_generate_custom_returns_201(client) -> None:
    """POST /api/generate/custom 接受 workflow 回傳 201"""
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {"class_type": "KSampler", "inputs": {"positive": ["6", 0], "negative": ["7", 0]}},
    }
    r = client.post(
        "/api/generate/custom",
        json={"workflow": wf, "prompt": "1girl, solo"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "job_id" in data
    assert "自訂" in (data.get("message") or "")


def test_get_workflow_templates_returns_list(client) -> None:
    """GET /api/generate/workflow-templates 回傳模板列表"""
    r = client.get("/api/generate/workflow-templates")
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)
    assert "default" in data["templates"]
