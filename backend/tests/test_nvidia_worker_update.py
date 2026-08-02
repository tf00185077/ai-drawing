from __future__ import annotations

import asyncio
import subprocess
import threading
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from app.services import nvidia_worker
from app.services.nvidia_worker_update import (
    NvidiaWorkerUpdateCoordinator,
    WorkerUpdateError,
    ensure_worker_compatible,
    trusted_local_commit,
)


PROTOCOL_VERSION = 2
UPDATE_CAPABILITY = 1


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> SimpleNamespace:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Task Six")
    _git(repo, "config", "user.email", "task-six@example.invalid")
    (repo / "tracked.txt").write_text("published\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "published")
    published = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", published)
    return SimpleNamespace(path=repo, origin_main=published)


def _health(commit: str, **overrides: Any) -> dict[str, Any]:
    value = {
        "protocol_version": PROTOCOL_VERSION,
        "source_commit": commit,
        "update_capability": UPDATE_CAPABILITY,
        "update_state": "idle",
    }
    value.update(overrides)
    return value


class FakeWorkerClient:
    def __init__(
        self,
        *,
        health_results: list[dict[str, Any] | Exception],
        update_results: list[dict[str, Any] | Exception] | None = None,
        status_results: list[dict[str, Any] | Exception] | None = None,
        preflight_result: dict[str, Any] | Exception | None = None,
    ) -> None:
        self._health_results = deque(health_results)
        self._last_health: dict[str, Any] | Exception | None = None
        self._update_results = deque(
            update_results or [{"request_id": "request-1", "status": "queued"}]
        )
        self._status_results = deque(status_results or [{"state": "ready"}])
        self._last_status: dict[str, Any] | Exception | None = None
        self.preflight_result = preflight_result or {
            "ready": True,
            "missing_node_types": [],
        }
        self.health_calls = 0
        self.health_timeouts: list[float | None] = []
        self.update_requests: list[str] = []
        self.update_request_timeouts: list[float | None] = []
        self.status_calls = 0
        self.status_timeouts: list[float | None] = []
        self.preflight_calls: list[list[str]] = []
        self.preflight_timeouts: list[float | None] = []

    @staticmethod
    def _value(queue: deque, last: Any = None) -> Any:
        value = queue.popleft() if queue else last
        if isinstance(value, Exception):
            raise value
        return value

    def health(self, *, timeout: float | None = None) -> dict[str, Any]:
        self.health_calls += 1
        self.health_timeouts.append(timeout)
        if self._health_results:
            self._last_health = self._health_results.popleft()
        value = self._last_health
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, dict)
        return value

    def request_update(
        self, target_commit: str, *, timeout: float | None = None
    ) -> dict[str, Any]:
        self.update_requests.append(target_commit)
        self.update_request_timeouts.append(timeout)
        return self._value(self._update_results)

    def update_status(self, *, timeout: float | None = None) -> dict[str, Any]:
        self.status_calls += 1
        self.status_timeouts.append(timeout)
        if self._status_results:
            self._last_status = self._status_results.popleft()
        value = self._last_status
        if isinstance(value, Exception):
            raise value
        assert isinstance(value, dict)
        value = dict(value)
        # Protocol 2's canonical status projection is correlated to the
        # accepted request. Tests may provide explicit bad values to exercise
        # rejection; setdefault deliberately preserves those values.
        value.setdefault("request_id", "request-1")
        value.setdefault("target_commit", self.update_requests[-1])
        value.setdefault("timestamp", "2026-08-01T00:00:00+00:00")
        return value

    def preflight(
        self, node_types: list[str], *, timeout: float | None = None
    ) -> dict[str, Any]:
        self.preflight_calls.append(node_types)
        self.preflight_timeouts.append(timeout)
        if isinstance(self.preflight_result, Exception):
            raise self.preflight_result
        return self.preflight_result


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_local_commit_requires_head_equal_origin_main(git_repo) -> None:
    (git_repo.path / "tracked.txt").write_text("local only\n", encoding="utf-8")
    _git(git_repo.path, "add", "tracked.txt")
    _git(git_repo.path, "commit", "-m", "local-only")

    with pytest.raises(WorkerUpdateError) as caught:
        trusted_local_commit(git_repo.path)

    assert caught.value.code == "MAC_COMMIT_NOT_ORIGIN_MAIN"
    assert git_repo.origin_main == _git(
        git_repo.path, "rev-parse", "origin/main^{commit}"
    )


def test_matching_worker_commit_skips_update(git_repo) -> None:
    client = FakeWorkerClient(health_results=[_health(git_repo.origin_main)])

    result = ensure_worker_compatible(client, git_repo.path)

    assert result.target_commit == git_repo.origin_main
    assert result.updated is False
    assert client.update_requests == []
    assert client.preflight_calls == []


def test_git_timeout_uses_stable_error_without_command_or_token(tmp_path: Path) -> None:
    secret = "Bearer-local-git-secret"

    def time_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["git", secret], 10)

    with pytest.raises(WorkerUpdateError) as caught:
        trusted_local_commit(tmp_path, run_command=time_out)

    assert caught.value.code == "MAC_GIT_TIMEOUT"
    assert secret not in str(caught.value)


def test_mismatch_requests_update_and_tolerates_expected_outage(git_repo) -> None:
    client = FakeWorkerClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)],
        status_results=[
            httpx.ConnectError("expected restart outage"),
            {"state": "restarting"},
            {"state": "ready"},
        ],
    )
    clock = FakeClock()
    coordinator = NvidiaWorkerUpdateCoordinator(
        clock=clock,
        sleeper=clock.sleep,
        poll_interval=1,
    )

    result = coordinator.ensure_worker_compatible(
        client, git_repo.path, timeout=1800
    )

    assert result.updated is True
    assert result.request_id == "request-1"
    assert client.update_requests == [git_repo.origin_main]
    assert client.preflight_calls == [[]]
    assert clock.sleeps == [1, 1]


def test_coordinator_accepts_every_canonical_pre_ready_graph_state(git_repo) -> None:
    client = FakeWorkerClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)],
        status_results=[
            {"state": state}
            for state in (
                "queued",
                "fetching",
                "staging",
                "installing",
                "validating",
                "activating",
                "restarting",
                "ready",
            )
        ],
    )
    clock = FakeClock()

    result = NvidiaWorkerUpdateCoordinator(
        clock=clock,
        sleeper=clock.sleep,
        poll_interval=1,
    ).ensure_worker_compatible(client, git_repo.path, timeout=30)

    assert result.updated is True
    assert client.status_calls == 8
    assert clock.sleeps == [1, 1, 1, 1, 1, 1, 1]


@pytest.mark.parametrize(
    "bad_status",
    [
        {"state": "ready", "request_id": None},
        {"state": "ready", "request_id": "another-request"},
        {"state": "ready", "target_commit": None},
        {"state": "ready", "target_commit": "b" * 40},
        {"state": "ready", "timestamp": None},
        {"state": "ready", "timestamp": ""},
    ],
)
def test_protocol_two_rejects_uncorrelated_update_status(git_repo, bad_status) -> None:
    client = FakeWorkerClient(
        health_results=[_health("a" * 40)],
        status_results=[bad_status],
    )

    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator().ensure_worker_compatible(client, git_repo.path)

    assert caught.value.code == "WORKER_UPDATE_STATUS_INVALID"
    assert client.health_calls == 1


def test_pre_acceptance_connection_failure_is_not_tolerated(git_repo) -> None:
    secret = "Bearer-request-must-not-leak"
    client = FakeWorkerClient(
        health_results=[_health("a" * 40)],
        update_results=[httpx.ConnectError(secret)],
    )
    coordinator = NvidiaWorkerUpdateCoordinator()

    with pytest.raises(WorkerUpdateError) as caught:
        coordinator.ensure_worker_compatible(client, git_repo.path)

    assert caught.value.code == "WORKER_UPDATE_REQUEST_FAILED"
    assert secret not in str(caught.value)
    assert client.status_calls == 0
    assert secret not in str(coordinator.safe_status())


def test_accepted_update_stops_at_injected_30_minute_deadline(git_repo) -> None:
    client = FakeWorkerClient(
        health_results=[_health("a" * 40)],
        status_results=[httpx.ConnectError("offline")],
    )
    clock = FakeClock()
    coordinator = NvidiaWorkerUpdateCoordinator(
        clock=clock,
        sleeper=clock.sleep,
        poll_interval=600,
    )

    with pytest.raises(WorkerUpdateError) as caught:
        coordinator.ensure_worker_compatible(
            client, git_repo.path, timeout=1800
        )

    assert caught.value.code == "WORKER_UPDATE_TIMEOUT"
    assert clock.now == 1800
    assert clock.sleeps == [600, 600, 600]


def test_status_result_returned_after_deadline_is_rejected(git_repo) -> None:
    clock = FakeClock()

    class SlowStatusClient(FakeWorkerClient):
        def update_status(self, *, timeout: float | None = None) -> dict[str, Any]:
            self.status_calls += 1
            self.status_timeouts.append(timeout)
            clock.now = 1801
            return {"state": "ready"}

    client = SlowStatusClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)]
    )

    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator(
            clock=clock,
            sleeper=clock.sleep,
        ).ensure_worker_compatible(client, git_repo.path, timeout=1800)

    assert caught.value.code == "WORKER_UPDATE_TIMEOUT"
    assert client.status_timeouts == [1800]
    assert client.health_calls == 1
    assert client.preflight_calls == []


def test_final_health_result_returned_after_deadline_is_rejected(git_repo) -> None:
    clock = FakeClock()

    class SlowHealthClient(FakeWorkerClient):
        def health(self, *, timeout: float | None = None) -> dict[str, Any]:
            value = super().health(timeout=timeout)
            if self.health_calls == 2:
                clock.now = 1801
            return value

    client = SlowHealthClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)],
        status_results=[{"state": "ready"}],
    )

    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator(
            clock=clock,
            sleeper=clock.sleep,
        ).ensure_worker_compatible(client, git_repo.path, timeout=1800)

    assert caught.value.code == "WORKER_UPDATE_TIMEOUT"
    assert client.status_timeouts == [1800]
    assert client.health_timeouts == [None, 1800]
    assert client.preflight_calls == []


def test_preflight_result_returned_after_deadline_is_rejected(git_repo) -> None:
    clock = FakeClock()

    class SlowPreflightClient(FakeWorkerClient):
        def preflight(
            self, node_types: list[str], *, timeout: float | None = None
        ) -> dict[str, Any]:
            value = super().preflight(node_types, timeout=timeout)
            clock.now = 1801
            return value

    client = SlowPreflightClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)],
        status_results=[{"state": "ready"}],
    )

    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator(
            clock=clock,
            sleeper=clock.sleep,
        ).ensure_worker_compatible(client, git_repo.path, timeout=1800)

    assert caught.value.code == "WORKER_UPDATE_TIMEOUT"
    assert client.status_timeouts == [1800]
    assert client.health_timeouts == [None, 1800]
    assert client.preflight_timeouts == [1800]


def test_each_post_acceptance_call_receives_shrinking_remaining_timeout(
    git_repo,
) -> None:
    clock = FakeClock()

    class AdvancingClient(FakeWorkerClient):
        def update_status(self, *, timeout: float | None = None) -> dict[str, Any]:
            value = super().update_status(timeout=timeout)
            clock.now += 5
            return value

        def health(self, *, timeout: float | None = None) -> dict[str, Any]:
            value = super().health(timeout=timeout)
            if self.health_calls == 2:
                clock.now += 7
            return value

        def preflight(
            self, node_types: list[str], *, timeout: float | None = None
        ) -> dict[str, Any]:
            value = super().preflight(node_types, timeout=timeout)
            clock.now += 3
            return value

    client = AdvancingClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)],
        status_results=[{"state": "ready"}],
    )

    result = NvidiaWorkerUpdateCoordinator(
        clock=clock,
        sleeper=clock.sleep,
    ).ensure_worker_compatible(client, git_repo.path, timeout=30)

    assert result.updated is True
    assert client.update_request_timeouts == [None]
    assert client.status_timeouts == [30]
    assert client.health_timeouts == [None, 25]
    assert client.preflight_timeouts == [18]
    assert clock.now == 15


@pytest.mark.parametrize(
    ("final_health", "preflight", "error_code"),
    [
        (_health("b" * 40), {"ready": True, "missing_node_types": []}, "WORKER_UPDATE_COMMIT_MISMATCH"),
        (_health("TARGET", protocol_version=3), {"ready": True, "missing_node_types": []}, "WORKER_PROTOCOL_INCOMPATIBLE"),
        (_health("TARGET", protocol_version=2.0), {"ready": True, "missing_node_types": []}, "WORKER_PROTOCOL_INCOMPATIBLE"),
        (_health("TARGET", update_capability=2), {"ready": True, "missing_node_types": []}, "WORKER_UPDATE_CAPABILITY_INCOMPATIBLE"),
        (_health("TARGET", update_capability=True), {"ready": True, "missing_node_types": []}, "WORKER_UPDATE_CAPABILITY_INCOMPATIBLE"),
        (_health("TARGET"), {"ready": False, "missing_node_types": ["KSampler"]}, "WORKER_PREFLIGHT_FAILED"),
    ],
)
def test_ready_requires_exact_commit_protocol_capability_and_preflight(
    git_repo, final_health, preflight, error_code
) -> None:
    final_health = {
        key: git_repo.origin_main if value == "TARGET" else value
        for key, value in final_health.items()
    }
    client = FakeWorkerClient(
        health_results=[_health("a" * 40), final_health],
        status_results=[{"state": "ready"}],
        preflight_result=preflight,
    )

    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator().ensure_worker_compatible(
            client, git_repo.path
        )

    assert caught.value.code == error_code


def test_same_target_callers_join_one_coordinator_operation(git_repo) -> None:
    entered_status = threading.Event()
    release_status = threading.Event()

    class BlockingClient(FakeWorkerClient):
        def update_status(self, *, timeout: float | None = None) -> dict[str, Any]:
            self.status_calls += 1
            self.status_timeouts.append(timeout)
            entered_status.set()
            assert release_status.wait(2)
            return {
                "state": "ready",
                "request_id": "request-1",
                "target_commit": self.update_requests[-1],
                "timestamp": "2026-08-01T00:00:00+00:00",
            }

    client = BlockingClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)]
    )
    coordinator = NvidiaWorkerUpdateCoordinator()
    results: list[Any] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(
                coordinator.ensure_worker_compatible(client, git_repo.path)
            )
        except BaseException as error:  # pragma: no cover - assertion below reports it
            errors.append(error)

    first = threading.Thread(target=run)
    second = threading.Thread(target=run)
    first.start()
    assert entered_status.wait(2)
    second.start()
    second.join(0.05)
    assert second.is_alive(), "the second caller did not join the active update"
    release_status.set()
    first.join(2)
    second.join(2)

    assert errors == []
    assert len(results) == 2
    assert client.update_requests == [git_repo.origin_main]
    assert client.status_calls == 1


def test_background_start_is_nonblocking_and_reuses_one_thread(git_repo) -> None:
    entered_health = threading.Event()
    release_health = threading.Event()

    class BlockingHealthClient(FakeWorkerClient):
        def health(self, *, timeout: float | None = None) -> dict[str, Any]:
            entered_health.set()
            assert release_health.wait(2)
            return super().health(timeout=timeout)

    client = BlockingHealthClient(
        health_results=[_health(git_repo.origin_main)]
    )
    coordinator = NvidiaWorkerUpdateCoordinator()

    first = coordinator.start_background(client, git_repo.path, timeout=1800)
    assert entered_health.wait(2)
    second = coordinator.start_background(client, git_repo.path, timeout=1800)

    assert first is second
    assert first.is_alive()
    release_health.set()
    first.join(2)
    assert not first.is_alive()


def test_worker_client_update_apis_use_fixed_authenticated_routes(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    class Response:
        @staticmethod
        def json() -> dict[str, Any]:
            return {"request_id": "request-1", "status": "queued"}

    def request(method: str, path: str, **kwargs: Any):
        calls.append((method, path, kwargs))
        return Response()

    monkeypatch.setattr(client, "_request", request)

    assert client.request_update("a" * 40)["request_id"] == "request-1"
    client.update_status()

    assert calls == [
        ("POST", "/v1/admin/update", {"json": {"target_commit": "a" * 40}}),
        ("GET", "/v1/admin/update/status", {}),
    ]


def test_worker_client_restart_apis_use_fixed_routes_without_command_or_path(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)
    calls = []

    class Response:
        def json(self):
            return {"request_id": "restart-1", "state": "queued"}

    monkeypatch.setattr(client, "_request", lambda method, path, **kwargs: calls.append((method, path, kwargs)) or Response())
    assert client.request_restart() == {"request_id": "restart-1", "state": "queued"}
    client.restart_status("restart-1")
    assert calls == [
        ("POST", "/v1/admin/restart", {"json": {}}),
        ("GET", "/v1/admin/restart/status", {"params": {"request_id": "restart-1"}}),
    ]


def test_protocol_one_has_explicit_bootstrap_migration_error(git_repo) -> None:
    client = FakeWorkerClient(health_results=[_health("a" * 40, protocol_version=1, update_capability=0)])
    with pytest.raises(WorkerUpdateError) as caught:
        NvidiaWorkerUpdateCoordinator().ensure_worker_compatible(client, git_repo.path)
    assert caught.value.code == "WORKER_BOOTSTRAP_MIGRATION_REQUIRED"


def test_worker_client_caps_coordinator_timeout_at_configured_timeout(
    monkeypatch,
) -> None:
    constructed_timeouts: list[float] = []

    class Response:
        @staticmethod
        def json() -> dict[str, Any]:
            return {"state": "queued"}

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Client:
        def __init__(self, *, timeout: float) -> None:
            constructed_timeouts.append(timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        @staticmethod
        def request(*_args, **_kwargs) -> Response:
            return Response()

    monkeypatch.setattr(nvidia_worker.httpx, "Client", Client)
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)

    client.health(timeout=90)
    client.update_status(timeout=4)
    client.preflight([], timeout=2.5)

    assert constructed_timeouts == [10, 4, 2.5]


@pytest.mark.parametrize("timeout", [True, 0, -1])
def test_worker_client_rejects_invalid_timeout_override(timeout) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)

    with pytest.raises(ValueError, match="timeout override must be positive"):
        client.health(timeout=timeout)


@pytest.mark.parametrize(
    "timeout",
    [True, False, float("nan"), float("inf"), float("-inf"), -1, 0],
)
def test_worker_client_rejects_invalid_configured_timeout(timeout) -> None:
    with pytest.raises(ValueError, match="configured timeout must be positive"):
        nvidia_worker.NvidiaWorkerClient("http://worker", timeout)


@pytest.mark.parametrize("corrupt_timeout", [float("nan"), float("inf"), 0])
def test_worker_request_revalidates_effective_timeout_before_http(
    monkeypatch, corrupt_timeout
) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)
    client._timeout_submit = corrupt_timeout
    monkeypatch.setattr(
        nvidia_worker.httpx,
        "Client",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("HTTP client constructed with invalid timeout")
        ),
    )

    with pytest.raises(ValueError, match="configured timeout must be positive"):
        client.health(timeout=1)


def test_worker_submission_waits_for_update_then_submits_exactly_once(
    monkeypatch,
) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)
    events: list[str] = []
    monkeypatch.setattr(
        nvidia_worker,
        "get_settings",
        lambda: SimpleNamespace(
            nvidia_worker_auto_update=True,
            nvidia_worker_update_timeout=1800,
        ),
    )
    monkeypatch.setattr(
        nvidia_worker,
        "ensure_worker_compatible",
        lambda selected, **kwargs: events.append("update")
        if selected is client and kwargs["timeout"] == 1800
        else None,
    )
    monkeypatch.setattr(
        client,
        "_submit_prompt_once",
        lambda prompt, *, client_id=None, extra_data=None: events.append("submit")
        or "prompt-1",
    )

    result = client.submit_prompt({"1": {"class_type": "KSampler"}})

    assert result == "prompt-1"
    assert events == ["update", "submit"]


def test_worker_submission_update_failure_has_no_submit_or_local_fallback(
    monkeypatch,
) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", 10)
    submitted = 0
    monkeypatch.setattr(
        nvidia_worker,
        "get_settings",
        lambda: SimpleNamespace(
            nvidia_worker_auto_update=True,
            nvidia_worker_update_timeout=1800,
        ),
    )

    def fail_update(*_args, **_kwargs):
        raise WorkerUpdateError("WORKER_UPDATE_TIMEOUT", "Worker update timed out.")

    def submit_once(*_args, **_kwargs):
        nonlocal submitted
        submitted += 1
        return "unexpected"

    monkeypatch.setattr(nvidia_worker, "ensure_worker_compatible", fail_update)
    monkeypatch.setattr(client, "_submit_prompt_once", submit_once)
    monkeypatch.setattr(
        nvidia_worker,
        "get_comfy_client",
        lambda: (_ for _ in ()).throw(AssertionError("local fallback used")),
    )

    with pytest.raises(WorkerUpdateError, match="WORKER_UPDATE_TIMEOUT"):
        client.submit_prompt({})

    assert submitted == 0


def test_settings_default_and_environment_override(monkeypatch) -> None:
    from app.config import Settings

    defaults = Settings(_env_file=None)
    assert defaults.nvidia_worker_auto_update is False
    assert defaults.nvidia_worker_update_timeout == 1800.0

    monkeypatch.setenv("NVIDIA_WORKER_AUTO_UPDATE", "true")
    monkeypatch.setenv("NVIDIA_WORKER_UPDATE_TIMEOUT", "42")
    configured = Settings(_env_file=None)
    assert configured.nvidia_worker_auto_update is True
    assert configured.nvidia_worker_update_timeout == 42.0


@pytest.mark.parametrize(
    "field",
    ["nvidia_worker_timeout", "nvidia_worker_update_timeout"],
)
@pytest.mark.parametrize(
    "value",
    [True, False, float("nan"), float("inf"), float("-inf"), -1, 0],
)
def test_settings_reject_invalid_worker_timeouts(field, value) -> None:
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_settings_accept_normal_numeric_strings_from_environment(monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setenv("NVIDIA_WORKER_TIMEOUT", "2.5")
    monkeypatch.setenv("NVIDIA_WORKER_UPDATE_TIMEOUT", "45")

    settings = Settings(_env_file=None)

    assert settings.nvidia_worker_timeout == 2.5
    assert settings.nvidia_worker_update_timeout == 45.0


@pytest.mark.parametrize(
    "timeout",
    [True, False, float("nan"), float("inf"), float("-inf"), -1, 0],
)
def test_coordinator_rejects_non_finite_or_non_positive_deadline(
    git_repo, timeout
) -> None:
    client = FakeWorkerClient(
        health_results=[_health("a" * 40), _health(git_repo.origin_main)]
    )

    with pytest.raises(ValueError, match="timeout must be positive and finite"):
        NvidiaWorkerUpdateCoordinator().ensure_worker_compatible(
            client,
            git_repo.path,
            timeout=timeout,
        )

    assert client.update_requests == []


def test_fastapi_startup_launches_update_check_without_awaiting_it(monkeypatch) -> None:
    from app import main
    from app.db import database

    events: list[str] = []
    monkeypatch.setattr(database, "init_db", lambda: events.append("db"))
    monkeypatch.setattr(main.lora_trainer, "register_on_complete", lambda callback: None)
    monkeypatch.setattr(main.lora_trainer, "ensure_worker", lambda: None)
    monkeypatch.setattr(main, "start_watching", lambda: None)
    monkeypatch.setattr(main, "stop_watching", lambda: None)
    monkeypatch.setattr(main, "start_queue_worker", lambda: None)
    monkeypatch.setattr(main, "stop_queue_worker", lambda: None)
    monkeypatch.setattr(main, "start_comfyui_watcher", lambda: None)
    monkeypatch.setattr(main, "stop_comfyui_watcher", lambda: None)
    monkeypatch.setattr(
        main,
        "start_worker_update_background",
        lambda: events.append("update-background"),
        raising=False,
    )

    async def exercise() -> None:
        context = main.lifespan(main.app)
        await context.__aenter__()
        events.append("serving")
        await context.__aexit__(None, None, None)

    asyncio.run(exercise())

    assert events[:3] == ["db", "update-background", "serving"]


def test_worker_status_exposes_only_safe_coordinator_error(monkeypatch) -> None:
    from app.api import workers

    secret = "Bearer-status-secret"
    monkeypatch.setattr(
        workers,
        "get_settings",
        lambda: SimpleNamespace(
            nvidia_worker_url="http://worker",
            nvidia_worker_token=secret,
            nvidia_worker_timeout=10,
            nvidia_worker_auto_update=True,
        ),
    )
    worker_client = MagicMock()
    worker_client.health.side_effect = RuntimeError(secret)
    monkeypatch.setattr(workers, "get_worker_client", lambda: worker_client)
    monkeypatch.setattr(
        workers,
        "worker_update_status",
        lambda: {"state": "error", "error_code": "WORKER_UPDATE_TIMEOUT"},
        raising=False,
    )

    result = workers.worker_status()

    assert result["auto_update"] == {
        "enabled": True,
        "state": "error",
        "error_code": "WORKER_UPDATE_TIMEOUT",
    }
    assert secret not in str(result)
