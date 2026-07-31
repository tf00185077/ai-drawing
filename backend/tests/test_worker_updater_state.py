"""Behavior tests for the durable Windows worker updater state machine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from worker.windows.updater.state import (
    InvalidUpdateTransition,
    StateStoreError,
    UpdateAlreadyRunning,
    UpdateStateStore,
)


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


def test_public_state_maps_unknown_error_codes_to_update_failed(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")
    store.fail("TOKEN_SECRET", "safe private diagnostic")

    assert store.read_public() == {"state": "failed_before_activation", "error_code": "UPDATE_FAILED"}


def test_each_state_write_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")

    assert json.loads(store.private_path.read_text(encoding="utf-8"))["state"] == "fetching"
    assert json.loads(store.public_path.read_text(encoding="utf-8")) == {"state": "fetching"}
    assert not list(tmp_path.glob("*.tmp"))
