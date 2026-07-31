"""Locked, durable state transitions for managed Windows worker updates."""
from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .request_lock import RequestLockError, exclusive_request_lock


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
_URL_CREDENTIALS = re.compile(r"://[^/\s@]+@")
_BEARER_SECRET = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(?:token|secret|password|api[_-]?key|authorization)\b\s*(?:=|:)?\s*[^\s,;]+"
)
PUBLIC_ERROR_CODES = frozenset(
    {
        "UPDATE_ALREADY_RUNNING",
        "TARGET_COMMIT_INVALID",
        "MAC_COMMIT_NOT_ORIGIN_MAIN",
        "WINDOWS_REMOTE_HEAD_MISMATCH",
        "UPDATER_CONFIG_INVALID",
        "SOURCE_REPOSITORY_INVALID",
        "INSUFFICIENT_DISK_SPACE",
        "RUNTIME_INSTALL_FAILED",
        "CUDA_VALIDATION_FAILED",
        "COMFYUI_VALIDATION_FAILED",
        "WORKER_CONTRACT_FAILED",
        "ACTIVATION_FAILED_ROLLED_BACK",
        "RECOVERY_REQUIRED",
        "UPDATE_FAILED",
    }
)
_VALID_STATES = frozenset({"idle", *TRANSITIONS, *TERMINAL_STATES})


class InvalidUpdateTransition(ValueError):
    """A requested update state is not reachable from the current state."""


class UpdateAlreadyRunning(ValueError):
    """A different update request is already active."""


class StateStoreError(RuntimeError):
    """Persisted updater state cannot be safely read or validated."""


@dataclass(frozen=True)
class ActiveUpdateRequest:
    """Validated private request metadata for the privileged updater only."""

    request_id: str
    target_commit: str
    state: str


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
                if private["target_commit"] == target_commit:
                    self._reconcile_public(private)
                    return private["request_id"]
                raise UpdateAlreadyRunning("a different update request is already active")
            next_private = {"state": "queued", "request_id": request_id, "target_commit": target_commit}
            self._write_private(next_private)
            self._write_public({"state": "queued"})
            return request_id

    def claim_queued_request(self, request_path: Path) -> ActiveUpdateRequest | None:
        """Atomically claim a new request or acknowledge its durable terminal result."""
        request_path = Path(request_path)
        if request_path != self.root / "update-request.json":
            raise StateStoreError("queued update request path is not canonical")
        try:
            with exclusive_request_lock(request_path):
                return self._claim_queued_request_locked(request_path)
        except RequestLockError as error:
            raise StateStoreError("queued update request lock is unavailable") from error

    def _claim_queued_request_locked(
        self, request_path: Path
    ) -> ActiveUpdateRequest | None:
        try:
            value = json.loads(Path(request_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            raise StateStoreError("queued update request is unreadable") from error
        if not isinstance(value, dict) or set(value) != {
            "request_id",
            "target_commit",
            "timestamp",
        }:
            raise StateStoreError("queued update request has an invalid structure")
        request_id = value.get("request_id")
        target_commit = value.get("target_commit")
        timestamp = value.get("timestamp")
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(target_commit, str)
            or not _COMMIT_PATTERN.fullmatch(target_commit)
            or not isinstance(timestamp, str)
            or not timestamp
        ):
            raise StateStoreError("queued update request has invalid metadata")
        with self._exclusive_lock():
            private = self._read_private()
            state = private["state"]
            if state not in {"idle", *TERMINAL_STATES}:
                if (
                    private["request_id"] != request_id
                    or private["target_commit"] != target_commit
                ):
                    raise StateStoreError(
                        "queued update request does not match active private state"
                    )
                self._reconcile_public(private)
                return ActiveUpdateRequest(request_id, target_commit, state)
            if state in TERMINAL_STATES and private["request_id"] == request_id:
                if private["target_commit"] != target_commit:
                    raise StateStoreError(
                        "queued update request does not match terminal private state"
                    )
                # The terminal private record is the durable acknowledgement. Keeping the
                # atomically-written request file makes crashes between runs replay-safe.
                self._reconcile_public(private)
                return None
            next_private = {
                "state": "queued",
                "request_id": request_id,
                "target_commit": target_commit,
            }
            self._write_private(next_private)
            self._write_public({"state": "queued"})
            return ActiveUpdateRequest(request_id, target_commit, "queued")

    def transition(self, next_state: str) -> None:
        """Move the active request to an explicitly permitted next state."""
        with self._exclusive_lock():
            private = self._read_private()
            current_state = private["state"]
            if next_state == current_state:
                self._reconcile_public(private)
                return
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
            safe_error_code = _public_error_code(error_code)
            if current_state in {"fetching", "staging", "installing", "validating"}:
                next_state = "failed_before_activation"
            elif current_state in {"activating", "restarting"}:
                next_state = "recovery_required"
            else:
                raise InvalidUpdateTransition(f"cannot fail update from {current_state}")
            private.update(
                {
                    "state": next_state,
                    "error_code": safe_error_code,
                    "error_message": _redact_private_message(message),
                }
            )
            self._write_private(private)
            self._write_public({"state": next_state, "error_code": safe_error_code})

    def terminal_failure(self, next_state: str, error_code: str, message: str) -> None:
        """Persist a declared terminal result without exposing arbitrary diagnostics."""
        if next_state not in {"rejected", "failed_before_activation", "rolled_back", "recovery_required"}:
            raise InvalidUpdateTransition(f"{next_state} is not a failure terminal state")
        with self._exclusive_lock():
            private = self._read_private()
            current_state = private["state"]
            safe_error_code = _public_error_code(error_code)
            if next_state not in TRANSITIONS.get(current_state, set()):
                raise InvalidUpdateTransition(f"cannot transition from {current_state} to {next_state}")
            private.update(
                {
                    "state": next_state,
                    "error_code": safe_error_code,
                    "error_message": _redact_private_message(message),
                }
            )
            self._write_private(private)
            self._write_public(
                {"state": next_state, "error_code": safe_error_code}
            )

    def read_active_request(self) -> ActiveUpdateRequest | None:
        """Return a typed snapshot of an active private request under the state lock."""
        with self._exclusive_lock():
            private = self._read_private()
            if private["state"] in {"idle", *TERMINAL_STATES}:
                self._reconcile_public(private)
                return None
            return ActiveUpdateRequest(
                request_id=private["request_id"],
                target_commit=private["target_commit"],
                state=private["state"],
            )

    def read_public(self) -> dict[str, str]:
        """Return the public status only, never request IDs or diagnostics."""
        with self._exclusive_lock():
            return self._reconcile_public(self._read_private())

    def _read_private(self) -> dict[str, Any]:
        try:
            value = json.loads(self.private_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"state": "idle"}
        except OSError as error:
            raise StateStoreError("unable to read private updater state") from error
        except (TypeError, ValueError) as error:
            raise StateStoreError("private updater state is malformed") from error
        return _validated_private_state(value)

    def _reconcile_public(self, private: Mapping[str, Any]) -> dict[str, str]:
        projection = _public_projection(private)
        try:
            current = json.loads(self.public_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = None
        if current != projection:
            self._write_public(projection)
        return projection

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
    return error_code if error_code in PUBLIC_ERROR_CODES else "UPDATE_FAILED"


def _redact_private_message(message: str) -> str:
    value = str(message).replace("\r", " ").replace("\n", " ")
    value = _URL_CREDENTIALS.sub("://[REDACTED]@", value)
    value = _BEARER_SECRET.sub("Bearer [REDACTED]", value)
    value = _NAMED_SECRET.sub("[REDACTED]", value)
    return value[:1024] or "update operation failed"


def _validated_private_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("state"), str):
        raise StateStoreError("private updater state has an invalid structure")
    state = value["state"]
    if state not in _VALID_STATES:
        raise StateStoreError("private updater state has an unknown state")
    if state != "idle":
        if not isinstance(value.get("request_id"), str) or not value["request_id"]:
            raise StateStoreError("private updater state is missing its request ID")
        target_commit = value.get("target_commit")
        if not isinstance(target_commit, str) or not _COMMIT_PATTERN.fullmatch(target_commit):
            raise StateStoreError("private updater state has an invalid target commit")
    return value


def _public_projection(private: Mapping[str, Any]) -> dict[str, str]:
    projection = {"state": str(private["state"])}
    error_code = private.get("error_code")
    if isinstance(error_code, str):
        projection["error_code"] = _public_error_code(error_code)
    return projection


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
