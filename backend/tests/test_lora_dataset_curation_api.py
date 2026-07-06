"""LoRA dataset curation API tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services import lora_dataset


def _settings(base: Path) -> SimpleNamespace:
    return SimpleNamespace(lora_train_dir=str(base), lora_train_threshold=2)


def _make_dataset(base: Path) -> Path:
    dataset = base / "character" / "miku"
    dataset.mkdir(parents=True)
    (dataset / "a.png").write_bytes(b"a")
    (dataset / "a.txt").write_text("Miku Token!, solo, lowres", encoding="utf-8")
    (dataset / "b.jpg").write_bytes(b"b")
    (dataset / "b.txt").write_text("solo, bad anatomy", encoding="utf-8")
    (dataset / ".lora-dataset.json").write_text(
        json.dumps(
            {
                "dataset_type": "character",
                "trigger_token": "Miku Token!",
                "protected_tags": ["solo"],
                "removable_tags": ["lowres", "bad anatomy"],
            }
        ),
        encoding="utf-8",
    )
    os.utime(dataset / "a.png", (2000, 2000))
    os.utime(dataset / "a.txt", (1000, 1000))
    os.utime(dataset / "b.jpg", (1000, 1000))
    os.utime(dataset / "b.txt", (2000, 2000))
    return dataset


def test_curation_api_apply_conflicts_manual_protection_and_rollback(tmp_path: Path, monkeypatch) -> None:
    """Curation API dry-runs, rejects stale hashes, applies with backup, and rolls back safely."""
    base = tmp_path / "lora_train"
    dataset = _make_dataset(base)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: _settings(base))
    client = TestClient(app)

    dry = client.post(
        "/api/lora-train/datasets/curate",
        json={"folder": "character/miku", "mode": "dry_run"},
    )
    assert dry.status_code == 200
    plan = dry.json()
    assert plan["ok"] is True
    assert plan["dataset_hash"]
    assert plan["profile_hash"]
    assert plan["summary"]["blocked_count"] == 1
    assert plan["skipped_files"] == ["character/miku/b.txt"]
    assert (dataset / "a.txt").read_text(encoding="utf-8") == "Miku Token!, solo, lowres"

    stale_dataset = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "apply",
            "expected_dataset_hash": "old-hash",
            "expected_profile_hash": plan["profile_hash"],
        },
    )
    assert stale_dataset.status_code == 409
    assert stale_dataset.json()["detail"]["code"] == "dataset_hash_mismatch"
    assert stale_dataset.json()["detail"]["details"]["current_dataset_hash"] == plan["dataset_hash"]

    stale_profile = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "apply",
            "expected_dataset_hash": plan["dataset_hash"],
            "expected_profile_hash": "old-profile",
        },
    )
    assert stale_profile.status_code == 409
    assert stale_profile.json()["detail"]["code"] == "profile_hash_mismatch"

    applied = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "apply",
            "expected_dataset_hash": plan["dataset_hash"],
            "expected_profile_hash": plan["profile_hash"],
        },
    )
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["backup_id"]
    assert applied_payload["changed_files"] == ["character/miku/a.txt"]
    assert applied_payload["skipped_files"] == ["character/miku/b.txt"]
    assert applied_payload["manually_overwritten_files"] == []
    assert (dataset / "a.txt").read_text(encoding="utf-8") == "miku_token, solo"
    assert (dataset / "b.txt").read_text(encoding="utf-8") == "solo, bad anatomy"

    (dataset / "a.txt").write_text("manual follow-up", encoding="utf-8")
    skipped_rollback = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "rollback",
            "backup_id": applied_payload["backup_id"],
        },
    )
    assert skipped_rollback.status_code == 200
    assert skipped_rollback.json()["restored_files"] == []
    assert skipped_rollback.json()["skipped_files"] == ["character/miku/a.txt"]
    assert (dataset / "a.txt").read_text(encoding="utf-8") == "manual follow-up"

    restored = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "rollback",
            "backup_id": applied_payload["backup_id"],
            "approved_manual_overwrite_paths": ["character/miku/a.txt"],
        },
    )
    assert restored.status_code == 200
    restored_payload = restored.json()
    assert restored_payload["restored_files"] == ["character/miku/a.txt"]
    assert restored_payload["manually_overwritten_files"] == ["character/miku/a.txt"]
    assert restored_payload["dataset_hash_after"]
    assert (dataset / "a.txt").read_text(encoding="utf-8") == "Miku Token!, solo, lowres"


def test_curation_api_reports_explicit_manual_overwrite_per_file(tmp_path: Path, monkeypatch) -> None:
    """Manual caption overwrite approval is accepted only for listed caption paths and reported per file."""
    base = tmp_path / "lora_train"
    dataset = _make_dataset(base)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: _settings(base))
    client = TestClient(app)

    plan = client.post(
        "/api/lora-train/datasets/curate",
        json={"folder": "character/miku", "mode": "dry_run"},
    ).json()
    applied = client.post(
        "/api/lora-train/datasets/curate",
        json={
            "folder": "character/miku",
            "mode": "apply",
            "expected_dataset_hash": plan["dataset_hash"],
            "expected_profile_hash": plan["profile_hash"],
            "approved_manual_overwrite_paths": ["character/miku/b.txt"],
        },
    )

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["changed_files"] == ["character/miku/a.txt", "character/miku/b.txt"]
    assert payload["skipped_files"] == []
    assert payload["manually_overwritten_files"] == ["character/miku/b.txt"]
    b_change = next(change for change in payload["changes"] if change["path"] == "character/miku/b.txt")
    assert b_change["manual"] is True
    assert b_change["manual_overwrite_approved"] is True
    assert (dataset / "b.txt").read_text(encoding="utf-8") == "miku_token, solo"
