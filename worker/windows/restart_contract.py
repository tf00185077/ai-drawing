"""Durable, correlated contract for the fixed Worker restart task."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict

try:
    from worker.windows.updater.request_lock import exclusive_request_lock
except ModuleNotFoundError:  # direct installed execution
    from updater.request_lock import exclusive_request_lock


RESTART_TASK_NAME = "AI-Drawing NVIDIA Worker Restart"
ACTIVE_RESTART_STATES = frozenset({"queued", "restarting"})
TERMINAL_RESTART_STATES = frozenset({"started", "failed", "timed_out"})
STALE_RESTART_AFTER = timedelta(minutes=4)


class RestartRequest(BaseModel):
    """The management API intentionally accepts no selectors or arguments."""

    model_config = ConfigDict(extra="forbid")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def read_restart_status(status_path: Path) -> dict[str, Any]:
    request_path = status_path.with_name("restart-request.json")
    with exclusive_request_lock(request_path):
        try:
            value = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            value = {}
        if not isinstance(value, dict):
            value = {}
        state = value.get("state")
        if state not in ACTIVE_RESTART_STATES | TERMINAL_RESTART_STATES:
            return {"request_id": None, "state": "idle", "timestamp": None}
        return {
            "request_id": value.get("request_id") if isinstance(value.get("request_id"), str) else None,
            "state": state,
            "timestamp": value.get("timestamp") if isinstance(value.get("timestamp"), str) else None,
            **({"error_code": value["error_code"]} if isinstance(value.get("error_code"), str) else {}),
        }


def write_restart_status(
    status_path: Path,
    request_id: str,
    state: str,
    *,
    error_code: str | None = None,
) -> None:
    """Publish a correlated terminal or intermediate restart state."""
    if state not in ACTIVE_RESTART_STATES | TERMINAL_RESTART_STATES:
        raise ValueError("invalid restart state")
    request_path = status_path.with_name("restart-request.json")
    with exclusive_request_lock(request_path):
        value: dict[str, Any] = {
            "request_id": request_id,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error_code:
            value["error_code"] = error_code
        _atomic_json(status_path, value)


def queue_restart(request_path: Path, status_path: Path) -> tuple[str, bool]:
    with exclusive_request_lock(request_path):
        try:
            current = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            current = {}
        if (
            isinstance(current, dict)
            and current.get("state") in ACTIVE_RESTART_STATES
            and _restart_status_is_fresh(current)
        ):
            request_id = current.get("request_id")
            if isinstance(request_id, str) and request_id:
                return request_id, False
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        _atomic_json(request_path, {"request_id": request_id, "timestamp": timestamp})
        _atomic_json(status_path, {"request_id": request_id, "state": "queued", "timestamp": timestamp})
        return request_id, True


def _restart_status_is_fresh(value: Mapping[str, Any]) -> bool:
    raw = value.get("timestamp")
    if not isinstance(raw, str) or not raw:
        return False
    try:
        timestamp = datetime.fromisoformat(raw)
        if timestamp.tzinfo is None:
            return False
        age = datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return False
    return timedelta(0) <= age <= STALE_RESTART_AFTER
