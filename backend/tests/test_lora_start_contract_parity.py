"""Cross-layer parity checks for the public LoRA training Start contract."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.schemas.lora_train import TrainStartRequest
from app.services import lora_dataset, lora_training_decision
from app.services.lora_training_recipe import (
    RecipeError,
    compile_training_recipe,
    normalize_recipe_input,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_MCP_SERVER_ROOT = str(_REPOSITORY_ROOT / "mcp-server")
if _MCP_SERVER_ROOT not in sys.path:
    sys.path.insert(0, _MCP_SERVER_ROOT)

from mcp_server.server import REMOVED_LORA_START_FIELDS  # noqa: E402
from mcp_server.tools.lora_train import lora_train_start  # noqa: E402
from app.api.lora_train import _REMOVED_START_FIELDS  # noqa: E402


_APPROVAL_HASH_FIELDS = frozenset(
    {
        "expected_dataset_hash",
        "expected_profile_hash",
    }
)

def _settings(base: Path) -> SimpleNamespace:
    return SimpleNamespace(
        lora_train_dir=str(base),
        lora_train_threshold=3,
        wd_trigger_word="",
        lora_default_checkpoint="model.safetensors",
        lora_model_family="sd15",
        lora_sdxl=False,
        lora_resolution=512,
        lora_batch_size=2,
        lora_learning_rate="1e-4",
        lora_class_tokens="miku_token",
        lora_keep_tokens=1,
        lora_num_repeats=10,
        lora_mixed_precision="fp16",
        lora_network_dim=32,
        lora_network_alpha=16,
        lora_anima_qwen3="",
        lora_anima_vae="",
        lora_anima_t5_tokenizer_path="",
        sd_scripts_python="",
    )


def _write_ready_dataset(base: Path) -> None:
    dataset = base / "character" / "miku"
    dataset.mkdir(parents=True)
    captions = [
        "miku_token, blue hair, twintails, school uniform, smile",
        "miku_token, blue hair, twintails, school uniform, looking at viewer",
        "miku_token, blue hair, twintails, school uniform, standing",
        "miku_token, blue hair, twintails, school uniform, close-up",
    ]
    for index, caption in enumerate(captions, start=1):
        image = dataset / f"{index:02d}.png"
        image.write_bytes(b"image")
        image.with_suffix(".txt").write_text(caption, encoding="utf-8")
    (dataset / ".lora-dataset.json").write_text(
        json.dumps(
            {
                "dataset_type": "character",
                "trigger_token": "miku_token",
                "caption_profile": "wd_tags",
                "model_family": "sd15",
                "protected_tags": ["miku_token"],
                "removable_tags": [],
            }
        ),
        encoding="utf-8",
    )


def test_backend_start_fields_are_exactly_the_canonical_transport() -> None:
    backend_fields = TrainStartRequest.model_fields

    assert set(backend_fields) == {
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe",
    }
    assert _APPROVAL_HASH_FIELDS.issubset(backend_fields)
    assert all(backend_fields[name].is_required() for name in _APPROVAL_HASH_FIELDS)
    assert backend_fields["recipe"].is_required()


def test_backend_and_mcp_start_transport_requiredness_and_migration_fields_match() -> None:
    backend_fields = TrainStartRequest.model_fields
    mcp_parameters = inspect.signature(lora_train_start).parameters

    assert set(mcp_parameters) == set(backend_fields)
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in mcp_parameters.values()
    )
    assert REMOVED_LORA_START_FIELDS == _REMOVED_START_FIELDS
    for recipe in ({}, '{"batchSize":"2"}'):
        payload = {
            "folder": "character/miku",
            "expected_dataset_hash": "dataset-hash",
            "expected_profile_hash": "profile-hash",
            "recipe": recipe,
        }
        assert TrainStartRequest.model_validate(payload).model_dump(
            mode="json"
        ) == payload
        mcp_parameters_signature = inspect.signature(lora_train_start)
        mcp_parameters_signature.bind(**payload)


def test_train_preflight_payload_validates_through_start_unchanged(
    tmp_path: Path,
) -> None:
    base = tmp_path / "lora_train"
    _write_ready_dataset(base)
    settings = _settings(base)

    with patch("app.services.lora_dataset.get_settings", return_value=settings):
        inspected = lora_dataset.inspect_dataset("character/miku")
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            expected_dataset_hash=inspected.dataset_hash,
            expected_profile_hash=inspected.profile_hash,
        )

    assert result.decision == "train"
    assert result.start_payload is not None
    payload = result.start_payload.model_dump(mode="json")
    assert payload["recipe"]["expected_recipe_hash"] == result.recipe_hash
    validated = TrainStartRequest.model_validate(payload)
    assert validated.model_dump(mode="json") == payload


@pytest.mark.parametrize("stale_kind", ["component", "capability"])
def test_start_recompile_rejects_stale_recipe_evidence(
    tmp_path: Path,
    stale_kind: str,
) -> None:
    base = tmp_path / "lora_train"
    _write_ready_dataset(base)
    settings = _settings(base)

    with patch("app.services.lora_dataset.get_settings", return_value=settings):
        inspected = lora_dataset.inspect_dataset("character/miku")
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            expected_dataset_hash=inspected.dataset_hash,
            expected_profile_hash=inspected.profile_hash,
        )

    assert result.start_payload is not None
    normalized = normalize_recipe_input(
        result.start_payload.recipe.model_dump(mode="json"),
        accept_materialized_policy_seed=True,
    )
    with patch("app.services.lora_dataset.get_settings", return_value=settings):
        context = lora_training_decision.build_recipe_compilation_context(
            inspected,
            normalized,
            approved_trigger_token=result.normalized_trigger_token,
        )

    if stale_kind == "component":
        changed = context.component_identities["checkpoint"].model_copy(
            update={
                "verification_status": "unverified",
                "reason": "component identity changed",
                "modified_time_ns": 123,
            }
        )
        context = context.model_copy(
            update={
                "component_identities": {
                    **dict(context.component_identities),
                    "checkpoint": changed,
                }
            }
        )
    else:
        context = context.model_copy(
            update={
                "capability": context.capability.model_copy(
                    update={
                        "platform": "cuda",
                        "status": "verified",
                        "reason": None,
                        "supported_mixed_precision": ("no", "fp16"),
                    }
                )
            }
        )

    with pytest.raises(RecipeError) as exc_info:
        compile_training_recipe(
            normalized,
            context=context,
            accept_materialized_policy_seed=True,
        )

    assert exc_info.value.code == "recipe_hash_mismatch"
