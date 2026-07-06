"""LoRA dataset discovery, preparation, validation, and locks."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import get_settings
from app.schemas.lora_train import (
    CaptionChange,
    DatasetFileItem,
    DatasetInspectResponse,
    DatasetItem,
    DatasetPrepareResponse,
    DatasetValidateResponse,
    ValidationIssue,
)
from app.services.caption_filter import filter_caption

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_TOKEN_RE = re.compile(r"[^A-Za-z0-9_]+")
_LOCK_GUARD = threading.Lock()
_LOCKS: dict[Path, threading.Lock] = {}
_LOCK_OWNERS: dict[Path, str] = {}


class DatasetServiceError(ValueError):
    """Structured dataset workflow error."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _base_dir() -> Path:
    return Path(get_settings().lora_train_dir).resolve()


def resolve_dataset_dir(folder: str) -> Path:
    """Resolve a dataset folder under lora_train_dir and reject traversal."""
    cleaned = (folder or "").strip().replace("\\", "/").strip("/")
    if not cleaned or ".." in cleaned:
        raise DatasetServiceError("invalid_dataset_folder", "invalid dataset folder")
    if not re.fullmatch(r"[\w\-/]+", cleaned):
        raise DatasetServiceError("invalid_dataset_folder", "invalid dataset folder")
    base = _base_dir()
    path = (base / cleaned).resolve()
    if path != base and _is_relative_to(path, base):
        return path
    raise DatasetServiceError("invalid_dataset_folder", "invalid dataset folder")


def _folder_for_path(path: Path) -> str:
    return path.resolve().relative_to(_base_dir()).as_posix()


def _lock_for(path: Path) -> threading.Lock:
    key = path.resolve()
    with _LOCK_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def is_path_locked(path: Path) -> bool:
    """Return whether a filesystem path is inside a locked dataset."""
    resolved = Path(path).resolve()
    with _LOCK_GUARD:
        locked_keys = [
            key for key, lock in _LOCKS.items()
            if lock.locked() and (resolved == key or _is_relative_to(resolved, key))
        ]
    return bool(locked_keys)


def is_dataset_locked(folder: str) -> bool:
    return is_path_locked(resolve_dataset_dir(folder))


@contextmanager
def dataset_lock(folder: str, owner: str = "dataset") -> Iterator[None]:
    """Non-blocking per-dataset lock context."""
    dataset_dir = resolve_dataset_dir(folder)
    lock = _lock_for(dataset_dir)
    acquired = lock.acquire(blocking=False)
    if not acquired:
        raise DatasetServiceError(
            "dataset_locked",
            "dataset is locked",
            {"folder": folder, "owner": _LOCK_OWNERS.get(dataset_dir)},
        )
    with _LOCK_GUARD:
        _LOCK_OWNERS[dataset_dir] = owner
    try:
        yield
    finally:
        with _LOCK_GUARD:
            _LOCK_OWNERS.pop(dataset_dir, None)
        lock.release()


def _reset_locks_for_test() -> None:
    with _LOCK_GUARD:
        _LOCKS.clear()
        _LOCK_OWNERS.clear()


def normalize_trigger_token(token: str | None) -> str:
    """Sanitize a requested trigger token for caption text and Kohya class_tokens."""
    cleaned = _TOKEN_RE.sub("_", (token or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "sks"


def _parse_caption_tags(caption: str) -> list[str]:
    return [part.strip() for part in caption.split(",") if part.strip()]


def normalize_caption(caption: str, trigger_token: str) -> str:
    """Put trigger_token once at the start and remove duplicates elsewhere."""
    normalized = normalize_trigger_token(trigger_token)
    seen: set[str] = {normalized.lower()}
    tags = [normalized]
    for tag in _parse_caption_tags(caption):
        key = tag.lower()
        if key == normalized.lower() or key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return ", ".join(tags)


def _caption_for_image(image_path: Path) -> Path:
    return image_path.with_suffix(".txt")


def _read_caption(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _collect_files(dataset_dir: Path) -> list[DatasetFileItem]:
    base = _base_dir()
    files: list[DatasetFileItem] = []
    for image in sorted(dataset_dir.iterdir(), key=lambda p: p.name.lower()):
        if not image.is_file() or image.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        caption_path = _caption_for_image(image)
        has_caption = caption_path.exists()
        caption = _read_caption(caption_path) if has_caption else None
        image_rel = image.relative_to(base).as_posix()
        caption_rel = caption_path.relative_to(base).as_posix()
        files.append(
            DatasetFileItem(
                image_path=image_rel,
                caption_path=caption_rel,
                caption=caption,
                has_caption=has_caption,
                caption_empty=has_caption and not (caption or "").strip(),
            )
        )
    return files


def compute_dataset_hash(folder: str) -> str:
    """Hash image/caption membership and caption contents deterministically."""
    dataset_dir = resolve_dataset_dir(folder)
    digest = hashlib.sha256()
    for item in _collect_files(dataset_dir):
        digest.update(item.image_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((item.caption_path or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(b"1" if item.has_caption else b"0")
        digest.update(b"\0")
        digest.update((item.caption or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _trigger_candidates(files: list[DatasetFileItem]) -> list[str]:
    counts: dict[str, int] = {}
    for item in files:
        tags = _parse_caption_tags(item.caption or "")
        if not tags:
            continue
        candidate = normalize_trigger_token(tags[0])
        counts[candidate] = counts.get(candidate, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _summary_from_dir(dataset_dir: Path) -> DatasetItem:
    files = _collect_files(dataset_dir)
    folder = _folder_for_path(dataset_dir)
    caption_count = sum(1 for item in files if item.has_caption)
    return DatasetItem(
        folder=folder,
        image_count=len(files),
        caption_count=caption_count,
        missing_caption_count=len(files) - caption_count,
        dataset_hash=compute_dataset_hash(folder),
        locked=is_path_locked(dataset_dir),
        trigger_token_candidates=_trigger_candidates(files),
    )


def list_datasets() -> list[DatasetItem]:
    """List folders under lora_train_dir that contain trainable images."""
    base = _base_dir()
    if not base.exists() or not base.is_dir():
        return []
    result: list[DatasetItem] = []
    for directory in sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: p.as_posix()):
        if directory.name in {"output", "logs", ".lora_prep_backups"}:
            continue
        files = _collect_files(directory)
        if files:
            result.append(_summary_from_dir(directory))
    return result


def inspect_dataset(folder: str) -> DatasetInspectResponse:
    dataset_dir = resolve_dataset_dir(folder)
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise DatasetServiceError("dataset_not_found", "dataset folder not found")
    files = _collect_files(dataset_dir)
    caption_count = sum(1 for item in files if item.has_caption)
    return DatasetInspectResponse(
        folder=_folder_for_path(dataset_dir),
        image_count=len(files),
        caption_count=caption_count,
        missing_caption_count=len(files) - caption_count,
        dataset_hash=compute_dataset_hash(_folder_for_path(dataset_dir)),
        locked=is_path_locked(dataset_dir),
        files=files,
        trigger_token_candidates=_trigger_candidates(files),
        validation=None,
    )


def _cleanup_caption_with_ai(caption: str, settings) -> str:
    if not getattr(settings, "llm_caption_url", None):
        raise DatasetServiceError("ai_cleanup_not_configured", "llm caption provider is not configured")
    import httpx

    response = httpx.post(
        settings.llm_caption_url,
        json={"caption": caption},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json().get("caption", "")


def _planned_changes(folder: str, trigger_token: str, use_ai_cleanup: bool) -> tuple[str, str, list[CaptionChange]]:
    dataset_dir = resolve_dataset_dir(folder)
    files = _collect_files(dataset_dir)
    settings = get_settings()
    normalized_token = normalize_trigger_token(trigger_token)
    changes: list[CaptionChange] = []
    base = _base_dir()
    for item in files:
        caption_path = base / (item.caption_path or "")
        before = item.caption or ""
        source = before
        if use_ai_cleanup:
            source = _cleanup_caption_with_ai(source, settings)
            source = filter_caption(
                source,
                max_tags=getattr(settings, "wd_tag_limit", None),
            )
        after = normalize_caption(source, normalized_token)
        changes.append(
            CaptionChange(
                path=caption_path.relative_to(base).as_posix(),
                before=before,
                after=after,
                changed=before != after,
            )
        )
    return normalized_token, compute_dataset_hash(folder), changes


def _check_expected_hash(folder: str, expected_dataset_hash: str | None) -> str:
    current_hash = compute_dataset_hash(folder)
    if expected_dataset_hash and expected_dataset_hash != current_hash:
        raise DatasetServiceError(
            "dataset_hash_mismatch",
            "dataset hash does not match expected hash",
            {"expected_dataset_hash": expected_dataset_hash, "current_dataset_hash": current_hash},
        )
    return current_hash


def _backup_dataset(dataset_dir: Path, changes: list[CaptionChange]) -> str:
    backup_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid.uuid4().hex[:8]}"
    backup_dir = dataset_dir / ".lora_prep_backups" / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)
    base = _base_dir()
    manifest = {"backup_id": backup_id, "files": []}
    for change in changes:
        caption_path = base / change.path
        entry = {
            "path": change.path,
            "existed": caption_path.exists(),
            "backup_name": None,
        }
        if caption_path.exists():
            backup_name = f"{len(manifest['files']):04d}_{Path(change.path).name}"
            shutil.copy2(caption_path, backup_dir / backup_name)
            entry["backup_name"] = backup_name
        manifest["files"].append(entry)
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_id


def prepare_dataset(
    folder: str,
    *,
    trigger_token: str | None,
    dry_run: bool = True,
    use_ai_cleanup: bool = False,
    expected_dataset_hash: str | None = None,
    restore_backup_id: str | None = None,
) -> DatasetPrepareResponse:
    """Prepare captions with dry-run/apply semantics."""
    if restore_backup_id:
        return restore_dataset(folder, restore_backup_id)

    if use_ai_cleanup and not getattr(get_settings(), "llm_caption_url", None):
        raise DatasetServiceError("ai_cleanup_not_configured", "llm caption provider is not configured")

    dataset_dir = resolve_dataset_dir(folder)
    normalized_token, before_hash, changes = _planned_changes(
        _folder_for_path(dataset_dir),
        trigger_token,
        use_ai_cleanup,
    )
    changed_count = sum(1 for change in changes if change.changed)
    unchanged_count = len(changes) - changed_count
    if dry_run:
        return DatasetPrepareResponse(
            ok=True,
            folder=_folder_for_path(dataset_dir),
            normalized_trigger_token=normalized_token,
            changes=changes,
            changed_count=changed_count,
            unchanged_count=unchanged_count,
            dataset_hash_before=before_hash,
            dataset_hash_after=None,
            backup_id=None,
        )

    _check_expected_hash(_folder_for_path(dataset_dir), expected_dataset_hash)
    with dataset_lock(_folder_for_path(dataset_dir), owner="prepare"):
        backup_id = _backup_dataset(dataset_dir, changes)
        base = _base_dir()
        for change in changes:
            caption_path = base / change.path
            caption_path.parent.mkdir(parents=True, exist_ok=True)
            caption_path.write_text(change.after, encoding="utf-8")
        after_hash = compute_dataset_hash(_folder_for_path(dataset_dir))
    return DatasetPrepareResponse(
        ok=True,
        folder=_folder_for_path(dataset_dir),
        normalized_trigger_token=normalized_token,
        changes=changes,
        changed_count=changed_count,
        unchanged_count=unchanged_count,
        dataset_hash_before=before_hash,
        dataset_hash_after=after_hash,
        backup_id=backup_id,
    )


def restore_dataset(folder: str, backup_id: str) -> DatasetPrepareResponse:
    """Restore captions from a preparation backup."""
    dataset_dir = resolve_dataset_dir(folder)
    backup_dir = dataset_dir / ".lora_prep_backups" / backup_id
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise DatasetServiceError("backup_not_found", "dataset preparation backup not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    with dataset_lock(_folder_for_path(dataset_dir), owner="restore"):
        base = _base_dir()
        for entry in manifest.get("files", []):
            rel_path = entry["path"]
            caption_path = base / rel_path
            if entry.get("existed"):
                backup_name = entry.get("backup_name")
                if not backup_name:
                    continue
                caption_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_dir / backup_name, caption_path)
            elif caption_path.exists():
                caption_path.unlink()
            restored.append(rel_path)
        restored_hash = compute_dataset_hash(_folder_for_path(dataset_dir))
    return DatasetPrepareResponse(
        ok=True,
        folder=_folder_for_path(dataset_dir),
        restored_files=restored,
        dataset_hash_after=restored_hash,
    )


def validate_dataset(
    folder: str,
    *,
    trigger_token: str,
    expected_dataset_hash: str | None = None,
) -> DatasetValidateResponse:
    """Validate dataset readiness before training."""
    dataset_dir = resolve_dataset_dir(folder)
    inspected = inspect_dataset(_folder_for_path(dataset_dir))
    normalized_token = normalize_trigger_token(trigger_token)
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    settings = get_settings()
    min_images = max(1, int(getattr(settings, "lora_train_threshold", 1) or 1))

    if inspected.locked:
        errors.append(ValidationIssue(code="dataset_locked", message="dataset is locked"))
    if inspected.image_count < min_images:
        errors.append(
            ValidationIssue(
                code="insufficient_images",
                message=f"dataset has {inspected.image_count} images; requires at least {min_images}",
            )
        )
    if expected_dataset_hash and expected_dataset_hash != inspected.dataset_hash:
        errors.append(
            ValidationIssue(
                code="dataset_hash_mismatch",
                message="dataset hash does not match expected hash",
                details={
                    "expected_dataset_hash": expected_dataset_hash,
                    "current_dataset_hash": inspected.dataset_hash,
                },
            )
        )

    for item in inspected.files:
        if not item.has_caption:
            errors.append(
                ValidationIssue(code="missing_caption", message="missing caption", path=item.image_path)
            )
            continue
        tags = [tag.lower() for tag in _parse_caption_tags(item.caption or "")]
        if not tags:
            errors.append(ValidationIssue(code="empty_caption", message="empty caption", path=item.caption_path))
            continue
        if normalized_token.lower() not in tags:
            errors.append(
                ValidationIssue(
                    code="missing_trigger_token",
                    message="caption does not contain trigger token",
                    path=item.caption_path,
                )
            )

    return DatasetValidateResponse(
        ok=not errors,
        folder=inspected.folder,
        normalized_trigger_token=normalized_token,
        dataset_hash=inspected.dataset_hash,
        image_count=inspected.image_count,
        caption_count=inspected.caption_count,
        missing_caption_count=inspected.missing_caption_count,
        warnings=warnings,
        errors=errors,
        locked=inspected.locked,
    )
