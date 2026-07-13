"""CIV-SA-A internal, offline source-alias registry service (no API/MCP side effects)."""
from __future__ import annotations

from datetime import timezone
import json
import re
import unicodedata
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasDomainResult,
    CivitaiSourceAliasRegistryView,
    CivitaiSourceAliasRememberRequest,
    CivitaiSourceAliasView,
    CivitaiSourceAliasImmutableIdentity,
    canonical_json,
    canonical_sha256,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def normalize_alias(value: str) -> str:
    """Normalize the one global alias namespace exactly once at every boundary."""
    if not isinstance(value, str):
        raise ValueError("alias must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\s+", " ", normalized, flags=re.UNICODE).strip()
    if not normalized:
        raise ValueError("alias normalizes to an empty key")
    return normalized


def _aliases(request: CivitaiSourceAliasRememberRequest) -> list[tuple[str, str, str]]:
    values = [(request.primary_alias, "primary"), *((item, "alternate") for item in request.alternate_aliases)]
    try:
        normalized = [(original, normalize_alias(original), kind) for original, kind in values]
    except ValueError:
        raise
    keys = [key for _, key, _ in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_alias_in_request")
    return normalized


def _identity_json(request: CivitaiSourceAliasRememberRequest) -> str:
    return canonical_json(request.source_identity.model_dump(mode="json", exclude_none=True))


def _result(status: str, code: str, *, record: CivitaiSourceAliasRegistryView | None = None, alias: CivitaiSourceAliasView | None = None) -> CivitaiSourceAliasDomainResult:
    return CivitaiSourceAliasDomainResult(status=status, code=code, record=record, alias=alias)


def _record_view(row: CivitaiSourceAliasRegistryRecord) -> tuple[CivitaiSourceAliasRegistryView | None, str | None]:
    """Read a persisted binding defensively: malformed audit data is never returned."""
    try:
        identity = json.loads(row.source_identity_json)
        evidence = json.loads(row.acquisition_evidence_json)
        tags = json.loads(row.approved_tags_json)
    except (TypeError, json.JSONDecodeError):
        return None, "stored_json_invalid"
    if not isinstance(identity, dict) or not isinstance(evidence, dict) or not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return None, "stored_shape_invalid"
    try:
        canonical_identity = CivitaiSourceAliasImmutableIdentity.model_validate(identity).model_dump(mode="json", exclude_none=True)
    except Exception:
        return None, "identity_invalid"
    if canonical_json(canonical_identity) != row.source_identity_json:
        return None, "identity_noncanonical"
    if not isinstance(row.acquisition_evidence_sha256, str) or _SHA256.fullmatch(row.acquisition_evidence_sha256) is None:
        return None, "evidence_hash_invalid"
    if canonical_sha256(evidence) != row.acquisition_evidence_sha256:
        return None, "evidence_hash_mismatch"
    if not isinstance(row.parent_recipe_sha256, str) or _SHA256.fullmatch(row.parent_recipe_sha256) is None:
        return None, "parent_recipe_sha_invalid"
    if row.registry_version is None or row.registry_version < 1 or row.created_at is None:
        return None, "record_invalid"
    created_at = row.created_at if row.created_at.tzinfo is not None else row.created_at.replace(tzinfo=timezone.utc)
    try:
        return CivitaiSourceAliasRegistryView(
            registry_version=row.registry_version,
            source_identity=canonical_identity,
            acquisition_evidence_snapshot=evidence,
            acquisition_evidence_sha256=row.acquisition_evidence_sha256,
            parent_recipe_sha256=row.parent_recipe_sha256,
            thumbnail_url=row.thumbnail_url,
            thumbnail_path=row.thumbnail_path,
            user_note=row.user_note,
            approved_tags=tags,
            prompt_summary=row.prompt_summary,
            created_at=created_at.astimezone(timezone.utc),
        ), None
    except Exception:
        return None, "record_invalid"


def remember(request: CivitaiSourceAliasRememberRequest, *, db: Any) -> CivitaiSourceAliasDomainResult:
    """Atomically establish aliases, or return a fail-closed domain result with no writes."""
    try:
        aliases = _aliases(request)
    except ValueError as exc:
        return _result("rejected", "duplicate_alias_in_request" if str(exc) == "duplicate_alias_in_request" else "alias_invalid")

    keys = [key for _, key, _ in aliases]
    found = db.query(CivitaiSourceAlias).filter(CivitaiSourceAlias.normalized_key.in_(keys)).all()
    if found:
        if len(found) != len({row.normalized_key for row in found}):
            return _result("corrupt", "non_unique_alias")
        existing_versions = {row.registry_version for row in found}
        if len(existing_versions) != 1 or len(found) != len(keys):
            return _result("conflict", "alias_already_bound")
        record = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=next(iter(existing_versions))).all()
        if len(record) != 1:
            return _result("corrupt", "record_non_unique_or_missing")
        view, code = _record_view(record[0])
        if view is None:
            return _result("corrupt", code or "record_invalid")
        if canonical_json(view.source_identity) != _identity_json(request):
            return _result("conflict", "alias_target_conflict")
        return _result("success", "idempotent", record=view)

    record = CivitaiSourceAliasRegistryRecord(
        source_identity_json=_identity_json(request),
        acquisition_evidence_json=canonical_json(request.acquisition_evidence_snapshot),
        acquisition_evidence_sha256=request.acquisition_evidence_sha256,
        parent_recipe_sha256=request.parent_recipe_sha256,
        thumbnail_url=str(request.thumbnail_url) if request.thumbnail_url is not None else None,
        thumbnail_path=request.thumbnail_path,
        user_note=request.user_note,
        approved_tags_json=canonical_json(request.approved_tags),
        prompt_summary=request.prompt_summary,
    )
    try:
        db.add(record)
        db.flush()
        for original, normalized, kind in aliases:
            db.add(CivitaiSourceAlias(registry_version=record.registry_version, original_alias=original, normalized_key=normalized, alias_kind=kind))
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent writer won the unique key. Re-read; never try to repoint or repair.
        reread = db.query(CivitaiSourceAlias).filter(CivitaiSourceAlias.normalized_key.in_(keys)).all()
        if len(reread) == len(keys) and len({row.normalized_key for row in reread}) == len(keys):
            versions = {row.registry_version for row in reread}
            if len(versions) == 1:
                existing = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=next(iter(versions))).first()
                view, code = _record_view(existing) if existing is not None else (None, "record_missing")
                if view is not None and canonical_json(view.source_identity) == _identity_json(request):
                    return _result("success", "idempotent", record=view)
                if view is None:
                    return _result("corrupt", code or "record_invalid")
        return _result("conflict", "alias_already_bound")

    view, code = _record_view(record)
    if view is None:  # Defensive: do not claim success if persistence mutated unexpectedly.
        return _result("corrupt", code or "record_invalid")
    return _result("success", "created", record=view)


def exact_resolve(alias: str, *, db: Any) -> CivitaiSourceAliasDomainResult:
    """Resolve one normalized exact key, failing closed on missing, ambiguity, or corruption."""
    try:
        key = normalize_alias(alias)
    except ValueError:
        return _result("missing", "invalid_alias")
    rows = db.query(CivitaiSourceAlias).filter_by(normalized_key=key).all()
    if not rows:
        return _result("missing", "not_found")
    if len(rows) != 1:
        return _result("corrupt", "non_unique_alias")
    alias_row = rows[0]
    records = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=alias_row.registry_version).all()
    if len(records) != 1:
        return _result("corrupt", "record_non_unique_or_missing")
    view, code = _record_view(records[0])
    if view is None:
        return _result("corrupt", code or "record_invalid")
    if alias_row.alias_kind not in {"primary", "alternate"} or not alias_row.original_alias or alias_row.normalized_key != key:
        return _result("corrupt", "alias_invalid")
    return _result("success", "resolved", record=view, alias=CivitaiSourceAliasView(original_alias=alias_row.original_alias, normalized_key=key, kind=alias_row.alias_kind))


# Explicit stage-local names; the concise aliases remain convenient for internal callers/tests.
remember_source_alias = remember
resolve_source_alias_exact = exact_resolve
