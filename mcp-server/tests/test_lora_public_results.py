"""MCP public result boundary via real HTTP client and mock transport (no network)."""
import json
from unittest.mock import patch

import httpx
import pytest

from mcp_server.client import HttpBackendClient
from mcp_server.tools import lora_train

MARKER = "MCP_SYNTHETIC_14"
RAW = f"API_TOKEN={MARKER} /private/{MARKER} C:\\Private\\{MARKER}"


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("tool", ['status', 'start', 'preflight'])
def test_mcp_job_projects_nested_evidence_and_failure_fields(legacy, tool):
    payload = {
        "ok": True, "job_id": "job-14", "status": "failed", "stage": "failed",
        "run_locator": None if legacy else "旅人_002__stamp", "resolved_output_name": None if legacy else "旅人_002",
        "output_name": None if legacy else "旅人", "output_serial": None if legacy else 2,
        "output_config_hash": "a" * 64, "output_path": f"/private/{MARKER}/result", "log_path": f"C:\\Private\\{MARKER}\\training.log",
        "execution_evidence": {"argv": [RAW], "dataset_config_content": RAW, "reason": RAW},
        "component_identities": {"checkpoint": {"resolved_locator": f"/private/{MARKER}", "reason": RAW}},
        "params": {"checkpoint": f"C:\\Private\\{MARKER}", "epochs": 4, "raw": RAW},
        "error_code": "unexpected_error", "error_message": RAW, "error_details": {"nested": RAW},
        "registration_error": RAW, "smoke_test_error": RAW,
    }
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    original = httpx.Client
    with patch.object(lora_train, "_get_client", return_value=HttpBackendClient("http://backend.test/api")), patch("httpx.Client", side_effect=lambda **kw: original(transport=transport, **kw)):
        if tool == 'status':
            result = lora_train.lora_train_job_status("job-14")
        elif tool == 'start':
            result = lora_train.lora_train_start('fixture', output_name='旅人', expected_dataset_hash='a'*64, expected_profile_hash='b'*64, recipe={})
        else:
            result = lora_train.lora_training_decision_preflight('fixture', output_name='旅人')
    assert MARKER not in json.dumps(result)
    assert result["ok"] is True
    assert result["output_name"] == payload["output_name"]
    if tool != 'preflight':
        assert result["status"] == "failed"
        assert result["output_serial"] == payload["output_serial"]
        assert result["run_locator"] == payload["run_locator"]
    if tool == 'status':
        assert result["params"]["epochs"] == 4
        assert result["error_code"] and result["error_message"] and result["error_details"]["hint"]


def test_mcp_bounded_logs_do_not_replay_legacy_exception_text():
    payload = {"ok": True, "job_id": "job-14", "log_path": f"/private/{MARKER}/log", "lines": [RAW], "truncated": True}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    original = httpx.Client
    with patch.object(lora_train, "_get_client", return_value=HttpBackendClient("http://backend.test/api")), patch("httpx.Client", side_effect=lambda **kw: original(transport=transport, **kw)):
        result = lora_train.lora_train_logs("job-14", 1)
    assert result["ok"] is True and result["truncated"] is True
    assert result["lines"] and "redacted" in result["lines"][0]
    assert MARKER not in json.dumps(result)
