"""Local, typed contract for requesting Windows worker updates."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field


class UpdateRequest(BaseModel):
    target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


class UpdateAlreadyRunning(Exception):
    """A distinct target was requested before the current one completed."""


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def queue_update(request_path: Path, target_commit: str) -> str:
    try:
        active_request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        active_request = None

    if isinstance(active_request, dict):
        active_target = active_request.get("target_commit")
        active_request_id = active_request.get("request_id")
        if active_target == target_commit and isinstance(active_request_id, str):
            return active_request_id
        raise UpdateAlreadyRunning

    request_id = str(uuid.uuid4())
    atomic_write_json(
        request_path,
        {
            "request_id": request_id,
            "target_commit": target_commit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return request_id


def read_public_update_status(status_path: Path) -> dict[str, str]:
    try:
        value = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    state = value.get("state") if isinstance(value, dict) else None
    return {"state": state if isinstance(state, str) and state else "idle"}
