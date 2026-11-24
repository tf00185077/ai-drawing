"""D2: real routes/client validation; only remote HTTP and LAN candidates are fake."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import system, workers
from app.config import Settings, get_settings
from app.main import app as backend_app
from app.services import dependency_status, nvidia_worker


@pytest.fixture(autouse=True)
def isolated_cache():
    nvidia_worker.clear_runtime_worker_urls()
    yield
    nvidia_worker.clear_runtime_worker_urls()


def export(name, data):
    destination = os.environ.get("HEALTH_WORKER_HTTP_EXPORT")
    if destination:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("case", [
    "unconfigured", "up", "connection", "http", "hostname", "protocol",
    "invalid-json", "invalid-object", "url-only", "discovered-then-invalid",
])
def test_worker_route_configuration_and_current_observation(monkeypatch, case):
    # Breaks if failed probes erase configuration, borrow expectations/cache as
    # observations, or replace configured URL with the selected runtime endpoint.
    configured = "http://192.0.2.10:8791"
    resolved = "http://192.0.2.11:8791"
    settings = Settings(_env_file=None, nvidia_worker_url="" if case == "unconfigured" else configured + "/",
                        nvidia_worker_hostname="" if case == "url-only" else "EXPECTED-PC",
                        nvidia_worker_discovery_enabled=case == "discovered-then-invalid")
    monkeypatch.setattr(workers, "get_settings", lambda: settings)
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)
    scans = []
    def candidates(**kwargs):
        assert case == "discovered-then-invalid", "Unexpected LAN discovery"
        scans.append(kwargs)
        return [resolved]
    monkeypatch.setattr(nvidia_worker, "_open_worker_candidates", candidates)
    requests = []
    failed_identity = False
    accepted = {"protocol_version": 2, "worker_version": "test"}
    if case != "url-only":
        accepted["hostname"] = "expected-pc"
    def respond(request):
        requests.append([request.method, str(request.url)])
        assert request.method == "GET" and request.url.path == "/v1/worker/status"
        if case == "connection" or (case == "discovered-then-invalid" and request.url.host == "192.0.2.10"):
            raise httpx.ConnectError("private-upstream-detail", request=request)
        if case == "http":
            return httpx.Response(503, text="private-upstream-detail")
        if case == "invalid-json":
            return httpx.Response(200, text="private-upstream-detail")
        if case == "invalid-object":
            return httpx.Response(200, json=[])
        body = dict(accepted)
        if case == "hostname" or failed_identity:
            body["hostname"] = "OTHER-PC"
        if case == "protocol":
            body["protocol_version"] = 1
        # Existing discovery matches hostname case sensitively before health's
        # accepted case-insensitive validation. Keep that production policy.
        if case == "discovered-then-invalid" and not failed_identity:
            body["hostname"] = "EXPECTED-PC"
        return httpx.Response(200, json=body)
    real_client = httpx.Client
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(nvidia_worker.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs))
    route_app = FastAPI()
    route_app.include_router(workers.router)
    client = TestClient(route_app)
    snapshots = []
    for attempt in range(2 if case == "discovered-then-invalid" else 1):
        response = client.get("/api/workers/status")
        assert response.status_code == 200
        body = response.json()
        snapshots.append(body)
        assert body["configured"] is (case != "unconfigured")
        assert body["url"] == (None if case == "unconfigured" else configured)
        assert body["expected_hostname"] == (None if case == "url-only" else "EXPECTED-PC")
        assert body["expected_protocol_version"] == 2
        success = case in {"up", "url-only", "discovered-then-invalid"} and attempt == 0
        assert body["reachable"] is success
        if success:
            assert body["status"] == "ready"
            assert body["worker"]["protocol_version"] == body["protocol_version"] == 2
            assert body["hostname"] == (None if case == "url-only" else body["worker"]["hostname"])
            assert body["resolved_url"] == (resolved if scans else configured)
            assert body["last_error"] is None
        else:
            assert body["status"] == ("not_configured" if case == "unconfigured" else "unavailable")
            assert body["hostname"] is body["protocol_version"] is body["resolved_url"] is None
            assert "worker" not in body
            if case != "unconfigured":
                assert body["last_error"] and "retry" in body["last_error"].lower()
                assert body["error_type"] == ("ConnectError" if case == "connection" else "HTTPStatusError" if case == "http" else "WorkerConfigurationError")
        assert "private-upstream-detail" not in json.dumps(body)
        failed_identity = True
    if case == "discovered-then-invalid":
        assert len(scans) == 1
        assert nvidia_worker.get_worker_client().base_url == resolved  # cache survives; observation does not
        assert requests == [["GET", configured + "/v1/worker/status"], *[["GET", resolved + "/v1/worker/status"]] * 3]
    else:
        assert not scans
        assert requests == ([] if case == "unconfigured" else [["GET", configured + "/v1/worker/status"]])
    export(case, {"responses": snapshots, "requests": requests})


@pytest.mark.parametrize("state", ["connected", "no_models", "degraded", "unreachable", "not_configured"])
def test_real_system_route_exports_dependency_states(monkeypatch, tmp_path, state):
    # Keep system route/schema/inventory/probe parsing real, mocking urlopen only.
    checkpoints = tmp_path / "checkpoints"
    diffusion = tmp_path / "diffusion"
    checkpoints.mkdir()
    if state != "degraded":
        diffusion.mkdir()
    if state in {"connected", "degraded"}:
        (checkpoints / "fixture.safetensors").write_bytes(b"not-a-model; inventory-only")
    settings = Settings(_env_file=None, comfyui_mode="disabled" if state == "not_configured" else "external",
                        comfyui_base_url="http://backend-local.invalid:8188",
                        comfyui_checkpoints_dir=str(checkpoints), comfyui_diffusion_models_dir=str(diffusion))
    requests = []
    def urlopen(url, timeout):
        requests.append(["GET", url])
        if state == "unreachable":
            raise OSError("offline")
        return io.BytesIO(b"{}")
    monkeypatch.setattr(dependency_status, "urlopen", urlopen)
    route_app = FastAPI()
    route_app.include_router(system.router)
    route_app.dependency_overrides[get_settings] = lambda: settings
    response = TestClient(route_app).get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["comfyui"]["state"] == state
    assert body["comfyui"]["reachable"] is (state in {"connected", "no_models", "degraded"})
    assert all(method == "GET" and url.startswith("http://backend-local.invalid:8188/") for method, url in requests)
    export("comfyui-" + state, {"response": body, "requests": requests})


def test_application_health_export():
    response = TestClient(backend_app).get("/health")
    assert response.status_code == 200 and response.json() == {"status": "healthy"}
    export("backend", {"response": response.json(), "requests": [["GET", "/health"]]})
