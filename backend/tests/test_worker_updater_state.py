"""Behavior tests for the durable Windows worker updater state machine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from worker.windows.updater.state import (
    ActiveUpdateRequest,
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
