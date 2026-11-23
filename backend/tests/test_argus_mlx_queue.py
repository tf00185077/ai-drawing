from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import queue as q
from app.db.database import Base
from app.db.models import GeneratedArtifact
from app.services.argus_mlx_i2v import ArgusMlxI2VError, ArgusMlxI2VResult


def _database():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _settings(tmp_path: Path) -> SimpleNamespace:
    staging = tmp_path / "staging"
    work = tmp_path / "argus-work"
    gallery = tmp_path / "gallery"
    comfy_input = tmp_path / "comfy-input"
    for path in (staging, work, gallery, comfy_input):
        path.mkdir()
    return SimpleNamespace(
        video_staging_dir=str(staging),
        comfyui_input_dir=str(comfy_input),
        argus_mlx_work_root=str(work),
        gallery_dir=str(gallery),
        argus_mlx_runtime_root="minimax-h3-mac-pr4",
        argus_mlx_checkpoint="MiniMax-H3",
        argus_mlx_transformer="MiniMax-H3-MLX-Argus-Calibrated-INT8",
        argus_mlx_turbo_lora="MiniMax-H3-Turbo-v4-step600-EMA-MLX",
    )


def _queued_job(tmp_path: Path, settings: SimpleNamespace, *, job_id: str) -> q._Job:
    staged = Path(settings.video_staging_dir) / f"{job_id}.png"
    staged.write_bytes(b"input")
    job = q._Job(
        job_id=job_id,
        submitted_at="2026-09-01T00:00:00Z",
        params={
            "execution_engine": "argus_mlx_i2v",
            "prompt": "small natural wave",
            "staged_input_paths": [str(staged)],
            "argus_mlx_i2v": {
                "staged_image": str(staged),
                "width": 256,
                "height": 256,
                "total_seconds": 1,
                "native_frames": 39,
            },
        },
    )
    q._pending.append(job)
    return job


def test_argus_queue_success_never_calls_comfy_records_video_and_cleans_work(
    tmp_path: Path, monkeypatch
) -> None:
    sessions = _database()
    settings = _settings(tmp_path)
    q._reset_for_test()
    monkeypatch.setattr(q, "SessionLocal", sessions)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    job = _queued_job(tmp_path, settings, job_id="argus-success")
    work_dir = Path(settings.argus_mlx_work_root) / job.job_id
    work_dir.mkdir()
    output = work_dir / "output.mp4"
    output.write_bytes(b"verified mp4")
    profile = work_dir / "forward-profile.json"
    profile.write_text("{}")
    runner = MagicMock()
    runner.run.return_value = ArgusMlxI2VResult(
        output, profile, "safe log", 24.0, 39, 1.625, 256, 256
    )
    monkeypatch.setattr(q, "get_argus_mlx_i2v_runner", lambda: runner)
    comfy = MagicMock()

    q._process_pending(comfy)

    comfy.assert_not_called()
    assert q.get_job_status(job.job_id) is None
    assert not Path(job.params["staged_input_paths"][0]).exists()
    assert not work_dir.exists()
    with sessions() as db:
        artifact = db.query(GeneratedArtifact).one()
        metadata = json.loads(artifact.metadata_json)
    assert artifact.source_node_type == "SaveVideo"
    assert artifact.mime_type == "video/mp4"
    assert (artifact.fps, artifact.frame_count, artifact.duration) == (24.0, 39, 1.625)
    assert metadata["execution_engine"] == "argus_mlx_i2v"
    assert metadata["requested_seconds"] == 1
    assert metadata["native_frames"] == 39
    assert metadata["seed"] == job.params["seed"]
    assert (Path(settings.gallery_dir) / artifact.gallery_path).read_bytes() == b"verified mp4"


def test_argus_queue_failure_is_terminal_without_fallback_or_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    sessions = _database()
    settings = _settings(tmp_path)
    q._reset_for_test()
    monkeypatch.setattr(q, "SessionLocal", sessions)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    job = _queued_job(tmp_path, settings, job_id="argus-failure")
    runner = MagicMock()
    runner.run.side_effect = ArgusMlxI2VError(
        "runtime_missing", "required setting argus_mlx_runtime_root is unavailable"
    )
    monkeypatch.setattr(q, "get_argus_mlx_i2v_runner", lambda: runner)
    comfy = MagicMock()

    q._process_pending(comfy)

    comfy.assert_not_called()
    status = q.get_job_status(job.job_id)
    assert status["status"] == "failed"
    assert status["failure_code"] == "runtime_missing"
    assert "argus_mlx_runtime_root" in status["error"]
    assert not Path(job.params["staged_input_paths"][0]).exists()
    with sessions() as db:
        assert db.query(GeneratedArtifact).count() == 0


def test_argus_queue_cancel_removes_staged_upload(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    job = _queued_job(tmp_path, settings, job_id="argus-cancel")
    staged = Path(job.params["staged_input_paths"][0])

    assert q.cancel(job.job_id) is True
    assert not staged.exists()
    assert q.get_job_status(job.job_id) is None


def test_unknown_execution_engine_fails_closed_without_comfy(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    q._reset_for_test()
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    job = q._Job(
        job_id="unknown-engine",
        submitted_at="2026-09-01T00:00:00Z",
        params={"execution_engine": "unknown"},
    )
    q._pending.append(job)
    comfy = MagicMock()

    q._process_pending(comfy)

    comfy.assert_not_called()
    status = q.get_job_status(job.job_id)
    assert status["status"] == "failed"
    assert status["failure_code"] == "unknown_execution_engine"


def test_stop_worker_does_not_construct_unused_argus_runner(monkeypatch) -> None:
    q._stop_event.clear()
    monkeypatch.setattr(q, "_worker_thread", None)
    monkeypatch.setattr(q, "_argus_runner", None)
    constructor = MagicMock(side_effect=AssertionError("must not construct runner"))
    monkeypatch.setattr(q, "get_argus_mlx_i2v_runner", constructor)

    q.stop_worker()

    constructor.assert_not_called()
