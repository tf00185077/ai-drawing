"""LoRA training MCP tool contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.lora_train import (
    lora_dataset_inspect,
    lora_dataset_list,
    lora_dataset_prepare,
    lora_dataset_validate,
    lora_train_cancel,
    lora_train_job_status,
    lora_train_logs,
    lora_train_smoke_test,
    lora_train_start,
    lora_train_status,
)


def _http_error(status_code: int, detail: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://backend.test/api")
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(str(status_code), request=request, response=response)


def test_lora_dataset_tools_return_structured_success() -> None:
    """Dataset list/inspect/prepare tools return dict payloads and forward backend calls."""
    mock_client = MagicMock()
    mock_client.get.side_effect = [
        {"datasets": [{"folder": "character/miku", "image_count": 2, "dataset_hash": "hash-a"}]},
        {"folder": "character/miku", "files": [], "dataset_hash": "hash-a"},
    ]
    mock_client.post.return_value = {
        "ok": True,
        "folder": "character/miku",
        "normalized_trigger_token": "miku_token",
        "changed_count": 1,
        "dataset_hash_before": "hash-a",
        "dataset_hash_after": None,
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        listed = lora_dataset_list()
        inspected = lora_dataset_inspect("character/miku", trigger_token="miku_token")
        prepared = lora_dataset_prepare(
            "character/miku",
            trigger_token="miku_token",
            dry_run=True,
            expected_dataset_hash="hash-a",
        )

    assert listed["ok"] is True
    assert listed["tool"] == "lora_dataset_list"
    assert listed["datasets"][0]["folder"] == "character/miku"
    assert inspected["tool"] == "lora_dataset_inspect"
    assert prepared["submitted"]["expected_dataset_hash"] == "hash-a"
    mock_client.get.assert_any_call("lora-train/datasets")
    mock_client.get.assert_any_call(
        "lora-train/datasets/character/miku",
        params={"trigger_token": "miku_token"},
    )
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/prepare",
        json={
            "folder": "character/miku",
            "trigger_token": "miku_token",
            "dry_run": True,
            "use_ai_cleanup": False,
            "expected_dataset_hash": "hash-a",
        },
    )


def test_lora_dataset_validate_surfaces_blocking_errors() -> None:
    """Backend validation ok=false becomes a machine-readable MCP failure."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": False,
        "folder": "character/miku",
        "normalized_trigger_token": "miku_token",
        "dataset_hash": "hash-a",
        "errors": [{"code": "missing_trigger_token", "message": "caption missing trigger"}],
        "warnings": [],
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_validate("character/miku", "miku_token")

    assert result["ok"] is False
    assert result["tool"] == "lora_dataset_validate"
    assert result["error"]["code"] == "missing_trigger_token"
    assert result["error"]["details"]["response"]["dataset_hash"] == "hash-a"


def test_lora_dataset_validate_surfaces_stale_hash_conflict() -> None:
    """HTTP conflict details are preserved for agents to re-inspect/re-validate."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        409,
        {
            "code": "dataset_hash_mismatch",
            "message": "dataset hash does not match expected hash",
            "details": {"current_dataset_hash": "hash-new"},
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_validate("character/miku", "miku_token", expected_dataset_hash="hash-old")

    assert result["ok"] is False
    assert result["status_code"] == 409
    assert result["error"]["code"] == "dataset_hash_mismatch"
    assert result["error"]["details"]["current_dataset_hash"] == "hash-new"


def test_lora_train_start_and_status_return_structured_success() -> None:
    """Training start and aggregate status no longer require text parsing."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "job_id": "job-1",
        "status": "queued",
        "stage": "queued",
        "dataset_hash": "hash-a",
        "normalized_trigger_token": "miku_token",
    }
    mock_client.get.return_value = {
        "status": "queued",
        "queue": [{"job_id": "job-1", "folder": "character/miku"}],
        "current_job": None,
        "last_result": None,
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        started = lora_train_start(
            "character/miku",
            checkpoint="model.safetensors",
            epochs=2,
            trigger_token="miku_token",
            expected_dataset_hash="hash-a",
        )
        status = lora_train_status()

    assert started["ok"] is True
    assert started["tool"] == "lora_train_start"
    assert started["job_id"] == "job-1"
    assert started["submitted"]["expected_dataset_hash"] == "hash-a"
    assert status["ok"] is True
    assert status["queue"][0]["job_id"] == "job-1"


def test_lora_train_job_status_not_found_is_structured() -> None:
    """Not-found jobs return ok=false with backend error code."""
    mock_client = MagicMock()
    mock_client.get.side_effect = _http_error(
        404,
        {"code": "job_not_found", "message": "LoRA training job not found", "details": {}},
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_job_status("missing")

    assert result["ok"] is False
    assert result["tool"] == "lora_train_job_status"
    assert result["status_code"] == 404
    assert result["error"]["code"] == "job_not_found"


def test_lora_train_logs_maps_backend_log_error_payload() -> None:
    """Log retrieval ok=false payloads become structured MCP errors."""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "ok": False,
        "job_id": "job-1",
        "lines": [],
        "truncated": False,
        "log_path": "/tmp/missing.log",
        "error_code": "log_not_found",
        "error_message": "job log file not found",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_logs("job-1", lines=20)

    assert result["ok"] is False
    assert result["tool"] == "lora_train_logs"
    assert result["error"]["code"] == "log_not_found"
    assert result["error"]["details"]["response"]["log_path"] == "/tmp/missing.log"
    mock_client.get.assert_called_once_with("lora-train/jobs/job-1/logs", params={"lines": 20})


def test_lora_train_cancel_returns_structured_status() -> None:
    """Cancellation result includes job id and resulting status."""
    mock_client = MagicMock()
    mock_client.post.return_value = {"ok": True, "job_id": "job-1", "status": "cancelled"}

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_cancel("job-1")

    assert result == {"ok": True, "tool": "lora_train_cancel", "job_id": "job-1", "status": "cancelled"}


def test_lora_train_smoke_test_precondition_is_structured() -> None:
    """Smoke-test precondition failures expose the backend code/details."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        400,
        {
            "code": "smoke_test_precondition_failed",
            "message": "LoRA job has no registered_lora_name",
            "details": {"registration_error": "not configured"},
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_smoke_test("job-1")

    assert result["ok"] is False
    assert result["tool"] == "lora_train_smoke_test"
    assert result["error"]["code"] == "smoke_test_precondition_failed"
    assert result["error"]["details"]["registration_error"] == "not configured"
