from __future__ import annotations

import importlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models
from app.db.database import Base


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _batch_service():
    return importlib.import_module("app.core.generation_batches")


def test_generation_batch_models_persist_parent_members_and_unique_seeds() -> None:
    assert hasattr(models, "GenerationBatch")
    assert hasattr(models, "GenerationBatchMember")
    batches = _batch_service()
    factory = _session_factory()

    with factory() as db:
        batches.create_batch(
            db,
            public_job_id="parent-1",
            execution_ids=("child-a", "child-b", "child-c", "child-d"),
            seeds=(11, 22, 33, 44),
            submitted_at="2026-07-25T01:02:03Z",
        )

    with factory() as db:
        parent = db.query(models.GenerationBatch).one()
        members = (
            db.query(models.GenerationBatchMember)
            .order_by(models.GenerationBatchMember.batch_index.asc())
            .all()
        )

    assert parent.public_job_id == "parent-1"
    assert parent.status == "queued"
    assert parent.batch_total == 4
    assert parent.batch_completed == 0
    assert parent.batch_failed == 0
    assert [member.execution_id for member in members] == [
        "child-a",
        "child-b",
        "child-c",
        "child-d",
    ]
    assert [member.seed for member in members] == [11, 22, 33, 44]
    assert [member.batch_index for member in members] == [0, 1, 2, 3]


def test_failed_member_persists_only_bounded_sanitized_failure() -> None:
    batches = _batch_service()
    factory = _session_factory()
    with factory() as db:
        batches.create_batch(
            db,
            public_job_id="parent-secret",
            execution_ids=("child-a",),
            seeds=(99,),
            submitted_at="2026-07-25T01:02:03Z",
        )
        status = batches.mark_member_terminal(
            db,
            public_job_id="parent-secret",
            batch_index=0,
            succeeded=False,
            failure_code="comfyui execution/error",
            failure_message=(
                "Bearer SUPER-SECRET api_key=ALSO-SECRET "
                + ("detail " * 200)
            ),
        )

    assert status["status"] == "failed"
    assert status["batch_completed"] == 0
    assert status["batch_failed"] == 1
    failed = status["failed_members"][0]
    assert failed["code"] == "comfyui_execution_error"
    assert "SUPER-SECRET" not in failed["message"]
    assert "ALSO-SECRET" not in failed["message"]
    assert "[REDACTED]" in failed["message"]
    assert len(failed["message"]) <= 500


def test_persisted_mixed_outcome_survives_fresh_session() -> None:
    batches = _batch_service()
    factory = _session_factory()
    with factory() as db:
        batches.create_batch(
            db,
            public_job_id="parent-mixed",
            execution_ids=("a", "b", "c", "d"),
            seeds=(1, 2, 3, 4),
            submitted_at="2026-07-25T01:02:03Z",
        )
        for batch_index in range(3):
            batches.mark_member_terminal(
                db,
                public_job_id="parent-mixed",
                batch_index=batch_index,
                succeeded=True,
            )
        batches.mark_member_terminal(
            db,
            public_job_id="parent-mixed",
            batch_index=3,
            succeeded=False,
            failure_code="comfyui_execution_error",
            failure_message="node failed",
        )

    with factory() as fresh_db:
        status = batches.get_batch_status(fresh_db, "parent-mixed")

    assert status["status"] == "completed"
    assert status["batch_total"] == 4
    assert status["batch_completed"] == 3
    assert status["batch_failed"] == 1
    assert status["failed_members"] == [
        {
            "batch_index": 3,
            "seed": 4,
            "code": "comfyui_execution_error",
            "message": "node failed",
        }
    ]


def test_restart_reconciliation_preserves_success_and_fails_unfinished_members() -> None:
    batches = _batch_service()
    factory = _session_factory()
    with factory() as db:
        batches.create_batch(
            db,
            public_job_id="parent-restart",
            execution_ids=("a", "b", "c", "d"),
            seeds=(10, 20, 30, 40),
            submitted_at="2026-07-25T01:02:03Z",
        )
        batches.mark_member_terminal(
            db,
            public_job_id="parent-restart",
            batch_index=0,
            succeeded=True,
        )
        batches.mark_member_running(
            db,
            public_job_id="parent-restart",
            batch_index=1,
        )

    assert batches.reconcile_interrupted_batches(factory) == 1

    with factory() as fresh_db:
        status = batches.get_batch_status(fresh_db, "parent-restart")

    assert status["status"] == "completed"
    assert status["batch_completed"] == 1
    assert status["batch_failed"] == 3
    assert [item["batch_index"] for item in status["failed_members"]] == [1, 2, 3]
    assert {item["code"] for item in status["failed_members"]} == {
        "backend_restarted"
    }


def test_queue_worker_reconciles_persisted_batches_before_thread_start(
    monkeypatch,
) -> None:
    from app.core import queue as q

    events: list[str] = []

    class _FakeThread:
        def is_alive(self):
            return False

        def start(self):
            events.append("thread_started")

        def join(self, timeout=None):
            return None

    monkeypatch.setattr(
        q,
        "reconcile_interrupted_batches",
        lambda factory: events.append("reconciled"),
    )
    monkeypatch.setattr(
        q.threading,
        "Thread",
        lambda **kwargs: _FakeThread(),
    )
    monkeypatch.setattr(q, "_worker_thread", None)

    q.start_worker()

    assert events == ["reconciled", "thread_started"]
