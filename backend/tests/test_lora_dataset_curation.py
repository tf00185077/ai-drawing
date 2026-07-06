"""LoRA dataset deterministic curation service tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import lora_dataset, lora_dataset_curation


@pytest.fixture(autouse=True)
def reset_dataset_locks():
    lora_dataset._reset_locks_for_test()
    yield
    lora_dataset._reset_locks_for_test()


def _settings(base: Path) -> SimpleNamespace:
    return SimpleNamespace(lora_train_dir=str(base), lora_train_threshold=2)


def _write_dataset(base: Path) -> Path:
    dataset = base / "character" / "miku"
    dataset.mkdir(parents=True)
    (dataset / "a.png").write_bytes(b"a")
    (dataset / "a.txt").write_text(
        "Miku Token!, solo, solo, lowres, keep_me",
        encoding="utf-8",
    )
    (dataset / "b.jpg").write_bytes(b"b")
    (dataset / "b.txt").write_text(
        "solo, bad anatomy, blue hair",
        encoding="utf-8",
    )
    (dataset / "c.webp").write_bytes(b"c")
    (dataset / "c.txt").write_text(
        "miku_token, cactus, spaceship, orchestra",
        encoding="utf-8",
    )
    (dataset / ".lora-dataset.json").write_text(
        json.dumps(
            {
                "dataset_type": "character",
                "trigger_token": "Miku Token!",
                "protected_tags": ["keep_me"],
                "removable_tags": ["lowres", "bad anatomy", "keep_me"],
            }
        ),
        encoding="utf-8",
    )
    os.utime(dataset / "a.png", (2000, 2000))
    os.utime(dataset / "a.txt", (1000, 1000))
    os.utime(dataset / "b.jpg", (1000, 1000))
    os.utime(dataset / "b.txt", (2000, 2000))
    os.utime(dataset / "c.webp", (2000, 2000))
    os.utime(dataset / "c.txt", (1000, 1000))
    return dataset


def test_curation_dry_run_normalizes_policy_flags_manual_and_writes_nothing(tmp_path: Path) -> None:
    """Dry-run returns per-file caption edits, manual blocks, outliers, hashes, and no file writes."""
    base = tmp_path / "lora_train"
    dataset = _write_dataset(base)
    original_a = (dataset / "a.txt").read_text(encoding="utf-8")
    original_b = (dataset / "b.txt").read_text(encoding="utf-8")
    original_profile = (dataset / ".lora-dataset.json").read_text(encoding="utf-8")

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        inspected = lora_dataset.inspect_dataset("character/miku")
        plan = lora_dataset_curation.plan_curation("character/miku")

    assert plan.mode == "dry_run"
    assert plan.folder == "character/miku"
    assert plan.normalized_trigger_token == "miku_token"
    assert plan.dataset_hash == inspected.dataset_hash
    assert plan.profile_hash == inspected.profile_hash
    assert plan.dataset_hash_before == inspected.dataset_hash
    assert plan.dataset_hash_after is None
    assert plan.backup_id is None

    by_path = {change.path: change for change in plan.changes}
    assert by_path["character/miku/a.txt"].after == "miku_token, solo, keep_me"
    assert by_path["character/miku/a.txt"].removed_tags == ["lowres"]
    assert by_path["character/miku/a.txt"].duplicate_tags == ["solo"]
    assert by_path["character/miku/a.txt"].protected_tags == ["keep_me"]
    assert by_path["character/miku/a.txt"].status == "changed"

    manual = by_path["character/miku/b.txt"]
    assert manual.after == "miku_token, solo, blue hair"
    assert manual.status == "review_required"
    assert manual.blocked is True
    assert manual.review_required is True
    assert manual.manual is True
    assert manual.manual_reason == "caption_newer_than_image"
    assert manual.manual_overwrite_approved is False

    outlier = by_path["character/miku/c.txt"]
    assert outlier.status == "unchanged"
    assert outlier.outlier_flags == ["low_shared_tag_overlap"]
    assert plan.summary.total_files == 3
    assert plan.summary.changed_count == 1
    assert plan.summary.blocked_count == 1
    assert plan.summary.manual_count == 1
    assert plan.summary.outlier_count == 1
    assert plan.skipped_files == ["character/miku/b.txt"]

    assert (dataset / "a.txt").read_text(encoding="utf-8") == original_a
    assert (dataset / "b.txt").read_text(encoding="utf-8") == original_b
    assert (dataset / ".lora-dataset.json").read_text(encoding="utf-8") == original_profile
    assert not (dataset / lora_dataset_curation.CURATION_BACKUP_DIR).exists()


def test_curation_apply_uses_hashes_backup_and_manual_approval(tmp_path: Path) -> None:
    """Apply checks dataset/profile hashes, backs up writes, and reports approved manual overwrites."""
    base = tmp_path / "lora_train"
    dataset = _write_dataset(base)

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        plan = lora_dataset_curation.plan_curation("character/miku")
        stale_hash = "old-hash"
        with pytest.raises(lora_dataset.DatasetServiceError) as stale:
            lora_dataset_curation.apply_curation(
                "character/miku",
                expected_dataset_hash=stale_hash,
                expected_profile_hash=plan.profile_hash,
            )
        assert stale.value.code == "dataset_hash_mismatch"
        assert stale.value.details["current_dataset_hash"] == plan.dataset_hash

        applied = lora_dataset_curation.apply_curation(
            "character/miku",
            expected_dataset_hash=plan.dataset_hash,
            expected_profile_hash=plan.profile_hash,
            approved_manual_overwrite_paths=["character/miku/b.txt"],
        )

    assert applied.mode == "apply"
    assert applied.backup_id
    assert applied.dataset_hash_before == plan.dataset_hash
    assert applied.dataset_hash_after != plan.dataset_hash
    assert applied.changed_files == ["character/miku/a.txt", "character/miku/b.txt"]
    assert applied.skipped_files == []
    assert applied.manually_overwritten_files == ["character/miku/b.txt"]
    assert (dataset / "a.txt").read_text(encoding="utf-8") == "miku_token, solo, keep_me"
    assert (dataset / "b.txt").read_text(encoding="utf-8") == "miku_token, solo, blue hair"
    assert (dataset / lora_dataset_curation.CURATION_BACKUP_DIR / applied.backup_id / "manifest.json").exists()


def test_curation_rollback_restores_backup_unless_caption_changed_after_apply(tmp_path: Path) -> None:
    """Rollback restores backup files and skips newer manual edits until explicitly approved."""
    base = tmp_path / "lora_train"
    dataset = _write_dataset(base)
    original_a = (dataset / "a.txt").read_text(encoding="utf-8")

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(base)):
        plan = lora_dataset_curation.plan_curation("character/miku")
        applied = lora_dataset_curation.apply_curation(
            "character/miku",
            expected_dataset_hash=plan.dataset_hash,
            expected_profile_hash=plan.profile_hash,
        )
        assert applied.changed_files == ["character/miku/a.txt"]
        (dataset / "a.txt").write_text("manual follow-up edit", encoding="utf-8")

        skipped = lora_dataset_curation.rollback_curation("character/miku", applied.backup_id)
        assert skipped.restored_files == []
        assert skipped.skipped_files == ["character/miku/a.txt"]
        assert (dataset / "a.txt").read_text(encoding="utf-8") == "manual follow-up edit"

        restored = lora_dataset_curation.rollback_curation(
            "character/miku",
            applied.backup_id,
            approved_manual_overwrite_paths=["character/miku/a.txt"],
        )

    assert restored.restored_files == ["character/miku/a.txt"]
    assert restored.manually_overwritten_files == ["character/miku/a.txt"]
    assert restored.dataset_hash_after
    assert (dataset / "a.txt").read_text(encoding="utf-8") == original_a
