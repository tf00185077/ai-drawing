"""Locked, durable state transitions for managed Windows worker updates."""
from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


TRANSITIONS = {
    "queued": {"fetching", "rejected"},
    "fetching": {"staging", "failed_before_activation"},
    "staging": {"installing", "failed_before_activation"},
    "installing": {"validating", "failed_before_activation"},
    "validating": {"activating", "failed_before_activation"},
    "activating": {"restarting", "rolled_back", "recovery_required"},
    "restarting": {"ready", "rolled_back", "recovery_required"},
}
TERMINAL_STATES = {"ready", "rejected", "failed_before_activation", "rolled_back", "recovery_required"}
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_ERROR_CODE_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class InvalidUpdateTransition(ValueError):
    """A requested update state is not reachable from the current state."""


class UpdateAlreadyRunning(ValueError):
    """A different update request is already active."""


class UpdateStateStore:
    """Persist updater progress without exposing request data to public status readers."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.private_path = self.root / "update-state.private.json"
        self.public_path = self.root / "update-status.json"
        self.lock_path = self.root / "update-state.lock"

    def queue(self, request_id: str, target_commit: str) -> str:
        """Create an update request, or return the same active request unchanged."""
        if not request_id:
            raise ValueError("request ID must be non-empty")
        if not _COMMIT_PATTERN.fullmatch(target_commit):
            raise ValueError("target commit must be a 40-character lowercase SHA")
        with self._exclusive_lock():
            private = self._read_private()
            state = private["state"]
            if state not in {"idle", *TERMINAL_STATES}:
                if private.get("request_id") == request_id and private.get("target_commit") == target_commit:
                    return request_id
                raise UpdateAlreadyRunning("a different update request is already active")
            next_private = {"state": "queued", "request_id": request_id, "target_commit": target_commit}
            self._write_private(next_private)
            self._write_public({"state": "queued"})
            return request_id

    def transition(self, next_state: str) -> None:
        """Move the active request to an explicitly permitted next state."""
        with self._exclusive_lock():
            private = self._read_private()
            current_state = private["state"]
            if next_state not in TRANSITIONS.get(current_state, set()):
                raise InvalidUpdateTransition(f"cannot transition from {current_state} to {next_state}")
            private["state"] = next_state
            self._write_private(private)
            self._write_public({"state": next_state})

    def fail(self, error_code: str, message: str) -> None:
        """Record a private diagnostic and expose only a safe state and error code."""
        with self._exclusive_lock():
            private = self._read_private()
            current_state = private["state"]
            if current_state in {"fetching", "staging", "installing", "validating"}:
                next_state = "failed_before_activation"
            elif current_state in {"activating", "restarting"}:
                next_state = "recovery_required"
            else:
                raise InvalidUpdateTransition(f"cannot fail update from {current_state}")
            private.update({"state": next_state, "error_code": error_code, "error_message": message})
            self._write_private(private)
            self._write_public({"state": next_state, "error_code": _public_error_code(error_code)})

    def read_public(self) -> dict[str, str]:
        """Return the public status only, never request IDs or diagnostics."""
        with self._exclusive_lock():
            try:
                value = json.loads(self.public_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {"state": "idle"}
            if not isinstance(value, dict) or not isinstance(value.get("state"), str):
                return {"state": "idle"}
            status = {"state": value["state"]}
            if isinstance(value.get("error_code"), str) and _ERROR_CODE_PATTERN.fullmatch(value["error_code"]):
                status["error_code"] = value["error_code"]
            return status

    def _read_private(self) -> dict[str, Any]:
        try:
            value = json.loads(self.private_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": "idle"}
        if not isinstance(value, dict) or not isinstance(value.get("state"), str):
            return {"state": "idle"}
        return value

    def _write_private(self, value: Mapping[str, Any]) -> None:
        _atomic_write_json(self.private_path, value)

    def _write_public(self, value: Mapping[str, str]) -> None:
        _atomic_write_json(self.public_path, value)

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_file:
            lock_file.seek(0)
            if not lock_file.read(1):
                lock_file.seek(0)
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            _lock_exclusive(lock_file)
            try:
                yield
            finally:
                lock_file.seek(0)
                _unlock(lock_file)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(value, temporary_file, sort_keys=True, separators=(",", ":"))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _public_error_code(error_code: str) -> str:
    return error_code if _ERROR_CODE_PATTERN.fullmatch(error_code) else "UPDATE_FAILED"


def _lock_exclusive(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)


def _unlock(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
