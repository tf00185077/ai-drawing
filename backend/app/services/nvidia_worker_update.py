"""Mac-side coordination for exact-commit NVIDIA Worker updates.

The coordinator is deliberately synchronous because generation submission runs
in the Backend queue thread. FastAPI startup uses :meth:`start_background`, so
Git and network operations never block the async event loop. Coordination is
process-local; multiple Backend processes converge through the Worker's
same-target update-request reuse contract.
"""
from __future__ import annotations

import logging
import math
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

EXPECTED_PROTOCOL_VERSION = 2
EXPECTED_UPDATE_CAPABILITY = 1
DEFAULT_UPDATE_TIMEOUT = 1800.0
DEFAULT_GIT_TIMEOUT = 10.0
DEFAULT_POLL_INTERVAL = 1.0
_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ACTIVE_UPDATE_STATES = frozenset({
    "queued",
    "fetching",
    "staging",
    "installing",
    "validating",
    "activating",
    "restarting",
})
_FAILED_UPDATE_STATES = {
    "failed_before_activation",
    "rolled_back",
    "recovery_required",
}

_SAFE_MESSAGES = {
    "MAC_GIT_TIMEOUT": "Local Git inspection timed out.",
    "MAC_GIT_UNAVAILABLE": "Local Git state could not be inspected.",
    "MAC_GIT_INVALID_COMMIT": "Local Git returned an invalid commit.",
    "MAC_COMMIT_NOT_ORIGIN_MAIN": "Local HEAD is not the published origin/main commit.",
    "WORKER_UNAVAILABLE": "NVIDIA Worker status is unavailable.",
    "WORKER_PROTOCOL_INCOMPATIBLE": "NVIDIA Worker protocol is incompatible.",
    "WORKER_UPDATE_CAPABILITY_INCOMPATIBLE": "NVIDIA Worker update capability is incompatible.",
    "WORKER_UPDATE_REQUEST_FAILED": "NVIDIA Worker update request failed.",
    "WORKER_UPDATE_REQUEST_INVALID": "NVIDIA Worker update request was not accepted.",
    "WORKER_UPDATE_STATUS_INVALID": "NVIDIA Worker update status is invalid.",
    "WORKER_UPDATE_FAILED": "NVIDIA Worker update failed.",
    "WORKER_UPDATE_TIMEOUT": "NVIDIA Worker update timed out.",
    "WORKER_UPDATE_COMMIT_MISMATCH": "NVIDIA Worker did not activate the requested commit.",
    "WORKER_PREFLIGHT_FAILED": "NVIDIA Worker preflight failed.",
    "WORKER_UPDATE_CANCELLED": "NVIDIA Worker update check was cancelled.",
}


class WorkerUpdateError(RuntimeError):
    """A stable, token-safe coordinator failure."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.safe_message = message or _SAFE_MESSAGES.get(
            code, "NVIDIA Worker update failed."
        )
        super().__init__(f"{self.code}: {self.safe_message}")


class WorkerUpdateClient(Protocol):
    def health(self, *, timeout: float | None = None) -> dict[str, Any]: ...

    def request_update(
        self, target_commit: str, *, timeout: float | None = None
    ) -> dict[str, Any]: ...

    def update_status(self, *, timeout: float | None = None) -> dict[str, Any]: ...

    def preflight(
        self, node_types: list[str], *, timeout: float | None = None
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class WorkerCompatibilityResult:
    target_commit: str
    updated: bool
    request_id: str | None = None


@dataclass
class _CoordinatorRun:
    target_commit: str
    done: bool = False
    result: WorkerCompatibilityResult | None = None
    error_code: str | None = None
    error_message: str | None = None


def _git_commit(
    repository: Path,
    revision: str,
    *,
    timeout: float,
    run_command: Callable[..., subprocess.CompletedProcess[str]],
) -> str:
    try:
        result = run_command(
            ["git", "-C", str(repository), "rev-parse", revision],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise WorkerUpdateError("MAC_GIT_TIMEOUT") from None
    except (OSError, subprocess.SubprocessError):
        raise WorkerUpdateError("MAC_GIT_UNAVAILABLE") from None
    commit = result.stdout.strip().lower()
    if not _FULL_COMMIT.fullmatch(commit):
        raise WorkerUpdateError("MAC_GIT_INVALID_COMMIT")
    return commit


def trusted_local_commit(
    repository: str | Path = _PROJECT_ROOT,
    *,
    timeout: float = DEFAULT_GIT_TIMEOUT,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Return HEAD only when it exactly equals the local origin/main ref.

    This function performs local ``rev-parse`` calls only. It never fetches,
    pulls, or mutates the Mac working tree.
    """

    repository_path = Path(repository).resolve()
    head = _git_commit(
        repository_path,
        "HEAD",
        timeout=timeout,
        run_command=run_command,
    )
    origin_main = _git_commit(
        repository_path,
        "origin/main^{commit}",
        timeout=timeout,
        run_command=run_command,
    )
    if head != origin_main:
        raise WorkerUpdateError("MAC_COMMIT_NOT_ORIGIN_MAIN")
    return head


class NvidiaWorkerUpdateCoordinator:
    """Serialize compatibility checks and let same-target callers join."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._clock = clock
        self._sleeper = sleeper
        self._poll_interval = poll_interval
        self._condition = threading.Condition()
        self._active: _CoordinatorRun | None = None
        self._state = "idle"
        self._error_code: str | None = None
        self._background_thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def safe_status(self) -> dict[str, str | None]:
        with self._condition:
            return {
                "state": self._state,
                "error_code": self._error_code,
            }

    def _set_status(self, state: str, error_code: str | None = None) -> None:
        with self._condition:
            self._state = state
            self._error_code = error_code

    @staticmethod
    def _raise_run_error(run: _CoordinatorRun) -> None:
        if run.error_code is not None:
            raise WorkerUpdateError(run.error_code, run.error_message)

    def ensure_worker_compatible(
        self,
        client: WorkerUpdateClient,
        repository: str | Path = _PROJECT_ROOT,
        *,
        timeout: float = DEFAULT_UPDATE_TIMEOUT,
    ) -> WorkerCompatibilityResult:
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be positive and finite")
        timeout = float(timeout)
        target_commit = trusted_local_commit(repository)

        while True:
            with self._condition:
                active = self._active
                if active is None:
                    run = _CoordinatorRun(target_commit=target_commit)
                    self._active = run
                    self._state = "checking"
                    self._error_code = None
                    break
                if active.target_commit != target_commit:
                    self._condition.wait_for(lambda: active.done)
                    continue
                self._condition.wait_for(lambda: active.done)
                self._raise_run_error(active)
                assert active.result is not None
                return active.result

        try:
            result = self._coordinate(client, target_commit, timeout)
        except WorkerUpdateError as error:
            with self._condition:
                run.error_code = error.code
                run.error_message = error.safe_message
                self._state = "error"
                self._error_code = error.code
            raise
        except Exception:
            error = WorkerUpdateError("WORKER_UPDATE_FAILED")
            with self._condition:
                run.error_code = error.code
                run.error_message = error.safe_message
                self._state = "error"
                self._error_code = error.code
            raise error from None
        else:
            with self._condition:
                run.result = result
                self._state = "ready"
                self._error_code = None
            return result
        finally:
            with self._condition:
                run.done = True
                if self._active is run:
                    self._active = None
                self._condition.notify_all()

    def start_background(
        self,
        client: WorkerUpdateClient,
        repository: str | Path = _PROJECT_ROOT,
        *,
        timeout: float = DEFAULT_UPDATE_TIMEOUT,
    ) -> threading.Thread:
        """Start at most one bounded compatibility thread and return promptly."""

        with self._condition:
            if (
                self._background_thread is not None
                and self._background_thread.is_alive()
            ):
                return self._background_thread
            self._cancel.clear()
            thread = threading.Thread(
                target=self._background_entry,
                args=(client, Path(repository), timeout),
                name="nvidia-worker-update",
                daemon=True,
            )
            self._background_thread = thread
            thread.start()
            return thread

    def stop_background(self, join_timeout: float = 0.1) -> None:
        self._cancel.set()
        with self._condition:
            thread = self._background_thread
            self._condition.notify_all()
        if thread is not None and thread is not threading.current_thread():
            thread.join(max(0.0, join_timeout))

    def _background_entry(
        self,
        client: WorkerUpdateClient,
        repository: Path,
        timeout: float,
    ) -> None:
        try:
            self.ensure_worker_compatible(client, repository, timeout=timeout)
        except WorkerUpdateError as error:
            # Log only the stable code; exception details may contain URLs or
            # transport diagnostics and must not expose the bearer token.
            logger.warning("NVIDIA Worker background update check failed: %s", error.code)

    @staticmethod
    def _health_value(client: WorkerUpdateClient) -> dict[str, Any]:
        try:
            value = client.health()
        except Exception:
            raise WorkerUpdateError("WORKER_UNAVAILABLE") from None
        if not isinstance(value, dict):
            raise WorkerUpdateError("WORKER_UNAVAILABLE")
        return value

    @staticmethod
    def _validate_identity(health: dict[str, Any], target_commit: str) -> None:
        protocol_version = health.get("protocol_version")
        if (
            type(protocol_version) is not int
            or protocol_version != EXPECTED_PROTOCOL_VERSION
        ):
            raise WorkerUpdateError("WORKER_PROTOCOL_INCOMPATIBLE")
        update_capability = health.get("update_capability")
        if (
            type(update_capability) is not int
            or update_capability != EXPECTED_UPDATE_CAPABILITY
        ):
            raise WorkerUpdateError("WORKER_UPDATE_CAPABILITY_INCOMPATIBLE")
        if health.get("source_commit") != target_commit:
            raise WorkerUpdateError("WORKER_UPDATE_COMMIT_MISMATCH")

    @staticmethod
    def _is_expected_outage(error: BaseException) -> bool:
        return isinstance(error, (httpx.TransportError, OSError))

    def _pause_until_deadline(self, deadline: float) -> None:
        remaining = self._remaining_timeout(deadline)
        delay = min(self._poll_interval, remaining)
        if self._sleeper is None:
            self._cancel.wait(delay)
        else:
            self._sleeper(delay)
        if self._cancel.is_set():
            raise WorkerUpdateError("WORKER_UPDATE_CANCELLED")

    def _remaining_timeout(self, deadline: float) -> float:
        if self._cancel.is_set():
            raise WorkerUpdateError("WORKER_UPDATE_CANCELLED")
        now = self._clock()
        remaining = deadline - now
        if (
            not math.isfinite(deadline)
            or not math.isfinite(now)
            or not math.isfinite(remaining)
            or remaining <= 0
        ):
            raise WorkerUpdateError("WORKER_UPDATE_TIMEOUT")
        return remaining

    def _coordinate(
        self,
        client: WorkerUpdateClient,
        target_commit: str,
        timeout: float,
    ) -> WorkerCompatibilityResult:
        health = self._health_value(client)
        if health.get("source_commit") == target_commit:
            self._validate_identity(health, target_commit)
            return WorkerCompatibilityResult(target_commit, updated=False)

        protocol_version = health.get("protocol_version")
        if (
            type(protocol_version) is not int
            or protocol_version != EXPECTED_PROTOCOL_VERSION
        ):
            raise WorkerUpdateError("WORKER_PROTOCOL_INCOMPATIBLE")
        update_capability = health.get("update_capability")
        if (
            type(update_capability) is not int
            or update_capability != EXPECTED_UPDATE_CAPABILITY
        ):
            raise WorkerUpdateError("WORKER_UPDATE_CAPABILITY_INCOMPATIBLE")

        self._set_status("requesting")
        try:
            accepted = client.request_update(target_commit)
        except Exception:
            raise WorkerUpdateError("WORKER_UPDATE_REQUEST_FAILED") from None
        if not isinstance(accepted, dict):
            raise WorkerUpdateError("WORKER_UPDATE_REQUEST_INVALID")
        request_id = accepted.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise WorkerUpdateError("WORKER_UPDATE_REQUEST_INVALID")

        # Only an accepted request ID opens the expected-outage window.
        deadline = self._clock() + timeout
        if not math.isfinite(deadline):
            raise WorkerUpdateError("WORKER_UPDATE_TIMEOUT")
        self._set_status("updating")
        while True:
            remaining = self._remaining_timeout(deadline)
            try:
                status = client.update_status(timeout=remaining)
            except Exception as error:
                self._remaining_timeout(deadline)
                if not self._is_expected_outage(error):
                    raise WorkerUpdateError("WORKER_UPDATE_FAILED") from None
                self._pause_until_deadline(deadline)
                continue
            self._remaining_timeout(deadline)
            if not isinstance(status, dict) or not isinstance(status.get("state"), str):
                raise WorkerUpdateError("WORKER_UPDATE_STATUS_INVALID")
            state = status["state"]
            if state in _FAILED_UPDATE_STATES:
                raise WorkerUpdateError("WORKER_UPDATE_FAILED")
            if state == "ready":
                remaining = self._remaining_timeout(deadline)
                try:
                    final_health = client.health(timeout=remaining)
                except Exception as error:
                    self._remaining_timeout(deadline)
                    if self._is_expected_outage(error):
                        self._pause_until_deadline(deadline)
                        continue
                    raise WorkerUpdateError("WORKER_UPDATE_FAILED") from None
                self._remaining_timeout(deadline)
                if not isinstance(final_health, dict):
                    raise WorkerUpdateError("WORKER_UNAVAILABLE")
                self._validate_identity(final_health, target_commit)
                remaining = self._remaining_timeout(deadline)
                try:
                    preflight = client.preflight([], timeout=remaining)
                except Exception as error:
                    self._remaining_timeout(deadline)
                    if self._is_expected_outage(error):
                        self._pause_until_deadline(deadline)
                        continue
                    raise WorkerUpdateError("WORKER_UPDATE_FAILED") from None
                self._remaining_timeout(deadline)
                if (
                    not isinstance(preflight, dict)
                    or preflight.get("ready") is not True
                    or preflight.get("missing_node_types") != []
                ):
                    raise WorkerUpdateError("WORKER_PREFLIGHT_FAILED")
                return WorkerCompatibilityResult(
                    target_commit,
                    updated=True,
                    request_id=request_id,
                )
            if state not in _ACTIVE_UPDATE_STATES:
                raise WorkerUpdateError("WORKER_UPDATE_STATUS_INVALID")
            self._pause_until_deadline(deadline)


_default_coordinator = NvidiaWorkerUpdateCoordinator()


def ensure_worker_compatible(
    client: WorkerUpdateClient,
    repository: str | Path = _PROJECT_ROOT,
    *,
    timeout: float = DEFAULT_UPDATE_TIMEOUT,
) -> WorkerCompatibilityResult:
    return _default_coordinator.ensure_worker_compatible(
        client, repository, timeout=timeout
    )


def start_worker_update_background() -> threading.Thread | None:
    settings = get_settings()
    if not settings.nvidia_worker_auto_update:
        return None
    if not settings.nvidia_worker_url or not settings.nvidia_worker_token:
        return None
    # Local import prevents a module cycle: NvidiaWorkerClient uses the public
    # ensure_worker_compatible function for its pre-submission gate.
    from app.services.nvidia_worker import NvidiaWorkerClient

    client = NvidiaWorkerClient(
        settings.nvidia_worker_url.rstrip("/"),
        settings.nvidia_worker_token,
        settings.nvidia_worker_timeout,
    )
    return _default_coordinator.start_background(
        client,
        _PROJECT_ROOT,
        timeout=settings.nvidia_worker_update_timeout,
    )


def stop_worker_update_background() -> None:
    _default_coordinator.stop_background()


def worker_update_status() -> dict[str, str | None]:
    settings = get_settings()
    if not settings.nvidia_worker_auto_update:
        return {"state": "disabled", "error_code": None}
    if not settings.nvidia_worker_url or not settings.nvidia_worker_token:
        return {"state": "not_paired", "error_code": None}
    return _default_coordinator.safe_status()
