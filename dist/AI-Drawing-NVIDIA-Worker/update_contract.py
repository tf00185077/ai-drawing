"""Local, typed contract for requesting Windows worker updates."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

try:
    from worker.windows.updater.request_lock import RequestLockError, exclusive_request_lock
except ModuleNotFoundError:  # Supports direct execution from worker/windows.
    try:
        from updater.request_lock import RequestLockError, exclusive_request_lock
    except ModuleNotFoundError:  # Supports the legacy installer app directory.
        from request_lock import RequestLockError, exclusive_request_lock


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


class UpdateAlreadyRunning(Exception):
    """A distinct target was requested before the current one completed."""


TERMINAL_UPDATE_STATES = {"ready", "rolled_back", "failed_before_activation"}


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def write_update_status(status_path: Path, state: str) -> None:
    request_path = status_path.with_name("update-request.json")
    with exclusive_request_lock(request_path):
        _write_update_status_unlocked(status_path, state)


def queue_update(request_path: Path, status_path: Path, target_commit: str) -> str:
    with exclusive_request_lock(request_path):
        return _queue_update_locked(request_path, status_path, target_commit)


def _queue_update_locked(request_path: Path, status_path: Path, target_commit: str) -> str:
    try:
        active_request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        active_request = None

    if isinstance(active_request, dict):
        active_target = active_request.get("target_commit")
        active_request_id = active_request.get("request_id")
        state = _read_public_update_status_unlocked(status_path)["state"]
        if state not in TERMINAL_UPDATE_STATES:
            if active_target == target_commit and isinstance(active_request_id, str):
                return active_request_id
            raise UpdateAlreadyRunning
        if active_target == target_commit and isinstance(active_request_id, str):
            _write_update_status_unlocked(status_path, "queued")
            return active_request_id

    request_id = str(uuid.uuid4())
    atomic_write_json(
        request_path,
        {
            "request_id": request_id,
            "target_commit": target_commit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    _write_update_status_unlocked(status_path, "queued")
    return request_id


def read_public_update_status(status_path: Path) -> dict[str, str]:
    request_path = status_path.with_name("update-request.json")
    with exclusive_request_lock(request_path):
        return _read_public_update_status_unlocked(status_path)


def _read_public_update_status_unlocked(status_path: Path) -> dict[str, str]:
    try:
        value = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    state = value.get("state") if isinstance(value, dict) else None
    return {"state": state if isinstance(state, str) and state else "idle"}


def _write_update_status_unlocked(status_path: Path, state: str) -> None:
    atomic_write_json(status_path, {"state": state})
