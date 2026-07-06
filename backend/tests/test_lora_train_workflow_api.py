"""LoRA training workflow API tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import database
from app.db.models import LoraTrainingJob
from app.main import app
from app.services import lora_dataset, lora_dataset_assessment, lora_trainer


def _settings(tmp_path: Path, lora_train_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        lora_train_dir=str(lora_train_dir),
        lora_train_logs_dir=str(tmp_path / "logs"),
        comfyui_lora_dir=str(tmp_path / "comfyui_loras"),
        llm_caption_url=None,
        lora_train_threshold=2,
        lora_default_checkpoint="model.safetensors",
        lora_checkpoint_dirs="",
        lora_model_family="",
        lora_anima_qwen3="",
        lora_anima_vae="",
        lora_anima_t5_tokenizer_path="",
        lora_sdxl=False,
        lora_resolution=512,
        lora_batch_size=1,
        lora_learning_rate="1e-4",
        lora_class_tokens="miku_token",
        lora_keep_tokens=1,
        lora_num_repeats=10,
        lora_mixed_precision="fp16",
        lora_network_dim=16,
        lora_network_alpha=16,
        lora_save_every_n_epochs=None,
        sd_scripts_path=str(tmp_path / "sd-scripts"),
        sd_scripts_python="",
    )


def _make_dataset(base: Path) -> Path:
    dataset = base / "character" / "miku"
    dataset.mkdir(parents=True)
    (dataset / "a.png").write_bytes(b"a")
    (dataset / "a.txt").write_text("solo, blue hair", encoding="utf-8")
    (dataset / "b.jpg").write_bytes(b"b")
    (dataset / "b.txt").write_text("miku_token, smiling", encoding="utf-8")
    return dataset


def _client() -> TestClient:
    return TestClient(app)


def test_dataset_endpoints_list_inspect_prepare_restore_and_validate(tmp_path: Path, monkeypatch) -> None:
    """Dataset API endpoints expose list/inspect/prepare/restore/validate workflow."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)

    client = _client()
    listed = client.get("/api/lora-train/datasets")
    assert listed.status_code == 200
    assert listed.json()["datasets"][0]["folder"] == "character/miku"

    inspected = client.get("/api/lora-train/datasets/character/miku?trigger_token=miku_token")
    assert inspected.status_code == 200
    before_hash = inspected.json()["dataset_hash"]
    assert inspected.json()["validation"]["ok"] is False

    dry_run = client.post(
        "/api/lora-train/datasets/prepare",
        json={"folder": "character/miku", "trigger_token": "Miku Token", "dry_run": True},
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["backup_id"] is None
    assert dry_run.json()["dataset_hash_before"] == before_hash
    assert dry_run.json()["changed_count"] == 1
    assert dry_run.json()["unchanged_count"] == 1

    applied = client.post(
        "/api/lora-train/datasets/prepare",
        json={"folder": "character/miku", "trigger_token": "Miku Token", "dry_run": False},
    )
    assert applied.status_code == 200
    backup_id = applied.json()["backup_id"]
    assert backup_id
    prepared_hash = applied.json()["dataset_hash_after"]

    valid = client.post(
        "/api/lora-train/datasets/validate",
        json={
            "folder": "character/miku",
            "trigger_token": "miku_token",
            "expected_dataset_hash": prepared_hash,
        },
    )
    assert valid.status_code == 200
    assert valid.json()["ok"] is True

    monkeypatch.setattr(lora_dataset_assessment.lora_dataset, "get_settings", lambda: settings)
    assessed = client.post(
        "/api/lora-train/datasets/caption-assessment",
        json={"folder": "character/miku", "trigger_token": "miku_token"},
    )
    assert assessed.status_code == 200
    assessed_payload = assessed.json()
    assert assessed_payload["ok"] is True
    assert assessed_payload["folder"] == "character/miku"
    assert assessed_payload["image_count"] == 2
    assert assessed_payload["txt_count"] == 2
    assert assessed_payload["verdict"] in {"suitable", "needs_review"}
    assert assessed_payload["trigger_token_coverage"]["normalized_trigger_token"] == "miku_token"

    stale = client.post(
        "/api/lora-train/datasets/prepare",
        json={
            "folder": "character/miku",
            "trigger_token": "miku_token",
            "dry_run": False,
            "expected_dataset_hash": "old-hash",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "dataset_hash_mismatch"

    restored = client.post(
        "/api/lora-train/datasets/restore",
        json={"folder": "character/miku", "restore_backup_id": backup_id},
    )
    assert restored.status_code == 200
    assert restored.json()["restored_files"] == ["character/miku/a.txt", "character/miku/b.txt"]


def test_dataset_profile_fields_are_returned_without_starting_training(tmp_path: Path, monkeypatch) -> None:
    """List/inspect/validate expose profile metadata and never enqueue training."""
    lora_train_dir = tmp_path / "lora_train"
    dataset = _make_dataset(lora_train_dir)
    (dataset / ".lora-dataset.json").write_text(
        json.dumps(
            {
                "dataset_type": "character",
                "trigger_token": "miku_token",
                "caption_profile": "wd_tags",
                "model_family": "sd15",
                "auto_train": True,
            }
        ),
        encoding="utf-8",
    )
    settings = _settings(tmp_path, lora_train_dir)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)

    client = _client()
    with patch("app.api.lora_train.lora_trainer.enqueue") as enqueue:
        listed = client.get("/api/lora-train/datasets")
        inspected = client.get("/api/lora-train/datasets/character/miku?trigger_token=miku_token")
        validated = client.post(
            "/api/lora-train/datasets/validate",
            json={"folder": "character/miku", "trigger_token": "miku_token"},
        )

    assert listed.status_code == 200
    listed_profile = listed.json()["datasets"][0]["profile"]
    assert listed_profile["present"] is True
    assert listed_profile["dataset_type"] == "character"
    assert listed_profile["auto_train"] is True
    assert listed_profile["profile_hash"] == listed.json()["datasets"][0]["profile_hash"]

    assert inspected.status_code == 200
    inspected_payload = inspected.json()
    assert inspected_payload["image_count"] == 2
    assert inspected_payload["caption_count"] == 2
    assert inspected_payload["profile"]["trigger_token"] == "miku_token"
    assert inspected_payload["profile"]["warnings"][0]["code"] == "auto_train_descriptive_only"
    assert inspected_payload["profile_hash"] != inspected_payload["dataset_hash"]

    assert validated.status_code == 200
    assert validated.json()["folder"] == "character/miku"
    enqueue.assert_not_called()


def test_dataset_metadata_endpoints_validate_update_and_conflict(tmp_path: Path, monkeypatch) -> None:
    """Metadata endpoints validate proposed profiles, write explicitly, and reject stale hashes."""
    lora_train_dir = tmp_path / "lora_train"
    dataset = _make_dataset(lora_train_dir)
    profile_path = dataset / ".lora-dataset.json"
    settings = _settings(tmp_path, lora_train_dir)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)

    client = _client()
    missing = client.get("/api/lora-train/datasets/character/miku/metadata")
    assert missing.status_code == 200
    missing_payload = missing.json()
    assert missing_payload["ok"] is True
    assert missing_payload["valid"] is True
    assert missing_payload["profile_hash"] is None
    assert missing_payload["profile"]["present"] is False
    assert missing_payload["profile"]["trigger_token"] == "miku_token"

    invalid = client.post(
        "/api/lora-train/datasets/character/miku/metadata/validate",
        json={"profile": {"dataset_type": "vehicle", "protected_tags": "miku_token"}},
    )
    assert invalid.status_code == 200
    invalid_payload = invalid.json()
    assert invalid_payload["ok"] is True
    assert invalid_payload["valid"] is False
    assert {error["code"] for error in invalid_payload["errors"]} == {
        "unsupported_dataset_type",
        "invalid_profile_field",
    }
    assert not profile_path.exists()

    updated = client.put(
        "/api/lora-train/datasets/character/miku/metadata",
        json={
            "expected_profile_hash": None,
            "profile": {
                "dataset_type": "character",
                "trigger_token": "Miku Token!",
                "caption_profile": "wd_tags",
                "model_family": "sd15",
                "protected_tags": [" solo ", ""],
                "remove_tags": ["bad anatomy"],
                "auto_train": True,
            },
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["ok"] is True
    assert updated_payload["updated"] is True
    assert updated_payload["valid"] is True
    assert updated_payload["profile"]["trigger_token"] == "miku_token"
    assert updated_payload["profile"]["removable_tags"] == ["bad anatomy"]
    assert updated_payload["profile"]["warnings"][0]["code"] == "auto_train_descriptive_only"
    current_hash = updated_payload["profile_hash"]
    assert current_hash == hashlib.sha256(profile_path.read_bytes()).hexdigest()
    written_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert written_profile["dataset_type"] == "character"
    assert written_profile["removable_tags"] == ["bad anatomy"]

    before_bytes = profile_path.read_bytes()
    validate_after_update = client.post(
        "/api/lora-train/datasets/character/miku/metadata/validate",
        json={"profile": {"dataset_type": "style", "trigger_token": "style_token"}},
    )
    assert validate_after_update.status_code == 200
    assert validate_after_update.json()["valid"] is True
    assert profile_path.read_bytes() == before_bytes

    stale = client.put(
        "/api/lora-train/datasets/character/miku/metadata",
        json={"expected_profile_hash": "old-hash", "profile": {"dataset_type": "style"}},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "profile_hash_mismatch"
    assert stale.json()["detail"]["details"]["current_profile_hash"] == current_hash


def test_dataset_metadata_get_reports_malformed_profile_as_payload(tmp_path: Path, monkeypatch) -> None:
    """Malformed metadata is a structured profile state, not a backend transport failure."""
    lora_train_dir = tmp_path / "lora_train"
    dataset = _make_dataset(lora_train_dir)
    profile_path = dataset / ".lora-dataset.json"
    profile_path.write_text("{not json", encoding="utf-8")
    settings = _settings(tmp_path, lora_train_dir)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)

    client = _client()
    response = client.get("/api/lora-train/datasets/character/miku/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["valid"] is False
    assert payload["profile_hash"] == hashlib.sha256(profile_path.read_bytes()).hexdigest()
    assert payload["profile"]["present"] is True
    assert payload["errors"][0]["code"] == "invalid_profile_json"


def test_dataset_agent_inspect_composes_profile_caption_and_validation(tmp_path: Path, monkeypatch) -> None:
    """Agent inspection bundles profile, caption suitability, hashes, and validation without training."""
    lora_train_dir = tmp_path / "lora_train"
    dataset = _make_dataset(lora_train_dir)
    (dataset / ".lora-dataset.json").write_text(
        json.dumps({"dataset_type": "vehicle", "trigger_token": "miku_token"}),
        encoding="utf-8",
    )
    settings = _settings(tmp_path, lora_train_dir)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)

    client = _client()
    with patch("app.api.lora_train.lora_trainer.enqueue") as enqueue:
        response = client.get("/api/lora-train/datasets/character/miku/agent-inspect")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["folder"] == "character/miku"
    assert payload["dataset"]["image_count"] == 2
    assert payload["dataset_hash"]
    assert payload["profile_hash"]
    assert payload["profile"]["valid"] is False
    assert payload["profile_validation"]["errors"][0]["code"] == "unsupported_dataset_type"
    assert payload["caption_suitability"]["verdict"] in {"suitable", "needs_review", "not_suitable"}
    assert payload["caption_suitability"]["trigger_token_coverage"]["normalized_trigger_token"] == "miku_token"
    assert payload["validation"]["normalized_trigger_token"] == "miku_token"
    enqueue.assert_not_called()


def test_start_status_logs_cancel_and_aggregate_status(tmp_path: Path, monkeypatch) -> None:
    """Start creates durable queued job, logs are readable, cancel persists, aggregate status stays compatible."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    sd_scripts = Path(settings.sd_scripts_path)
    sd_scripts.mkdir()
    (sd_scripts / "train_network.py").write_text("# kohya train script\n", encoding="utf-8")
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    prepared = lora_dataset.prepare_dataset("character/miku", trigger_token="miku_token", dry_run=False)
    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "model.safetensors",
            "trigger_token": "miku_token",
            "expected_dataset_hash": prepared.dataset_hash_after,
            "epochs": 2,
            "mixed_precision": "fp32",
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    assert started.json()["status"] == "queued"

    status = client.get(f"/api/lora-train/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "queued"
    assert status.json()["dataset_hash"] == prepared.dataset_hash_after
    assert status.json()["params"]["model_family"] == "sd15"
    assert status.json()["params"]["trainer_script"] == "train_network.py"
    assert status.json()["params"]["mixed_precision"] == "fp32"
    assert status.json()["params"]["kohya_mixed_precision"] == "no"
    assert status.json()["params"]["network_module"] == "networks.lora"

    logs = client.get(f"/api/lora-train/jobs/{job_id}/logs?lines=10")
    assert logs.status_code == 200
    assert logs.json()["ok"] is True
    assert any("queued" in line for line in logs.json()["lines"])

    aggregate = client.get("/api/lora-train/status")
    assert aggregate.status_code == 200
    assert aggregate.json()["status"] == "queued"
    assert aggregate.json()["queue"][0]["job_id"] == job_id

    cancelled = client.post(f"/api/lora-train/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json() == {"ok": True, "job_id": job_id, "status": "cancelled"}

    terminal = client.get(f"/api/lora-train/jobs/{job_id}")
    assert terminal.status_code == 200
    assert terminal.json()["status"] == "cancelled"
    assert terminal.json()["cancel_requested_at"]
    lora_trainer._reset_for_test()


def test_start_rejects_missing_sd_scripts_before_persisting_job(tmp_path: Path, monkeypatch) -> None:
    """Missing sd-scripts is reported as structured API 400 before any job is queued."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    assert not Path(settings.sd_scripts_path).exists()
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    prepared = lora_dataset.prepare_dataset("character/miku", trigger_token="miku_token", dry_run=False)
    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "model.safetensors",
            "trigger_token": "miku_token",
            "expected_dataset_hash": prepared.dataset_hash_after,
            "epochs": 2,
        },
    )

    assert started.status_code == 400
    assert started.json()["detail"]["code"] == "sd_scripts_path_missing"
    assert started.json()["detail"]["details"]["sd_scripts_path"] == settings.sd_scripts_path
    db = session_local()
    try:
        assert db.query(LoraTrainingJob).count() == 0
    finally:
        db.close()
    assert lora_trainer.get_status()["status"] == "idle"


def test_start_anima_records_model_family_and_trainer_script(tmp_path: Path, monkeypatch) -> None:
    """Anima requests are queued with anima_train_network.py instead of SD1.x/SDXL scripts."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    sd_scripts = Path(settings.sd_scripts_path)
    sd_scripts.mkdir()
    (sd_scripts / "anima_train_network.py").write_text("# kohya anima train script\n", encoding="utf-8")
    qwen3 = tmp_path / "qwen_3_06b_base.safetensors"
    qwen3.write_bytes(b"qwen3")
    vae = tmp_path / "qwen_image_vae.safetensors"
    vae.write_bytes(b"vae")
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "anima_baseV10.safetensors",
            "model_family": "anima",
            "qwen3": str(qwen3),
            "vae": str(vae),
            "epochs": 1,
            "mixed_precision": "fp32",
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    status = client.get(f"/api/lora-train/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["params"]["model_family"] == "anima"
    assert status.json()["params"]["trainer_script"] == "anima_train_network.py"
    assert status.json()["params"]["network_module"] == "networks.lora_anima"
    assert status.json()["params"]["sdxl"] is False
    assert status.json()["params"]["kohya_mixed_precision"] == "no"
    assert status.json()["params"]["anima_qwen3"] == str(qwen3.resolve())
    assert status.json()["params"]["anima_vae"] == str(vae.resolve())
    assert status.json()["params"]["anima_t5_tokenizer_path"] is None
    lora_trainer._reset_for_test()


def test_start_network_module_override_is_persisted(tmp_path: Path, monkeypatch) -> None:
    """Explicit network_module overrides are preserved in durable job params."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    sd_scripts = Path(settings.sd_scripts_path)
    sd_scripts.mkdir()
    (sd_scripts / "anima_train_network.py").write_text("# kohya anima train script\n", encoding="utf-8")
    qwen3 = tmp_path / "qwen_3_06b_base.safetensors"
    qwen3.write_bytes(b"qwen3")
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "anima_baseV10.safetensors",
            "model_family": "anima",
            "network_module": "networks.custom_anima_lora",
            "qwen3": str(qwen3),
            "epochs": 1,
        },
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    status = client.get(f"/api/lora-train/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["params"]["model_family"] == "anima"
    assert status.json()["params"]["trainer_script"] == "anima_train_network.py"
    assert status.json()["params"]["network_module"] == "networks.custom_anima_lora"
    lora_trainer._reset_for_test()


def test_start_anima_rejects_missing_qwen3_before_persisting_job(tmp_path: Path, monkeypatch) -> None:
    """Anima requests require qwen3 before a durable training job is created."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    sd_scripts = Path(settings.sd_scripts_path)
    sd_scripts.mkdir()
    (sd_scripts / "anima_train_network.py").write_text("# kohya anima train script\n", encoding="utf-8")
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "anima_baseV10.safetensors",
            "model_family": "anima",
            "epochs": 1,
        },
    )

    assert started.status_code == 400
    assert started.json()["detail"]["code"] == "anima_qwen3_missing"
    db = session_local()
    try:
        assert db.query(LoraTrainingJob).count() == 0
    finally:
        db.close()
    assert lora_trainer.get_status()["status"] == "idle"


def test_start_rejects_unsupported_model_family_before_persisting_job(tmp_path: Path, monkeypatch) -> None:
    """Unsupported model families return structured API 400 and do not create jobs."""
    lora_train_dir = tmp_path / "lora_train"
    _make_dataset(lora_train_dir)
    settings = _settings(tmp_path, lora_train_dir)
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    lora_trainer._reset_for_test()

    client = _client()
    started = client.post(
        "/api/lora-train/start",
        json={
            "folder": "character/miku",
            "checkpoint": "model.safetensors",
            "model_family": "wan",
            "epochs": 1,
        },
    )

    assert started.status_code == 400
    assert started.json()["detail"]["code"] == "unsupported_model_family"
    assert started.json()["detail"]["details"]["accepted"] == ["anima", "sd15", "sdxl"]
    db = session_local()
    try:
        assert db.query(LoraTrainingJob).count() == 0
    finally:
        db.close()
    assert lora_trainer.get_status()["status"] == "idle"


def test_terminal_job_status_and_log_errors_are_durable(tmp_path: Path, monkeypatch) -> None:
    """Terminal job rows remain queryable even when the in-memory queue is empty."""
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    lora_trainer._reset_for_test()

    db = session_local()
    db.add(
        LoraTrainingJob(
            job_id="job-terminal",
            folder="character/miku",
            status="completed",
            stage="completed",
            progress=1.0,
            log_path=str(tmp_path / "missing.log"),
            output_path=str(tmp_path / "out.safetensors"),
            registered_lora_name="out.safetensors",
            dataset_hash="hash-a",
            normalized_trigger_token="miku_token",
            params_json='{"checkpoint": "model.safetensors"}',
        )
    )
    db.commit()
    db.close()

    client = _client()
    status = client.get("/api/lora-train/jobs/job-terminal")
    assert status.status_code == 200
    assert status.json()["registered_lora_name"] == "out.safetensors"

    logs = client.get("/api/lora-train/jobs/job-terminal/logs")
    assert logs.status_code == 200
    assert logs.json()["ok"] is False
    assert logs.json()["error_code"] == "log_not_found"

    missing = client.get("/api/lora-train/jobs/job-missing")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "job_not_found"


def test_register_output_lora_success_and_not_configured(tmp_path: Path, monkeypatch) -> None:
    """Registration copies safetensors atomically and reports missing config clearly."""
    source = tmp_path / "output" / "miku.safetensors"
    source.parent.mkdir()
    source.write_bytes(b"model")
    settings = _settings(tmp_path, tmp_path / "lora_train")
    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)

    name, target = lora_trainer._register_output_lora(source, "job-1")
    assert name == "miku.safetensors"
    assert Path(target).read_bytes() == b"model"

    settings.comfyui_lora_dir = ""
    try:
        lora_trainer._register_output_lora(source, "job-2")
    except lora_trainer.TrainerServiceError as exc:
        assert exc.code == "lora_registration_not_configured"
    else:
        raise AssertionError("expected TrainerServiceError")


def test_smoke_test_endpoint_success_and_precondition_failure(tmp_path: Path, monkeypatch) -> None:
    """Smoke-test endpoint submits generation for completed registered LoRA and rejects unmet preconditions."""
    engine = create_engine(f"sqlite:///{tmp_path / 'lora.db'}", connect_args={"check_same_thread": False})
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(lora_trainer, "submit_generation", lambda params: "gen-1")
    lora_trainer._reset_for_test()

    db = session_local()
    db.add(
        LoraTrainingJob(
            job_id="job-completed",
            folder="character/miku",
            status="completed",
            stage="completed",
            progress=1.0,
            registered_lora_name="miku.safetensors",
            normalized_trigger_token="miku_token",
            params_json='{"checkpoint": "model.safetensors"}',
        )
    )
    db.add(
        LoraTrainingJob(
            job_id="job-no-lora",
            folder="character/miku",
            status="completed",
            stage="completed",
            progress=1.0,
        )
    )
    db.commit()
    db.close()

    client = _client()
    smoke = client.post("/api/lora-train/jobs/job-completed/smoke-test", json={"prompt": "portrait"})
    assert smoke.status_code == 200
    assert smoke.json()["generation_job_id"] == "gen-1"
    assert smoke.json()["smoke_test_status"] == "submitted"

    status = client.get("/api/lora-train/jobs/job-completed")
    assert status.json()["smoke_test_job_id"] == "gen-1"

    precondition = client.post("/api/lora-train/jobs/job-no-lora/smoke-test")
    assert precondition.status_code == 400
    assert precondition.json()["detail"]["code"] == "smoke_test_precondition_failed"
