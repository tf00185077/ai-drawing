"""LoRA dataset preparation and validation service tests."""

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
