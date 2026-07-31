"""Behavior tests for the durable Windows worker updater state machine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from worker.windows.updater.state import (
    InvalidUpdateTransition,
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


def test_each_state_write_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    store.transition("fetching")

    assert json.loads(store.private_path.read_text(encoding="utf-8"))["state"] == "fetching"
    assert json.loads(store.public_path.read_text(encoding="utf-8")) == {"state": "fetching"}
    assert not list(tmp_path.glob("*.tmp"))
