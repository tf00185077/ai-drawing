from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


WORKER_PATH = (
    Path(__file__).resolve().parents[2] / "worker" / "windows" / "worker.py"
)


def _load_worker():
    spec = importlib.util.spec_from_file_location("windows_worker_under_test", WORKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def worker_runtime(monkeypatch):
    monkeypatch.delenv("AI_DRAWING_COMFYUI_URL", raising=False)
    worker = _load_worker()
    return worker, TestClient(worker.app)


@pytest.fixture
def worker_module(worker_runtime):
    return worker_runtime[0]


@pytest.fixture
def worker_client(worker_runtime):
    return worker_runtime[1]


class ProxyResponse:
    def __init__(
        self,
        *,
        content: bytes = b"{}",
        status_code: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}


def test_comfyui_url_defaults_to_the_exact_production_loopback(monkeypatch) -> None:
    monkeypatch.delenv("AI_DRAWING_COMFYUI_URL", raising=False)

    worker = _load_worker()

    assert worker.COMFYUI_URL == "http://127.0.0.1:8188"


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:8188",
        "http://0.0.0.0:8188",
        "http://example.test:8188",
        "http://user@127.0.0.1:8188",
        "http://127.0.0.1:8188/path",
        "http://127.0.0.1:8188?query=1",
        "http://127.0.0.1:8188#fragment",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
    ],
)
def test_invalid_comfyui_override_fails_worker_startup(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("AI_DRAWING_COMFYUI_URL", value)

    with pytest.raises(ValueError, match="AI_DRAWING_COMFYUI_URL"):
        _load_worker()


def test_loopback_comfyui_override_is_used_only_by_direct_proxy(
    monkeypatch,
) -> None:
    override = "http://127.0.0.1:49152"
    monkeypatch.setenv("AI_DRAWING_COMFYUI_URL", override)
    worker = _load_worker()
    client = TestClient(worker.app)
    seen: list[tuple[str, str, dict[str, Any]]] = []

    def request(method: str, url: str, **kwargs: Any) -> ProxyResponse:
        seen.append((method, url, kwargs))
        return ProxyResponse(content=b'{"prompt_id":"prompt-1"}')

    monkeypatch.setattr(worker.httpx, "request", request)

    status = client.get("/v1/worker/status")
    prompt = client.post("/prompt", json={"prompt": {"1": {}}})

    assert status.status_code == 200
    assert prompt.json() == {"prompt_id": "prompt-1"}
    assert seen == [
        (
            "POST",
            f"{override}/prompt",
            {"timeout": 60, "json": {"prompt": {"1": {}}}},
        )
    ]


def test_status_is_only_open_discovery_metadata(
    worker_client, monkeypatch
) -> None:
    monkeypatch.setenv("COMPUTERNAME", "OPEN-CONTROL-WORKER")

    response = worker_client.get("/v1/worker/status")

    assert response.status_code == 200
    assert response.json() == {
        "protocol_version": 2,
        "worker_version": "0.3.0",
        "hostname": "OPEN-CONTROL-WORKER",
    }


def test_open_control_protocol_version_matches_example_default_status_and_discovery(
    worker_module, monkeypatch
) -> None:
    from app.config import Settings
    from app.services import nvidia_worker

    monkeypatch.delenv("NVIDIA_WORKER_PROTOCOL_VERSION", raising=False)
    monkeypatch.setenv("COMPUTERNAME", "OPEN-CONTROL-WORKER")
    example_lines = (
        Path(__file__).resolve().parents[2] / ".env.example"
    ).read_text(encoding="utf-8").splitlines()
    example_version = int(
        next(
            line.split("=", 1)[1]
            for line in example_lines
            if line.startswith("NVIDIA_WORKER_PROTOCOL_VERSION=")
        )
    )
    settings_version = Settings(_env_file=None).nvidia_worker_protocol_version
    status = worker_module.status()
    candidate = "http://192.168.1.120:8791"
    monkeypatch.setattr(
        nvidia_worker, "_open_worker_candidates", lambda **_kwargs: [candidate]
    )
    monkeypatch.setattr(
        nvidia_worker, "_probe_worker_status", lambda *_args, **_kwargs: status
    )

    discovered = nvidia_worker.discover_worker_url(
        failed_url="http://192.168.1.106:8791",
        expected_hostname="OPEN-CONTROL-WORKER",
        expected_protocol_version=settings_version,
        discovery_cidr="192.168.1.0/24",
        discovery_timeout=0.1,
    )

    assert example_version == settings_version == status["protocol_version"] == 2
    assert discovered == candidate


def test_prompt_ignores_applying_legacy_update_state(
    tmp_path, monkeypatch
) -> None:
    legacy_state_root = tmp_path / "legacy-update-state"
    legacy_status = legacy_state_root / "state" / "update-status.json"
    legacy_status.parent.mkdir(parents=True)
    legacy_status.write_text(json.dumps({"state": "applying"}), encoding="utf-8")
    monkeypatch.setenv("AI_DRAWING_WORKER_UPDATE_STATE_ROOT", str(legacy_state_root))
    worker = _load_worker()
    client = TestClient(worker.app)
    proxied: list[tuple[str, str, dict[str, Any]]] = []

    def request(method: str, url: str, **kwargs: Any) -> ProxyResponse:
        proxied.append((method, url, kwargs))
        return ProxyResponse(content=b'{"prompt_id":"prompt-1"}')

    monkeypatch.setattr(worker.httpx, "request", request)

    response = client.post("/prompt", json={"prompt": {"1": {}}})

    assert response.status_code == 200
    assert response.json() == {"prompt_id": "prompt-1"}
    assert proxied == [
        (
            "POST",
            f"{worker.COMFYUI_URL}/prompt",
            {"timeout": 60, "json": {"prompt": {"1": {}}}},
        )
    ]


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/v1/admin/update", {"json": {}}),
        ("get", "/v1/admin/update/status", {}),
        ("post", "/v1/admin/restart", {"json": {}}),
        ("get", "/v1/admin/restart/status?request_id=legacy", {}),
        ("post", "/v1/resources/plan", {"json": {}}),
        ("put", "/v1/resources/content", {}),
        ("post", "/v1/workflows/preflight", {"json": {}}),
    ],
)
def test_legacy_managed_and_validation_routes_are_not_live(
    worker_client, method: str, path: str, kwargs: dict[str, object]
) -> None:
    response = getattr(worker_client, method)(path, **kwargs)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/v1/worker/status", {}),
        ("post", "/prompt", {"json": {"prompt": {}}}),
        ("get", "/queue", {}),
    ],
)
def test_retained_worker_routes_need_no_authorization(
    worker_client,
    worker_module,
    monkeypatch,
    method: str,
    path: str,
    kwargs: dict[str, object],
) -> None:
    monkeypatch.setattr(
        worker_module.httpx,
        "request",
        lambda *_args, **_kwargs: ProxyResponse(),
    )

    response = getattr(worker_client, method)(path, **kwargs)

    assert "Authorization" not in response.request.headers
    assert response.status_code != 401


def test_prompt_returns_comfyui_error_body_unchanged(
    worker_client, worker_module, monkeypatch
) -> None:
    body = {
        "error": {"type": "prompt_outputs_failed_validation"},
        "node_errors": {"7": {"errors": [{"message": "missing model"}]}},
    }
    monkeypatch.setattr(
        worker_module.httpx,
        "request",
        lambda *_args, **_kwargs: ProxyResponse(
            content=json.dumps(body).encode("utf-8"),
            status_code=422,
        ),
    )

    response = worker_client.post("/prompt", json={"prompt": {}})

    assert response.status_code == 422
    assert response.json() == body
