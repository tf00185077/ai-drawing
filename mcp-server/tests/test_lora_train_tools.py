"""LoRA training MCP tool contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.lora_train import (
    lora_dataset_caption_assess,
    lora_dataset_agent_inspect,
    lora_dataset_curate,
    lora_dataset_inspect,
    lora_dataset_list,
    lora_dataset_metadata_get,
    lora_dataset_metadata_update,
    lora_dataset_metadata_validate,
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


def test_lora_dataset_caption_assess_returns_structured_success() -> None:
    """Caption assessment forwards to backend and keeps not_suitable as a successful report."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": True,
        "folder": "character/miku",
        "verdict": "not_suitable",
        "reasons": ["1 image(s) are missing .txt captions"],
        "image_count": 3,
        "txt_count": 2,
        "missing_txt_count": 1,
        "empty_txt_count": 0,
        "dataset_hash": "hash-a",
        "trigger_token_coverage": {
            "normalized_trigger_token": "miku_token",
            "covered_count": 2,
            "total_count": 2,
            "coverage": 1.0,
        },
        "top_tags": [],
        "rare_tags": [],
        "metrics": {"unique_tag_count": 0},
        "warnings": [{"code": "missing_txt", "message": "missing"}],
        "recommendations": ["Generate captions."],
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_caption_assess("character/miku", trigger_token="miku_token")

    assert result["ok"] is True
    assert result["tool"] == "lora_dataset_caption_assess"
    assert result["verdict"] == "not_suitable"
    assert result["missing_txt_count"] == 1
    assert "error" not in result
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/caption-assessment",
        json={"folder": "character/miku", "trigger_token": "miku_token"},
    )


def test_lora_dataset_caption_assess_surfaces_backend_error() -> None:
    """Invalid assessment folders are returned as structured MCP errors."""
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        404,
        {"code": "dataset_not_found", "message": "dataset folder not found", "details": {}},
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_caption_assess("character/missing")

    assert result["ok"] is False
    assert result["tool"] == "lora_dataset_caption_assess"
    assert result["status_code"] == 404
    assert result["error"]["code"] == "dataset_not_found"


def test_lora_dataset_metadata_tools_return_structured_payloads() -> None:
    """Metadata get/validate/update forward backend payloads without treating invalid profiles as transport errors."""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "ok": True,
        "folder": "character/miku",
        "valid": True,
        "profile_hash": "profile-hash-a",
        "profile": {"present": True, "valid": True, "dataset_type": "character"},
        "warnings": [],
        "errors": [],
    }
    mock_client.post.return_value = {
        "ok": True,
        "folder": "character/miku",
        "valid": False,
        "profile_hash": "profile-hash-a",
        "profile": {"present": True, "valid": False, "dataset_type": "unknown"},
        "warnings": [],
        "errors": [{"code": "unsupported_dataset_type", "message": "unsupported"}],
    }
    mock_client.put.return_value = {
        "ok": True,
        "folder": "character/miku",
        "valid": True,
        "updated": True,
        "profile_hash": "profile-hash-b",
        "profile": {"present": True, "valid": True, "dataset_type": "style"},
        "warnings": [],
        "errors": [],
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        got = lora_dataset_metadata_get("character/miku")
        validated = lora_dataset_metadata_validate("character/miku", {"dataset_type": "vehicle"})
        updated = lora_dataset_metadata_update(
            "character/miku",
            {"dataset_type": "style"},
            expected_profile_hash="profile-hash-a",
        )

    assert got["ok"] is True
    assert got["tool"] == "lora_dataset_metadata_get"
    assert got["profile_hash"] == "profile-hash-a"
    assert validated["ok"] is True
    assert validated["tool"] == "lora_dataset_metadata_validate"
    assert validated["valid"] is False
    assert "error" not in validated
    assert updated["ok"] is True
    assert updated["tool"] == "lora_dataset_metadata_update"
    assert updated["updated"] is True
    assert updated["submitted"]["expected_profile_hash"] == "profile-hash-a"
    mock_client.get.assert_called_once_with("lora-train/datasets/character/miku/metadata")
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/character/miku/metadata/validate",
        json={"profile": {"dataset_type": "vehicle"}},
    )
    mock_client.put.assert_called_once_with(
        "lora-train/datasets/character/miku/metadata",
        json={
            "profile": {"dataset_type": "style"},
            "expected_profile_hash": "profile-hash-a",
        },
    )


def test_lora_dataset_metadata_update_surfaces_profile_hash_conflict() -> None:
    """Stale profile hashes are forwarded as structured MCP conflicts."""
    mock_client = MagicMock()
    mock_client.put.side_effect = _http_error(
        409,
        {
            "code": "profile_hash_mismatch",
            "message": "profile hash does not match expected hash",
            "details": {"current_profile_hash": "profile-hash-new"},
        },
    )

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_metadata_update(
            "character/miku",
            {"dataset_type": "style"},
            expected_profile_hash="profile-hash-old",
        )

    assert result["ok"] is False
    assert result["tool"] == "lora_dataset_metadata_update"
    assert result["status_code"] == 409
    assert result["error"]["code"] == "profile_hash_mismatch"
    assert result["error"]["details"]["current_profile_hash"] == "profile-hash-new"


def test_lora_dataset_agent_inspect_returns_profile_states_as_payloads() -> None:
    """Agent inspection keeps valid, missing, and invalid profile states as successful structured payloads."""
    mock_client = MagicMock()
    mock_client.get.side_effect = [
        {
            "ok": True,
            "folder": "character/valid",
            "dataset_hash": "dataset-hash-a",
            "profile_hash": "profile-hash-a",
            "dataset": {"folder": "character/valid", "image_count": 2},
            "profile": {"present": True, "valid": True, "dataset_type": "character"},
            "profile_validation": {"valid": True, "warnings": [], "errors": []},
            "caption_suitability": {"verdict": "suitable", "reasons": [], "recommendations": []},
            "validation": {"ok": True},
        },
        {
            "ok": True,
            "folder": "character/missing",
            "dataset_hash": "dataset-hash-b",
            "profile_hash": None,
            "dataset": {"folder": "character/missing", "image_count": 2},
            "profile": {"present": False, "valid": True, "dataset_type": "unknown"},
            "profile_validation": {"valid": True, "warnings": [], "errors": []},
            "caption_suitability": {"verdict": "needs_review", "reasons": ["low coverage"]},
            "validation": {"ok": False},
        },
        {
            "ok": True,
            "folder": "character/invalid",
            "dataset_hash": "dataset-hash-c",
            "profile_hash": "profile-hash-c",
            "dataset": {"folder": "character/invalid", "image_count": 2},
            "profile": {"present": True, "valid": False, "dataset_type": "unknown"},
            "profile_validation": {
                "valid": False,
                "warnings": [],
                "errors": [{"code": "invalid_profile_json", "message": "invalid"}],
            },
            "caption_suitability": {"verdict": "not_suitable", "reasons": ["missing captions"]},
            "validation": {"ok": False},
        },
    ]

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        valid = lora_dataset_agent_inspect("character/valid", trigger_token="valid_token")
        missing = lora_dataset_agent_inspect("character/missing")
        invalid = lora_dataset_agent_inspect("character/invalid")

    assert valid["ok"] is True
    assert valid["tool"] == "lora_dataset_agent_inspect"
    assert valid["profile_validation"]["valid"] is True
    assert missing["ok"] is True
    assert missing["profile"]["present"] is False
    assert missing["caption_suitability"]["verdict"] == "needs_review"
    assert invalid["ok"] is True
    assert invalid["profile_validation"]["valid"] is False
    assert invalid["caption_suitability"]["verdict"] == "not_suitable"
    assert "error" not in invalid
    mock_client.get.assert_any_call(
        "lora-train/datasets/character/valid/agent-inspect",
        params={"trigger_token": "valid_token"},
    )
    mock_client.get.assert_any_call("lora-train/datasets/character/missing/agent-inspect", params=None)
    mock_client.get.assert_any_call("lora-train/datasets/character/invalid/agent-inspect", params=None)


def test_lora_dataset_curate_dry_run_keeps_blocked_edits_as_payload() -> None:
    """Curation dry-run forwards backend blocked/review-required edits as a successful structured payload."""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "ok": True,
        "mode": "dry_run",
        "folder": "character/miku",
        "dataset_hash": "hash-a",
        "profile_hash": "profile-hash-a",
        "changes": [
            {
                "path": "character/miku/a.txt",
                "before": "solo, lowres",
                "after": "miku_token, solo",
                "changed": True,
                "status": "review_required",
                "blocked": True,
                "review_required": True,
                "manual": True,
                "outlier_flags": [],
            }
        ],
        "summary": {"total_files": 1, "blocked_count": 1, "review_required_count": 1},
        "skipped_files": ["character/miku/a.txt"],
    }

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        result = lora_dataset_curate("character/miku", mode="dry_run", trigger_token="miku_token")

    assert result["ok"] is True
    assert result["tool"] == "lora_dataset_curate"
    assert result["summary"]["blocked_count"] == 1
    assert result["changes"][0]["status"] == "review_required"
    assert "error" not in result
    mock_client.post.assert_called_once_with(
        "lora-train/datasets/curate",
        json={"folder": "character/miku", "mode": "dry_run", "trigger_token": "miku_token"},
    )


def test_lora_dataset_curate_apply_and_rollback_payloads() -> None:
    """Curation apply and rollback include reviewed hashes, backup ids, and manual approvals."""
    mock_client = MagicMock()
    mock_client.post.side_effect = [
        {
            "ok": True,
            "mode": "apply",
            "folder": "character/miku",
            "backup_id": "backup-1",
            "changed_files": ["character/miku/a.txt"],
            "skipped_files": [],
            "manually_overwritten_files": ["character/miku/a.txt"],
            "dataset_hash_after": "hash-b",
        },
        {
            "ok": True,
            "mode": "rollback",
            "folder": "character/miku",
            "backup_id": "backup-1",
            "restored_files": ["character/miku/a.txt"],
            "dataset_hash_after": "hash-a",
        },
    ]

    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        applied = lora_dataset_curate(
            "character/miku",
            mode="apply",
            expected_dataset_hash="hash-a",
            expected_profile_hash="profile-hash-a",
            approved_manual_overwrite_paths=["character/miku/a.txt"],
        )
        rolled_back = lora_dataset_curate(
            "character/miku",
            mode="rollback",
            backup_id="backup-1",
        )

    assert applied["ok"] is True
    assert applied["tool"] == "lora_dataset_curate"
    assert applied["backup_id"] == "backup-1"
    assert applied["manually_overwritten_files"] == ["character/miku/a.txt"]
    assert applied["submitted"]["expected_dataset_hash"] == "hash-a"
    assert applied["submitted"]["approved_manual_overwrite_paths"] == ["character/miku/a.txt"]
    assert rolled_back["ok"] is True
    assert rolled_back["restored_files"] == ["character/miku/a.txt"]
    mock_client.post.assert_any_call(
        "lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "apply",
            "expected_dataset_hash": "hash-a",
            "expected_profile_hash": "profile-hash-a",
            "approved_manual_overwrite_paths": ["character/miku/a.txt"],
        },
    )
    mock_client.post.assert_any_call(
        "lora-train/datasets/curate",
        json={"folder": "character/miku", "mode": "rollback", "backup_id": "backup-1"},
    )


def test_lora_dataset_curate_surfaces_stale_hash_conflict() -> None:
    """Curation stale hash backend failures stay structured for agents."""
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
        result = lora_dataset_curate(
            "character/miku",
            mode="apply",
            expected_dataset_hash="hash-old",
            expected_profile_hash="profile-hash-a",
        )

    assert result["ok"] is False
    assert result["tool"] == "lora_dataset_curate"
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
            model_family="anima",
            network_module="networks.custom_anima_lora",
            anima_qwen3="/models/text_encoders/qwen_3_06b_base.safetensors",
            anima_vae="/models/vae/qwen_image_vae.safetensors",
        )
        status = lora_train_status()

    assert started["ok"] is True
    assert started["tool"] == "lora_train_start"
    assert started["job_id"] == "job-1"
    assert started["submitted"]["expected_dataset_hash"] == "hash-a"
    assert started["submitted"]["model_family"] == "anima"
    assert started["submitted"]["network_module"] == "networks.custom_anima_lora"
    assert started["submitted"]["anima_qwen3"] == "/models/text_encoders/qwen_3_06b_base.safetensors"
    assert started["submitted"]["anima_vae"] == "/models/vae/qwen_image_vae.safetensors"
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
