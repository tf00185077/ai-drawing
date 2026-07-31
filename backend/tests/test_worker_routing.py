from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import generate
from app.core import queue as generation_queue
from app.main import app
from app.services.nvidia_worker import WorkerConfigurationError


def test_generate_defaults_to_local_target(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(generate, "submit", lambda params: captured.update(params) or "job")
    client = TestClient(app)

    response = client.post("/api/generate/", json={"prompt": "test"})

    assert response.status_code == 201
    assert captured["execution_target"] == "local"


def test_generate_routes_explicit_worker_without_fallback(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(generate, "submit", lambda params: captured.update(params) or "job")
    client = TestClient(app)

    response = client.post(
        "/api/generate/",
        json={"prompt": "test", "execution_target": "worker"},
    )

    assert response.status_code == 201
    assert captured["execution_target"] == "worker"


def test_generate_rejects_auto_target() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/generate/",
        json={"prompt": "test", "execution_target": "auto"},
    )

    assert response.status_code == 422


def test_unpaired_worker_selection_becomes_terminal_failed_job(monkeypatch) -> None:
    generation_queue._reset_for_test()
    try:
        job_id = generation_queue.submit(
            {"prompt": "fail closed", "execution_target": "worker"}
        )

        def reject_worker(_target: str):
            raise WorkerConfigurationError("NVIDIA Worker is not paired")

        monkeypatch.setattr(
            generation_queue, "get_generation_client", reject_worker
        )

        generation_queue._process_pending()

        status = generation_queue.get_job_status(job_id)
        assert status is not None
        assert status["status"] == "failed"
        assert "not paired" in status["error"]
        assert generation_queue._running is None
    finally:
        generation_queue._reset_for_test()
