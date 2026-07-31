from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import queue as q
from app.db.database import Base
from app.db.models import GeneratedArtifact


def _database():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _artifact() -> dict:
    return {
        "filename": "raw.mp4", "subfolder": "video", "type": "output",
        "artifact_type": "video", "mime_type": "video/mp4",
        "source_node_id": "21", "source_node_type": "SaveVideo", "output_key": "video",
    }


def test_queue_film_success_persists_only_final_artifact_with_timing(tmp_path: Path, monkeypatch) -> None:
    sessions = _database()
    gallery = tmp_path / "gallery"
    settings = SimpleNamespace(
        gallery_dir=str(gallery), film_model_path=str(tmp_path / "film.pt"), film_work_dir=str(tmp_path / "work")
    )
    monkeypatch.setattr(q, "SessionLocal", sessions)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    comfy = MagicMock()
    comfy.fetch_image.return_value = b"raw video"
    job = q._Job(job_id="film-success", submitted_at="t", params={
        "prompt": "motion", "workflow_json": {"21": {"class_type": "SaveVideo"}},
        "film_postprocess": {"target_frames": 321, "total_seconds": 5.0},
    })

    def interpolate(**kwargs):
        assert kwargs["input_path"].read_bytes() == b"raw video"
        kwargs["output_path"].write_bytes(b"final film")
        return {
            "fps": 64.0,
            "frame_count": 321,
            "timeline_span_seconds": 5.0,
            "container_duration_seconds": 5.015625,
            "width": 480,
            "height": 720,
            "timeline_contract": "first_to_last_span",
        }

    with patch("app.services.film_postprocess.interpolate_video_exact", side_effect=interpolate):
        assert q._save_job_outputs(comfy, job, [_artifact()]) == 1

    with sessions() as db:
        artifact = db.query(GeneratedArtifact).one()
        metadata = json.loads(artifact.metadata_json)
    final = gallery / artifact.gallery_path
    assert final.name.endswith("_film.mp4")
    assert final.read_bytes() == b"final film"
    assert artifact.source_node_type == "SaveVideo"
    assert (artifact.fps, artifact.frame_count, artifact.duration) == (64.0, 321, 5.015625)
    assert metadata["output_key"] == "film_postprocessed"
    assert metadata["timeline_contract"] == "first_to_last_span"
    assert metadata["timeline_span_seconds"] == 5.0
    assert metadata["container_duration_seconds"] == 5.015625
    assert "duration" not in metadata
    assert not any(path.name.endswith("_0.mp4") for path in final.parent.iterdir())


def test_queue_film_failure_reports_terminal_failure_and_leaves_no_artifact(tmp_path: Path, monkeypatch) -> None:
    sessions = _database()
    staging = tmp_path / "staging"
    staging.mkdir()
    staged = staging / "input.png"
    staged.write_bytes(b"input")
    settings = SimpleNamespace(
        gallery_dir=str(tmp_path / "gallery"), film_model_path=str(tmp_path / "film.pt"),
        film_work_dir=str(tmp_path / "work"), video_staging_dir=str(staging),
        comfyui_input_dir=str(tmp_path / "comfy-input"),
    )
    monkeypatch.setattr(q, "SessionLocal", sessions)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    job = q._Job(job_id="film-failure", submitted_at="t", params={
        "workflow_json": {"21": {"class_type": "SaveVideo"}},
        "film_postprocess": {"target_frames": 321, "total_seconds": 5.0},
        "staged_input_paths": [str(staged)],
    })
    job.prompt_id = "pid"
    q._running = job
    comfy = MagicMock()
    comfy.get_queue.return_value = {"queue_running": [], "queue_pending": []}
    comfy.get_history.return_value = {"pid": {"status": {"status_str": "success"}, "outputs": {
        "21": {"video": [{"filename": "raw.mp4", "subfolder": "video", "type": "output"}]}
    }}}
    comfy.fetch_image.return_value = b"raw video"

    with patch("app.services.film_postprocess.interpolate_video_exact", side_effect=RuntimeError("FILM crashed")):
        q._check_running_complete(comfy)

    status = q.get_job_status("film-failure")
    assert status["status"] == "failed"
    assert "FILM crashed" in status["error"]
    assert status["recording_error"]["code"] == "recording_failed"
    assert not staged.exists()
    with sessions() as db:
        assert db.query(GeneratedArtifact).count() == 0
    assert not list((tmp_path / "gallery").rglob("*.mp4"))
