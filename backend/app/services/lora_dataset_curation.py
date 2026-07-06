"""Deterministic LoRA dataset caption curation."""
from __future__ import annotations

import json
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.lora_train import (
    DatasetCurationFileChange,
    DatasetCurationResponse,
    DatasetCurationSummary,
)
from app.services import lora_dataset

CURATION_BACKUP_DIR = ".lora_curation_backups"


def _clean_policy_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        tag = raw.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
    return cleaned


def _tag_key(tag: str) -> str:
    return tag.strip().lower()


def _parse_tags(caption: str) -> list[str]:
    return [part.strip() for part in caption.split(",") if part.strip()]


def _is_manual_caption(image_path: Path, caption_path: Path) -> tuple[bool, str | None]:
    if not caption_path.exists():
        return False, None
    try:
        if caption_path.stat().st_mtime > image_path.stat().st_mtime:
            return True, "caption_newer_than_image"
    except OSError:
        return False, None
    return False, None


def _normalize_caption_tags(
    caption: str,
    *,
    trigger_token: str | None,
    protected_tags: list[str],
    removable_tags: list[str],
) -> tuple[str, list[str], list[str], list[str], list[str]]:
    protected_keys = {_tag_key(tag) for tag in protected_tags}
    removable_keys = {_tag_key(tag) for tag in removable_tags} - protected_keys
    trigger_key = _tag_key(trigger_token or "")
    seen: set[str] = set()
    output: list[str] = []
    removed: list[str] = []
    duplicates: list[str] = []
    preserved: list[str] = []
    reasons: list[str] = []

    if trigger_token:
        output.append(trigger_token)
        seen.add(trigger_key)

    for tag in _parse_tags(caption):
        key = _tag_key(tag)
        tag_is_trigger = bool(
            trigger_token
            and (key == trigger_key or lora_dataset.normalize_trigger_token(tag) == trigger_token)
        )
        if tag_is_trigger:
            if tag != trigger_token:
                reasons.append("trigger_normalized")
            continue
        if key in removable_keys:
            removed.append(tag)
            continue
        if key in seen:
            duplicates.append(tag)
            continue
        seen.add(key)
        output.append(tag)
        if key in protected_keys:
            preserved.append(tag)

    caption_has_trigger = any(
        _tag_key(tag) == trigger_key or lora_dataset.normalize_trigger_token(tag) == trigger_token
        for tag in _parse_tags(caption)
    )
    if trigger_token and not caption_has_trigger:
        reasons.append("trigger_added")
    if removed:
        reasons.append("removable_tags_removed")
    if duplicates:
        reasons.append("duplicate_tags_removed")
    if preserved:
        reasons.append("protected_tags_preserved")

    return ", ".join(output), reasons, removed, duplicates, preserved


def _policy_for_dataset(
    inspected,
    *,
    trigger_token: str | None,
    protected_tags: list[str] | None,
    removable_tags: list[str] | None,
) -> tuple[str | None, list[str], list[str]]:
    raw_trigger = trigger_token or inspected.profile.trigger_token
    if not raw_trigger and inspected.trigger_token_candidates:
        raw_trigger = inspected.trigger_token_candidates[0]
    normalized_trigger = lora_dataset.normalize_trigger_token(raw_trigger) if raw_trigger else None
    resolved_protected = _clean_policy_tags(
        protected_tags if protected_tags is not None else inspected.profile.protected_tags
    )
    resolved_removable = _clean_policy_tags(
        removable_tags if removable_tags is not None else inspected.profile.removable_tags
    )
    if normalized_trigger:
        resolved_protected = _clean_policy_tags([normalized_trigger, *resolved_protected])
    return normalized_trigger, resolved_protected, resolved_removable


def _outlier_flags_by_path(changes: list[DatasetCurationFileChange], trigger_token: str | None) -> dict[str, list[str]]:
    tag_sets: dict[str, set[str]] = {}
    trigger_key = _tag_key(trigger_token or "")
    for change in changes:
        tags = {_tag_key(tag) for tag in _parse_tags(change.after)}
        tag_sets[change.path] = tags

    counter: Counter[str] = Counter()
    for tags in tag_sets.values():
        counter.update(tags)

    flags: dict[str, list[str]] = {change.path: [] for change in changes}
    for path, tags in tag_sets.items():
        if trigger_token and trigger_key not in tags:
            flags[path].append("missing_trigger")
        comparable = {tag for tag in tags if tag != trigger_key}
        if len(tag_sets) >= 3 and comparable:
            shared = {tag for tag in comparable if counter[tag] >= 2}
            if not shared:
                flags[path].append("low_shared_tag_overlap")
    return flags


def _summary(changes: list[DatasetCurationFileChange]) -> DatasetCurationSummary:
    return DatasetCurationSummary(
        total_files=len(changes),
        changed_count=sum(1 for change in changes if change.status == "changed"),
        unchanged_count=sum(1 for change in changes if change.status == "unchanged"),
        skipped_count=sum(1 for change in changes if change.status == "skipped"),
        blocked_count=sum(1 for change in changes if change.blocked),
        review_required_count=sum(1 for change in changes if change.review_required),
        manual_count=sum(1 for change in changes if change.manual),
        outlier_count=sum(1 for change in changes if change.outlier_flags),
    )


def plan_curation(
    folder: str,
    *,
    trigger_token: str | None = None,
    protected_tags: list[str] | None = None,
    removable_tags: list[str] | None = None,
    approved_manual_overwrite_paths: list[str] | None = None,
) -> DatasetCurationResponse:
    """Return a deterministic curation plan without writing captions or metadata."""
    inspected = lora_dataset.inspect_dataset(folder)
    normalized_trigger, resolved_protected, resolved_removable = _policy_for_dataset(
        inspected,
        trigger_token=trigger_token,
        protected_tags=protected_tags,
        removable_tags=removable_tags,
    )
    base = lora_dataset._base_dir()
    approved_paths = set(approved_manual_overwrite_paths or [])
    changes: list[DatasetCurationFileChange] = []

    for item in inspected.files:
        if not item.caption_path:
            continue
        image_path = base / item.image_path
        caption_path = base / item.caption_path
        before = item.caption or ""
        after, reasons, removed, duplicates, preserved = _normalize_caption_tags(
            before,
            trigger_token=normalized_trigger,
            protected_tags=resolved_protected,
            removable_tags=resolved_removable,
        )
        changed = before != after
        manual, manual_reason = _is_manual_caption(image_path, caption_path)
        approved = item.caption_path in approved_paths
        blocked = bool(changed and manual and not approved)
        review_required = blocked
        status = "review_required" if blocked else ("changed" if changed else "unchanged")
        change_reasons = list(dict.fromkeys(reasons))
        if item.has_caption is False:
            change_reasons.append("missing_caption")
            review_required = True
            status = "review_required"
        if manual:
            change_reasons.append("manual_caption")

        changes.append(
            DatasetCurationFileChange(
                path=item.caption_path,
                image_path=item.image_path,
                before=before,
                after=after,
                changed=changed,
                status=status,
                reasons=change_reasons,
                blocked=blocked,
                review_required=review_required,
                manual=manual,
                manual_reason=manual_reason,
                manual_overwrite_approved=bool(changed and manual and approved),
                removed_tags=removed,
                duplicate_tags=duplicates,
                protected_tags=preserved,
            )
        )

    outliers = _outlier_flags_by_path(changes, normalized_trigger)
    for change in changes:
        change.outlier_flags = outliers.get(change.path, [])
        if change.outlier_flags and "outlier_flagged" not in change.reasons:
            change.reasons.append("outlier_flagged")

    return DatasetCurationResponse(
        mode="dry_run",
        folder=inspected.folder,
        normalized_trigger_token=normalized_trigger,
        dataset_hash=inspected.dataset_hash,
        profile_hash=inspected.profile_hash,
        dataset_hash_before=inspected.dataset_hash,
        changes=changes,
        summary=_summary(changes),
        changed_files=[change.path for change in changes if change.status == "changed"],
        skipped_files=[change.path for change in changes if change.blocked],
        manually_overwritten_files=[
            change.path for change in changes if change.manual_overwrite_approved
        ],
    )


def _check_expected_hashes(
    folder: str,
    *,
    expected_dataset_hash: str | None,
    expected_profile_hash: str | None,
) -> tuple[str, str | None]:
    if not expected_dataset_hash:
        current_hash = lora_dataset.compute_dataset_hash(folder)
        raise lora_dataset.DatasetServiceError(
            "expected_dataset_hash_required",
            "expected_dataset_hash is required to apply curation",
            {"current_dataset_hash": current_hash},
        )
    current_dataset_hash = lora_dataset.compute_dataset_hash(folder)
    if expected_dataset_hash != current_dataset_hash:
        raise lora_dataset.DatasetServiceError(
            "dataset_hash_mismatch",
            "dataset hash does not match expected hash",
            {
                "expected_dataset_hash": expected_dataset_hash,
                "current_dataset_hash": current_dataset_hash,
            },
        )
    dataset_dir = lora_dataset.resolve_dataset_dir(folder)
    current_profile_hash = lora_dataset._current_profile_hash(dataset_dir)
    if expected_profile_hash != current_profile_hash:
        raise lora_dataset.DatasetServiceError(
            "profile_hash_mismatch",
            "profile hash does not match expected hash",
            {
                "expected_profile_hash": expected_profile_hash,
                "current_profile_hash": current_profile_hash,
            },
        )
    return current_dataset_hash, current_profile_hash


def _backup_changes(
    dataset_dir: Path,
    *,
    folder: str,
    dataset_hash_before: str,
    profile_hash_before: str | None,
    changes: list[DatasetCurationFileChange],
) -> str:
    backup_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid.uuid4().hex[:8]}"
    backup_dir = dataset_dir / CURATION_BACKUP_DIR / backup_id
    backup_dir.mkdir(parents=True, exist_ok=False)
    base = lora_dataset._base_dir()
    manifest: dict[str, Any] = {
        "backup_id": backup_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "folder": folder,
        "dataset_hash_before": dataset_hash_before,
        "profile_hash_before": profile_hash_before,
        "files": [],
    }
    for change in changes:
        caption_path = base / change.path
        entry = {
            "path": change.path,
            "existed": caption_path.exists(),
            "backup_name": None,
            "after": change.after,
            "manual_overwrite_approved": change.manual_overwrite_approved,
        }
        if caption_path.exists():
            backup_name = f"{len(manifest['files']):04d}_{Path(change.path).name}"
            shutil.copy2(caption_path, backup_dir / backup_name)
            entry["backup_name"] = backup_name
        manifest["files"].append(entry)
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return backup_id


def apply_curation(
    folder: str,
    *,
    expected_dataset_hash: str | None,
    expected_profile_hash: str | None,
    trigger_token: str | None = None,
    protected_tags: list[str] | None = None,
    removable_tags: list[str] | None = None,
    approved_manual_overwrite_paths: list[str] | None = None,
) -> DatasetCurationResponse:
    """Apply a reviewed curation plan after hash checks and backup creation."""
    dataset_dir = lora_dataset.resolve_dataset_dir(folder)
    resolved_folder = lora_dataset._folder_for_path(dataset_dir)
    with lora_dataset.dataset_lock(resolved_folder, owner="curation_apply"):
        before_hash, profile_hash = _check_expected_hashes(
            resolved_folder,
            expected_dataset_hash=expected_dataset_hash,
            expected_profile_hash=expected_profile_hash,
        )
        plan = plan_curation(
            resolved_folder,
            trigger_token=trigger_token,
            protected_tags=protected_tags,
            removable_tags=removable_tags,
            approved_manual_overwrite_paths=approved_manual_overwrite_paths,
        )
        writable = [
            change for change in plan.changes
            if change.changed and not change.blocked and change.status == "changed"
        ]
        skipped = [
            change for change in plan.changes
            if change.blocked or (change.changed and change.status != "changed")
        ]
        backup_id = _backup_changes(
            dataset_dir,
            folder=resolved_folder,
            dataset_hash_before=before_hash,
            profile_hash_before=profile_hash,
            changes=writable,
        )
        base = lora_dataset._base_dir()
        for change in writable:
            caption_path = base / change.path
            caption_path.parent.mkdir(parents=True, exist_ok=True)
            caption_path.write_text(change.after, encoding="utf-8")
        after_hash = lora_dataset.compute_dataset_hash(resolved_folder)

    result_changes: list[DatasetCurationFileChange] = []
    writable_paths = {change.path for change in writable}
    skipped_paths = {change.path for change in skipped}
    for change in plan.changes:
        if change.path in writable_paths:
            change.status = "changed"
        elif change.path in skipped_paths:
            change.status = "skipped"
        result_changes.append(change)

    return DatasetCurationResponse(
        mode="apply",
        folder=resolved_folder,
        normalized_trigger_token=plan.normalized_trigger_token,
        dataset_hash=after_hash,
        profile_hash=profile_hash,
        dataset_hash_before=before_hash,
        dataset_hash_after=after_hash,
        backup_id=backup_id,
        changes=result_changes,
        summary=_summary(result_changes),
        changed_files=[change.path for change in writable],
        skipped_files=[change.path for change in skipped],
        manually_overwritten_files=[
            change.path for change in writable if change.manual_overwrite_approved
        ],
    )


def rollback_curation(
    folder: str,
    backup_id: str,
    *,
    approved_manual_overwrite_paths: list[str] | None = None,
) -> DatasetCurationResponse:
    """Restore caption files from a curation backup without clobbering newer manual edits."""
    dataset_dir = lora_dataset.resolve_dataset_dir(folder)
    resolved_folder = lora_dataset._folder_for_path(dataset_dir)
    backup_dir = dataset_dir / CURATION_BACKUP_DIR / backup_id
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise lora_dataset.DatasetServiceError("backup_not_found", "dataset curation backup not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    approved_paths = set(approved_manual_overwrite_paths or [])
    restored: list[str] = []
    skipped: list[str] = []
    changes: list[DatasetCurationFileChange] = []
    with lora_dataset.dataset_lock(resolved_folder, owner="curation_rollback"):
        base = lora_dataset._base_dir()
        for entry in manifest.get("files", []):
            rel_path = entry["path"]
            caption_path = base / rel_path
            before = caption_path.read_text(encoding="utf-8") if caption_path.exists() else ""
            original = ""
            if entry.get("existed") and entry.get("backup_name"):
                original = (backup_dir / entry["backup_name"]).read_text(encoding="utf-8")
            current_is_applied = before == entry.get("after", "")
            approved = rel_path in approved_paths
            if not current_is_applied and not approved:
                skipped.append(rel_path)
                changes.append(
                    DatasetCurationFileChange(
                        path=rel_path,
                        image_path="",
                        before=before,
                        after=original,
                        changed=before != original,
                        status="skipped",
                        reasons=["newer_manual_edit"],
                        blocked=True,
                        review_required=True,
                        manual=True,
                        manual_reason="caption_changed_after_curation",
                    )
                )
                continue

            if entry.get("existed"):
                caption_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_dir / entry["backup_name"], caption_path)
            elif caption_path.exists():
                caption_path.unlink()
            restored.append(rel_path)
            changes.append(
                DatasetCurationFileChange(
                    path=rel_path,
                    image_path="",
                    before=before,
                    after=original,
                    changed=before != original,
                    status="restored",
                    reasons=["restored_from_backup"],
                    manual=not current_is_applied,
                    manual_reason=None if current_is_applied else "caption_changed_after_curation",
                    manual_overwrite_approved=bool(not current_is_applied and approved),
                )
            )
        after_hash = lora_dataset.compute_dataset_hash(resolved_folder)
        profile_hash = lora_dataset._current_profile_hash(dataset_dir)

    return DatasetCurationResponse(
        mode="rollback",
        folder=resolved_folder,
        dataset_hash=after_hash,
        profile_hash=profile_hash,
        dataset_hash_after=after_hash,
        backup_id=backup_id,
        changes=changes,
        summary=_summary(changes),
        skipped_files=skipped,
        restored_files=restored,
        manually_overwritten_files=[
            change.path for change in changes if change.manual_overwrite_approved
        ],
    )
