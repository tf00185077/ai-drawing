from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from app.schemas.lora_train import (
    ComponentIdentity,
    EvidenceValue,
    RecipeCompilationContext,
    RecipePolicySnapshot,
    TrainerCapabilitySnapshot,
    ValidationIssue,
)
from app.services import lora_trainer
from app.services.lora_training_recipe import compile_training_recipe


APPROVED_DATASET_HASH = "dataset-v1"
APPROVED_PROFILE_HASH = "profile-v1"
APPROVED_MODEL_FAMILY = "sdxl"


class _ControlledStopEvent:
    def __init__(self) -> None:
        self.stopped = False

    def is_set(self) -> bool:
        return self.stopped

    def set(self) -> None:
        self.stopped = True

    def wait(self, _timeout: float | None = None) -> bool:
        raise AssertionError("single-job worker unexpectedly became idle")


def _make_job(tmp_path: Path) -> lora_trainer._TrainJob:
    compiled = compile_training_recipe(
        {
            "model": {
                "family": APPROVED_MODEL_FAMILY,
                "checkpoint": "checkpoint.safetensors",
                "allow_unverified_checkpoint": True,
            },
            "dataset": {
                "trigger_token": "alice_token",
                "resolution": 1024,
                "batch_size": 3,
                "keep_tokens": 1,
                "num_repeats": 10,
            },
            "optimization": {
                "epochs": 2,
                "learning_rate": "1e-4",
                "seed": 42,
                "mixed_precision": "fp16",
            },
        },
        context=RecipeCompilationContext(
            dataset_hash=APPROVED_DATASET_HASH,
            profile_hash=APPROVED_PROFILE_HASH,
            profile_model_family=APPROVED_MODEL_FAMILY,
            approved_trigger_token="alice_token",
            image_count=1,
            policy=RecipePolicySnapshot(
                default_checkpoint="checkpoint.safetensors",
                resolution=1024,
                batch_size=1,
                learning_rate="1e-4",
                keep_tokens=1,
                num_repeats=10,
                mixed_precision="fp16",
                network_dim=32,
                network_alpha=16,
            ),
            capability=TrainerCapabilitySnapshot(
                platform="cuda",
                status="verified",
                supported_mixed_precision=("no", "fp16"),
            ),
            component_identities={
                "checkpoint": ComponentIdentity(
                    kind="checkpoint",
                    requested_locator="checkpoint.safetensors",
                    resolved_locator="checkpoint.safetensors",
                    verification_status="unverified",
                    reason="offline worker fixture",
                    bypass_used=True,
                )
            },
        ),
    )
    return lora_trainer._TrainJob(
        job_id="job-locked-validation",
        folder="characters/alice",
        checkpoint="checkpoint.safetensors",
        model_family=APPROVED_MODEL_FAMILY,
        sdxl=True,
        epochs=2,
        submitted_at="2026-07-29T00:00:00Z",
        resolution=1024,
        batch_size=3,
        learning_rate="1e-4",
        class_tokens="alice_token",
        keep_tokens=1,
        num_repeats=10,
        mixed_precision="fp16",
        network_module="networks.lora",
        network_dim=32,
        network_alpha=16,
        dataset_hash=APPROVED_DATASET_HASH,
        profile_hash=APPROVED_PROFILE_HASH,
        normalized_trigger_token="alice_token",
        log_path=str(tmp_path / "job.log"),
        recipe=compiled,
    )


def _run_one_worker_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    outcome: str = "completed",
    current_dataset_hash: str = APPROVED_DATASET_HASH,
    current_profile_hash: str = APPROVED_PROFILE_HASH,
    current_model_family: str = APPROVED_MODEL_FAMILY,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, bool]]:
    lora_root = tmp_path / "lora"
    dataset_dir = lora_root / "characters" / "alice"
    sd_scripts_dir = tmp_path / "sd-scripts"
    dataset_dir.mkdir(parents=True)
    sd_scripts_dir.mkdir()

    if outcome == "completed":
        output_path = lora_root / "output" / "characters_alice.safetensors"
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"trained")

    events: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    lock_state = {"held": False}
    stop_event = _ControlledStopEvent()
    job = _make_job(tmp_path)

    def record(name: str, **details: Any) -> None:
        events.append({"name": name, "lock_held": lock_state["held"], **details})

    def resolve_dataset_dir(folder: str) -> Path:
        record("resolve", folder=folder)
        return dataset_dir

    @contextmanager
    def dataset_lock(folder: str, owner: str = "dataset") -> Iterator[None]:
        record("lock_enter", folder=folder, owner=owner)
        assert not lock_state["held"]
        lock_state["held"] = True
        try:
            yield
        finally:
            record("lock_exit", folder=folder, owner=owner)
            lock_state["held"] = False

    def inspect_dataset(folder: str) -> SimpleNamespace:
        record("inspect", folder=folder)
        return SimpleNamespace(
            folder=folder,
            dataset_hash=current_dataset_hash,
            profile_hash=current_profile_hash,
            profile=SimpleNamespace(model_family=current_model_family),
        )

    def validate_dataset(
        folder: str,
        *,
        trigger_token: str,
        expected_dataset_hash: str | None = None,
        ignore_lock: bool = False,
        **_kwargs: Any,
    ) -> SimpleNamespace:
        record(
            "validate",
            folder=folder,
            trigger_token=trigger_token,
            expected_dataset_hash=expected_dataset_hash,
            ignore_lock=ignore_lock,
        )
        errors = []
        if current_dataset_hash != expected_dataset_hash:
            errors.append(
                ValidationIssue(
                    code="dataset_hash_mismatch",
                    message="dataset hash does not match expected hash",
                    details={
                        "expected_dataset_hash": expected_dataset_hash,
                        "current_dataset_hash": current_dataset_hash,
                    },
                )
            )
        return SimpleNamespace(
            ok=not errors,
            folder=folder,
            normalized_trigger_token=trigger_token,
            dataset_hash=current_dataset_hash,
            image_count=1,
            caption_count=1,
            missing_caption_count=0,
            warnings=[],
            errors=errors,
            locked=False,
        )

    def compute_dataset_hash(folder: str) -> str:
        record("compute_hash", folder=folder)
        return current_dataset_hash

    class FakeProcess:
        stdout = ["step 1\n"] if outcome == "cancelled" else []
        returncode = 9 if outcome == "failed" else 0

        def terminate(self) -> None:
            record("terminate")

        def wait(self, *_args: Any, **_kwargs: Any) -> int:
            record("wait")
            stop_event.set()
            return self.returncode

    def launch(**kwargs: Any) -> FakeProcess:
        record(
            "launch",
            argv=tuple(kwargs["argv"]),
            sd_scripts_path=kwargs["sd_scripts_path"],
        )
        return FakeProcess()

    def is_cancel_requested(_job_id: str) -> bool:
        record("cancel_check")
        return outcome == "cancelled"

    def update_job(_job_id: str, **fields: Any) -> None:
        updates.append(fields)
        if "execution_evidence_json" in fields:
            record(
                "persist_evidence",
                evidence=json.loads(fields["execution_evidence_json"]),
            )
        if fields.get("status") in lora_trainer.TERMINAL_STATUSES:
            stop_event.set()

    monkeypatch.setattr(
        lora_trainer,
        "get_settings",
        lambda: SimpleNamespace(
            lora_train_dir=str(lora_root),
            sd_scripts_path=str(sd_scripts_dir),
            sd_scripts_python="trainer-python",
        ),
    )
    monkeypatch.setattr(lora_trainer.lora_dataset, "resolve_dataset_dir", resolve_dataset_dir)
    monkeypatch.setattr(lora_trainer.lora_dataset, "dataset_lock", dataset_lock)
    monkeypatch.setattr(lora_trainer.lora_dataset, "inspect_dataset", inspect_dataset)
    monkeypatch.setattr(lora_trainer.lora_dataset, "validate_dataset", validate_dataset)
    monkeypatch.setattr(lora_trainer.lora_dataset, "compute_dataset_hash", compute_dataset_hash)
    monkeypatch.setattr(lora_trainer, "_run_training_subprocess", launch)
    monkeypatch.setattr(
        lora_trainer,
        "select_accelerate_launcher",
        lambda _python: (
            ("trainer-python", "-m", "accelerate", "launch"),
            EvidenceValue(status="verified", value="trainer-python"),
        ),
    )
    monkeypatch.setattr(
        lora_trainer,
        "collect_sd_scripts_revision",
        lambda _path: EvidenceValue(
            status="verified",
            value="a" * 40,
        ),
    )
    monkeypatch.setattr(lora_trainer, "_is_cancel_requested", is_cancel_requested)
    monkeypatch.setattr(lora_trainer, "_update_persistent_job", update_job)
    monkeypatch.setattr(lora_trainer, "_append_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lora_trainer, "get_and_clear_pending_generate", lambda _folder: None)
    def register_output(source: Path, _job_id: str) -> tuple[str, str]:
        record("register", source=str(source))
        return source.name, str(source)

    monkeypatch.setattr(lora_trainer, "_register_output_lora", register_output)
    monkeypatch.setattr(lora_trainer, "_on_complete_callbacks", [])
    monkeypatch.setattr(lora_trainer, "_queue", [job])
    monkeypatch.setattr(lora_trainer, "_running", None)
    monkeypatch.setattr(lora_trainer, "_last_result", None)
    monkeypatch.setattr(lora_trainer, "_stop_event", stop_event)

    lora_trainer._worker_loop()
    return events, updates, lock_state


def _event_names(events: list[dict[str, Any]]) -> list[str]:
    return [event["name"] for event in events]


def _terminal_status(updates: list[dict[str, Any]]) -> str | None:
    for fields in reversed(updates):
        if fields.get("status") in lora_trainer.TERMINAL_STATUSES:
            return str(fields["status"])
    return None


def test_worker_revalidates_approved_identity_and_family_after_lock_before_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, updates, lock_state = _run_one_worker_job(monkeypatch, tmp_path)
    names = _event_names(events)

    required_order = [
        "lock_enter",
        "resolve",
        "inspect",
        "validate",
        "persist_evidence",
        "launch",
        "wait",
        "register",
        "lock_exit",
    ]
    assert all(name in names for name in required_order)
    assert [names.index(name) for name in required_order] == sorted(names.index(name) for name in required_order)
    assert all(
        event["lock_held"]
        for event in events
        if event["name"] in {
            "resolve",
            "inspect",
            "validate",
            "persist_evidence",
            "launch",
            "wait",
            "register",
        }
    )

    validation = next(event for event in events if event["name"] == "validate")
    assert validation["expected_dataset_hash"] == APPROVED_DATASET_HASH
    assert validation["trigger_token"] == "alice_token"
    assert validation["ignore_lock"] is True
    assert _terminal_status(updates) == "completed"
    assert lock_state["held"] is False

    evidence_event = next(
        event for event in events if event["name"] == "persist_evidence"
    )
    launch_event = next(event for event in events if event["name"] == "launch")
    assert tuple(evidence_event["evidence"]["argv"]) == launch_event["argv"]
    assert evidence_event["evidence"]["dataset_config_content"].startswith(
        "[general]\n"
    )
    assert len(evidence_event["evidence"]["dataset_config_sha256"]) == 64


@pytest.mark.parametrize(
    ("current_dataset_hash", "current_profile_hash", "expected_error_code"),
    [
        ("dataset-v2", APPROVED_PROFILE_HASH, "dataset_hash_mismatch"),
        (APPROVED_DATASET_HASH, "profile-v2", "profile_hash_mismatch"),
    ],
    ids=["dataset-hash-stale", "profile-hash-stale"],
)
def test_worker_rejects_stale_queued_approval_inside_lock_without_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    current_dataset_hash: str,
    current_profile_hash: str,
    expected_error_code: str,
) -> None:
    events, updates, lock_state = _run_one_worker_job(
        monkeypatch,
        tmp_path,
        current_dataset_hash=current_dataset_hash,
        current_profile_hash=current_profile_hash,
    )

    assert "launch" not in _event_names(events)
    assert "lock_enter" in _event_names(events)
    assert all(
        event["lock_held"]
        for event in events
        if event["name"] in {"resolve", "inspect", "validate", "compute_hash"}
    )
    assert any(
        fields.get("status") == "failed" and fields.get("error_code") == expected_error_code
        for fields in updates
    )
    terminal_update = next(
        fields
        for fields in reversed(updates)
        if fields.get("status") == "failed"
    )
    expected_current_key = (
        "current_dataset_hash"
        if expected_error_code == "dataset_hash_mismatch"
        else "current_profile_hash"
    )
    assert terminal_update["error_details"][expected_current_key] in {
        current_dataset_hash,
        current_profile_hash,
    }
    assert lock_state["held"] is False


def test_worker_rejects_locked_profile_family_mismatch_without_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, updates, lock_state = _run_one_worker_job(
        monkeypatch,
        tmp_path,
        current_model_family="sd15",
    )

    assert "validate" in _event_names(events)
    assert "launch" not in _event_names(events)
    assert any(
        fields.get("status") == "failed" and fields.get("error_code") == "model_family_mismatch"
        for fields in updates
    )
    assert lock_state["held"] is False


@pytest.mark.parametrize("outcome", ["completed", "failed", "cancelled"])
def test_worker_holds_training_lock_through_subprocess_and_releases_on_terminal_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    outcome: str,
) -> None:
    events, updates, lock_state = _run_one_worker_job(monkeypatch, tmp_path, outcome=outcome)
    names = _event_names(events)

    assert _terminal_status(updates) == outcome
    assert names.index("lock_enter") < names.index("launch") < names.index("wait") < names.index("lock_exit")
    assert all(
        event["lock_held"]
        for event in events
        if event["name"] in {"launch", "terminate", "wait", "cancel_check"}
    )
    assert lock_state["held"] is False
