"""Durable parent/member accounting for independent generation batches."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models import GenerationBatch, GenerationBatchMember


TERMINAL_MEMBER_STATUSES = {"completed", "failed"}
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\b"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\b(bearer)\s+[^\s,;]+")
_FAILURE_CODE_CHARS = re.compile(r"[^a-z0-9_]+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def sanitize_failure_code(value: str | None) -> str:
    normalized = _FAILURE_CODE_CHARS.sub(
        "_", str(value or "member_failed").strip().lower()
    ).strip("_")
    return (normalized or "member_failed")[:64]


def sanitize_failure_message(value: object) -> str:
    message = str(value or "generation member failed")
    message = _BEARER_TOKEN.sub(r"\1 [REDACTED]", message)
    message = _SENSITIVE_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        message,
    )
    return message[:500]


def create_batch(
    db: Session,
    *,
    public_job_id: str,
    execution_ids: tuple[str, ...],
    seeds: tuple[int, ...],
    submitted_at: str | datetime,
) -> None:
    if not execution_ids or len(execution_ids) != len(seeds):
        raise ValueError("batch members require matching execution IDs and seeds")
    if len(set(execution_ids)) != len(execution_ids):
        raise ValueError("batch execution IDs must be unique")
    if len(set(seeds)) != len(seeds):
        raise ValueError("batch seeds must be unique")

    parent = GenerationBatch(
        public_job_id=public_job_id,
        batch_seed_mode="independent",
        status="queued",
        batch_total=len(seeds),
        batch_completed=0,
        batch_failed=0,
        submitted_at=_parse_timestamp(submitted_at),
    )
    db.add(parent)
    db.add_all(
        [
            GenerationBatchMember(
                public_job_id=public_job_id,
                execution_id=execution_id,
                batch_index=batch_index,
                seed=seed,
                status="queued",
            )
            for batch_index, (execution_id, seed) in enumerate(
                zip(execution_ids, seeds, strict=True)
            )
        ]
    )
    db.commit()


def _members(db: Session, public_job_id: str) -> list[GenerationBatchMember]:
    return (
        db.query(GenerationBatchMember)
        .filter(GenerationBatchMember.public_job_id == public_job_id)
        .order_by(GenerationBatchMember.batch_index.asc())
        .all()
    )


def _status_payload(
    parent: GenerationBatch,
    members: list[GenerationBatchMember],
) -> dict[str, Any]:
    failed_members = [
        {
            "batch_index": member.batch_index,
            "seed": member.seed,
            "code": member.failure_code or "member_failed",
            "message": member.failure_message or "generation member failed",
        }
        for member in members
        if member.status == "failed"
    ]
    return {
        "job_id": parent.public_job_id,
        "status": parent.status,
        "submitted_at": (
            parent.submitted_at.isoformat().replace("+00:00", "Z")
            if parent.submitted_at is not None
            else None
        ),
        "batch_total": parent.batch_total,
        "batch_completed": parent.batch_completed,
        "batch_failed": parent.batch_failed,
        "current_batch_index": parent.current_batch_index,
        "failed_members": failed_members,
    }


def get_batch_status(
    db: Session,
    public_job_id: str,
) -> dict[str, Any] | None:
    parent = (
        db.query(GenerationBatch)
        .filter(GenerationBatch.public_job_id == public_job_id)
        .one_or_none()
    )
    if parent is None:
        return None
    return _status_payload(parent, _members(db, public_job_id))


def mark_member_running(
    db: Session,
    *,
    public_job_id: str,
    batch_index: int,
) -> dict[str, Any]:
    parent = (
        db.query(GenerationBatch)
        .filter(GenerationBatch.public_job_id == public_job_id)
        .one()
    )
    member = (
        db.query(GenerationBatchMember)
        .filter(
            GenerationBatchMember.public_job_id == public_job_id,
            GenerationBatchMember.batch_index == batch_index,
        )
        .one()
    )
    now = _utcnow()
    if member.status not in TERMINAL_MEMBER_STATUSES:
        member.status = "running"
        member.started_at = member.started_at or now
        parent.status = "running"
        parent.started_at = parent.started_at or now
        parent.current_batch_index = batch_index
        db.commit()
    return _status_payload(parent, _members(db, public_job_id))


def mark_member_terminal(
    db: Session,
    *,
    public_job_id: str,
    batch_index: int,
    succeeded: bool,
    failure_code: str | None = None,
    failure_message: object | None = None,
) -> dict[str, Any]:
    parent = (
        db.query(GenerationBatch)
        .filter(GenerationBatch.public_job_id == public_job_id)
        .one()
    )
    member = (
        db.query(GenerationBatchMember)
        .filter(
            GenerationBatchMember.public_job_id == public_job_id,
            GenerationBatchMember.batch_index == batch_index,
        )
        .one()
    )
    if member.status not in TERMINAL_MEMBER_STATUSES:
        member.status = "completed" if succeeded else "failed"
        member.completed_at = _utcnow()
        if succeeded:
            member.failure_code = None
            member.failure_message = None
        else:
            member.failure_code = sanitize_failure_code(failure_code)
            member.failure_message = sanitize_failure_message(failure_message)
        db.flush()

        members = _members(db, public_job_id)
        parent.batch_completed = sum(
            item.status == "completed" for item in members
        )
        parent.batch_failed = sum(item.status == "failed" for item in members)
        terminal_count = parent.batch_completed + parent.batch_failed
        if terminal_count == parent.batch_total:
            parent.status = (
                "completed" if parent.batch_completed > 0 else "failed"
            )
            parent.current_batch_index = None
            parent.completed_at = _utcnow()
        else:
            parent.status = "running"
        db.commit()
    return _status_payload(parent, _members(db, public_job_id))


def cancel_queued_batch(db: Session, public_job_id: str) -> bool:
    parent = (
        db.query(GenerationBatch)
        .filter(GenerationBatch.public_job_id == public_job_id)
        .one_or_none()
    )
    if parent is None:
        return False
    members = _members(db, public_job_id)
    if parent.status != "queued" or any(
        member.status != "queued" for member in members
    ):
        raise ValueError("generation batch is already running")
    for member in members:
        member.status = "failed"
        member.failure_code = "cancelled"
        member.failure_message = "generation batch was cancelled before execution"
        member.completed_at = _utcnow()
    parent.status = "failed"
    parent.batch_failed = parent.batch_total
    parent.current_batch_index = None
    parent.completed_at = _utcnow()
    db.commit()
    return True


def reconcile_interrupted_batches(
    session_factory: Callable[[], Session],
) -> int:
    reconciled = 0
    with session_factory() as db:
        parents = (
            db.query(GenerationBatch)
            .filter(GenerationBatch.status.in_(("queued", "running")))
            .all()
        )
        for parent in parents:
            members = _members(db, parent.public_job_id)
            changed = False
            for member in members:
                if member.status in TERMINAL_MEMBER_STATUSES:
                    continue
                member.status = "failed"
                member.failure_code = "backend_restarted"
                member.failure_message = (
                    "Backend restarted before this batch member reached a terminal state"
                )
                member.completed_at = _utcnow()
                changed = True
            if not changed:
                continue
            parent.batch_completed = sum(
                member.status == "completed" for member in members
            )
            parent.batch_failed = sum(
                member.status == "failed" for member in members
            )
            parent.status = (
                "completed" if parent.batch_completed > 0 else "failed"
            )
            parent.current_batch_index = None
            parent.completed_at = _utcnow()
            reconciled += 1
        db.commit()
    return reconciled
