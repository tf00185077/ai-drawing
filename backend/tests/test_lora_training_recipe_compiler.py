"""Deterministic LoRA training recipe compiler tests."""
from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.lora_train import (
    ComponentIdentity,
    RecipeCompilationContext,
    RecipePolicySnapshot,
    TrainerCapabilitySnapshot,
)
from app.services.lora_training_recipe import (
    RecipeError,
    compile_training_recipe,
)


def _capability(
    platform: str = "unknown",
    *,
    status: str | None = None,
    supported: tuple[str, ...] | None = None,
) -> TrainerCapabilitySnapshot:
    resolved_status = status or ("verified" if platform != "unknown" else "unavailable")
    supported_modes = supported
    if supported_modes is None:
        supported_modes = ("no", "fp16", "bf16") if platform == "cuda" else ("no",)
    return TrainerCapabilitySnapshot(
        platform=platform,
        status=resolved_status,
        reason=None if resolved_status == "verified" else "runtime was not inspectable",
        torch_version="2.7.0" if resolved_status == "verified" else None,
        accelerate_version="1.11.0" if resolved_status == "verified" else None,
        python_version="3.11.9",
        supported_mixed_precision=supported_modes,
    )


def _context(
    family: str = "sd15",
    *,
    platform: str = "unknown",
    capability_status: str | None = None,
    supported_precision: tuple[str, ...] | None = None,
    image_count: int = 10,
    configured_resolution: int = 512,
    configured_batch_size: int = 4,
    configured_precision: str = "fp16",
    dataset_hash: str = "d" * 64,
    profile_hash: str = "p" * 64,
    checkpoint_sha: str = "c" * 64,
) -> RecipeCompilationContext:
    checkpoint = f"models/{family}.safetensors"
    components = {
        "checkpoint": ComponentIdentity(
            kind="checkpoint",
            requested_locator=checkpoint,
            resolved_locator=f"D:/resolved/{family}.safetensors",
            size_bytes=1234,
            modified_time_ns=99,
            sha256=checkpoint_sha,
            verification_status="verified",
            bypass_used=False,
        )
    }
    if family == "anima":
        components["text_encoder"] = ComponentIdentity(
            kind="text_encoder",
            requested_locator="models/qwen3",
            resolved_locator="D:/resolved/qwen3",
            verification_status="unverified",
            reason="directory digest is unavailable",
        )
    return RecipeCompilationContext(
        dataset_hash=dataset_hash,
        profile_hash=profile_hash,
        profile_model_family=family,
        approved_trigger_token="sks",
        image_count=image_count,
        policy=RecipePolicySnapshot(
            default_checkpoint=checkpoint,
            default_anima_qwen3="models/qwen3",
            default_anima_vae=None,
            default_anima_t5_tokenizer_path=None,
            resolution=configured_resolution,
            batch_size=configured_batch_size,
            learning_rate="1e-4",
            keep_tokens=1,
            num_repeats=10,
            mixed_precision=configured_precision,
            network_dim=32,
            network_alpha=16,
        ),
        capability=_capability(
            platform,
            status=capability_status,
            supported=supported_precision,
        ),
        component_identities=components,
    )


def _compile(
    recipe: object,
    *,
    context: RecipeCompilationContext | None = None,
    family: str = "sd15",
):
    return compile_training_recipe(
        recipe,
        context=context or _context(family),
        policy_source="preflight_policy",
        seed_factory=lambda: 123456789,
    )


@pytest.mark.parametrize(
    ("family", "denoiser_kind", "network_module", "cache_text", "epochs"),
    [
        ("sd15", "unet", "networks.lora", False, 12),
        ("sdxl", "unet", "networks.lora", True, 12),
        ("anima", "dit", "networks.lora_anima", True, 8),
    ],
)
def test_family_matrix_defaults_to_denoiser_only_and_complete_policy(
    family: str,
    denoiser_kind: str,
    network_module: str,
    cache_text: bool,
    epochs: int,
) -> None:
    compiled = _compile({}, family=family)
    effective = compiled.effective

    assert effective.model.family == family
    assert effective.model.network_module == network_module
    assert effective.scope.model_dump() == {
        "denoiser_kind": denoiser_kind,
        "train_denoiser": True,
        "train_text_encoder": False,
        "native_scope_flag": "--network_train_unet_only",
        "verification_status": "source_contract",
    }
    assert effective.optimization.text_encoder_learning_rates == ()
    assert effective.caching.cache_text_encoder_outputs is cache_text
    assert effective.optimization.epochs == epochs
    assert effective.server.gradient_checkpointing is True
    assert effective.server.shuffle_caption is (not cache_text)


def test_explicit_shuffle_caption_false_is_preserved_with_text_encoder_cache() -> None:
    compiled = _compile(
        {
            "dataset": {"shuffle_caption": False},
            "caching": {"cache_text_encoder_outputs": True},
        },
        family="anima",
    )

    assert compiled.effective.server.shuffle_caption is False
    assert compiled.field_sources["server.shuffle_caption"] == "caller"


def test_text_encoder_cache_rejects_explicit_caption_shuffling() -> None:
    with pytest.raises(RecipeError) as raised:
        _compile(
            {
                "dataset": {"shuffle_caption": True},
                "caching": {"cache_text_encoder_outputs": True},
            },
            family="anima",
        )

    assert raised.value.code == "incompatible_training_recipe"
    assert {
        issue["location"] for issue in raised.value.details["issues"]
    } == {
        "dataset.shuffle_caption",
        "caching.cache_text_encoder_outputs",
    }


@pytest.mark.parametrize(
    ("family", "expected_rates"),
    [
        ("sd15", ("0.00002",)),
        ("sdxl", ("0.00002", "0.00002")),
        ("anima", ("0.00002",)),
    ],
)
def test_text_encoder_opt_in_expands_scalar_family_learning_rate(
    family: str,
    expected_rates: tuple[str, ...],
) -> None:
    compiled = _compile(
        {
            "scope": {"train_text_encoder": True},
            "optimization": {"text_encoder_lr": "2e-5"},
            "caching": {"cache_text_encoder_outputs": False},
        },
        family=family,
    )

    assert compiled.effective.scope.train_text_encoder is True
    assert compiled.effective.scope.native_scope_flag is None
    assert compiled.effective.optimization.text_encoder_learning_rates == expected_rates


def test_sdxl_explicit_one_item_text_encoder_rate_list_is_rejected() -> None:
    with pytest.raises(RecipeError) as raised:
        _compile(
            {
                "scope": {"train_text_encoder": True},
                "optimization": {"text_encoder_learning_rates": ["2e-5"]},
                "caching": {"cache_text_encoder_outputs": False},
            },
            family="sdxl",
        )

    assert raised.value.code == "recipe_validation_failed"
    assert raised.value.details["issues"][0]["expected_count"] == 2


def test_text_encoder_training_rejects_text_encoder_output_cache() -> None:
    with pytest.raises(RecipeError) as raised:
        _compile(
            {
                "scope": {"train_text_encoder": True},
                "caching": {"cache_text_encoder_outputs": True},
            },
            family="anima",
        )

    assert raised.value.code == "incompatible_training_recipe"
    assert {
        issue["location"] for issue in raised.value.details["issues"]
    } == {
        "scope.train_text_encoder",
        "caching.cache_text_encoder_outputs",
    }


@pytest.mark.parametrize(
    ("family", "module"),
    [
        ("sd15", "networks.lora_anima"),
        ("sdxl", "custom.evil"),
        ("anima", "networks.lora"),
    ],
)
def test_untrusted_network_module_is_rejected_for_each_family(
    family: str,
    module: str,
) -> None:
    with pytest.raises(RecipeError) as raised:
        _compile({"model": {"network_module": module}}, family=family)

    assert raised.value.code == "unsupported_network_module"
    assert raised.value.details["family"] == family
    assert "allowed_identifiers" in raised.value.details


@pytest.mark.parametrize(
    ("family", "platform", "resolution", "expected_batch"),
    [
        ("sd15", "cuda", 512, 4),
        ("sd15", "cuda", 1024, 1),
        ("sdxl", "cuda", 512, 1),
        ("anima", "cuda", 512, 1),
        ("sd15", "mps", 512, 1),
        ("sd15", "cpu", 512, 1),
        ("sd15", "unknown", 512, 1),
    ],
)
def test_omitted_batch_uses_family_resolution_and_platform_policy(
    family: str,
    platform: str,
    resolution: int,
    expected_batch: int,
) -> None:
    context = _context(
        family,
        platform=platform,
        configured_resolution=resolution,
    )

    compiled = _compile({}, context=context)

    assert compiled.effective.dataset.batch_size == expected_batch
    assert compiled.field_sources["dataset.batch_size"] == "preflight_policy"


@pytest.mark.parametrize(
    ("platform", "status", "configured", "expected"),
    [
        ("unknown", "unavailable", "fp16", "no"),
        ("mps", "verified", "fp16", "no"),
        ("cpu", "verified", "bf16", "no"),
        ("cuda", "verified", "fp16", "fp16"),
    ],
)
def test_omitted_precision_uses_conservative_capability_policy(
    platform: str,
    status: str,
    configured: str,
    expected: str,
) -> None:
    context = _context(
        platform=platform,
        capability_status=status,
        configured_precision=configured,
    )

    compiled = _compile({}, context=context)

    assert compiled.effective.optimization.mixed_precision == expected


def test_explicit_mps_precision_requires_verified_compatible_capability() -> None:
    context = _context(
        platform="mps",
        capability_status="unavailable",
        supported_precision=("no",),
    )
    with pytest.raises(RecipeError) as raised:
        _compile({"mixed_precision": "fp16"}, context=context)

    assert raised.value.code == "unsupported_runtime_precision"
    assert raised.value.hint == "use mixed_precision=no or verify trainer capability"


def test_explicit_verified_mps_precision_is_accepted() -> None:
    context = _context(
        platform="mps",
        capability_status="verified",
        supported_precision=("no", "fp16"),
    )

    compiled = _compile({"mixed_precision": "fp16"}, context=context)

    assert compiled.effective.optimization.mixed_precision == "fp16"
    assert compiled.field_sources["optimization.mixed_precision"] == "caller"


def test_persistent_workers_require_positive_worker_count() -> None:
    with pytest.raises(RecipeError) as raised:
        _compile(
            {
                "execution": {
                    "max_data_loader_n_workers": 0,
                    "persistent_data_loader_workers": True,
                }
            }
        )

    assert raised.value.code == "incompatible_training_recipe"
    assert {
        issue["location"] for issue in raised.value.details["issues"]
    } == {
        "execution.max_data_loader_n_workers",
        "execution.persistent_data_loader_workers",
    }


@pytest.mark.parametrize(
    "dataset",
    [
        {"min_bucket_reso": 1024, "max_bucket_reso": 512},
        {"min_bucket_reso": 250, "max_bucket_reso": 1024, "bucket_reso_steps": 64},
        {"min_bucket_reso": 256, "max_bucket_reso": 1000, "bucket_reso_steps": 64},
        {
            "resolution": 1000,
            "min_bucket_reso": 256,
            "max_bucket_reso": 2048,
            "bucket_reso_steps": 64,
        },
    ],
)
def test_bucket_invariants_fail_closed(dataset: dict) -> None:
    with pytest.raises(RecipeError) as raised:
        _compile({"dataset": dataset})

    assert raised.value.code == "recipe_validation_failed"
    assert raised.value.details["issues"][0]["type"] == "bucket_invariant"


def test_zero_save_cadence_is_explicit_final_only() -> None:
    compiled = _compile({"execution": {"save_every_n_epochs": 0}})

    assert compiled.effective.execution.save_every_n_epochs == 0
    assert compiled.effective.execution.final_only is True
    assert compiled.field_sources["execution.save_every_n_epochs"] == "caller"
    assert compiled.field_sources["execution.final_only"] == "derived"


def test_every_effective_leaf_has_a_source() -> None:
    compiled = _compile({}, family="anima")

    def leaves(value: object, prefix: str = "") -> set[str]:
        if isinstance(value, dict):
            found: set[str] = set()
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else key
                if item is not None:
                    found |= leaves(item, path)
            return found
        return {prefix}

    effective_leaves = leaves(
        compiled.effective.model_dump(mode="json", exclude_none=True)
    )
    assert set(compiled.field_sources) == effective_leaves


def test_step_plan_uses_documented_ceiling_formula_and_ratio_warmup() -> None:
    context = _context(image_count=11)
    compiled = _compile(
        {
            "dataset": {"num_repeats": 3, "batch_size": 4},
            "optimization": {
                "epochs": 3,
                "gradient_accumulation_steps": 2,
                "warmup": {"mode": "ratio", "value": 0.1},
            },
        },
        context=context,
    )

    assert compiled.step_plan.model_dump() == {
        "image_count": 11,
        "num_repeats": 3,
        "train_examples": 33,
        "batch_size": 4,
        "batches_per_epoch": 9,
        "gradient_accumulation_steps": 2,
        "optimizer_steps_per_epoch": 5,
        "epochs": 3,
        "total_optimizer_steps": 15,
        "warmup_steps": 2,
        "process_count": 1,
    }
    assert compiled.effective.optimization.warmup.resolved_steps == 2


def test_fixed_and_random_seeds_are_materialized_once_and_reused() -> None:
    fixed = _compile({"seed": 42})
    random = _compile({"seed": "random"})

    assert fixed.requested.optimization.seed.model_dump() == {
        "mode": "fixed",
        "value": 42,
        "source": "caller",
    }
    assert fixed.effective.optimization.seed == fixed.requested.optimization.seed
    assert random.requested.optimization.seed.model_dump() == {
        "mode": "random",
        "value": 123456789,
        "source": "caller",
    }
    assert random.effective.optimization.seed == random.requested.optimization.seed


def test_preflight_materialized_random_seed_is_not_redrawn_by_start_replay() -> None:
    draws = 0

    def preflight_seed() -> int:
        nonlocal draws
        draws += 1
        return 987654321

    preflight = compile_training_recipe(
        {},
        context=_context(),
        policy_source="preflight_policy",
        seed_factory=preflight_seed,
    )
    start_recipe = preflight.requested.model_dump(mode="json", exclude_none=True)
    start_recipe["expected_recipe_hash"] = preflight.recipe_hash

    replay = compile_training_recipe(
        start_recipe,
        context=_context(),
        policy_source="server_policy",
        seed_factory=lambda: pytest.fail("Start must not redraw a preflight seed"),
        accept_materialized_policy_seed=True,
    )

    assert draws == 1
    assert replay.recipe_hash == preflight.recipe_hash
    assert replay.requested.optimization.seed.source == "preflight_policy"
    assert replay.requested.optimization.seed.value == 987654321


def test_canonical_key_order_and_aliases_do_not_change_recipe_hash() -> None:
    first = _compile(
        {
            "modelFamily": "sd15",
            "batch": "2",
            "optimization": {"seed": 42, "learning_rate": "1e-4"},
        }
    )
    second = _compile(
        {
            "optimization": {"learningRate": "0.0001000", "seed": "42"},
            "dataset": {"batch_size": 2},
            "model": {"family": "sd1.5"},
        }
    )

    assert first.recipe_hash == second.recipe_hash
    assert first.effective == second.effective


@pytest.mark.parametrize(
    "mutator",
    [
        lambda recipe: recipe["optimization"].update({"seed": 43}),
        lambda recipe: recipe["optimization"].update({"optimizer": "Lion"}),
        lambda recipe: recipe["dataset"].update({"batch_size": 2}),
        lambda recipe: recipe["scope"].update({"train_text_encoder": True}),
    ],
)
def test_semantic_recipe_changes_change_hash(mutator) -> None:
    baseline_recipe = {
        "scope": {"train_text_encoder": False},
        "dataset": {"batch_size": 1},
        "optimization": {"seed": 42, "optimizer": "AdamW"},
    }
    changed_recipe = deepcopy(baseline_recipe)
    mutator(changed_recipe)

    baseline = _compile(baseline_recipe)
    if changed_recipe["scope"].get("train_text_encoder"):
        changed_recipe["caching"] = {"cache_text_encoder_outputs": False}
    changed = _compile(changed_recipe)

    assert baseline.recipe_hash != changed.recipe_hash


def test_dataset_profile_and_component_identity_are_semantic_hash_inputs() -> None:
    baseline = _compile({"seed": 42})
    changed_dataset = _compile(
        {"seed": 42},
        context=_context(dataset_hash="e" * 64),
    )
    changed_profile = _compile(
        {"seed": 42},
        context=_context(profile_hash="q" * 64),
    )
    changed_component = _compile(
        {"seed": 42},
        context=_context(checkpoint_sha="f" * 64),
    )

    assert len(
        {
            baseline.recipe_hash,
            changed_dataset.recipe_hash,
            changed_profile.recipe_hash,
            changed_component.recipe_hash,
        }
    ) == 4


def test_expected_hash_is_transport_only_but_stale_value_is_rejected() -> None:
    preview = _compile({"seed": 42})
    replay = _compile(
        {
            "expected_recipe_hash": preview.recipe_hash,
            "seed": {
                "mode": "fixed",
                "value": 42,
                "source": "preflight_policy",
            },
        }
    )

    assert replay.recipe_hash == preview.recipe_hash
    with pytest.raises(RecipeError) as raised:
        _compile({"expected_recipe_hash": "0" * 64, "seed": 42})
    assert raised.value.code == "recipe_hash_mismatch"
