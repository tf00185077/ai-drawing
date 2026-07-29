"""Durable v1 LoRA recipe envelope persistence tests."""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.schemas.lora_train import (
    ComponentIdentity,
    LoraTrainJobStatusResponse,
    RecipeCompilationContext,
    RecipePolicySnapshot,
    TrainerCapabilitySnapshot,
)
from app.services import lora_trainer
from app.services.lora_training_recipe import compile_training_recipe


def _compiled():
    capability = TrainerCapabilitySnapshot(
        platform="unknown",
        status="unavailable",
        reason="offline persistence fixture",
        supported_mixed_precision=("no",),
    )
    context = RecipeCompilationContext(
        dataset_hash="d" * 64,
        profile_hash="e" * 64,
        profile_model_family="sd15",
        approved_trigger_token="sks",
        image_count=10,
        policy=RecipePolicySnapshot(
            default_checkpoint="models/sd15.safetensors",
            resolution=512,
            mixed_precision="no",
        ),
        capability=capability,
        component_identities={
            "checkpoint": ComponentIdentity(
                kind="checkpoint",
                requested_locator="models/sd15.safetensors",
                resolved_locator="D:/models/sd15.safetensors",
                verification_status="unverified",
                reason="offline persistence fixture",
            )
        },
    )
    return compile_training_recipe(
        {"seed": 42, "batch_size": 1},
        context=context,
        policy_source="preflight_policy",
    )


def _job(compiled):
    effective = compiled.effective
    return lora_trainer._TrainJob(
        job_id="recipe-job",
        folder="character/miku",
        checkpoint=effective.model.checkpoint,
        model_family=effective.model.family,
        sdxl=False,
        epochs=effective.optimization.epochs,
        submitted_at="2026-07-29T00:00:00Z",
        resolution=effective.dataset.resolution,
        batch_size=effective.dataset.batch_size,
        learning_rate=effective.optimization.learning_rate,
        class_tokens=effective.dataset.class_tokens,
        keep_tokens=effective.dataset.keep_tokens,
        num_repeats=effective.dataset.num_repeats,
        mixed_precision=effective.optimization.mixed_precision,
        network_module=effective.model.network_module,
        network_dim=effective.model.network_dim,
        network_alpha=effective.model.network_alpha,
        dataset_hash="d" * 64,
        profile_hash="e" * 64,
        normalized_trigger_token="sks",
        recipe=compiled,
    )


def test_new_queued_row_contains_complete_v1_recipe_before_worker_start(
    monkeypatch,
) -> None:
    compiled = _compiled()
    captured = []

    class FakeDb:
        def add(self, row) -> None:
            captured.append(row)

    monkeypatch.setattr(
        lora_trainer,
        "_with_db",
        lambda operation: operation(FakeDb()),
    )

    lora_trainer._create_persistent_job(_job(compiled))

    assert len(captured) == 1
    row = captured[0]
    envelope = json.loads(row.recipe_json)
    evidence = json.loads(row.execution_evidence_json)
    assert row.status == "queued"
    assert row.recipe_schema_version == "lora-training-recipe/v1"
    assert row.recipe_hash == compiled.recipe_hash
    assert envelope["requested"] == compiled.requested.model_dump(
        mode="json",
        exclude_none=True,
    )
    assert envelope["effective"] == compiled.effective.model_dump(mode="json")
    assert envelope["field_sources"] == dict(compiled.field_sources)
    assert envelope["step_plan"] == compiled.step_plan.model_dump(mode="json")
    assert envelope["component_identities"]["checkpoint"][
        "verification_status"
    ] == "unverified"
    assert envelope["capability"]["status"] == "unavailable"
    assert evidence["status"] == "unverified"
    assert row.params_json is not None


def test_status_deserializes_typed_recipe_and_keeps_legacy_params_projection() -> None:
    compiled = _compiled()
    job = _job(compiled)
    row = SimpleNamespace(
        job_id=job.job_id,
        folder=job.folder,
        status="queued",
        stage="queued",
        progress=0.0,
        current_epoch=None,
        total_epochs=job.epochs,
        dataset_hash=job.dataset_hash,
        profile_hash=job.profile_hash,
        normalized_trigger_token=job.normalized_trigger_token,
        log_path=None,
        output_path=None,
        registered_lora_name=None,
        registration_error=None,
        error_code=None,
        error_message=None,
        error_details_json=None,
        params_json=lora_trainer._params_json(job),
        recipe_schema_version=compiled.effective.schema_version,
        recipe_hash=compiled.recipe_hash,
        recipe_json=lora_trainer._recipe_envelope_json(compiled),
        execution_evidence_json=lora_trainer._execution_evidence_json(compiled),
        smoke_test_status=None,
        smoke_test_job_id=None,
        smoke_test_artifact=None,
        smoke_test_error=None,
        created_at=None,
        updated_at=None,
        started_at=None,
        completed_at=None,
        cancel_requested_at=None,
    )

    payload = lora_trainer._serialize_job(row)
    status = LoraTrainJobStatusResponse.model_validate(payload)

    assert status.requested_recipe.optimization.seed.value == 42
    assert status.effective_recipe.scope.train_text_encoder is False
    assert status.requested_scope is None
    assert status.effective_scope.native_scope_flag == "--network_train_unet_only"
    assert status.field_sources["dataset.batch_size"] == "caller"
    assert status.step_plan.total_optimizer_steps > 0
    assert status.component_identities["checkpoint"].verification_status == "unverified"
    assert status.execution_evidence.status == "unverified"
    assert status.params["batch_size"] == 1


def test_historical_status_never_invents_verified_recipe_or_evidence() -> None:
    row = SimpleNamespace(
        job_id="historical",
        folder="character/legacy",
        status="completed",
        stage="completed",
        progress=1.0,
        current_epoch=3,
        total_epochs=3,
        dataset_hash=None,
        profile_hash=None,
        normalized_trigger_token=None,
        log_path=None,
        output_path="legacy.safetensors",
        registered_lora_name=None,
        registration_error=None,
        error_code=None,
        error_message=None,
        error_details_json=None,
        params_json='{"epochs":3}',
        recipe_schema_version=None,
        recipe_hash=None,
        recipe_json=None,
        execution_evidence_json=None,
        smoke_test_status=None,
        smoke_test_job_id=None,
        smoke_test_artifact=None,
        smoke_test_error=None,
        created_at=None,
        updated_at=None,
        started_at=None,
        completed_at=None,
        cancel_requested_at=None,
    )

    status = LoraTrainJobStatusResponse.model_validate(
        lora_trainer._serialize_job(row)
    )

    assert status.recipe_schema_version is None
    assert status.requested_recipe is None
    assert status.effective_recipe is None
    assert status.execution_evidence is None
    assert status.params == {"epochs": 3}
