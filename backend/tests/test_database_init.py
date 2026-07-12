"""Database initialization/migration tests."""
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db import database


def test_init_db_adds_artifact_table_without_changing_image_rows(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE generated_images (
                    id INTEGER PRIMARY KEY,
                    job_id VARCHAR(64),
                    image_path VARCHAR(512) NOT NULL,
                    checkpoint VARCHAR(256),
                    lora VARCHAR(256),
                    template VARCHAR(128),
                    diffusion_model VARCHAR(256),
                    text_encoder VARCHAR(256),
                    vae VARCHAR(256),
                    seed INTEGER,
                    steps INTEGER,
                    cfg FLOAT,
                    prompt TEXT,
                    negative_prompt TEXT,
                    workflow_json TEXT,
                    source_image VARCHAR(512),
                    source_mask VARCHAR(512),
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO generated_images (id, job_id, image_path, prompt)
                VALUES (1, 'job-legacy', '2026-06-22/legacy.png', 'legacy prompt')
                """
            )
        )

    monkeypatch.setattr(database, "engine", engine)

    database.init_db()
    database.init_db()

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "generated_artifacts" in tables
    assert "downloaded_resources" in tables
    assert "lora_training_jobs" in tables
    image_columns = {c["name"] for c in inspector.get_columns("generated_images")}
    assert {
        "recipe_json",
        "recipe_sha256",
        "recipe_workflow_json",
        "recipe_workflow_sha256",
        "recipe_input_hashes_json",
        "recipe_resource_locks_json",
        "recipe_runtime_provenance_json",
        "recipe_reproduction_level",
    }.issubset(image_columns)
    downloaded_columns = {c["name"] for c in inspector.get_columns("downloaded_resources")}
    assert {
        "resource_name",
        "resource_type",
        "source_url",
        "local_path",
        "storage_root",
        "sha256",
        "status",
        "downloaded_at",
    }.issubset(downloaded_columns)
    lora_job_columns = {c["name"] for c in inspector.get_columns("lora_training_jobs")}
    assert {
        "job_id",
        "folder",
        "status",
        "stage",
        "progress",
        "current_epoch",
        "total_epochs",
        "log_path",
        "output_path",
        "registered_lora_name",
        "error_code",
        "error_message",
        "dataset_hash",
        "params_json",
        "smoke_test_status",
        "smoke_test_job_id",
        "created_at",
        "started_at",
        "completed_at",
        "cancel_requested_at",
    }.issubset(lora_job_columns)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, job_id, image_path, prompt FROM generated_images")
        ).mappings().one()

    assert dict(row) == {
        "id": 1,
        "job_id": "job-legacy",
        "image_path": "2026-06-22/legacy.png",
        "prompt": "legacy prompt",
    }
