"""LoRA training decision preflight service and API tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import lora_dataset, lora_training_decision


@pytest.fixture(autouse=True)
def reset_dataset_locks():
    lora_dataset._reset_locks_for_test()
    yield
    lora_dataset._reset_locks_for_test()


def _settings(base: Path, threshold: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        lora_train_dir=str(base),
        lora_train_threshold=threshold,
        wd_trigger_word="",
        lora_default_checkpoint="model.safetensors",
        lora_model_family="",
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
    )


def _write_dataset(
    base: Path,
    captions: list[str | None],
    profile: dict,
    *,
    folder: str = "character/miku",
) -> Path:
    dataset = base / folder
    dataset.mkdir(parents=True)
    for index, caption in enumerate(captions, start=1):
        image = dataset / f"{index:02d}.png"
        image.write_bytes(b"image")
        if caption is not None:
            image.with_suffix(".txt").write_text(caption, encoding="utf-8")
    (dataset / ".lora-dataset.json").write_text(
        json.dumps(profile, ensure_ascii=False),
        encoding="utf-8",
    )
    return dataset


def _ready_profile() -> dict:
    return {
        "dataset_type": "character",
        "trigger_token": "miku_token",
        "caption_profile": "wd_tags",
        "model_family": "sd15",
        "protected_tags": ["miku_token"],
        "removable_tags": [],
    }


def test_training_decision_returns_exact_canonical_start_payload_without_hints(
    tmp_path: Path,
) -> None:
    """A valid, coherent, curated dataset returns train without side effects."""
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, looking at viewer",
            "miku_token, blue hair, twintails, school uniform, standing",
            "miku_token, blue hair, twintails, school uniform, close-up",
        ],
        _ready_profile(),
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        inspected = lora_dataset.inspect_dataset("character/miku")
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            expected_dataset_hash=inspected.dataset_hash,
            expected_profile_hash=inspected.profile_hash,
        )

    assert result.decision == "train"
    assert result.dataset_hash == inspected.dataset_hash
    assert result.profile_hash == inspected.profile_hash
    assert result.normalized_trigger_token == "miku_token"
    assert result.blocking_issues == []
    assert result.requested_recipe is not None
    assert result.requested_recipe.model is None
    assert result.requested_recipe.dataset is None
    assert result.requested_recipe.optimization is not None
    assert result.requested_recipe.optimization.model_dump(
        exclude_none=True
    ).keys() == {"seed"}
    assert result.requested_recipe.optimization.seed.mode == "random"
    assert result.requested_recipe.optimization.seed.source == "preflight_policy"
    assert result.effective_recipe is not None
    assert result.effective_recipe.dataset.batch_size == 1
    assert result.effective_recipe.dataset.class_tokens == "miku_token"
    assert result.field_sources["dataset.batch_size"] == "preflight_policy"
    assert result.recipe_hash is not None
    assert result.start_payload is not None
    assert result.start_payload.folder == "character/miku"
    assert result.start_payload.expected_dataset_hash == inspected.dataset_hash
    assert result.start_payload.expected_profile_hash == inspected.profile_hash
    assert (
        result.start_payload.recipe.expected_recipe_hash
        == result.recipe_hash
    )
    assert (
        result.start_payload.recipe.optimization.seed.value
        == result.requested_recipe.optimization.seed.value
    )
    assert result.suggested_params is not None
    assert result.suggested_params.params == result.start_payload.model_dump(
        mode="json"
    )
    assert any("explicit approval" in action for action in result.next_actions)


def test_training_decision_requires_review_when_configured_family_conflicts_with_profile(
    tmp_path: Path,
) -> None:
    """A configured/profile family conflict cannot suggest a ready default checkpoint."""
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, looking at viewer",
            "miku_token, blue hair, twintails, school uniform, standing",
            "miku_token, blue hair, twintails, school uniform, close-up",
        ],
        _ready_profile(),
    )
    settings = _settings(base)
    settings.lora_model_family = "sdxl"
    settings.lora_default_checkpoint = "sdxl-default.safetensors"

    with patch("app.services.lora_dataset.get_settings", return_value=settings):
        result = lora_training_decision.decide_training_preflight("character/miku")

    assert result.decision == "needs_review"
    assert result.blocking_issues == []
    mismatch = next(warning for warning in result.warnings if warning.code == "model_family_mismatch")
    assert mismatch.details == {
        "configured_model_family": "sdxl",
        "dataset_profile_model_family": "sd15",
    }
    assert result.suggested_params is None
    assert result.start_payload is None


def test_training_decision_returns_needs_review_for_caption_and_curation_warnings(tmp_path: Path) -> None:
    """Reviewable caption coherence and curation outliers are not transport errors."""
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, glass tower, sunset, orange dress",
            "miku_token, rainy alley, umbrella, neon sign",
            "miku_token, beach chair, striped towel, noon",
            "miku_token, library shelf, red scarf, candle",
        ],
        _ready_profile(),
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_training_decision.decide_training_preflight("character/miku")

    assert result.decision == "needs_review"
    assert result.blocking_issues == []
    assert result.suggested_params is None
    assert result.start_payload is None
    warning_codes = {warning.code for warning in result.warnings}
    assert "over_fragmented_tags" in warning_codes
    assert "curation_outliers_detected" in warning_codes
    assert any("rerun decision preflight" in action for action in result.next_actions)


def test_training_decision_returns_do_not_train_for_blocking_issues_and_stale_hashes(tmp_path: Path) -> None:
    """Invalid metadata, validation failures, and stale hashes block training."""
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        ["miku_token, blue hair", None, ""],
        {
            "dataset_type": "vehicle",
            "trigger_token": "miku_token",
            "caption_profile": "wd_tags",
            "model_family": "sd15",
        },
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            expected_dataset_hash="old-dataset-hash",
            expected_profile_hash="old-profile-hash",
        )

    assert result.decision == "do_not_train"
    assert result.suggested_params is None
    blocking_codes = {issue.code for issue in result.blocking_issues}
    assert {
        "unsupported_dataset_type",
        "dataset_hash_mismatch",
        "profile_hash_mismatch",
        "missing_caption",
        "empty_caption",
    }.issubset(blocking_codes)
    assert any("Do not call lora_train_start" in action for action in result.next_actions)


def test_training_decision_api_does_not_enqueue_training(tmp_path: Path, monkeypatch) -> None:
    """The backend preflight endpoint returns a payload and never starts training."""
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, looking at viewer",
            "miku_token, blue hair, twintails, school uniform, standing",
        ],
        _ready_profile(),
    )
    settings = _settings(base)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    client = TestClient(app)

    with patch("app.api.lora_train.lora_trainer.enqueue") as enqueue:
        response = client.post(
            "/api/lora-train/datasets/training-decision-preflight",
            json={"folder": "character/miku"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["decision"] == "train"
    assert payload["start_payload"]["expected_dataset_hash"] == payload["dataset_hash"]
    assert payload["start_payload"]["expected_profile_hash"] == payload["profile_hash"]
    assert (
        payload["start_payload"]["recipe"]["expected_recipe_hash"]
        == payload["recipe_hash"]
    )
    enqueue.assert_not_called()


def test_training_decision_normalizes_partial_aliased_recipe_hints(
    tmp_path: Path,
) -> None:
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, looking at viewer",
            "miku_token, blue hair, twintails, school uniform, standing",
        ],
        _ready_profile(),
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            recipe={
                "batchSize": "2",
                "gradientAccumulation": "3",
                "saveCadence": "0",
            },
        )

    assert result.decision == "train"
    requested = result.requested_recipe.model_dump(mode="json", exclude_none=True)
    assert requested["dataset"] == {"batch_size": 2}
    assert requested["optimization"]["gradient_accumulation_steps"] == 3
    assert set(requested["optimization"]) == {
        "gradient_accumulation_steps",
        "seed",
    }
    assert requested["execution"] == {"save_every_n_epochs": 0}
    assert result.effective_recipe.execution.final_only is True
    assert result.start_payload.recipe.model_dump(
        mode="json",
        exclude_none=True,
    ) == {
        **requested,
        "expected_recipe_hash": result.recipe_hash,
    }


def test_invalid_recipe_hint_is_structured_and_never_enqueues(
    tmp_path: Path,
) -> None:
    base = tmp_path / "lora_train"
    _write_dataset(
        base,
        [
            "miku_token, blue hair, twintails, school uniform, smile",
            "miku_token, blue hair, twintails, school uniform, standing",
            "miku_token, blue hair, twintails, school uniform, close-up",
        ],
        _ready_profile(),
    )

    with (
        patch("app.services.lora_dataset.get_settings", return_value=_settings(base)),
        patch("app.services.lora_trainer.enqueue") as enqueue,
    ):
        result = lora_training_decision.decide_training_preflight(
            "character/miku",
            recipe={"dataset": {"batch_szie": "SECRET_DO_NOT_ECHO"}},
        )

    assert result.decision == "do_not_train"
    issue = next(
        item
        for item in result.blocking_issues
        if item.code == "recipe_validation_failed"
    )
    assert issue.details["hint"] == "apply the suggested field correction and retry"
    assert "SECRET_DO_NOT_ECHO" not in json.dumps(issue.model_dump())
    assert result.requested_recipe is None
    assert result.start_payload is None
    enqueue.assert_not_called()


def test_training_decision_api_reports_invalid_folder_structurally() -> None:
    """Invalid folder syntax is returned as a structured API error."""
    client = TestClient(app)

    response = client.post(
        "/api/lora-train/datasets/training-decision-preflight",
        json={"folder": "../outside"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_dataset_folder"
