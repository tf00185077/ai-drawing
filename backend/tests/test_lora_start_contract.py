"""Public LoRA Start request contract tests."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.lora_trainer import TrainerServiceError


def _client() -> TestClient:
    return TestClient(app)


def _approved_start_payload() -> dict[str, object]:
    return {
        "folder": "character/miku",
        "expected_dataset_hash": "dataset-sha256",
        "expected_profile_hash": "profile-sha256",
        "recipe": {
            "schemaVersion": "v1",
            "batchSize": "7",
        },
    }


def test_start_requires_both_approval_hashes_and_recipe_without_calling_enqueue() -> None:
    client = _client()

    with (
        patch(
            "app.api.lora_train.lora_trainer.enqueue",
            return_value="unexpected-job",
        ) as enqueue,
        patch(
            "app.api.lora_train.lora_trainer.get_job_status",
            return_value={"status": "queued", "stage": "queued"},
        ),
    ):
        missing_dataset = client.post(
            "/api/lora-train/start",
            json={
                "folder": "character/miku",
                "expected_profile_hash": "profile-sha256",
            },
        )
        missing_profile = client.post(
            "/api/lora-train/start",
            json={
                "folder": "character/miku",
                "expected_dataset_hash": "dataset-sha256",
                "recipe": {},
            },
        )
        missing_recipe = client.post(
            "/api/lora-train/start",
            json={
                "folder": "character/miku",
                "expected_dataset_hash": "dataset-sha256",
                "expected_profile_hash": "profile-sha256",
            },
        )

    assert missing_dataset.status_code == 422
    assert missing_profile.status_code == 422
    assert missing_recipe.status_code == 422
    enqueue.assert_not_called()


def test_start_rejects_unknown_fields_without_calling_enqueue() -> None:
    payload = _approved_start_payload()
    payload["surprise_option"] = "must-not-be-ignored"

    with (
        patch(
            "app.api.lora_train.lora_trainer.enqueue",
            return_value="unexpected-job",
        ) as enqueue,
        patch(
            "app.api.lora_train.lora_trainer.get_job_status",
            return_value={"status": "queued", "stage": "queued"},
        ),
    ):
        response = _client().post("/api/lora-train/start", json=payload)

    assert response.status_code == 422
    enqueue.assert_not_called()


def test_start_rejects_legacy_flat_fields_with_redacted_migration_guidance() -> None:
    payload = _approved_start_payload()
    payload.update(
        {
            "batch_size": "super-secret-batch-value",
            "checkpoint": "https://secret.example/model?token=do-not-echo",
        }
    )

    with patch(
        "app.api.lora_train.lora_trainer.enqueue",
        return_value="unexpected-job",
    ) as enqueue:
        response = _client().post("/api/lora-train/start", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "legacy_training_fields_removed"
    assert detail["details"]["fields"] == ["batch_size", "checkpoint"]
    assert "decision preflight" in detail["hint"]
    assert "super-secret-batch-value" not in response.text
    assert "do-not-echo" not in response.text
    enqueue.assert_not_called()


def test_start_forwards_broad_recipe_and_both_approval_hashes_unchanged() -> None:
    queued_status = {
        "status": "queued",
        "stage": "queued",
        "dataset_hash": "dataset-sha256",
        "profile_hash": "profile-sha256",
        "normalized_trigger_token": None,
        "recipe_schema_version": "lora-training-recipe/v1",
        "recipe_hash": "a" * 64,
        "requested_recipe": {
            "schema_version": "lora-training-recipe/v1",
            "dataset": {"batch_size": 7},
        },
        "effective_recipe": None,
    }

    with (
        patch(
            "app.api.lora_train.lora_trainer.enqueue",
            return_value="lora-job-contract",
        ) as enqueue,
        patch(
            "app.api.lora_train.lora_trainer.get_job_status",
            return_value=queued_status,
        ),
    ):
        response = _client().post(
            "/api/lora-train/start",
            json=_approved_start_payload(),
        )

    assert response.status_code == 202
    enqueue.assert_called_once()
    forwarded = enqueue.call_args.kwargs
    assert forwarded["recipe"] == {
        "schemaVersion": "v1",
        "batchSize": "7",
    }
    assert forwarded["expected_dataset_hash"] == "dataset-sha256"
    assert forwarded["expected_profile_hash"] == "profile-sha256"
    assert response.json()["dataset_hash"] == "dataset-sha256"
    assert response.json()["profile_hash"] == "profile-sha256"
    assert response.json()["recipe_schema_version"] == "lora-training-recipe/v1"
    assert response.json()["recipe_hash"] == "a" * 64


def test_start_maps_stale_profile_approval_to_conflict() -> None:
    with patch(
        "app.api.lora_train.lora_trainer.enqueue",
        side_effect=TrainerServiceError(
            "profile_hash_mismatch",
            "dataset profile changed after approval",
            {
                "expected_profile_hash": "profile-sha256",
                "current_profile_hash": "profile-sha256-new",
            },
        ),
    ):
        response = _client().post(
            "/api/lora-train/start",
            json=_approved_start_payload(),
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "profile_hash_mismatch"


def test_start_status_fallback_keeps_the_approved_hash_identity() -> None:
    with (
        patch(
            "app.api.lora_train.lora_trainer.enqueue",
            return_value="lora-job-contract",
        ),
        patch(
            "app.api.lora_train.lora_trainer.get_job_status",
            side_effect=TrainerServiceError(
                "job_not_found",
                "status has not become visible yet",
                {"job_id": "lora-job-contract"},
            ),
        ),
    ):
        response = _client().post(
            "/api/lora-train/start",
            json=_approved_start_payload(),
        )

    assert response.status_code == 202
    assert response.json()["dataset_hash"] == "dataset-sha256"
    assert response.json()["profile_hash"] == "profile-sha256"
