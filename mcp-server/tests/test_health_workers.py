"""D1-D3 through registration, envelope, real HTTP client and route-exported bodies."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import httpx
import pytest

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp


EXPORTS = Path(os.environ.get("HEALTH_WORKER_HTTP_EXPORT", Path(__file__).parent / "fixtures" / "health-workers"))
CASES = ["unconfigured", "up", "connection", "http", "hostname", "protocol", "invalid-json", "invalid-object", "url-only", "discovered-then-invalid"]


def exported(name):
    return json.loads((EXPORTS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("MCP_BACKEND_API_URL", "http://backend.invalid:8001")
    monkeypatch.setenv("MCP_COMFYUI_API_URL", "http://direct-admin.invalid:8188")
    get_mcp_settings.cache_clear()
    responses = {
        "/health": exported("backend")["response"],
        "/api/system/status": exported("comfyui-connected")["response"],
        "/api/workers/status": exported("up")["responses"][0],
    }
    requests = []
    def respond(request):
        requests.append([request.method, str(request.url)])
        assert request.method == "GET" and request.url.host == "backend.invalid"
        result = responses[request.url.path]  # unknown path/control requests fail
        if isinstance(result, str):
            if result == "connection":
                raise httpx.ConnectError("private-read-detail", request=request)
            if result == "http":
                return httpx.Response(503, json={"detail": {"code": "private-read-detail", "message": "private-read-detail"}})
            if result == "invalid-json":
                return httpx.Response(200, text="private-read-detail")
        return httpx.Response(200, content=json.dumps(result))
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    yield responses, requests
    get_mcp_settings.cache_clear()


async def call(name):
    blocks, structured = await mcp.call_tool(name, {})
    assert json.loads(blocks[0].text) == structured
    assert set(structured) == ({"ok", "data"} if structured["ok"] else {"ok", "error"})
    return structured


def paths(requests, expected):
    assert requests == [["GET", "http://backend.invalid:8001" + path] for path in expected]


@pytest.mark.parametrize("case", CASES)
async def test_list_keeps_configuration_and_only_current_accepted_observations(backend, case):
    # Faults: configured-down -> [], expectation substituted for hostname,
    # resolved URL replacing configuration, stale cache identity, stale error.
    responses, requests = backend
    samples = exported(case)["responses"]
    for body in samples:
        responses["/api/workers/status"] = body
        result = await call("list_workers")
        assert result["ok"] is True
        entries = result["data"]["workers"]
        if case == "unconfigured":
            assert entries == []
            continue
        assert len(entries) == 1
        worker = entries[0]
        assert worker["url"] == "http://192.0.2.10:8791"
        assert worker["expected_hostname"] == (None if case == "url-only" else "EXPECTED-PC")
        assert worker["expected_protocol_version"] == 2
        success = body["reachable"]
        assert worker["reachable"] is success
        assert worker["status"] == ("ready" if success else "unavailable")
        if success:
            assert worker["protocol_version"] == 2
            assert worker["hostname"] == (None if case == "url-only" else "EXPECTED-PC" if case == "discovered-then-invalid" else "expected-pc")
            assert worker["resolved_url"] == ("http://192.0.2.11:8791" if case == "discovered-then-invalid" else "http://192.0.2.10:8791")
            assert worker["last_error"] is None
        else:
            assert worker["hostname"] is worker["protocol_version"] is worker["resolved_url"] is None
            assert worker["last_error"] and "retry" in worker["last_error"].lower()
    paths(requests, ["/api/workers/status"] * len(samples))


@pytest.mark.parametrize("case", CASES)
async def test_health_retains_each_component_for_reported_worker_state(backend, case):
    responses, requests = backend
    responses["/api/workers/status"] = exported(case)["responses"][-1]
    result = await call("health")
    assert result["ok"] is True
    data = result["data"]
    assert set(data) == {"backend", "comfyui", "worker"}
    assert data["backend"]["reachable"] is data["comfyui"]["reachable"] is True
    worker = data["worker"]
    assert worker["configured"] is (case != "unconfigured")
    assert worker["reachable"] is (case in {"up", "url-only"})
    if not worker["reachable"]:
        assert worker["reason"]
        assert worker["reason_code"] == ("not_configured" if case == "unconfigured" else "reported_unreachable")
    paths(requests, ["/health", "/api/system/status", "/api/workers/status"])


@pytest.mark.parametrize("state", ["connected", "no_models", "degraded", "unreachable", "not_configured"])
async def test_health_preserves_backend_local_comfyui_state_and_hints(backend, state):
    # Fault: treating no_models/degraded as disconnected, or using direct admin.
    responses, requests = backend
    observed = exported("comfyui-" + state)["response"]["comfyui"]
    responses["/api/system/status"] = {"application": "healthy", "comfyui": observed}
    data = (await call("health"))["data"]["comfyui"]
    assert {key: data[key] for key in observed} == observed
    assert data["reachable"] is (state in {"connected", "no_models", "degraded"})
    assert (data["reason"] is None) is data["reachable"]
    if not data["reachable"]:
        assert data["reason_code"] == ("not_configured" if state == "not_configured" else "reported_unreachable")
    paths(requests, ["/health", "/api/system/status", "/api/workers/status"])


@pytest.mark.parametrize("failure", ["connection", "http", "invalid-json", [], {}, None, {"status": "unhealthy"}])
async def test_backend_health_read_failure_keeps_dependencies_not_observed(backend, failure):
    responses, requests = backend
    responses["/health"] = failure
    result = await call("health")
    assert result["ok"] is True
    data = result["data"]
    assert set(data) == {"backend", "comfyui", "worker"}
    assert data["backend"]["reachable"] is False
    assert data["backend"]["reason"]
    for component in ["comfyui", "worker"]:
        assert data[component]["reachable"] is False
        assert data[component]["configured"] is None
        assert data[component]["reason_code"] == "not_observed"
        assert "not observed" in data[component]["reason"].lower()
    assert "private-read-detail" not in json.dumps(result)
    paths(requests, ["/health"])


@pytest.mark.parametrize("path,component,other", [("/api/system/status", "comfyui", "worker"), ("/api/workers/status", "worker", "comfyui")])
@pytest.mark.parametrize("failure", ["connection", "http", "invalid-json", [], {}, None])
async def test_partial_read_failure_does_not_invent_failed_dependency_probe(backend, path, component, other, failure):
    responses, requests = backend
    responses[path] = failure
    result = await call("health")
    assert result["ok"] is True
    data = result["data"]
    assert set(data) == {"backend", "comfyui", "worker"}
    assert data["backend"]["reachable"] is data[other]["reachable"] is True
    assert data[component]["reachable"] is False
    assert data[component]["configured"] is None
    assert data[component]["reason_code"] == "not_observed"
    assert "not observed" in data[component]["reason"].lower()
    assert data[component]["read_error"]["code"] in {"backend_unavailable", "backend_http_error", "invalid_backend_status"}
    assert "private-read-detail" not in json.dumps(result)
    paths(requests, ["/health", "/api/system/status", "/api/workers/status"])


@pytest.mark.parametrize("failure,code", [("connection", "backend_unavailable"), ("http", "backend_http_error"), ("invalid-json", "invalid_backend_status"), ([], "invalid_backend_status"), ({}, "invalid_backend_status"), (None, "invalid_backend_status")])
async def test_unknown_worker_configuration_is_common_error_never_empty(backend, failure, code):
    responses, requests = backend
    responses["/api/workers/status"] = failure
    result = await call("list_workers")
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert result["error"]["message"]
    assert "retry this read" in result["error"]["hint"].lower()
    assert "private-read-detail" not in json.dumps(result)
    paths(requests, ["/api/workers/status"])


@pytest.mark.parametrize("change", [
    {"configured": "false"}, {"configured": False}, {"reachable": "true"},
    {"status": "not_configured"}, {"url": None}, {"expected_protocol_version": None},
    {"protocol_version": True}, {"protocol_version": 1}, {"resolved_url": None},
    {"hostname": "OTHER-PC"}, {"hostname": None}, {"last_error": "old-error"},
    {"reachable": False, "status": "unavailable", "last_error": "retry"},
])
async def test_inconsistent_worker_status_is_unknown_in_both_tools(backend, change):
    responses, _ = backend
    body = copy.deepcopy(exported("up")["responses"][0])
    body.update(change)
    responses["/api/workers/status"] = body
    result = await call("list_workers")
    assert result["ok"] is False and result["error"]["code"] == "invalid_backend_status"
    worker = (await call("health"))["data"]["worker"]
    assert worker["configured"] is None and worker["reason_code"] == "not_observed"


async def test_both_partial_reads_can_fail_without_losing_components(backend):
    responses, requests = backend
    responses["/api/system/status"] = "http"
    responses["/api/workers/status"] = "connection"
    data = (await call("health"))["data"]
    assert set(data) == {"backend", "comfyui", "worker"}
    assert data["backend"]["reachable"] is True
    assert all(data[key]["reason_code"] == "not_observed" for key in ["comfyui", "worker"])
    paths(requests, ["/health", "/api/system/status", "/api/workers/status"])
