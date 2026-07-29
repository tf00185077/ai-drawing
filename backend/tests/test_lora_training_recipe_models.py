"""Typed v1 LoRA recipe and evidence contract tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.lora_train import (
    ComponentIdentity,
    EffectiveTrainingRecipeV1,
    ExecutionEvidence,
    RecipeCompilationResult,
    TrainerCapabilitySnapshot,
    TrainingStepPlan,
)


def _effective_payload() -> dict:
    return {
        "schema_version": "lora-training-recipe/v1",
        "model": {
            "family": "anima",
            "checkpoint": "models/anima.safetensors",
            "allow_unverified_checkpoint": False,
            "network_module": "networks.lora_anima",
            "network_dim": 32,
            "network_alpha": 16,
            "anima": {
                "qwen3": "models/qwen3",
                "vae": None,
                "t5_tokenizer_path": None,
            },
        },
        "scope": {
            "denoiser_kind": "dit",
            "train_denoiser": True,
            "train_text_encoder": False,
            "native_scope_flag": "--network_train_unet_only",
            "verification_status": "source_contract",
        },
        "dataset": {
            "trigger_token": "sks",
            "class_tokens": "sks",
            "resolution": 1024,
            "batch_size": 1,
            "keep_tokens": 1,
            "num_repeats": 8,
            "enable_bucket": True,
            "bucket_no_upscale": True,
            "min_bucket_reso": 256,
            "max_bucket_reso": 2048,
            "bucket_reso_steps": 64,
        },
        "optimization": {
            "epochs": 8,
            "learning_rate": "1e-4",
            "denoiser_learning_rate": "1e-4",
            "text_encoder_learning_rates": [],
            "gradient_accumulation_steps": 1,
            "optimizer_type": "AdamW",
            "optimizer_args": [],
            "lr_scheduler": "constant",
            "lr_scheduler_args": [],
            "warmup": {"mode": "steps", "value": 0, "resolved_steps": 0},
            "seed": {
                "mode": "random",
                "value": 1700000001,
                "source": "preflight_policy",
            },
            "mixed_precision": "no",
        },
        "caching": {
            "cache_latents": True,
            "cache_text_encoder_outputs": True,
            "cache_to_disk": True,
            "latent_cache_to_disk": True,
            "text_encoder_cache_to_disk": True,
        },
        "execution": {
            "max_data_loader_n_workers": 0,
            "persistent_data_loader_workers": False,
            "save_every_n_epochs": 1,
            "final_only": False,
        },
        "server": {
            "gradient_checkpointing": True,
            "caption_extension": ".txt",
            "shuffle_caption": True,
            "save_model_as": "safetensors",
            "launcher_num_cpu_threads_per_process": 1,
        },
    }


def test_v1_models_validate_a_complete_immutable_compilation_envelope() -> None:
    effective = EffectiveTrainingRecipeV1.model_validate(_effective_payload())
    capability = TrainerCapabilitySnapshot(
        platform="unknown",
        status="unavailable",
        reason="trainer runtime was not inspectable",
        supported_mixed_precision=["no"],
    )
    component = ComponentIdentity(
        kind="checkpoint",
        requested_locator="models/anima.safetensors",
        resolved_locator="D:/models/anima.safetensors",
        verification_status="unverified",
        reason="digest unavailable",
        bypass_used=True,
    )
    plan = TrainingStepPlan(
        image_count=10,
        num_repeats=8,
        train_examples=80,
        batch_size=1,
        batches_per_epoch=80,
        gradient_accumulation_steps=1,
        optimizer_steps_per_epoch=80,
        epochs=8,
        total_optimizer_steps=640,
        warmup_steps=0,
        process_count=1,
    )
    evidence = ExecutionEvidence(
        status="unverified",
        reason="source contract only; bounded trainer probe is deferred",
        capability=capability,
    )
    compiled = RecipeCompilationResult(
        requested={"optimization": {"seed": effective.optimization.seed}},
        effective=effective,
        field_sources={
            "scope.train_text_encoder": "preflight_policy",
            "dataset.class_tokens": "derived",
        },
        component_identities={"checkpoint": component},
        capability=capability,
        step_plan=plan,
        recipe_hash="a" * 64,
        execution_evidence=evidence,
    )

    assert compiled.effective.scope.denoiser_kind == "dit"
    assert compiled.field_sources["dataset.class_tokens"] == "derived"
    with pytest.raises(ValidationError):
        compiled.effective.dataset.batch_size = 2
    with pytest.raises(AttributeError):
        compiled.effective.optimization.optimizer_args.append("unsafe=true")
    with pytest.raises(TypeError):
        compiled.field_sources["model.family"] = "caller"


def test_v1_models_forbid_unknown_fields_at_every_typed_boundary() -> None:
    payload = _effective_payload()
    payload["dataset"]["batch_szie"] = 2

    with pytest.raises(ValidationError) as raised:
        EffectiveTrainingRecipeV1.model_validate(payload)

    assert raised.value.errors()[0]["loc"] == ("dataset", "batch_szie")
