"""Security regressions for the explicit LoRA training start boundary."""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.schemas.lora_train import (
    DatasetInspectResponse,
    DatasetProfileSummary,
    DatasetValidateResponse,
)
from app.services import lora_dataset, lora_trainer


DATASET_HASH = "a" * 64
PROFILE_HASH = "b" * 64


def _write_trainable_dataset(dataset_dir: Path, *, image_count: int = 2) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    for index in range(image_count):
        (dataset_dir / f"{index}.png").write_bytes(b"image")
        (dataset_dir / f"{index}.txt").write_text("sks, subject", encoding="utf-8")
    (dataset_dir / ".lora-dataset.json").write_text(
        (
            '{"type":"character","trigger_token":"sks",'
            '"caption_profile":"wd_tags","model_family":"sd15"}'
        ),
        encoding="utf-8",
    )


def _trainer_settings(base: Path, tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        lora_train_dir=str(base),
        lora_train_logs_dir=str(tmp_path / "logs"),
        lora_train_threshold=2,
        lora_default_checkpoint="org/model",
        lora_model_family="sd15",
        lora_sdxl=False,
        lora_checkpoint_dirs="",
        comfyui_checkpoints_dir="",
        sd_scripts_path=str(tmp_path / "sd-scripts"),
        lora_resolution=512,
        lora_batch_size=1,
        lora_learning_rate="1e-4",
        lora_class_tokens="sks",
        lora_keep_tokens=1,
        lora_num_repeats=1,
        lora_mixed_precision="fp16",
        lora_network_dim=4,
        lora_network_alpha=4,
        lora_save_every_n_epochs=1,
        sd_scripts_python="",
    )


def _approved_inspection(folder: str) -> DatasetInspectResponse:
    return DatasetInspectResponse(
        folder=folder,
        image_count=2,
        caption_count=2,
        missing_caption_count=0,
        dataset_hash=DATASET_HASH,
        profile_hash=PROFILE_HASH,
        profile=DatasetProfileSummary(
            present=True,
            valid=True,
            dataset_type="character",
            trigger_token="sks",
            caption_profile="wd_tags",
            model_family="sd15",
            profile_hash=PROFILE_HASH,
        ),
        locked=False,
        files=[],
        trigger_token_candidates=["sks"],
    )


def _approved_validation(folder: str) -> DatasetValidateResponse:
    return DatasetValidateResponse(
        ok=True,
        folder=folder,
        normalized_trigger_token="sks",
        dataset_hash=DATASET_HASH,
        image_count=2,
        caption_count=2,
        missing_caption_count=0,
        warnings=[],
        errors=[],
        locked=False,
    )


def _assert_enqueue_rejects_escaped_folder(
    folder: str,
    *,
    base: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise enqueue while keeping unrelated approval/runtime gates valid."""
    settings = _trainer_settings(base, tmp_path)
    create_persistent_job = Mock()

    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(
        lora_dataset,
        "inspect_dataset",
        lambda candidate: _approved_inspection(candidate),
    )
    monkeypatch.setattr(
        lora_dataset,
        "validate_dataset",
        lambda candidate, **_kwargs: _approved_validation(candidate),
    )
    monkeypatch.setattr(lora_trainer, "_validate_trainer_runtime", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lora_trainer, "_create_persistent_job", create_persistent_job)
    monkeypatch.setattr(lora_trainer, "_log_path", lambda _job_id: str(tmp_path / "job.log"))
    monkeypatch.setattr(lora_trainer, "_append_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    monkeypatch.setattr(lora_trainer, "_queue", deque())
    monkeypatch.setattr(lora_trainer, "_running", None)

    with pytest.raises(lora_trainer.TrainerServiceError) as exc_info:
        lora_trainer.enqueue(
            folder,
            expected_dataset_hash=DATASET_HASH,
            expected_profile_hash=PROFILE_HASH,
            recipe={
                "model": {
                    "family": "sd15",
                    "checkpoint": "org/model",
                    "allow_unverified_checkpoint": True,
                },
                "dataset": {"trigger_token": "sks"},
            },
        )

    assert exc_info.value.code == "invalid_dataset_folder"
    create_persistent_job.assert_not_called()


def test_enqueue_rejects_absolute_dataset_folder_before_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absolute locator must not escape lora_train_dir or create a durable job."""
    base = tmp_path / "lora_train"
    base.mkdir()
    outside = tmp_path / "outside"
    _write_trainable_dataset(outside)

    _assert_enqueue_rejects_escaped_folder(
        str(outside.resolve()),
        base=base,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


def test_enqueue_rejects_parent_traversal_before_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent traversal locator must be rejected before durable state exists."""
    base = tmp_path / "lora_train"
    base.mkdir()
    outside = tmp_path / "outside"
    _write_trainable_dataset(outside)

    _assert_enqueue_rejects_escaped_folder(
        "../outside",
        base=base,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


@pytest.mark.parametrize("folder", ["/character/miku", "\\character\\miku"])
def test_enqueue_rejects_rooted_dataset_folder_before_persisting(
    folder: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rooted slash forms must not be reinterpreted as relative locators."""
    base = tmp_path / "lora_train"
    base.mkdir()

    _assert_enqueue_rejects_escaped_folder(
        folder,
        base=base,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


def test_enqueue_rejects_symlink_escape_before_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child symlink resolving outside lora_train_dir must not be trainable."""
    base = tmp_path / "lora_train"
    base.mkdir()
    outside = tmp_path / "outside"
    _write_trainable_dataset(outside)
    link = base / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable for this user: {exc}")

    _assert_enqueue_rejects_escaped_folder(
        "escape",
        base=base,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )


def test_enqueue_canonicalizes_relative_backslash_folder_before_validation_and_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equivalent Windows locators must share one stable job/dataset identity."""
    base = tmp_path / "lora_train"
    _write_trainable_dataset(base / "character" / "miku")
    settings = _trainer_settings(base, tmp_path)
    inspect_dataset = Mock(
        side_effect=lambda folder: _approved_inspection(folder),
    )
    validate_dataset = Mock(
        side_effect=lambda folder, **_kwargs: _approved_validation(folder),
    )
    create_persistent_job = Mock()

    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_dataset, "inspect_dataset", inspect_dataset)
    monkeypatch.setattr(lora_dataset, "validate_dataset", validate_dataset)
    monkeypatch.setattr(lora_trainer, "_validate_trainer_runtime", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lora_trainer, "_create_persistent_job", create_persistent_job)
    monkeypatch.setattr(lora_trainer, "_log_path", lambda _job_id: str(tmp_path / "job.log"))
    monkeypatch.setattr(lora_trainer, "_append_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lora_trainer, "_ensure_worker", lambda: None)
    monkeypatch.setattr(lora_trainer, "_queue", deque())
    monkeypatch.setattr(lora_trainer, "_running", None)

    lora_trainer.enqueue(
        "character\\miku",
        expected_dataset_hash=DATASET_HASH,
        expected_profile_hash=PROFILE_HASH,
        recipe={
            "model": {
                "family": "sd15",
                "checkpoint": "org/model",
                "allow_unverified_checkpoint": True,
            },
            "dataset": {"trigger_token": "sks"},
        },
    )

    inspect_dataset.assert_called_once_with("character/miku")
    assert validate_dataset.call_args.args[0] == "character/miku"
    persisted_job = create_persistent_job.call_args.args[0]
    assert persisted_job.folder == "character/miku"
    assert list(lora_trainer._queue)[0].folder == "character/miku"


def test_trigger_check_discovers_eligible_candidates_without_enqueueing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery may recommend Start, but must not create or enqueue a job."""
    base = tmp_path / "lora_train"
    _write_trainable_dataset(base / "eligible")
    settings = _trainer_settings(base, tmp_path)
    enqueue = Mock(return_value="unexpected-job")
    create_persistent_job = Mock()

    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_trainer, "enqueue", enqueue)
    monkeypatch.setattr(lora_trainer, "_create_persistent_job", create_persistent_job)
    monkeypatch.setattr(lora_trainer, "_queue", deque())
    monkeypatch.setattr(lora_trainer, "_running", None)

    result = lora_trainer.trigger_check()

    assert result == {
        "should_trigger": True,
        "candidates": [{"folder": "eligible", "image_count": 2}],
    }
    enqueue.assert_not_called()
    create_persistent_job.assert_not_called()


def test_enqueue_reports_missing_captions_through_structured_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "lora_train"
    dataset_dir = base / "character" / "miku"
    dataset_dir.mkdir(parents=True)
    for index in range(2):
        (dataset_dir / f"{index}.png").write_bytes(b"image")
    (dataset_dir / ".lora-dataset.json").write_text(
        (
            '{"type":"character","trigger_token":"sks",'
            '"caption_profile":"wd_tags","model_family":"sd15"}'
        ),
        encoding="utf-8",
    )
    settings = _trainer_settings(base, tmp_path)

    monkeypatch.setattr(lora_trainer, "get_settings", lambda: settings)
    monkeypatch.setattr(lora_dataset, "get_settings", lambda: settings)
    monkeypatch.setattr(
        lora_trainer,
        "_validate_trainer_runtime",
        lambda *_args, **_kwargs: None,
    )

    inspected = lora_dataset.inspect_dataset("character/miku")
    with pytest.raises(lora_trainer.TrainerServiceError) as exc_info:
        lora_trainer.enqueue(
            "character/miku",
            expected_dataset_hash=inspected.dataset_hash,
            expected_profile_hash=inspected.profile_hash,
            recipe={
                "model": {
                    "family": "sd15",
                    "checkpoint": "org/model",
                    "allow_unverified_checkpoint": True,
                },
                "dataset": {"trigger_token": "sks"},
            },
        )

    assert exc_info.value.code == "missing_caption"
    assert exc_info.value.details["errors"][0]["path"].endswith("0.png")


class _PublicEnqueueCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_names: list[str] = []
        self.calls: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_names.append(node.name)
        self.generic_visit(node)
        self.function_names.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_names.append(node.name)
        self.generic_visit(node)
        self.function_names.pop()

    def visit_Call(self, node: ast.Call) -> None:
        target = node.func
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "enqueue"
            and isinstance(target.value, ast.Name)
            and target.value.id == "lora_trainer"
        ):
            self.calls.append(self.function_names[-1] if self.function_names else "<module>")
        self.generic_visit(node)


def test_start_route_is_the_only_public_lora_trainer_enqueue_trigger() -> None:
    """No discovery or helper API may gain a direct durable enqueue side effect."""
    api_dir = Path(__file__).resolve().parents[1] / "app" / "api"
    public_enqueue_calls: list[tuple[str, str]] = []

    for source_path in sorted(api_dir.glob("*.py")):
        visitor = _PublicEnqueueCallVisitor()
        visitor.visit(ast.parse(source_path.read_text(encoding="utf-8")))
        public_enqueue_calls.extend((source_path.name, name) for name in visitor.calls)

    assert public_enqueue_calls == [("lora_train.py", "start_training")]
