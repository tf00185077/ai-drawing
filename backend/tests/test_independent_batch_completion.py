from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import queue as q
from app.core.comfyui import ComfyUIError
from app.core.generation_batches import get_batch_status
from app.db.database import Base
from app.db.models import GeneratedArtifact, GeneratedImage


class _BatchComfy:
    def __init__(self, failed_prompt_numbers: set[int] | None = None) -> None:
        self.failed_prompt_numbers = failed_prompt_numbers or set()
        self.submitted: list[dict] = []

    def submit_prompt(self, prompt):
        self.submitted.append(prompt)
        return f"prompt-{len(self.submitted)}"

    def get_queue(self):
        return {"queue_running": [], "queue_pending": []}

    def get_history(self, prompt_id):
        prompt_number = int(prompt_id.rsplit("-", 1)[-1])
        if prompt_number in self.failed_prompt_numbers:
            return {
                prompt_id: {
                    "status": {
                        "status_str": "error",
                        "messages": [
                            [
                                "execution_error",
                                {
                                    "node_id": "3",
                                    "node_type": "KSampler",
                                    "exception_message": "ComfyUI execution error",
                                },
                            ]
                        ],
                    },
                    "outputs": {},
                }
            }
        return {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "same-output.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

    def fetch_image(self, *args, **kwargs):
        return b"image"


def _factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )


def _settings(tmp_path):
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "model.safetensors").write_text("", encoding="utf-8")
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(checkpoint_dir),
        lora_default_checkpoint="",
        lora_sdxl=False,
        gallery_dir=str(tmp_path / "gallery"),
        controlnet_default_pose_image="",
    )


def _run_one(comfy) -> None:
    q._process_pending(comfy)
    q._check_running_complete(comfy)


def test_child_two_failure_does_not_cancel_later_siblings_and_parent_is_mixed(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    monkeypatch.setattr(q, "get_settings", lambda: _settings_value)
    q._reset_for_test()
    _settings_value = _settings(tmp_path)
    comfy = _BatchComfy(failed_prompt_numbers={2})
    parent_id = q.submit(
        {
            "prompt": "four variants",
            "batch_size": 4,
            "batch_seed_mode": "independent",
        }
    )

    for expected_terminal_count in range(1, 5):
        _run_one(comfy)
        with factory() as db:
            status = get_batch_status(db, parent_id)
        assert (
            status["batch_completed"] + status["batch_failed"]
            == expected_terminal_count
        )

    assert len(comfy.submitted) == 4
    assert q._pending == []
    assert q._running is None
    with factory() as db:
        status = get_batch_status(db, parent_id)
        images = (
            db.query(GeneratedImage)
            .filter(GeneratedImage.job_id == parent_id)
            .order_by(GeneratedImage.id.asc())
            .all()
        )
        artifacts = (
            db.query(GeneratedArtifact)
            .filter(GeneratedArtifact.job_id == parent_id)
            .order_by(GeneratedArtifact.id.asc())
            .all()
        )

    assert status["status"] == "completed"
    assert status["batch_completed"] == 3
    assert status["batch_failed"] == 1
    assert status["failed_members"][0]["batch_index"] == 1
    assert len(images) == 3
    assert len(artifacts) == 3
    assert len({image.seed for image in images}) == 3
    engine.dispose()


def test_all_failed_children_make_parent_failed_without_images(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = _BatchComfy(failed_prompt_numbers={1, 2})
    parent_id = q.submit(
        {
            "prompt": "all fail",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    _run_one(comfy)
    _run_one(comfy)

    with factory() as db:
        status = get_batch_status(db, parent_id)
        assert (
            db.query(GeneratedArtifact)
            .filter(GeneratedArtifact.job_id == parent_id)
            .count()
            == 0
        )
    assert status["status"] == "failed"
    assert status["batch_completed"] == 0
    assert status["batch_failed"] == 2
    engine.dispose()


def test_malformed_submit_response_releases_slot_and_later_sibling_starts(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = [None, "prompt-2"]
    parent_id = q.submit(
        {
            "prompt": "malformed first submit",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        first_status = get_batch_status(db, parent_id)
    assert first_status["batch_failed"] == 1

    q._process_pending(comfy)
    assert q._running is not None
    assert q._running.batch_index == 1
    engine.dispose()


def test_recording_failure_is_sanitized_releases_slot_and_sibling_succeeds(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = _BatchComfy()
    parent_id = q.submit(
        {
            "prompt": "record first child failure",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    with patch(
        "app.core.queue._save_job_outputs",
        side_effect=[RuntimeError("Bearer TOP-SECRET"), 1],
    ):
        _run_one(comfy)
        assert q._running is None
        assert len(q._pending) == 1
        _run_one(comfy)

    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["status"] == "completed"
    assert status["batch_completed"] == 1
    assert status["batch_failed"] == 1
    assert "TOP-SECRET" not in status["failed_members"][0]["message"]
    engine.dispose()


def test_malformed_comfy_node_errors_do_not_leak_slot_or_cancel_sibling(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = [
        ComfyUIError("invalid prompt", node_errors=object()),
        "prompt-2",
    ]
    parent_id = q.submit(
        {
            "prompt": "malformed node errors",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    with patch(
        "app.core.queue.structure_node_errors",
        side_effect=ValueError("malformed node errors"),
    ):
        q._process_pending(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_failed"] == 1

    q._process_pending(comfy)
    assert q._running is not None
    assert q._running.batch_index == 1
    engine.dispose()


def test_malformed_execution_error_is_terminal_and_sibling_continues(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = _BatchComfy(failed_prompt_numbers={1})
    parent_id = q.submit(
        {
            "prompt": "malformed execution error",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    with patch(
        "app.core.queue.structure_execution_error",
        side_effect=ValueError("malformed history status"),
    ):
        q._check_running_complete(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_failed"] == 1

    _run_one(comfy)
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["status"] == "completed"
    assert status["batch_completed"] == 1
    engine.dispose()


def test_persistent_malformed_history_releases_slot_and_sibling_continues(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ["prompt-1", "prompt-2"]
    comfy.get_queue.return_value = {
        "queue_running": [],
        "queue_pending": [],
    }
    comfy.get_history.side_effect = [list() for _ in range(q.MAX_COMPLETION_POLLS)] + [
        {
            "prompt-2": {
                "status": {"status_str": "success"},
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "second.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        },
    ]
    comfy.fetch_image.return_value = b"image"
    parent_id = q.submit(
        {
            "prompt": "malformed history",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    for _ in range(q.MAX_COMPLETION_POLLS - 1):
        q._check_running_complete(comfy)
        assert q._running is not None
        assert q._running.batch_index == 0

    q._check_running_complete(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_failed"] == 1

    _run_one(comfy)
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["status"] == "completed"
    assert status["batch_completed"] == 1
    engine.dispose()


def test_transient_malformed_queue_keeps_running_slot_and_sibling_waits(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ["prompt-1", "prompt-2"]
    comfy.get_queue.side_effect = [
        None,
        {
            "queue_running": [[1, "prompt-1"]],
            "queue_pending": [],
        },
    ]
    comfy.get_history.return_value = {}
    parent_id = q.submit(
        {
            "prompt": "transient malformed queue response",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    q._check_running_complete(comfy)

    assert q._running is not None
    assert q._running.batch_index == 0
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_completed"] == 0
    assert status["batch_failed"] == 0

    q._process_pending(comfy)
    assert q._running is not None
    assert q._running.batch_index == 0
    assert comfy.submit_prompt.call_count == 1

    q._check_running_complete(comfy)

    assert q._running is not None
    assert q._running.batch_index == 0
    assert comfy.get_history.call_count == 1
    engine.dispose()


def test_malformed_queue_uses_terminal_history_and_completes_member(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ["prompt-1", "prompt-2"]
    comfy.get_queue.return_value = None
    comfy.get_history.return_value = {
        "prompt-1": {
            "status": {"status_str": "success"},
            "outputs": {
                "9": {
                    "images": [
                        {
                            "filename": "first.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ]
                }
            },
        }
    }
    comfy.fetch_image.return_value = b"image"
    parent_id = q.submit(
        {
            "prompt": "terminal history fallback",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    q._check_running_complete(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_completed"] == 1
    assert status["batch_failed"] == 0

    q._process_pending(comfy)
    assert q._running is not None
    assert q._running.batch_index == 1
    engine.dispose()


def test_persistent_malformed_queue_and_history_eventually_releases_slot(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = ["prompt-1", "prompt-2"]
    comfy.get_queue.return_value = None
    comfy.get_history.return_value = []
    parent_id = q.submit(
        {
            "prompt": "persistent malformed ComfyUI status",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    for _ in range(q.MAX_COMPLETION_POLLS - 1):
        q._check_running_complete(comfy)
        assert q._running is not None
        assert q._running.batch_index == 0
        with factory() as db:
            status = get_batch_status(db, parent_id)
        assert status["batch_completed"] == 0
        assert status["batch_failed"] == 0

    q._check_running_complete(comfy)

    assert q._running is None
    assert len(q._pending) == 1
    with factory() as db:
        status = get_batch_status(db, parent_id)
    assert status["batch_completed"] == 0
    assert status["batch_failed"] == 1
    assert status["failed_members"][0]["code"] == "malformed_queue_response"

    q._process_pending(comfy)
    assert q._running is not None
    assert q._running.batch_index == 1
    engine.dispose()


class _PreviewThenSaveComfy(_BatchComfy):
    def get_history(self, prompt_id):
        prompt_number = int(prompt_id.rsplit("-", 1)[-1])
        node_id = "13" if prompt_number == 1 else "9"
        filename = "preview.png" if prompt_number == 1 else "saved.png"
        return {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    node_id: {
                        "images": [
                            {
                                "filename": filename,
                                "subfolder": "",
                                "type": "temp" if prompt_number == 1 else "output",
                            }
                        ]
                    }
                },
            }
        }


def test_preview_only_member_fails_without_delivery_and_saveimage_sibling_succeeds(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = _PreviewThenSaveComfy()
    parent_id = q.submit(
        {
            "prompt": "preview is not a durable result",
            "template": "anima",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    _run_one(comfy)
    assert q._running is None
    assert len(q._pending) == 1
    _run_one(comfy)

    with factory() as db:
        status = get_batch_status(db, parent_id)
        artifacts = (
            db.query(GeneratedArtifact)
            .filter(GeneratedArtifact.job_id == parent_id)
            .all()
        )
    assert status["status"] == "completed"
    assert status["batch_completed"] == 1
    assert status["batch_failed"] == 1
    assert status["failed_members"][0]["code"] == "no_saveimage_artifact"
    assert [artifact.source_node_type for artifact in artifacts] == ["SaveImage"]
    engine.dispose()


def test_all_failed_parent_exposes_only_durable_aggregate_failures(
    tmp_path, monkeypatch
) -> None:
    engine, factory = _factory()
    monkeypatch.setattr(q, "SessionLocal", factory)
    settings = _settings(tmp_path)
    monkeypatch.setattr(q, "get_settings", lambda: settings)
    q._reset_for_test()
    comfy = MagicMock()
    comfy.submit_prompt.side_effect = [
        ComfyUIError(
            "first member failed",
            node_errors={
                "3": {
                    "class_type": "KSampler",
                    "message": "raw node error one",
                }
            },
        ),
        ComfyUIError(
            "second member " + ("failed " * 200),
            node_errors={
                "3": {
                    "class_type": "KSampler",
                    "message": "raw node error two",
                }
            },
        ),
    ]
    parent_id = q.submit(
        {
            "prompt": "all failures remain aggregate",
            "batch_size": 2,
            "batch_seed_mode": "independent",
        }
    )

    q._process_pending(comfy)
    q._process_pending(comfy)

    public_status = q.get_job_status(parent_id)
    assert public_status is not None
    assert public_status["status"] == "failed"
    assert public_status["error"] == "all independent batch members failed"
    assert public_status.get("node_errors", []) == []
    assert public_status["batch_total"] == 2
    assert public_status["batch_completed"] == 0
    assert public_status["batch_failed"] == 2
    assert len(public_status["failed_members"]) == 2
    assert [item["batch_index"] for item in public_status["failed_members"]] == [
        0,
        1,
    ]
    assert all(
        len(item["message"]) <= 500
        for item in public_status["failed_members"]
    )
    engine.dispose()
