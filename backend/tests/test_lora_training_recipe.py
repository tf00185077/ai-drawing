"""Versioned LoRA training recipe normalization and compilation tests."""
from __future__ import annotations

import json

import pytest

from app.services.lora_training_recipe import (
    RecipeError,
    normalize_recipe_input,
)


def _normalize(value: object, *, seed: int = 123456789):
    return normalize_recipe_input(
        value,
        policy_source="server_policy",
        seed_factory=lambda: seed,
    )


def test_equivalent_object_and_json_string_normalize_to_one_requested_shape() -> None:
    recipe = {
        "schema_version": 1,
        "model": {
            "family": "SDXL",
            "checkpoint": "models/base.safetensors",
        },
        "scope": {"trainable_scope": "denoiser_only"},
        "dataset": {
            "class_tokens": " sks ",
            "batch": "2",
            "resolution": "1024",
        },
        "optimization": {
            "epochs": "3",
            "seed": "42",
            "optimizer": "AdamW",
            "scheduler": "constant",
        },
    }

    from_object = _normalize(recipe)
    from_string = _normalize(json.dumps(recipe))

    expected = {
        "schema_version": "lora-training-recipe/v1",
        "model": {
            "family": "sdxl",
            "checkpoint": "models/base.safetensors",
        },
        "scope": {"train_text_encoder": False},
        "dataset": {
            "trigger_token": "sks",
            "batch_size": 2,
            "resolution": 1024,
        },
        "optimization": {
            "epochs": 3,
            "seed": {
                "mode": "fixed",
                "value": 42,
                "source": "caller",
            },
            "optimizer_type": "AdamW",
            "lr_scheduler": "constant",
        },
    }
    assert from_object.requested.model_dump(exclude_none=True) == expected
    assert from_string.requested == from_object.requested
    assert from_string.provided_fields == from_object.provided_fields


def test_flat_camel_aliases_and_lossless_scalars_are_normalized() -> None:
    normalized = _normalize(
        {
            "schemaVersion": "v1",
            "modelFamily": "anima",
            "checkpoint": "models/anima.safetensors",
            "qwen3": "models/qwen3",
            "batchSize": "1",
            "gradientAccumulation": "4",
            "workers": "2",
            "persistentWorkers": "true",
            "saveCadence": "0",
            "cacheLatents": "1",
            "cacheTextEncoderOutputs": "true",
            "cacheToDisk": "false",
        }
    )

    requested = normalized.requested.model_dump(exclude_none=True)
    assert requested["model"] == {
        "family": "anima",
        "checkpoint": "models/anima.safetensors",
        "anima": {"qwen3": "models/qwen3"},
    }
    assert requested["dataset"]["batch_size"] == 1
    assert requested["optimization"]["gradient_accumulation_steps"] == 4
    assert requested["execution"] == {
        "max_data_loader_n_workers": 2,
        "persistent_data_loader_workers": True,
        "save_every_n_epochs": 0,
    }
    assert requested["caching"] == {
        "cache_latents": True,
        "cache_text_encoder_outputs": True,
        "cache_to_disk": False,
    }


@pytest.mark.parametrize(
    ("raw_args", "expected"),
    [
        ({"weight_decay": 0.01, "decouple": True}, ("decouple=true", "weight_decay=0.01")),
        (["weight_decay=0.01", "decouple=true"], ("decouple=true", "weight_decay=0.01")),
        ("weight_decay=0.01 decouple=true", ("decouple=true", "weight_decay=0.01")),
    ],
)
def test_optimizer_and_scheduler_argument_forms_are_canonical_lists(
    raw_args: object,
    expected: list[str],
) -> None:
    normalized = _normalize(
        {
            "optimization": {
                "optimizer_args": raw_args,
                "lr_scheduler_args": raw_args,
            }
        }
    )

    optimization = normalized.requested.optimization
    assert optimization is not None
    assert optimization.optimizer_args == expected
    assert optimization.lr_scheduler_args == expected


@pytest.mark.parametrize(
    ("raw_rate", "expected"),
    [
        ("5e-5", ("0.00005",)),
        (["5e-5", "4e-5"], ("0.00005", "0.00004")),
        ([0.00005, 0.00004], ("0.00005", "0.00004")),
    ],
)
def test_scalar_and_list_text_encoder_learning_rates_are_canonical(
    raw_rate: object,
    expected: list[str],
) -> None:
    normalized = _normalize(
        {"optimization": {"text_encoder_lr": raw_rate}}
    )

    assert normalized.requested.optimization is not None
    assert normalized.requested.optimization.text_encoder_learning_rates == expected


def test_numeric_equivalent_rate_aliases_do_not_conflict() -> None:
    normalized = _normalize(
        {
            "learning_rate": "1e-4",
            "optimization": {"learningRate": "0.0001000"},
        }
    )

    assert normalized.requested.optimization is not None
    assert normalized.requested.optimization.learning_rate == "0.0001"


@pytest.mark.parametrize(
    "raw_args",
    [
        ["--network_module=evil"],
        {"--network_module": "evil"},
        "weight_decay=0.01 --network_module=evil",
        ["weight_decay=0.01", "weight_decay=0.02"],
        ["not-a-key-value"],
    ],
)
def test_optimizer_arguments_reject_raw_flags_and_ambiguous_forms(
    raw_args: object,
) -> None:
    with pytest.raises(RecipeError) as raised:
        _normalize({"optimization": {"optimizer_args": raw_args}})

    assert raised.value.code == "recipe_validation_failed"
    assert raised.value.details["issues"][0]["location"] == "optimization.optimizer_args"


def test_partial_recipe_preserves_omissions_and_materializes_seed_once() -> None:
    calls = 0

    def draw_seed() -> int:
        nonlocal calls
        calls += 1
        return 777

    normalized = normalize_recipe_input(
        {},
        policy_source="preflight_policy",
        seed_factory=draw_seed,
    )

    assert calls == 1
    assert normalized.requested.model is None
    assert normalized.requested.dataset is None
    assert normalized.requested.optimization is not None
    assert normalized.requested.optimization.model_dump(exclude_none=True) == {
        "seed": {
            "mode": "random",
            "value": 777,
            "source": "preflight_policy",
        }
    }
    assert normalized.provided_fields == frozenset()


def test_conflicting_aliases_fail_without_silently_selecting_one() -> None:
    with pytest.raises(RecipeError) as raised:
        _normalize(
            {
                "batch": 1,
                "dataset": {"batch_size": 2},
            }
        )

    error = raised.value
    assert error.code == "recipe_field_conflict"
    assert error.hint == "remove one conflicting alias and retry"
    assert error.details == {
        "issues": [
            {
                "location": "dataset.batch_size",
                "type": "alias_conflict",
                "accepted_forms": ["batch", "batchSize", "batch_size"],
            }
        ]
    }


def test_unknown_field_returns_redacted_closest_field_guidance() -> None:
    secret_value = "https://secret.invalid/model?token=do-not-echo"

    with pytest.raises(RecipeError) as raised:
        _normalize({"dataset": {"batch_szie": secret_value}})

    error = raised.value
    assert error.code == "recipe_validation_failed"
    assert error.message == "training recipe is invalid"
    assert error.hint == "apply the suggested field correction and retry"
    assert len(error.details["issues"]) == 1
    issue = error.details["issues"][0]
    assert issue["location"] == "dataset.batch_szie"
    assert issue["type"] == "unknown_field"
    assert issue["suggestion"] == "batch_size"
    assert {"batch", "batchSize", "batch_size"} <= set(issue["accepted_forms"])
    assert secret_value not in str(error)
    assert secret_value not in json.dumps(error.details)


def test_unsafe_unknown_field_name_is_redacted() -> None:
    secret = "Bearer_DO_NOT_ECHO"

    with pytest.raises(RecipeError) as raised:
        _normalize({f"unknown?token={secret}": 1})

    serialized = json.dumps(raised.value.details)
    assert secret not in serialized
    assert raised.value.details["issues"][0]["location"] == "<unknown>"


def test_untrusted_seed_envelope_cannot_forge_policy_provenance() -> None:
    normalized = _normalize(
        {
            "optimization": {
                "seed": {
                    "mode": "random",
                    "value": 123,
                    "source": "preflight_policy",
                }
            }
        }
    )

    assert normalized.requested.optimization is not None
    assert normalized.requested.optimization.seed is not None
    assert normalized.requested.optimization.seed.source == "caller"


@pytest.mark.parametrize(
    "raw",
    [
        {"dataset": {"batch_size": "1.5"}},
        {"execution": {"persistent_data_loader_workers": "sometimes"}},
        {"optimization": {"seed": "not-a-seed"}},
    ],
)
def test_invalid_lossless_coercion_returns_safe_field_issue(raw: object) -> None:
    with pytest.raises(RecipeError) as raised:
        _normalize(raw)

    error = raised.value
    assert error.code == "recipe_validation_failed"
    assert error.hint == "apply the suggested field correction and retry"
    issue = error.details["issues"][0]
    assert issue["type"] == "invalid_value"
    assert "input" not in issue
    assert "url" not in issue


@pytest.mark.parametrize("raw", ["[]", "42", "null", ["not", "an", "object"]])
def test_non_object_recipe_transport_is_rejected(raw: object) -> None:
    with pytest.raises(RecipeError) as raised:
        _normalize(raw)

    assert raised.value.code == "recipe_validation_failed"
    assert raised.value.details == {
        "issues": [
            {
                "location": "recipe",
                "type": "object_required",
                "accepted_forms": ["JSON object", "JSON-object string"],
            }
        ]
    }
