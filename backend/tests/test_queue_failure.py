"""自訂 workflow 失敗：ComfyUI node_errors 結構化、不重試、可查詢"""
from unittest.mock import MagicMock

from app.core import queue as q
from app.core.comfyui import ComfyUIError, structure_node_errors


# --- 結構化 node_errors 純函式 -------------------------------------------


def test_structure_node_errors_dict_form() -> None:
    raw = {
        "7": {
            "class_type": "KSampler",
            "errors": [{"message": "Value not in list", "details": "sampler_name"}],
        }
    }
    out = structure_node_errors(raw)
    assert out == [
        {"node_id": "7", "class_type": "KSampler", "reason": "Value not in list: sampler_name"}
    ]


def test_structure_node_errors_falls_back_to_workflow_class_type() -> None:
    raw = {"3": "Required input is missing"}
    wf = {"3": {"class_type": "VAEEncode"}}
    out = structure_node_errors(raw, wf)
    assert out[0]["class_type"] == "VAEEncode"
    assert "missing" in out[0]["reason"]


# --- worker 失敗處理 ------------------------------------------------------


def _drain_pending(monkeypatch, comfy) -> None:
    """執行一次 _process_pending（用假 comfy）。"""
    q._process_pending(comfy)


def test_invalid_custom_workflow_marked_failed_not_requeued(monkeypatch) -> None:
    q._reset_for_test()
    job_id = q.submit_custom({"workflow": {"7": {"class_type": "KSampler"}}, "prompt": "x"})

    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ComfyUIError(
        "invalid prompt",
        node_errors={"7": {"class_type": "KSampler", "errors": [{"message": "bad", "details": ""}]}},
    )
    # patch load_template 不需要（custom 有 workflow），但 apply 流程會走到 submit_prompt
    q._process_pending(comfy)

    status = q.get_job_status(job_id)
    assert status is not None
    assert status["status"] == "failed"
    assert status["node_errors"] == [
        {"node_id": "7", "class_type": "KSampler", "reason": "bad"}
    ]
    # 不得被重新排回 pending（過去的隊首阻塞 bug）
    assert all(j.job_id != job_id for j in q._pending)
    assert q._running is None


def test_custom_workflow_uses_its_locked_checkpoint_without_inventory_default(monkeypatch) -> None:
    """A compiled recipe workflow must not depend on mutable backend inventory."""
    q._reset_for_test()
    workflow = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "locked-recipe.safetensors"},
        }
    }
    q.submit_custom({"workflow": workflow})
    monkeypatch.setattr(q, "default_checkpoint", lambda settings: None)
    comfy = MagicMock()
    comfy.submit_prompt.return_value = "prompt-1"

    q._process_pending(comfy)

    comfy.submit_prompt.assert_called_once()
    submitted = comfy.submit_prompt.call_args.args[0]
    assert submitted["4"]["inputs"]["ckpt_name"] == "locked-recipe.safetensors"


def test_connection_failure_marked_failed_without_node_errors(monkeypatch) -> None:
    import httpx

    q._reset_for_test()
    job_id = q.submit_custom({"workflow": {"7": {"class_type": "KSampler"}}, "prompt": "x"})
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = httpx.ConnectError("refused")
    q._process_pending(comfy)

    status = q.get_job_status(job_id)
    assert status["status"] == "failed"
    assert status["node_errors"] == []


def test_job_status_api_passes_through_node_errors() -> None:
    """GET /api/generate/job/{id} 對 failed 任務回傳 error 與結構化 node_errors"""
    from fastapi.testclient import TestClient
    from app.main import app

    q._reset_for_test()
    job_id = q.submit_custom({"workflow": {"7": {"class_type": "KSampler"}}, "prompt": "x"})
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ComfyUIError(
        "invalid prompt",
        node_errors={"7": {"class_type": "KSampler", "errors": [{"message": "bad", "details": ""}]}},
    )
    q._process_pending(comfy)

    c = TestClient(app)
    r = c.get(f"/api/generate/job/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["error"] == "invalid prompt"
    assert body["node_errors"][0]["node_id"] == "7"


def test_job_status_api_passes_through_recording_error() -> None:
    """GET /api/generate/job/{id} exposes structured recording errors."""
    from fastapi.testclient import TestClient
    from app.main import app

    q._reset_for_test()
    job = q._Job(job_id="job-recording", params={}, submitted_at="t")
    q._record_failure(
        job,
        RuntimeError("generation finished with no supported output artifact"),
        recording_error={
            "code": "no_supported_output_artifact",
            "message": "generation finished with no supported output artifact",
        },
    )

    r = TestClient(app).get("/api/generate/job/job-recording")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["recording_error"] == {
        "code": "no_supported_output_artifact",
        "message": "generation finished with no supported output artifact",
    }
