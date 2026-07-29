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


def _http_error(status_code: int, detail: dict | list[dict]) -> httpx.HTTPStatusError:
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
        "unexpected_backend_field": "must-not-escape",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client), patch(
        "mcp_server.tools.lora_train.lora_train_start"
    ) as start:
        result = lora_training_decision_preflight(
            "character/miku",
            trigger_token="miku_token",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={"batchSize": "1"},
        )

    assert result["ok"] is True
    assert result["tool"] == "lora_training_decision_preflight"
    assert result["decision"] == "train"
    assert "suggested_params" not in result
    assert "unexpected_backend_field" not in result
    assert "submitted" not in result
    start.assert_not_called()
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/training-decision-preflight",
        json={
            "folder": "character/miku",
            "trigger_token": "miku_token",
            "expected_dataset_hash": "hash-a",
            "expected_profile_hash": "profile-hash-a",
            "recipe": {"batchSize": "1"},
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


def test_lora_train_start_forwards_broad_recipe_and_returns_canonical_identity() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "job_id": "job-1",
        "status": "queued",
        "stage": "queued",
        "dataset_hash": "hash-a",
        "profile_hash": "profile-hash-a",
        "normalized_trigger_token": "miku_token",
        "recipe_schema_version": "lora-training-recipe/v1",
        "recipe_hash": "a" * 64,
        "requested_recipe": {
            "schema_version": "lora-training-recipe/v1",
            "dataset": {"batch_size": 1},
        },
        "effective_scope": {
            "denoiser_kind": "dit",
            "train_denoiser": True,
            "train_text_encoder": False,
            "native_scope_flag": "--network_train_unet_only",
            "verification_status": "source_contract",
        },
        "debug_internal": "must-not-cross-strict-output",
    }
    recipe = {
        "schemaVersion": "v1",
        "batchSize": "1",
        "modelFamily": "anima",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        started = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe=recipe,
        )

    assert started["ok"] is True
    assert started["tool"] == "lora_train_start"
    assert started["job_id"] == "job-1"
    assert started["recipe_schema_version"] == "lora-training-recipe/v1"
    assert started["recipe_hash"] == "a" * 64
    assert started["requested_recipe"]["dataset"]["batch_size"] == 1
    assert started["effective_scope"]["denoiser_kind"] == "dit"
    assert "debug_internal" not in started
    assert "submitted" not in started
    mock_client.post.assert_called_once_with(
        "lora-train/start",
        json={
            "folder": "character/miku",
            "expected_dataset_hash": "hash-a",
            "expected_profile_hash": "profile-hash-a",
            "recipe": recipe,
        },
    )


def test_lora_train_start_forwards_json_object_string_without_normalizing_it() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "job_id": "job-string",
        "status": "queued",
        "recipe_schema_version": "lora-training-recipe/v1",
        "recipe_hash": "b" * 64,
    }
    recipe = '{"batchSize":"2","seed":"random"}'

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe=recipe,
        )

    assert result["ok"] is True
    assert "submitted" not in result
    assert mock_client.post.call_args.kwargs["json"]["recipe"] == recipe


def test_lora_train_start_sanitizes_list_shaped_request_validation_errors() -> None:
    """FastAPI validation entries stay structured without echoing submitted inputs."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        422,
        [
            {
                "loc": ["body", "batch_size"],
                "msg": "Input should be greater than or equal to 1",
                "type": "greater_than_equal",
                "ctx": {"ge": 1, "submitted_secret": "secret-context-value"},
                "input": "super-secret-value",
                "url": "https://errors.pydantic.dev/example",
            },
            {
                "loc": ["body", "expected_profile_hash"],
                "msg": "Field required",
                "type": "missing",
                "input": {"private": "payload"},
            },
        ],
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={"batchSize": 0},
        )

    assert result == {
        "ok": False,
        "tool": "lora_train_start",
        "status_code": 422,
        "error": {
            "code": "request_validation_failed",
            "message": "backend request validation failed",
            "hint": "correct the listed fields and retry",
            "details": {
                "validation_errors": [
                        {
                            "loc": ["body", "batch_size"],
                            "type": "greater_than_equal",
                            "ctx": {"ge": 1},
                        },
                        {
                            "loc": ["body", "expected_profile_hash"],
                            "type": "missing",
                        },
                ]
            },
        },
    }
    assert "secret-context-value" not in str(result)


def test_lora_train_start_preserves_dictionary_shaped_backend_error() -> None:
    """Application errors retain safe identity without echoing hash values."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        409,
        {
            "code": "profile_hash_mismatch",
            "message": "dataset profile changed after approval",
            "details": {
                "expected_profile_hash": "profile-hash-a",
                "current_profile_hash": "profile-hash-b",
            },
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={},
        )

    assert result == {
        "ok": False,
        "tool": "lora_train_start",
        "status_code": 409,
        "error": {
            "code": "profile_hash_mismatch",
            "message": "Backend rejected the LoRA request",
            "hint": "rerun decision preflight with current state before retrying",
            "details": {},
        },
    }
    assert "profile-hash-a" not in str(result)
    assert "profile-hash-b" not in str(result)


def test_lora_train_start_preserves_backend_recipe_repair_hint() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        400,
        {
            "code": "unsupported_runtime_precision",
            "message": "requested precision is not supported",
            "hint": "use precision=no or rerun preflight on a verified runtime",
            "details": {
                "issues": [
                    {
                        "location": "optimization.mixed_precision",
                        "type": "unsupported_value",
                    }
                ]
            },
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={"precision": "bf16"},
        )

    assert result["ok"] is False
    assert result["error"]["code"] == "unsupported_runtime_precision"
    assert result["error"]["hint"] == (
        "correct the referenced fields and rerun decision preflight"
    )


def test_lora_train_start_preserves_redacted_alias_conflict_code() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        400,
        {
            "code": "recipe_field_conflict",
            "message": "training recipe contains conflicting aliases",
            "hint": "remove one conflicting alias and retry",
            "details": {
                "issues": [
                    {
                        "location": "dataset.batch_size",
                        "type": "alias_conflict",
                        "accepted_forms": ["batch", "batchSize", "batch_size"],
                    }
                ]
            },
        },
    )
    recipe = {
        "batch": "1",
        "batchSize": "private-conflicting-value",
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe=recipe,
        )

    assert result["error"]["code"] == "recipe_field_conflict"
    assert result["error"]["details"]["issues"][0]["location"] == (
        "dataset.batch_size"
    )
    assert "private-conflicting-value" not in str(result)


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


def test_lora_train_job_status_preserves_historical_null_v1_fields() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "ok": True,
        "job_id": "legacy-job",
        "status": "completed",
        "recipe_schema_version": None,
        "recipe_hash": None,
        "requested_recipe": None,
        "effective_recipe": None,
        "requested_scope": None,
        "effective_scope": None,
        "field_sources": None,
        "step_plan": None,
        "component_identities": None,
        "capability": None,
        "execution_evidence": None,
        "params": {"epochs": 5},
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_job_status("legacy-job")

    assert result["ok"] is True
    assert result["recipe_schema_version"] is None
    assert result["recipe_hash"] is None
    assert result["execution_evidence"] is None
    assert result["params"] == {"epochs": 5}


def test_lora_train_logs_maps_backend_log_error_payload() -> None:
    """Log retrieval failures do not echo arbitrary Backend payload fields."""
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
    assert result["error"]["details"] == {}
    assert "/tmp/missing.log" not in str(result)
    mock_client.get.assert_called_once_with("lora-train/jobs/job-1/logs", params={"lines": 20})


def test_lora_train_start_redacts_untrusted_backend_error_context() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        400,
        {
            "code": "recipe_validation_failed",
            "message": "bad value super-secret-value at https://private.example/token",
            "hint": "retry with TOKEN=super-secret-value",
            "details": {
                "input": "super-secret-value",
                "url": "https://private.example/token",
                "environment": {"TOKEN": "super-secret-value"},
                "issues": [
                    {
                        "location": "dataset.batch_size",
                        "type": "greater_than_equal",
                        "accepted_forms": ["batch", "batchSize", "batch_size"],
                        "input": "super-secret-value",
                    }
                ],
            },
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={"batchSize": "super-secret-value"},
        )

    assert result["error"] == {
        "code": "recipe_validation_failed",
        "message": "Backend rejected the LoRA request",
        "hint": "correct the referenced fields and rerun decision preflight",
        "details": {
            "issues": [
                {
                    "location": "dataset.batch_size",
                    "type": "greater_than_equal",
                    "accepted_forms": ["batch", "batchSize", "batch_size"],
                }
            ]
        },
    }
    serialized = str(result)
    assert "super-secret-value" not in serialized
    assert "private.example" not in serialized


def test_lora_train_start_redacts_non_json_http_body_and_transport_exception() -> None:
    request = httpx.Request("POST", "http://backend.test/api")
    response = httpx.Response(
        500,
        text="TOKEN=super-secret-value https://private.example/token",
        request=request,
    )
    http_failure = httpx.HTTPStatusError(
        "super-secret-value",
        request=request,
        response=response,
    )
    mock_client = MagicMock()
    mock_client.post.side_effect = http_failure

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        http_result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={},
        )

    mock_client.post.side_effect = RuntimeError(
        "TOKEN=super-secret-value https://private.example/token"
    )
    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        transport_result = lora_train_start(
            "character/miku",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            recipe={},
        )

    assert http_result["error"]["code"] == "http_500"
    assert transport_result["error"]["code"] == "backend_unavailable"
    for result in (http_result, transport_result):
        serialized = str(result)
        assert "super-secret-value" not in serialized
        assert "private.example" not in serialized


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
