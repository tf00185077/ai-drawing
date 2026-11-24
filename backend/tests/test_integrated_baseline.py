"""Offline coexistence contract: unavailable Worker, durable LoRA, both graph targets."""
import json
import os
import subprocess
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import workers
from app.core.workflow import apply_params
from app.main import app
from app.schemas.lora_train import LoraSmokeTestRequest
from app.services import lora_trainer, nvidia_worker
from tests.test_lora_delivery import isolated_worker


@pytest.mark.parametrize("target", ["local", "worker"])
@pytest.mark.parametrize("identity", [
    {"hostname": "OTHER-PC", "protocol_version": 2},
    {"hostname": "EXPECTED-PC", "protocol_version": 1},
])
def test_unavailable_worker_preserves_lora_http_mcp_and_graph_contract(
    isolated_worker, monkeypatch, target, identity
):
    """Removing health identity validation makes the public unavailable assertion fail."""
    from pathlib import Path

    interpreter = os.environ.get("MCP_TEST_PYTHON")
    if not interpreter:
        pytest.skip("MCP_TEST_PYTHON must name the separate prepared MCP environment")
    w = isolated_worker
    locator = f"AI-Drawing/{w.job.run_locator}/{w.job.resolved_output_name}.safetensors"
    lora_trainer._update_persistent_job(
        w.job.job_id, status="completed", registered_lora_name=locator
    )
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=identity))
    monkeypatch.setattr(
        nvidia_worker.httpx, "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    worker = nvidia_worker.NvidiaWorkerClient(
        "http://worker.invalid:8791", expected_hostname="EXPECTED-PC",
        expected_protocol_version=2, discovery_enabled=False,
    )
    monkeypatch.setattr(workers, "get_worker_client", lambda: worker)
    monkeypatch.setattr(workers, "get_settings", lambda: SimpleNamespace(nvidia_worker_url=worker.base_url))
    client = TestClient(app)
    worker_status = client.get("/api/workers/status").json()
    assert {key: worker_status[key] for key in ("configured", "reachable", "status", "error_type")} == {
        "configured": True, "reachable": False, "status": "unavailable",
        "error_type": "WorkerConfigurationError",
    }
    response = client.get(f"/api/lora-train/jobs/{w.job.job_id}")
    assert response.status_code == 200
    public = response.json()
    assert public["resolved_output_name"] == w.job.resolved_output_name
    assert public["registered_lora_name"] == locator
    script = '''
import json,sys,httpx
from unittest.mock import patch
from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train
payload=json.load(sys.stdin); original=httpx.Client
transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload))
with patch.object(lora_train,'_get_client',return_value=HttpBackendClient('http://fixture.invalid/api')),patch('httpx.Client',side_effect=lambda **kw:original(transport=transport,**kw)):
 result=lora_train.lora_train_job_status('fixture')
assert result['ok'] is True and result['registered_lora_name']==payload['registered_lora_name']
assert result['resolved_output_name']==payload['resolved_output_name'] and result['output_serial']==payload['output_serial']
'''
    result = subprocess.run(
        [interpreter, "-c", script], input=response.text, text=True, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(Path.cwd() / "mcp-server")},
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    submitted = []
    monkeypatch.setattr(lora_trainer, "submit_generation", lambda params: submitted.append(params) or "mock-generation")
    smoke = lora_trainer.smoke_test_job(w.job.job_id, LoraSmokeTestRequest(execution_target=target))
    assert smoke["generation_job_id"] == "mock-generation"
    graph = apply_params({"1": {"class_type": "LoraLoader", "inputs": {
        "lora_name": "old", "model": ["0", 0], "clip": ["0", 1],
    }}}, lora=submitted[0]["lora"])
    assert submitted[0]["execution_target"] == target
    assert graph["1"]["inputs"]["lora_name"] == locator
