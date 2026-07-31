"""Behavior tests for the durable Windows worker updater state machine."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest

import worker.windows.update_contract as worker_update_contract
import worker.windows.updater.request_lock as request_lock
from worker.windows.update_contract import (
    UpdateAlreadyRunning as WorkerUpdateAlreadyRunning,
    atomic_write_json as worker_atomic_write_json,
    queue_update,
)
from worker.windows.updater.state import (
    ActiveUpdateRequest,
    InvalidUpdateTransition,
    StateStoreError,
    UpdateAlreadyRunning,
    UpdateStateStore,
)


@contextmanager
def _hold_request_file_lock(request_path: Path) -> Iterator[None]:
    lock_path = request_path.with_name("update-request.lock")
    ready_path = request_path.with_name("child-lock-ready")
    release_path = request_path.with_name("child-lock-release")
    script = r'''import os, pathlib, sys, time
lock_path, ready_path, release_path = map(pathlib.Path, sys.argv[1:])
lock_path.parent.mkdir(parents=True, exist_ok=True)
with lock_path.open("a+b") as lock_file:
    lock_file.seek(0)
    if not lock_file.read(1):
        lock_file.seek(0); lock_file.write(b"0"); lock_file.flush()
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    ready_path.write_text("ready", encoding="utf-8")
    while not release_path.exists():
        time.sleep(0.01)
    lock_file.seek(0)
    if os.name == "nt":
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
'''
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(lock_path), str(ready_path), str(release_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5
    while not ready_path.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(process.stderr.read() if process.stderr else "lock child failed")
        time.sleep(0.01)
    if not ready_path.exists():
        process.kill()
        raise AssertionError("lock child did not acquire the request lock")
    try:
        yield
    finally:
        release_path.touch()
        process.wait(timeout=5)
        ready_path.unlink(missing_ok=True)
        release_path.unlink(missing_ok=True)


def _write_request(path: Path, request_id: str, target_commit: str) -> None:
    worker_atomic_write_json(
        path,
        {
            "request_id": request_id,
            "target_commit": target_commit,
            "timestamp": "2026-08-01T00:00:00+00:00",
        },
    )


def test_os_request_lock_times_out_with_safe_typed_error(tmp_path: Path) -> None:
    request_path = tmp_path / "update-request.json"
    with _hold_request_file_lock(request_path):
        with pytest.raises(request_lock.RequestLockTimeout) as raised:
            with request_lock.exclusive_request_lock(request_path, timeout=0.1):
                pytest.fail("contended OS lock must not be acquired")

    assert str(raised.value) == "update request lock timed out"
    assert str(tmp_path) not in str(raised.value)


def test_os_request_lock_release_before_deadline_allows_progress(tmp_path: Path) -> None:
    request_path = tmp_path / "update-request.json"
    entered = threading.Event()
    errors: list[BaseException] = []

    def acquire() -> None:
        try:
            with request_lock.exclusive_request_lock(request_path, timeout=2):
                entered.set()
        except BaseException as error:
            errors.append(error)

    with _hold_request_file_lock(request_path):
        thread = threading.Thread(target=acquire)
        thread.start()
        assert not entered.wait(timeout=0.2)
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []
    assert entered.is_set()


def test_thread_request_lock_contention_uses_same_deadline(tmp_path: Path) -> None:
    request_path = tmp_path / "update-request.json"
    finished = threading.Event()
    errors: list[BaseException] = []

    def acquire() -> None:
        try:
            with request_lock.exclusive_request_lock(request_path, timeout=0.1):
                pytest.fail("contended thread lock must not be acquired")
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()

    with request_lock.exclusive_request_lock(request_path):
        thread = threading.Thread(target=acquire)
        thread.start()
        assert finished.wait(timeout=1)
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], request_lock.RequestLockTimeout)
    assert str(errors[0]) == "update request lock timed out"


def test_queue_replaces_request_before_publishing_queued_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path = tmp_path / "update-request.json"
    status_path = tmp_path / "update-status.json"
    _write_request(request_path, "old-request", "0" * 40)
    worker_atomic_write_json(status_path, {"state": "ready"})
    writes: list[str] = []
    real_write = worker_update_contract.atomic_write_json

    def record_write(path: Path, value: dict[str, Any]) -> None:
        writes.append(path.name)
        real_write(path, value)

    monkeypatch.setattr(worker_update_contract, "atomic_write_json", record_write)

    queue_update(request_path, status_path, "a" * 40)

    assert writes == ["update-request.json", "update-status.json"]


def test_failed_request_replace_never_publishes_queued_with_old_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path = tmp_path / "update-request.json"
    status_path = tmp_path / "update-status.json"
    _write_request(request_path, "old-request", "0" * 40)
    worker_atomic_write_json(status_path, {"state": "ready"})
    real_write = worker_update_contract.atomic_write_json

    def fail_request(path: Path, value: dict[str, Any]) -> None:
        if path == request_path:
            raise OSError("simulated request replace failure")
        real_write(path, value)

    monkeypatch.setattr(worker_update_contract, "atomic_write_json", fail_request)

    with pytest.raises(OSError):
        queue_update(request_path, status_path, "a" * 40)

    assert json.loads(request_path.read_text(encoding="utf-8"))["request_id"] == "old-request"
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"state": "ready"}


def test_failed_status_publish_is_retryable_without_losing_or_replacing_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path = tmp_path / "update-request.json"
    status_path = tmp_path / "update-status.json"
    _write_request(request_path, "old-request", "0" * 40)
    worker_atomic_write_json(status_path, {"state": "ready"})

    def fail_status(_path: Path, _state: str) -> None:
        raise OSError("simulated status publish failure")

    monkeypatch.setattr(worker_update_contract, "_write_update_status_unlocked", fail_status)
    with pytest.raises(OSError):
        queue_update(request_path, status_path, "a" * 40)
    pending = json.loads(request_path.read_text(encoding="utf-8"))
    assert pending["target_commit"] == "a" * 40
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"state": "ready"}

    monkeypatch.undo()
    retried_id = queue_update(request_path, status_path, "a" * 40)
    assert retried_id == pending["request_id"]
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"state": "queued"}


def test_different_target_replaces_only_unaccepted_request_after_publish_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_path = tmp_path / "update-request.json"
    status_path = tmp_path / "update-status.json"
    _write_request(request_path, "old-request", "0" * 40)
    worker_atomic_write_json(status_path, {"state": "ready"})
    real_publish = worker_update_contract._write_update_status_unlocked
    monkeypatch.setattr(
        worker_update_contract,
        "_write_update_status_unlocked",
        lambda _path, _state: (_ for _ in ()).throw(OSError("publish failed")),
    )
    with pytest.raises(OSError):
        queue_update(request_path, status_path, "a" * 40)
    unaccepted = json.loads(request_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(worker_update_contract, "_write_update_status_unlocked", real_publish)
    accepted_id = queue_update(request_path, status_path, "b" * 40)
    accepted = json.loads(request_path.read_text(encoding="utf-8"))
    assert accepted_id != unaccepted["request_id"]
    assert accepted == {
        "request_id": accepted_id,
        "target_commit": "b" * 40,
        "timestamp": accepted["timestamp"],
    }
    assert json.loads(status_path.read_text(encoding="utf-8")) == {"state": "queued"}


def test_state_machine_rejects_skipped_activation(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)

    with pytest.raises(InvalidUpdateTransition):
        store.transition("ready")


def test_state_machine_allows_only_the_declared_activation_path(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)

    for state in ("fetching", "staging", "installing", "validating", "activating", "restarting", "ready"):
        store.transition(state)

    assert store.read_public() == {"state": "ready"}


def test_queue_is_idempotent_for_the_same_request_and_commit(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)

    first = store.queue("request-1", "a" * 40)
    second = store.queue("request-1", "a" * 40)

    assert second == first
    assert json.loads(store.private_path.read_text(encoding="utf-8"))["request_id"] == "request-1"
    with pytest.raises(UpdateAlreadyRunning):
        store.queue("request-2", "b" * 40)


def test_queue_same_target_returns_stored_request_id_and_repairs_missing_public_status(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    stored_request_id = store.queue("request-1", "a" * 40)
    store.public_path.unlink()

    retried_request_id = store.queue("retry-with-a-different-request-id", "a" * 40)

    assert retried_request_id == stored_request_id
    assert json.loads(store.public_path.read_text(encoding="utf-8")) == {"state": "queued"}


def test_read_public_repairs_stale_public_projection_from_private_state(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")
    store.public_path.write_text('{"state":"queued"}', encoding="utf-8")

    assert store.read_public() == {"state": "fetching"}
    assert json.loads(store.public_path.read_text(encoding="utf-8")) == {"state": "fetching"}


def test_malformed_private_state_fails_closed_instead_of_queueing_over_it(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.private_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(StateStoreError):
        store.queue("req", "a" * 40)


def test_unreadable_private_state_fails_closed_instead_of_queueing_over_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("existing", "a" * 40)
    original_read_text = Path.read_text

    def unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == store.private_path:
            raise PermissionError("access denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)

    with pytest.raises(StateStoreError):
        store.queue("req", "b" * 40)


def test_public_state_redacts_secret_and_command(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("Bearer super-secret TOKEN=do-not-publish", "a" * 40)
    store.transition("fetching")
    store.fail("RUNTIME_INSTALL_FAILED", "safe message; command TOKEN Bearer super-secret")

    text = store.public_path.read_text(encoding="utf-8")
    assert "Bearer" not in text
    assert "TOKEN" not in text
    assert "command" not in text.casefold()
    assert json.loads(text) == {"state": "failed_before_activation", "error_code": "RUNTIME_INSTALL_FAILED"}


@pytest.mark.parametrize(
    "error_code",
    [
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
    ],
)
def test_public_state_exposes_each_canonical_error_code(tmp_path: Path, error_code: str) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")
    store.fail(error_code, "safe private diagnostic")

    assert store.read_public() == {"state": "failed_before_activation", "error_code": error_code}


def test_public_state_maps_unknown_error_codes_to_update_failed(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")
    store.fail("TOKEN_SECRET", "safe private diagnostic")

    assert store.read_public() == {"state": "failed_before_activation", "error_code": "UPDATE_FAILED"}
    assert json.loads(store.private_path.read_text(encoding="utf-8"))["error_code"] == "UPDATE_FAILED"


def test_each_state_write_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")

    assert json.loads(store.private_path.read_text(encoding="utf-8"))["state"] == "fetching"
    assert json.loads(store.public_path.read_text(encoding="utf-8")) == {"state": "fetching"}
    assert not list(tmp_path.glob("*.tmp"))


def test_read_active_request_returns_a_locked_typed_snapshot(tmp_path: Path) -> None:
    """Returning raw private JSON or omitting the current state must make this test fail."""
    store = UpdateStateStore(tmp_path)
    store.queue("request-1", "a" * 40)
    store.transition("fetching")

    assert store.read_active_request() == ActiveUpdateRequest(
        request_id="request-1",
        target_commit="a" * 40,
        state="fetching",
    )


def test_terminal_failure_records_rollback_code_and_redacts_private_message(tmp_path: Path) -> None:
    """Losing the rolled-back code or persisting an exception token must make this test fail."""
    store = UpdateStateStore(tmp_path)
    store.queue("request-1", "a" * 40)
    for state in ("fetching", "staging", "installing", "validating", "activating", "restarting"):
        store.transition(state)

    store.terminal_failure(
        "rolled_back",
        "ACTIVATION_FAILED_ROLLED_BACK",
        "https://alice:password@example.test Bearer very-secret TOKEN=also-secret failed",
    )

    private = json.loads(store.private_path.read_text(encoding="utf-8"))
    assert private["state"] == "rolled_back"
    assert private["error_code"] == "ACTIVATION_FAILED_ROLLED_BACK"
    assert "alice" not in private["error_message"]
    assert "very-secret" not in private["error_message"]
    assert "also-secret" not in private["error_message"]
    assert store.read_public() == {
        "state": "rolled_back",
        "error_code": "ACTIVATION_FAILED_ROLLED_BACK",
    }


def test_claim_queued_request_validates_fixed_request_shape_and_queues_it(tmp_path: Path) -> None:
    """Letting the CLI consume an untyped request dictionary must make this test fail."""
    store = UpdateStateStore(tmp_path / "state")
    request_path = tmp_path / "state" / "update-request.json"
    request_path.parent.mkdir(parents=True)
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "target_commit": "a" * 40,
                "timestamp": "2026-08-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    assert store.claim_queued_request(request_path) == ActiveUpdateRequest(
        request_id="request-1", target_commit="a" * 40, state="queued"
    )


def test_claim_terminal_request_is_durable_noop_and_new_id_can_queue(tmp_path: Path) -> None:
    """A scheduled retry must not replay a terminal request, while a new ID remains actionable."""
    store = UpdateStateStore(tmp_path)
    request_path = tmp_path / "update-request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "target_commit": "a" * 40,
                "timestamp": "2026-08-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    store.claim_queued_request(request_path)
    for state in ("fetching", "staging", "installing", "validating", "activating", "restarting", "ready"):
        store.transition(state)

    assert store.claim_queued_request(request_path) is None
    assert request_path.exists()
    assert store.read_public() == {"state": "ready"}

    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-2",
                "target_commit": "b" * 40,
                "timestamp": "2026-08-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    assert store.claim_queued_request(request_path) == ActiveUpdateRequest(
        request_id="request-2", target_commit="b" * 40, state="queued"
    )


@pytest.mark.parametrize(
    ("request_id", "target_commit"),
    [("request-2", "a" * 40), ("request-1", "b" * 40)],
)
def test_claim_rejects_request_inconsistent_with_active_private_state(
    tmp_path: Path, request_id: str, target_commit: str
) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("request-1", "a" * 40)
    request_path = tmp_path / "update-request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": request_id,
                "target_commit": target_commit,
                "timestamp": "2026-08-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(StateStoreError):
        store.claim_queued_request(request_path)


def test_claim_reads_request_only_after_acquiring_shared_request_lock(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    request_path = tmp_path / "update-request.json"
    _write_request(request_path, "request-old", "a" * 40)
    finished = threading.Event()
    result: list[ActiveUpdateRequest | None] = []
    errors: list[BaseException] = []

    def claim() -> None:
        try:
            result.append(store.claim_queued_request(request_path))
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()

    with _hold_request_file_lock(request_path):
        thread = threading.Thread(target=claim)
        thread.start()
        was_blocked = not finished.wait(timeout=0.25)
        _write_request(request_path, "request-new", "b" * 40)
    thread.join(timeout=5)

    assert errors == []
    assert was_blocked
    assert not thread.is_alive()
    assert result == [
        ActiveUpdateRequest("request-new", "b" * 40, "queued")
    ]


def test_two_writers_and_claimer_share_one_request_lock_without_losing_acceptance(
    tmp_path: Path,
) -> None:
    store = UpdateStateStore(tmp_path)
    request_path = tmp_path / "update-request.json"
    status_path = tmp_path / "update-status.json"
    store.queue("request-terminal", "0" * 40)
    for state in ("fetching", "staging", "installing", "validating", "activating", "restarting", "ready"):
        store.transition(state)
    _write_request(request_path, "request-terminal", "0" * 40)

    gate = threading.Barrier(4)
    finished = [threading.Event() for _ in range(3)]
    accepted: list[tuple[str, str]] = []
    writer_errors: list[BaseException] = []
    claim_errors: list[BaseException] = []

    def writer(index: int, target: str) -> None:
        gate.wait()
        try:
            accepted.append((queue_update(request_path, status_path, target), target))
        except BaseException as error:
            writer_errors.append(error)
        finally:
            finished[index].set()

    def claim() -> None:
        gate.wait()
        try:
            store.claim_queued_request(request_path)
        except BaseException as error:
            claim_errors.append(error)
        finally:
            finished[2].set()

    threads = [
        threading.Thread(target=writer, args=(0, "a" * 40)),
        threading.Thread(target=writer, args=(1, "b" * 40)),
        threading.Thread(target=claim),
    ]
    with _hold_request_file_lock(request_path):
        for thread in threads:
            thread.start()
        gate.wait()
        all_blocked = all(not event.wait(timeout=0.1) for event in finished)
    for thread in threads:
        thread.join(timeout=5)

    assert all_blocked
    assert all(not thread.is_alive() for thread in threads)
    assert len(accepted) == 1
    assert len(writer_errors) == 1
    assert isinstance(writer_errors[0], WorkerUpdateAlreadyRunning)
    assert claim_errors == []
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert (request["request_id"], request["target_commit"]) == accepted[0]
    active = store.claim_queued_request(request_path)
    assert active is not None
    assert (active.request_id, active.target_commit) == accepted[0]


@pytest.mark.parametrize(
    "request_payload",
    [
        {"request_id": "request-1", "target_commit": "a" * 40},
        {
            "request_id": "request-1",
            "target_commit": "a" * 40,
            "timestamp": "now",
            "command": "whoami",
        },
        {"request_id": "", "target_commit": "a" * 40, "timestamp": "now"},
        {"request_id": "request-1", "target_commit": "HEAD", "timestamp": "now"},
    ],
)
def test_claim_queued_request_rejects_missing_extra_or_invalid_fields(
    tmp_path: Path, request_payload: dict[str, str]
) -> None:
    """Accepting a path/command selector or malformed metadata must make this test fail."""
    store = UpdateStateStore(tmp_path)
    request_path = tmp_path / "update-request.json"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(json.dumps(request_payload), encoding="utf-8")

    with pytest.raises(StateStoreError):
        store.claim_queued_request(request_path)
