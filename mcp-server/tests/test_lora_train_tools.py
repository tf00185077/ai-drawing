"""LoRA training MCP tool contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.lora_train import (
    lora_training_decision_preflight,
    lora_train_cancel,
    lora_train_job_status,
    lora_train_logs,
    lora_train_start,
)


def _http_error(status_code: int, detail: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://backend.test/api")
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(str(status_code), request=request, response=response)


def test_lora_training_decision_preflight_returns_train_payload_without_starting_training() -> None:
    """Decision preflight forwards advisory train payloads and never calls training start."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": True,
        "folder": "character/miku",
        "decision": "train",
        "reasons": ["dataset validation passed"],
        "blocking_issues": [],
        "warnings": [],
        "next_actions": ["Ask the user for explicit approval, then call lora_train_start."],
        "dataset_hash": "hash-a",
        "profile_hash": "profile-hash-a",
        "normalized_trigger_token": "miku_token",
        "suggested_params": {
            "params": {
                "folder": "character/miku",
                "trigger_token": "miku_token",
                "expected_dataset_hash": "hash-a",
                "model_family": "sd15",
            },
            "rationale": ["metadata is complete"],
        },
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client), patch(
        "mcp_server.tools.lora_train.lora_train_start"
    ) as start:
        result = lora_training_decision_preflight(
            "character/miku",
            trigger_token="miku_token",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
        )

    assert result["ok"] is True
    assert result["tool"] == "lora_training_decision_preflight"
    assert result["decision"] == "train"
    assert result["suggested_params"]["params"]["expected_dataset_hash"] == "hash-a"
    assert result["submitted"]["expected_profile_hash"] == "profile-hash-a"
    start.assert_not_called()
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/training-decision-preflight",
        json={
            "folder": "character/miku",
            "trigger_token": "miku_token",
            "expected_dataset_hash": "hash-a",
            "expected_profile_hash": "profile-hash-a",
        },
    )


def test_lora_training_decision_preflight_keeps_do_not_train_as_success_payload() -> None:
    """A backend do_not_train decision is an assessment outcome, not an MCP transport error."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": True,
        "folder": "character/miku",
        "decision": "do_not_train",
        "reasons": ["dataset validation found blocking issues"],
        "blocking_issues": [{"code": "missing_caption", "message": "missing caption"}],
        "warnings": [],
        "next_actions": ["Do not call lora_train_start until blocking issues are resolved."],
        "dataset_hash": "hash-a",
        "profile_hash": "profile-hash-a",
        "normalized_trigger_token": "miku_token",
        "suggested_params": None,
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_training_decision_preflight("character/miku")

    assert result["ok"] is True
    assert result["tool"] == "lora_training_decision_preflight"
    assert result["decision"] == "do_not_train"
    assert result["blocking_issues"][0]["code"] == "missing_caption"
    assert "error" not in result
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/training-decision-preflight",
        json={"folder": "character/miku"},
    )


def test_lora_training_decision_preflight_surfaces_backend_error() -> None:
    """Backend transport/request failures remain structured MCP errors."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        404,
        {"code": "dataset_not_found", "message": "dataset folder not found", "details": {}},
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_training_decision_preflight("character/missing")

    assert result["ok"] is False
    assert result["tool"] == "lora_training_decision_preflight"
    assert result["status_code"] == 404
    assert result["error"]["code"] == "dataset_not_found"


def test_lora_train_start_returns_structured_success() -> None:
    """Training start no longer requires text parsing."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "job_id": "job-1",
        "status": "queued",
        "stage": "queued",
        "dataset_hash": "hash-a",
        "normalized_trigger_token": "miku_token",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        started = lora_train_start(
            "character/miku",
            checkpoint="model.safetensors",
            epochs=2,
            trigger_token="miku_token",
            expected_dataset_hash="hash-a",
            model_family="anima",
            network_module="networks.custom_anima_lora",
            anima_qwen3="/models/text_encoders/qwen_3_06b_base.safetensors",
            anima_vae="/models/vae/qwen_image_vae.safetensors",
        )

    assert started["ok"] is True
    assert started["tool"] == "lora_train_start"
    assert started["job_id"] == "job-1"
    assert started["submitted"]["expected_dataset_hash"] == "hash-a"
    assert started["submitted"]["model_family"] == "anima"
    assert started["submitted"]["network_module"] == "networks.custom_anima_lora"
    assert started["submitted"]["anima_qwen3"] == "/models/text_encoders/qwen_3_06b_base.safetensors"
    assert started["submitted"]["anima_vae"] == "/models/vae/qwen_image_vae.safetensors"


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
