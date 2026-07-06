"""LoRA dataset preparation and validation service tests."""

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import lora_dataset


@pytest.fixture(autouse=True)
def reset_dataset_locks():
    lora_dataset._reset_locks_for_test()
    yield
    lora_dataset._reset_locks_for_test()


@pytest.fixture
def dataset_root(tmp_path: Path) -> Path:
    base = tmp_path / "lora_train"
    ds = base / "character" / "miku"
    ds.mkdir(parents=True)
    (ds / "a.png").write_bytes(b"a")
    (ds / "a.txt").write_text("solo, blue hair", encoding="utf-8")
    (ds / "b.jpg").write_bytes(b"b")
    (ds / "b.txt").write_text("miku_token, solo, miku_token", encoding="utf-8")
    return base


def _settings(base: Path) -> MagicMock:
    settings = MagicMock()
    settings.lora_train_dir = str(base)
    settings.lora_train_threshold = 2
    settings.llm_caption_url = None
    return settings


def _write_profile(dataset_dir: Path, payload: dict) -> Path:
    profile_path = dataset_dir / ".lora-dataset.json"
    profile_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return profile_path


def test_dataset_list_inspect_hash_and_path_traversal(dataset_root: Path) -> None:
    """列出/檢查 dataset，雜湊會因 caption 內容改變，且拒絕 traversal。"""
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        datasets = lora_dataset.list_datasets()
        assert datasets[0].folder == "character/miku"
        assert datasets[0].image_count == 2
        assert datasets[0].caption_count == 2
        assert datasets[0].missing_caption_count == 0

        inspected = lora_dataset.inspect_dataset("character/miku")
        before_hash = inspected.dataset_hash
        assert inspected.files[0].image_path == "character/miku/a.png"
        assert inspected.files[0].caption_path == "character/miku/a.txt"
        assert "miku_token" in inspected.trigger_token_candidates

        (dataset_root / "character" / "miku" / "a.txt").write_text("changed", encoding="utf-8")
        assert lora_dataset.inspect_dataset("character/miku").dataset_hash != before_hash

        with pytest.raises(lora_dataset.DatasetServiceError, match="invalid_dataset_folder"):
            lora_dataset.inspect_dataset("../outside")


def test_missing_dataset_profile_uses_conservative_defaults(dataset_root: Path) -> None:
    """Missing metadata is valid, keeps discovery working, and defaults auto_train off."""
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        inspected = lora_dataset.inspect_dataset("character/miku")

    assert inspected.profile_hash is None
    assert inspected.profile.present is False
    assert inspected.profile.valid is True
    assert inspected.profile.dataset_type == "unknown"
    assert inspected.profile.trigger_token == "miku_token"
    assert inspected.profile.caption_profile == "unknown"
    assert inspected.profile.model_family == "unknown"
    assert inspected.profile.protected_tags == []
    assert inspected.profile.removable_tags == []
    assert inspected.profile.auto_train is False
    assert inspected.profile.errors == []
    assert inspected.profile.warnings == []


def test_valid_dataset_profile_is_normalized_and_hashed(dataset_root: Path) -> None:
    """Valid .lora-dataset.json values are normalized without entering dataset_hash."""
    dataset_dir = dataset_root / "character" / "miku"
    before_settings = _settings(dataset_root)
    with patch("app.services.lora_dataset.get_settings", return_value=before_settings):
        before_hash = lora_dataset.inspect_dataset("character/miku").dataset_hash

    profile_path = _write_profile(
        dataset_dir,
        {
            "type": "character",
            "trigger_token": "Miku Token!",
            "caption_profile": "wd_tags",
            "model_family": "sdxl",
            "protected_tags": ["miku_token", " solo ", ""],
            "remove_tags": ["bad anatomy"],
            "removable_tags": ["lowres", "bad anatomy"],
        },
    )
    expected_profile_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        listed = lora_dataset.list_datasets()[0]
        inspected = lora_dataset.inspect_dataset("character/miku")

    assert inspected.dataset_hash == before_hash
    assert listed.dataset_hash == before_hash
    assert inspected.profile_hash == expected_profile_hash
    assert listed.profile_hash == expected_profile_hash
    assert inspected.profile.present is True
    assert inspected.profile.valid is True
    assert inspected.profile.dataset_type == "character"
    assert inspected.profile.trigger_token == "miku_token"
    assert inspected.profile.caption_profile == "wd_tags"
    assert inspected.profile.model_family == "sdxl"
    assert inspected.profile.protected_tags == ["miku_token", "solo"]
    assert inspected.profile.removable_tags == ["bad anatomy", "lowres"]
    assert inspected.profile.auto_train is False
    assert inspected.profile.errors == []

    profile_path.write_text(
        json.dumps({"dataset_type": "style", "trigger_token": "style_token"}, ensure_ascii=False),
        encoding="utf-8",
    )
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        changed_profile = lora_dataset.inspect_dataset("character/miku")
    assert changed_profile.dataset_hash == before_hash
    assert changed_profile.profile_hash != expected_profile_hash


def test_malformed_dataset_profile_reports_error_without_breaking_discovery(dataset_root: Path) -> None:
    """Invalid JSON is reported structurally while raw image/caption discovery remains usable."""
    dataset_dir = dataset_root / "character" / "miku"
    profile_path = dataset_dir / ".lora-dataset.json"
    profile_path.write_text("{not json", encoding="utf-8")
    expected_profile_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        listed = lora_dataset.list_datasets()[0]
        inspected = lora_dataset.inspect_dataset("character/miku")

    assert listed.image_count == 2
    assert listed.caption_count == 2
    assert listed.profile_hash == expected_profile_hash
    assert listed.profile.valid is False
    assert inspected.files[0].caption == "solo, blue hair"
    assert inspected.profile.profile_hash == expected_profile_hash
    assert [error.code for error in inspected.profile.errors] == ["invalid_profile_json"]
    assert inspected.profile.errors[0].path == "character/miku/.lora-dataset.json"


def test_unsupported_dataset_profile_values_return_structured_errors(dataset_root: Path) -> None:
    """Unsupported enum values and invalid list fields do not abort dataset inspection."""
    dataset_dir = dataset_root / "character" / "miku"
    _write_profile(
        dataset_dir,
        {
            "dataset_type": "vehicle",
            "caption_profile": "html",
            "model_family": "wan",
            "protected_tags": "miku_token",
            "removable_tags": ["bad anatomy"],
        },
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        inspected = lora_dataset.inspect_dataset("character/miku")

    assert inspected.image_count == 2
    assert inspected.profile.valid is False
    assert inspected.profile.dataset_type == "unknown"
    assert inspected.profile.caption_profile == "unknown"
    assert inspected.profile.model_family == "unknown"
    assert inspected.profile.removable_tags == ["bad anatomy"]
    assert {error.code for error in inspected.profile.errors} == {
        "unsupported_dataset_type",
        "unsupported_caption_profile",
        "unsupported_model_family",
        "invalid_profile_field",
    }


def test_auto_train_profile_metadata_does_not_enqueue_training(dataset_root: Path) -> None:
    """auto_train may be reported from metadata but list/inspect/validate do not start training."""
    dataset_dir = dataset_root / "character" / "miku"
    _write_profile(
        dataset_dir,
        {
            "dataset_type": "character",
            "trigger_token": "miku_token",
            "auto_train": True,
        },
    )

    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)), patch(
        "app.services.lora_trainer.enqueue"
    ) as enqueue:
        listed = lora_dataset.list_datasets()[0]
        inspected = lora_dataset.inspect_dataset("character/miku")
        validated = lora_dataset.validate_dataset("character/miku", trigger_token="miku_token")

    assert listed.profile.auto_train is True
    assert inspected.profile.auto_train is True
    assert any(warning.code == "auto_train_descriptive_only" for warning in inspected.profile.warnings)
    assert validated.folder == "character/miku"
    enqueue.assert_not_called()


def test_normalize_trigger_token_and_caption() -> None:
    """trigger token 正規化後只會出現在 caption 開頭一次。"""
    token = lora_dataset.normalize_trigger_token(" Miku Token!! ")
    assert token == "miku_token"
    caption = lora_dataset.normalize_caption("solo, miku_token, blue hair, MIKU_TOKEN", token)
    assert caption == "miku_token, solo, blue hair"


def test_prepare_dry_run_apply_and_restore(dataset_root: Path) -> None:
    """prepare dry-run 不寫檔；apply 建 backup 並可 restore。"""
    settings = _settings(dataset_root)
    with patch("app.services.lora_dataset.get_settings", return_value=settings):
        dry = lora_dataset.prepare_dataset("character/miku", trigger_token="Miku Token", dry_run=True)
        assert dry.backup_id is None
        assert dry.changed_count == 2
        assert dry.dataset_hash_after is None
        assert (dataset_root / "character" / "miku" / "a.txt").read_text(encoding="utf-8") == "solo, blue hair"

        applied = lora_dataset.prepare_dataset("character/miku", trigger_token="Miku Token", dry_run=False)
        assert applied.backup_id
        assert applied.dataset_hash_after
        assert (dataset_root / "character" / "miku" / "a.txt").read_text(encoding="utf-8").startswith("miku_token, ")
        assert (dataset_root / "character" / "miku" / ".lora_prep_backups" / applied.backup_id).exists()

        restored = lora_dataset.restore_dataset("character/miku", applied.backup_id)
        assert restored.restored_files == ["character/miku/a.txt", "character/miku/b.txt"]
        assert (dataset_root / "character" / "miku" / "a.txt").read_text(encoding="utf-8") == "solo, blue hair"


def test_prepare_apply_rejects_stale_hash_and_ai_without_provider(dataset_root: Path) -> None:
    """套用時會拒絕 stale hash；AI cleanup 未設定時回明確錯誤。"""
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        with pytest.raises(lora_dataset.DatasetServiceError) as stale:
            lora_dataset.prepare_dataset(
                "character/miku",
                trigger_token="miku_token",
                dry_run=False,
                expected_dataset_hash="old-hash",
            )
        assert stale.value.code == "dataset_hash_mismatch"
        assert "current_dataset_hash" in stale.value.details

        with pytest.raises(lora_dataset.DatasetServiceError) as ai:
            lora_dataset.prepare_dataset(
                "character/miku",
                trigger_token="miku_token",
                dry_run=True,
                use_ai_cleanup=True,
            )
        assert ai.value.code == "ai_cleanup_not_configured"


def test_validate_dataset_reports_missing_trigger_stale_hash_and_locks(dataset_root: Path) -> None:
    """validation 回傳 missing trigger、stale hash 與 lock conflict。"""
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        result = lora_dataset.validate_dataset("character/miku", trigger_token="miku_token")
        assert result.ok is False
        assert any(issue.code == "missing_trigger_token" for issue in result.errors)

        current_hash = result.dataset_hash
        stale = lora_dataset.validate_dataset(
            "character/miku",
            trigger_token="miku_token",
            expected_dataset_hash="old-hash",
        )
        assert stale.ok is False
        assert any(issue.code == "dataset_hash_mismatch" for issue in stale.errors)
        assert stale.dataset_hash == current_hash

        with lora_dataset.dataset_lock("character/miku", owner="test"):
            locked = lora_dataset.validate_dataset("character/miku", trigger_token="miku_token")
            assert locked.ok is False
            assert locked.locked is True
            assert any(issue.code == "dataset_locked" for issue in locked.errors)


def test_dataset_lock_blocks_concurrent_apply(dataset_root: Path) -> None:
    """dataset lock 會阻擋同資料夾的寫入操作。"""
    with patch("app.services.lora_dataset.get_settings", return_value=_settings(dataset_root)):
        with lora_dataset.dataset_lock("character/miku", owner="test"):
            with pytest.raises(lora_dataset.DatasetServiceError) as exc:
                lora_dataset.prepare_dataset("character/miku", trigger_token="miku_token", dry_run=False)
        assert exc.value.code == "dataset_locked"
