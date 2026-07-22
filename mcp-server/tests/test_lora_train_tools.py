"""LoRA training MCP tool contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.lora_train import (
    lora_dataset_inspect,
    lora_dataset_list,
    lora_training_decision_preflight,
    lora_train_cancel,
    lora_train_job_status,
    lora_train_logs,
    lora_train_smoke_test,
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


def test_lora_dataset_list_returns_structured_datasets() -> None:
    """Dataset list forwards backend dataset summaries as a structured result."""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "datasets": [
            {"folder": "character/miku", "image_count": 12, "caption_count": 12, "dataset_hash": "hash-a"}
        ]
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_list()

    mock_client.get.assert_called_once_with("lora-train/datasets")
    assert result["ok"] is True
    assert result["tool"] == "lora_dataset_list"
    assert result["datasets"][0]["folder"] == "character/miku"


def test_lora_dataset_inspect_calls_agent_inspect_endpoint() -> None:
    """Dataset inspect calls the agent-inspect endpoint and returns structured review signals."""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "folder": "character/miku",
        "dataset_hash": "hash-a",
        "profile_hash": "profile-a",
        "caption_suitability": {"verdict": "suitable"},
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_inspect("character/miku")

    mock_client.get.assert_called_once_with("lora-train/datasets/character/miku/agent-inspect")
    assert result["ok"] is True
    assert result["tool"] == "lora_dataset_inspect"
    assert result["caption_suitability"]["verdict"] == "suitable"


def test_lora_dataset_inspect_surfaces_backend_error() -> None:
    """An invalid folder surfaces a structured backend error."""
    mock_client = MagicMock()
    mock_client.get.side_effect = _http_error(
        404, {"code": "dataset_not_found", "message": "no such dataset"}
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_inspect("character/ghost")

    assert result["ok"] is False
    assert result["tool"] == "lora_dataset_inspect"
    assert result["status_code"] == 404
    assert result["error"]["code"] == "dataset_not_found"


def test_lora_train_smoke_test_forwards_anima_component_overrides() -> None:
    """Smoke test forwards optional Anima component overrides and returns structured status."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": True,
        "job_id": "job-anima",
        "registered_lora_name": "louise.safetensors",
        "smoke_test_status": "submitted",
        "generation_job_id": "gen-1",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_smoke_test(
            "job-anima",
            prompt="portrait",
            diffusion_model="anima.safetensors",
            text_encoder="qwen3.safetensors",
        )

    call = mock_client.post.call_args
    assert call.args[0] == "lora-train/jobs/job-anima/smoke-test"
    assert call.kwargs["json"]["diffusion_model"] == "anima.safetensors"
    assert call.kwargs["json"]["text_encoder"] == "qwen3.safetensors"
    assert "vae" not in call.kwargs["json"]  # unset overrides are omitted
    assert result["ok"] is True
    assert result["tool"] == "lora_train_smoke_test"
    assert result["submitted"]["diffusion_model"] == "anima.safetensors"
