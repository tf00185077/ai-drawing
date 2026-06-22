"""harden-queue-completion：終局狀態處理（不再靜默消失）"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import queue as q
from app.db.database import Base
from app.db.models import GeneratedArtifact, GeneratedImage


def _set_running(prompt_id: str = "pid", **params) -> "q._Job":
    q._reset_for_test()
    job = q._Job(job_id="j1", params=dict(params), submitted_at="t")
    job.prompt_id = prompt_id
    q._running = job
    return job


def _queue(running=(), pending=()):
    fake = MagicMock()
    fake.get_queue.return_value = {
        "queue_running": [[0, p] for p in running],
        "queue_pending": [[0, p] for p in pending],
    }
    return fake


def _hist_success_with_image():
    return {"pid": {"status": {"status_str": "success"},
                    "outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}}}


def test_pending_in_comfy_stays_running() -> None:
    job = _set_running()
    fake = _queue(pending=["pid"])  # 仍在 ComfyUI 排隊
    q._check_running_complete(fake)
    assert q._running is job
    assert q.get_job_status("j1")["status"] == "running"


def test_history_lag_keeps_running_then_resolves() -> None:
    _set_running()
    fake = _queue()  # 已離開佇列
    fake.get_history.return_value = {}  # history 尚未出現
    q._check_running_complete(fake)
    assert q._running is not None  # 不丟，繼續等
    assert q._running.completion_polls == 1

    # 下一個 tick：history 出現且成功
    fake.get_history.return_value = _hist_success_with_image()
    with patch("app.core.queue._save_job_outputs", return_value=1) as m_save:
        q._check_running_complete(fake)
    m_save.assert_called_once()
    assert q._running is None
    assert "j1" not in q._failed  # 成功，非 failed


def test_history_timeout_marks_failed_and_releases() -> None:
    _set_running()
    fake = _queue()
    fake.get_history.return_value = {}
    for _ in range(q.MAX_COMPLETION_POLLS):
        q._check_running_complete(fake)
    assert q._running is None
    st = q.get_job_status("j1")
    assert st["status"] == "failed"
    assert "no result" in st["error"].lower()


def test_execution_error_marks_failed_with_structured_reason() -> None:
    _set_running()
    fake = _queue()
    fake.get_history.return_value = {
        "pid": {
            "status": {
                "status_str": "error",
                "messages": [["execution_error", {
                    "node_id": "6", "node_type": "CLIPTextEncode",
                    "exception_message": "clip input is invalid: None",
                }]],
            },
            "outputs": {},
        }
    }
    q._check_running_complete(fake)
    assert q._running is None
    st = q.get_job_status("j1")
    assert st["status"] == "failed"
    assert st["node_errors"] == [
        {"node_id": "6", "class_type": "CLIPTextEncode", "reason": "clip input is invalid: None"}
    ]


def test_success_no_outputs_marks_failed() -> None:
    _set_running()
    fake = _queue()
    fake.get_history.return_value = {"pid": {"status": {"status_str": "success"}, "outputs": {}}}
    q._check_running_complete(fake)
    assert q._running is None
    assert q.get_job_status("j1")["status"] == "failed"


def test_recording_failure_marks_failed_not_dropped() -> None:
    _set_running()
    fake = _queue()
    fake.get_history.return_value = _hist_success_with_image()
    with patch("app.core.queue._save_job_outputs", side_effect=RuntimeError("disk full")):
        q._check_running_complete(fake)
    assert q._running is None
    st = q.get_job_status("j1")
    assert st["status"] == "failed"
    assert "disk full" in st["error"]


def test_save_job_outputs_copies_video_artifact_to_gallery(tmp_path, monkeypatch) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    gallery_dir = tmp_path / "gallery"

    monkeypatch.setattr(q, "SessionLocal", session_factory)
    monkeypatch.setattr(q, "get_settings", lambda: SimpleNamespace(gallery_dir=str(gallery_dir)))

    fake = MagicMock()
    fake.fetch_image.return_value = b"video bytes"
    job = q._Job(
        job_id="abcdef123456",
        params={
            "prompt": "slow pan",
            "negative_prompt": "blur",
            "workflow_json": {"9": {"class_type": "VHS_VideoCombine"}},
        },
        submitted_at="t",
    )

    count = q._save_job_outputs(
        fake,
        job,
        [
            {
                "filename": "video render.mp4",
                "subfolder": "clips",
                "type": "output",
                "artifact_type": "video",
                "mime_type": "video/mp4",
                "source_node_id": "9",
                "source_node_type": "VHS_VideoCombine",
                "output_key": "gifs",
            }
        ],
    )

    assert count == 1
    fake.fetch_image.assert_called_once_with(
        "video render.mp4",
        subfolder="clips",
        ftype="output",
    )

    with session_factory() as db:
        artifact = db.query(GeneratedArtifact).one()
        assert db.query(GeneratedImage).count() == 0

    assert artifact.artifact_type == "video"
    assert artifact.mime_type == "video/mp4"
    assert artifact.job_id == "abcdef123456"
    assert artifact.gallery_path.endswith("/video_render_abcdef12_0.mp4")
    assert artifact.source_node_id == "9"
    assert artifact.source_node_type == "VHS_VideoCombine"
    assert artifact.file_size == len(b"video bytes")
    assert artifact.prompt == "slow pan"
    assert artifact.negative_prompt == "blur"
    assert artifact.metadata_json == '{"output_key": "gifs"}'
    assert (gallery_dir / artifact.gallery_path).read_bytes() == b"video bytes"
