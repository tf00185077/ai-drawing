"""CIV-SA-A internal, offline source-alias registry service (no API/MCP side effects)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import unicodedata
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasHistory, CivitaiSourceAliasRegistryRecord
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasDomainResult,
    CivitaiSourceAliasRegistryView,
    CivitaiSourceAliasRememberRequest,
    CivitaiSourceAliasView,
    CivitaiSourceAliasImmutableIdentity,
    CivitaiSourceAliasHistoryEventView,
    CivitaiSourceAliasRenameRequest,
    CivitaiSourceAliasRenameResult,
    CivitaiSourceAliasArchiveRequest,
    CivitaiSourceAliasArchiveResult,
    CivitaiSourceAliasRegistryEntry,
    CivitaiSourceAliasRegistryListResult,
    CivitaiSourceAliasRegistrySearchResult,
    CivitaiSourceAliasSearchCandidate,
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
    try:
        if canonical_json(canonical_identity) != row.source_identity_json:
            return None, "identity_noncanonical"
    except (TypeError, ValueError):
        return None, "identity_noncanonical"
    if not isinstance(row.acquisition_evidence_sha256, str) or _SHA256.fullmatch(row.acquisition_evidence_sha256) is None:
        return None, "evidence_hash_invalid"
    try:
        evidence_sha256 = canonical_sha256(evidence)
    except (TypeError, ValueError):
        return None, "evidence_noncanonical"
    if evidence_sha256 != row.acquisition_evidence_sha256:
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
        if record[0].archived_at is not None:
            return _result("conflict", "alias_archived")
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
                # A concurrent winner may have archived this exact immutable target
                # before our unique-key recovery.  Archive is terminal: never turn
                # that state into idempotent success or rebind aliases.
                if existing is not None and existing.archived_at is not None:
                    return _result("conflict", "alias_archived")
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
    if records[0].archived_at is not None:
        return _result("archived", "target_archived")
    return _result("success", "resolved", record=view, alias=CivitaiSourceAliasView(original_alias=alias_row.original_alias, normalized_key=key, kind=alias_row.alias_kind))


# Explicit stage-local names; the concise aliases remain convenient for internal callers/tests.
remember_source_alias = remember
resolve_source_alias_exact = exact_resolve


_DiscoveryStatus = Literal["success", "rejected", "corrupt"]
_DiscoveryField = Literal[
    "primary_alias", "alternate_aliases", "approved_tags", "user_note", "source_metadata", "prompt_summary",
]
_DISCOVERY_FIELD_ORDER: tuple[_DiscoveryField, ...] = (
    "primary_alias", "alternate_aliases", "approved_tags", "user_note", "source_metadata", "prompt_summary",
)
_DISCOVERY_WEIGHTS = {
    "primary_alias": 100,
    "alternate_aliases": 90,
    "approved_tags": 70,
    "user_note": 50,
    "source_metadata": 40,
    "prompt_summary": 30,
}
_SECRET_METADATA_KEYS = {
    "authorization", "api_key", "apikey", "access_token", "token", "secret", "password", "cookie",
    "client_secret", "refresh_token",
}


def _is_secret_metadata_key(key: str) -> bool:
    """Recognize complete credential-key names without matching unrelated substrings."""
    normalized = unicodedata.normalize("NFKC", key).casefold().strip()
    normalized = re.sub(r"[-\s]+", "_", normalized)
    return normalized in _SECRET_METADATA_KEYS


def _discovery_pagination(limit: Any, offset: Any) -> tuple[int, int] | None:
    actual_limit = 50 if limit is None else limit
    actual_offset = 0 if offset is None else offset
    if type(actual_limit) is not int or not 1 <= actual_limit <= 100:
        return None
    if type(actual_offset) is not int or actual_offset < 0:
        return None
    return actual_limit, actual_offset


def _discovery_empty_list(*, status: _DiscoveryStatus, code: str, limit: int = 50, offset: int = 0) -> CivitaiSourceAliasRegistryListResult:
    return CivitaiSourceAliasRegistryListResult(status=status, code=code, limit=limit, offset=offset)


def _discovery_empty_search(*, status: _DiscoveryStatus, code: str, normalized_query: str | None = None, limit: int = 50, offset: int = 0) -> CivitaiSourceAliasRegistrySearchResult:
    return CivitaiSourceAliasRegistrySearchResult(
        status=status, code=code, normalized_query=normalized_query, limit=limit, offset=offset,
    )


def _strict_discovery_tags(tags: list[str]) -> bool:
    return all(tag and tag == tag.strip() for tag in tags) and len(tags) == len(set(tags))


def _read_discovery_entries(*, db: Any) -> tuple[list[CivitaiSourceAliasRegistryEntry] | None, str | None]:
    """Read each persisted table once and reject the whole discovery result on any anomaly."""
    records = db.query(CivitaiSourceAliasRegistryRecord).all()
    aliases = db.query(CivitaiSourceAlias).all()
    records_by_version: dict[int, CivitaiSourceAliasRegistryRecord] = {}
    views_by_version: dict[int, CivitaiSourceAliasRegistryView] = {}
    for row in records:
        version = row.registry_version
        if type(version) is not int or version in records_by_version:
            return None, "record_non_unique_or_invalid"
        view, code = _record_view(row)
        if view is None:
            return None, code or "record_invalid"
        if not _strict_discovery_tags(view.approved_tags):
            return None, "tags_invalid"
        records_by_version[version] = row
        views_by_version[version] = view

    aliases_by_version: dict[int, list[CivitaiSourceAliasView]] = {version: [] for version in records_by_version}
    seen_keys: set[str] = set()
    for row in aliases:
        if row.registry_version not in aliases_by_version:
            return None, "dangling_alias_record"
        if not isinstance(row.original_alias, str) or not isinstance(row.normalized_key, str):
            return None, "alias_invalid"
        try:
            normalized = normalize_alias(row.original_alias)
        except (TypeError, ValueError):
            return None, "alias_invalid"
        if row.normalized_key != normalized or normalized in seen_keys or row.alias_kind not in {"primary", "alternate"}:
            return None, "alias_invalid" if normalized not in seen_keys else "non_unique_alias"
        try:
            alias = CivitaiSourceAliasView(original_alias=row.original_alias, normalized_key=normalized, kind=row.alias_kind)
        except Exception:
            return None, "alias_invalid"
        seen_keys.add(normalized)
        aliases_by_version[row.registry_version].append(alias)

    entries: list[CivitaiSourceAliasRegistryEntry] = []
    for version in sorted(records_by_version):
        aliases_for_record = aliases_by_version[version]
        primary = [alias for alias in aliases_for_record if alias.kind == "primary"]
        if len(primary) != 1:
            return None, "primary_alias_invalid"
        alternates = sorted((alias for alias in aliases_for_record if alias.kind == "alternate"), key=lambda item: item.normalized_key)
        entries.append(CivitaiSourceAliasRegistryEntry(
            primary_alias=primary[0], alternate_aliases=alternates, record=views_by_version[version],
        ))
    return entries, None


def _metadata_scalar_texts(value: Any) -> list[str]:
    """Return canonical JSON scalar leaves while excluding secret-key subtrees."""
    if isinstance(value, dict):
        leaves: list[str] = []
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("metadata_key_invalid")
            if _is_secret_metadata_key(key):
                continue
            leaves.extend(_metadata_scalar_texts(child))
        return leaves
    if isinstance(value, list):
        leaves: list[str] = []
        for child in value:
            leaves.extend(_metadata_scalar_texts(child))
        return leaves
    if value is None or type(value) in {str, int, float, bool}:
        return [canonical_json(value)]
    raise ValueError("metadata_scalar_invalid")


def _field_texts(entry: CivitaiSourceAliasRegistryEntry) -> dict[str, list[str]]:
    record = entry.record
    metadata = _metadata_scalar_texts(record.source_identity) + _metadata_scalar_texts(record.acquisition_evidence_snapshot)
    return {
        "primary_alias": [entry.primary_alias.normalized_key],
        "alternate_aliases": [alias.normalized_key for alias in entry.alternate_aliases],
        "approved_tags": [normalize_alias(tag) for tag in record.approved_tags],
        "user_note": [] if record.user_note is None else [normalize_alias(record.user_note)],
        "source_metadata": [normalize_alias(value) for value in metadata],
        "prompt_summary": [] if record.prompt_summary is None else [normalize_alias(record.prompt_summary)],
    }


def list_registry_sources(*, db: Any, limit: int | None = None, offset: int | None = None) -> CivitaiSourceAliasRegistryListResult:
    """CIV-SA-E deterministic read-only listing; no partial results from corrupt storage."""
    pagination = _discovery_pagination(limit, offset)
    if pagination is None:
        return _discovery_empty_list(status="rejected", code="invalid_pagination")
    actual_limit, actual_offset = pagination
    entries, code = _read_discovery_entries(db=db)
    if entries is None:
        return _discovery_empty_list(status="corrupt", code=code or "registry_invalid", limit=actual_limit, offset=actual_offset)
    return CivitaiSourceAliasRegistryListResult(
        status="success", code="listed", total=len(entries), limit=actual_limit, offset=actual_offset,
        entries=entries[actual_offset:actual_offset + actual_limit],
    )


def search_registry_sources(query: str, *, db: Any, limit: int | None = None, offset: int | None = None) -> CivitaiSourceAliasRegistrySearchResult:
    """CIV-SA-E deterministic candidate search; never selects, resolves, or mutates a target."""
    pagination = _discovery_pagination(limit, offset)
    if pagination is None:
        return _discovery_empty_search(status="rejected", code="invalid_pagination")
    actual_limit, actual_offset = pagination
    if not isinstance(query, str) or not 1 <= len(query) <= 512:
        return _discovery_empty_search(status="rejected", code="invalid_query", limit=actual_limit, offset=actual_offset)
    try:
        normalized_query = normalize_alias(query)
    except (TypeError, ValueError):
        return _discovery_empty_search(status="rejected", code="invalid_query", limit=actual_limit, offset=actual_offset)
    entries, code = _read_discovery_entries(db=db)
    if entries is None:
        return _discovery_empty_search(
            status="corrupt", code=code or "registry_invalid", normalized_query=normalized_query,
            limit=actual_limit, offset=actual_offset,
        )

    tokens = normalized_query.split(" ")
    candidates: list[CivitaiSourceAliasSearchCandidate] = []
    for entry in entries:
        try:
            texts = _field_texts(entry)
        except (TypeError, ValueError):
            return _discovery_empty_search(
                status="corrupt", code="source_metadata_invalid", normalized_query=normalized_query,
                limit=actual_limit, offset=actual_offset,
            )
        field_hits = {
            field: [any(token in text for text in texts[field]) for token in tokens]
            for field in _DISCOVERY_FIELD_ORDER
        }
        if not all(any(field_hits[field][index] for field in _DISCOVERY_FIELD_ORDER) for index in range(len(tokens))):
            continue
        matched_fields: list[_DiscoveryField] = [field for field in _DISCOVERY_FIELD_ORDER if any(field_hits[field])]
        if normalized_query == entry.primary_alias.normalized_key:
            score = 1000
        elif any(normalized_query == alias.normalized_key for alias in entry.alternate_aliases):
            score = 900
        else:
            score = sum(
                max(_DISCOVERY_WEIGHTS[field] for field in _DISCOVERY_FIELD_ORDER if field_hits[field][index])
                for index in range(len(tokens))
            )
        candidates.append(CivitaiSourceAliasSearchCandidate(
            primary_alias=entry.primary_alias,
            alternate_aliases=entry.alternate_aliases,
            record=entry.record,
            score=score,
            matched_fields=matched_fields,
        ))
    candidates.sort(key=lambda item: (-item.score, item.record.registry_version))
    return CivitaiSourceAliasRegistrySearchResult(
        status="success", code="searched", normalized_query=normalized_query, total=len(candidates),
        limit=actual_limit, offset=actual_offset, candidates=candidates[actual_offset:actual_offset + actual_limit],
    )


# CIV-SA-H stays intentionally internal: no API/MCP caller may supply target data.
def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event_payload(*, registry_version: int, operation: Literal["rename", "archive"], before_aliases: dict[str, Any], after_aliases: dict[str, Any], previous_event_sha256: str | None, created_at: datetime) -> dict[str, Any]:
    return {"registry_version": registry_version, "operation": operation, "before_aliases": before_aliases, "after_aliases": after_aliases, "previous_event_sha256": previous_event_sha256, "created_at": _utc(created_at).isoformat().replace("+00:00", "Z")}


def _canonical_alias_snapshot(value: Any) -> dict[str, Any] | None:
    """Validate the one auditable snapshot shape; arrays are canonicalized by key order."""
    if not isinstance(value, dict) or set(value) != {"primary", "alternates"}:
        return None
    primary, alternates = value["primary"], value["alternates"]
    if not isinstance(primary, dict) or set(primary) != {"original_alias", "normalized_key"} or not isinstance(alternates, list):
        return None
    entries = [primary, *alternates]
    keys: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"original_alias", "normalized_key"}:
            return None
        original, normalized = entry["original_alias"], entry["normalized_key"]
        try:
            if not isinstance(original, str) or not isinstance(normalized, str) or normalize_alias(original) != normalized:
                return None
        except (TypeError, ValueError):
            return None
        keys.append(normalized)
    if len(keys) != len(set(keys)) or [entry["normalized_key"] for entry in alternates] != sorted(entry["normalized_key"] for entry in alternates):
        return None
    return {"primary": dict(primary), "alternates": [dict(entry) for entry in alternates]}


def _alias_snapshot(rows: list[CivitaiSourceAlias]) -> dict[str, Any] | None:
    if any(row.alias_kind not in {"primary", "alternate"} for row in rows):
        return None
    primary = [row for row in rows if row.alias_kind == "primary"]
    if len(primary) != 1:
        return None
    alternates = [
        {"original_alias": row.original_alias, "normalized_key": row.normalized_key}
        for row in rows if row.alias_kind == "alternate"
    ]
    return _canonical_alias_snapshot({
        "primary": {"original_alias": primary[0].original_alias, "normalized_key": primary[0].normalized_key},
        "alternates": sorted(alternates, key=lambda item: item["normalized_key"]),
    })


def _valid_rename_transition(before: dict[str, Any], after: dict[str, Any]) -> bool:
    preserved = sorted([*before["alternates"], before["primary"]], key=lambda item: item["normalized_key"])
    return after["primary"]["normalized_key"] != before["primary"]["normalized_key"] and after["alternates"] == preserved


def verify_source_alias_history_chain(registry_version: int, *, db: Any) -> str | None:
    """Return a deterministic corruption code, or None for one canonical lifecycle chain."""
    record_rows = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=registry_version).all()
    if len(record_rows) != 1:
        return "history_invalid"
    record = record_rows[0]
    events = db.query(CivitaiSourceAliasHistory).filter_by(registry_version=registry_version).order_by(CivitaiSourceAliasHistory.id).all()
    previous: str | None = None
    previous_after: dict[str, Any] | None = None
    seen_hashes: set[str] = set()
    archive_event: CivitaiSourceAliasHistory | None = None
    for index, event in enumerate(events):
        try:
            before_raw, after_raw = json.loads(event.before_aliases_json), json.loads(event.after_aliases_json)
            before, after = _canonical_alias_snapshot(before_raw), _canonical_alias_snapshot(after_raw)
            if before is None or after is None or before_raw != before or after_raw != after:
                return "history_invalid"
            if canonical_json(before) != event.before_aliases_json or canonical_json(after) != event.after_aliases_json:
                return "history_invalid"
            if previous_after is not None and before != previous_after:
                return "history_invalid"
            if event.operation == "rename":
                if archive_event is not None or not _valid_rename_transition(before, after):
                    return "history_invalid"
            elif event.operation == "archive":
                if archive_event is not None or index != len(events) - 1 or before != after:
                    return "history_invalid"
                archive_event = event
            else:
                return "history_invalid"
            if event.registry_version != registry_version or event.previous_event_sha256 != previous or event.event_sha256 in seen_hashes or _SHA256.fullmatch(event.event_sha256 or "") is None or not isinstance(event.created_at, datetime):
                return "history_invalid"
            payload = _event_payload(registry_version=event.registry_version, operation=event.operation, before_aliases=before, after_aliases=after, previous_event_sha256=event.previous_event_sha256, created_at=event.created_at)
            if canonical_sha256(payload) != event.event_sha256:
                return "history_invalid"
        except (TypeError, ValueError, json.JSONDecodeError):
            return "history_invalid"
        previous = event.event_sha256
        previous_after = after
        seen_hashes.add(event.event_sha256)
    current = _alias_snapshot(db.query(CivitaiSourceAlias).filter_by(registry_version=registry_version).all())
    if current is None or (previous_after is not None and previous_after != current):
        return "history_invalid"
    if record.archived_at is None:
        return None if archive_event is None else "history_invalid"
    if archive_event is None or not isinstance(record.archived_at, datetime):
        return "history_invalid"
    return None if _utc(record.archived_at) == _utc(archive_event.created_at) else "history_invalid"


def _rename_result(status: str, code: str, **kwargs: Any) -> CivitaiSourceAliasRenameResult:
    return CivitaiSourceAliasRenameResult(status=status, code=code, **kwargs)


def validate_rename_request(value: Any) -> CivitaiSourceAliasRenameRequest | None:
    """Strict internal boundary: invalid raw payloads never reach a database write path."""
    try:
        raw_value = value.model_dump() if isinstance(value, CivitaiSourceAliasRenameRequest) else value
        request = CivitaiSourceAliasRenameRequest.model_validate(raw_value, strict=True)
        normalize_alias(request.current_primary_alias)
        normalize_alias(request.new_primary_alias)
        return request
    except (ValidationError, TypeError, ValueError):
        return None


def _acquire_active_target_gate(*, registry_version: int, db: Any, archived_at: datetime | None = None) -> bool:
    """Serialize lifecycle writes against a target that remains active at write time."""
    values = (
        {"archived_at": archived_at}
        if archived_at is not None
        else {"archived_at": CivitaiSourceAliasRegistryRecord.archived_at}
    )
    result = db.execute(
        update(CivitaiSourceAliasRegistryRecord)
        .where(
            CivitaiSourceAliasRegistryRecord.registry_version == registry_version,
            CivitaiSourceAliasRegistryRecord.archived_at.is_(None),
        )
        .values(**values)
    )
    return result.rowcount == 1


def rename_primary_source_alias(request: Any, *, db: Any) -> CivitaiSourceAliasRenameResult:
    """Atomically rename one primary alias while preserving its immutable target binding."""
    request = validate_rename_request(request)
    if request is None:
        return _rename_result("rejected", "invalid_request")
    try:
        current_key, new_key = normalize_alias(request.current_primary_alias), normalize_alias(request.new_primary_alias)
    except (TypeError, ValueError):
        return _rename_result("rejected", "alias_invalid")
    if current_key == new_key:
        return _rename_result("rejected", "alias_unchanged")
    current_rows = db.query(CivitaiSourceAlias).filter_by(normalized_key=current_key).all()
    if not current_rows:
        entries, registry_error = _read_discovery_entries(db=db)
        if entries is None:
            return _rename_result("corrupt", registry_error or "registry_invalid")
        return _rename_result("missing", "current_alias_not_found")
    if len(current_rows) != 1:
        return _rename_result("corrupt", "non_unique_alias")
    old_primary = current_rows[0]
    if old_primary.alias_kind != "primary":
        entries, registry_error = _read_discovery_entries(db=db)
        if entries is None:
            return _rename_result("corrupt", registry_error or "registry_invalid")
        return _rename_result("missing", "current_alias_not_primary")
    if old_primary.registry_version != request.expected_registry_version:
        return _rename_result("rejected", "stale_registry_version")
    entries, registry_error = _read_discovery_entries(db=db)
    if entries is None:
        return _rename_result("corrupt", registry_error or "registry_invalid")
    record_rows = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=request.expected_registry_version).all()
    if len(record_rows) != 1:
        return _rename_result("corrupt", "record_non_unique_or_missing")
    record_view, record_error = _record_view(record_rows[0])
    if record_view is None:
        return _rename_result("corrupt", record_error or "record_invalid")
    if verify_source_alias_history_chain(request.expected_registry_version, db=db) is not None:
        return _rename_result("corrupt", "history_invalid")
    if record_rows[0].archived_at is not None:
        return _rename_result("rejected", "target_archived")
    registry_rows = db.query(CivitaiSourceAlias).filter_by(registry_version=request.expected_registry_version).all()
    before = _alias_snapshot(registry_rows)
    if before is None:
        return _rename_result("corrupt", "primary_alias_invalid")
    if verify_source_alias_history_chain(request.expected_registry_version, db=db) is not None:
        return _rename_result("corrupt", "history_invalid")
    if db.query(CivitaiSourceAlias).filter_by(normalized_key=new_key).first() is not None:
        return _rename_result("conflict", "alias_already_bound")
    previous_event = db.query(CivitaiSourceAliasHistory).filter_by(registry_version=request.expected_registry_version).order_by(CivitaiSourceAliasHistory.id.desc()).first()
    created_at = datetime.now(timezone.utc)
    after = {"primary": {"original_alias": request.new_primary_alias, "normalized_key": new_key}, "alternates": sorted([*before["alternates"], {"original_alias": old_primary.original_alias, "normalized_key": old_primary.normalized_key}], key=lambda item: item["normalized_key"])}
    event = CivitaiSourceAliasHistory(registry_version=request.expected_registry_version, operation="rename", before_aliases_json=canonical_json(before), after_aliases_json=canonical_json(after), previous_event_sha256=previous_event.event_sha256 if previous_event is not None else None, created_at=created_at)
    event.event_sha256 = canonical_sha256(_event_payload(registry_version=event.registry_version, operation="rename", before_aliases=before, after_aliases=after, previous_event_sha256=event.previous_event_sha256, created_at=created_at))
    try:
        db.add(CivitaiSourceAlias(registry_version=request.expected_registry_version, original_alias=request.new_primary_alias, normalized_key=new_key, alias_kind="primary"))
        old_primary.alias_kind = "alternate"
        db.add(event)
        db.flush()
        if not _acquire_active_target_gate(registry_version=request.expected_registry_version, db=db):
            db.rollback()
            return _rename_result("rejected", "target_archived")
        db.commit()
    except IntegrityError:
        db.rollback()
        return _rename_result("conflict", "alias_already_bound")
    except Exception:
        db.rollback()
        return _rename_result("corrupt", "rename_write_failed")
    new_primary = CivitaiSourceAliasView(original_alias=request.new_primary_alias, normalized_key=new_key, kind="primary")
    preserved = CivitaiSourceAliasView(original_alias=old_primary.original_alias, normalized_key=old_primary.normalized_key, kind="alternate")
    alternates = [CivitaiSourceAliasView(original_alias=item["original_alias"], normalized_key=item["normalized_key"], kind="alternate") for item in after["alternates"]]
    return _rename_result("success", "renamed", record=record_view, new_primary=new_primary, preserved_old_alternate=preserved, alternate_aliases=alternates, event=CivitaiSourceAliasHistoryEventView(id=event.id, registry_version=event.registry_version, operation="rename", before_aliases=before, after_aliases=after, previous_event_sha256=event.previous_event_sha256, event_sha256=event.event_sha256, created_at=_utc(event.created_at)))


def _archive_result(status: str, code: str, **kwargs: Any) -> CivitaiSourceAliasArchiveResult:
    return CivitaiSourceAliasArchiveResult(status=status, code=code, **kwargs)


def validate_archive_request(value: Any) -> CivitaiSourceAliasArchiveRequest | None:
    """Strict internal boundary: archive metadata always remains backend-owned."""
    try:
        raw_value = value.model_dump() if isinstance(value, CivitaiSourceAliasArchiveRequest) else value
        request = CivitaiSourceAliasArchiveRequest.model_validate(raw_value, strict=True)
        normalize_alias(request.current_primary_alias)
        return request
    except (ValidationError, TypeError, ValueError):
        return None


def archive_source_alias(request: Any, *, db: Any) -> CivitaiSourceAliasArchiveResult:
    """Atomically append the only terminal archive event without changing any alias binding."""
    request = validate_archive_request(request)
    if request is None:
        return _archive_result("rejected", "invalid_request")
    try:
        current_key = normalize_alias(request.current_primary_alias)
    except (TypeError, ValueError):
        return _archive_result("rejected", "alias_invalid")
    current_rows = db.query(CivitaiSourceAlias).filter_by(normalized_key=current_key).all()
    if not current_rows:
        entries, registry_error = _read_discovery_entries(db=db)
        if entries is None:
            return _archive_result("corrupt", registry_error or "registry_invalid")
        return _archive_result("missing", "current_alias_not_found")
    if len(current_rows) != 1:
        return _archive_result("corrupt", "non_unique_alias")
    primary = current_rows[0]
    if primary.alias_kind != "primary":
        entries, registry_error = _read_discovery_entries(db=db)
        if entries is None:
            return _archive_result("corrupt", registry_error or "registry_invalid")
        return _archive_result("missing", "current_alias_not_primary")
    if primary.registry_version != request.expected_registry_version:
        return _archive_result("rejected", "stale_registry_version")
    entries, registry_error = _read_discovery_entries(db=db)
    if entries is None:
        return _archive_result("corrupt", registry_error or "registry_invalid")
    record_rows = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=request.expected_registry_version).all()
    if len(record_rows) != 1:
        return _archive_result("corrupt", "record_non_unique_or_missing")
    record = record_rows[0]
    record_view, record_error = _record_view(record)
    if record_view is None:
        return _archive_result("corrupt", record_error or "record_invalid")
    if verify_source_alias_history_chain(request.expected_registry_version, db=db) is not None:
        return _archive_result("corrupt", "history_invalid")
    if record.archived_at is not None:
        return _archive_result("conflict", "already_archived")
    rows = db.query(CivitaiSourceAlias).filter_by(registry_version=request.expected_registry_version).all()
    snapshot = _alias_snapshot(rows)
    if snapshot is None:
        return _archive_result("corrupt", "primary_alias_invalid")
    previous_event = db.query(CivitaiSourceAliasHistory).filter_by(registry_version=request.expected_registry_version).order_by(CivitaiSourceAliasHistory.id.desc()).first()
    created_at = datetime.now(timezone.utc)
    event = CivitaiSourceAliasHistory(
        registry_version=request.expected_registry_version,
        operation="archive",
        before_aliases_json=canonical_json(snapshot),
        after_aliases_json=canonical_json(snapshot),
        previous_event_sha256=previous_event.event_sha256 if previous_event is not None else None,
        created_at=created_at,
    )
    event.event_sha256 = canonical_sha256(_event_payload(
        registry_version=event.registry_version, operation="archive", before_aliases=snapshot, after_aliases=snapshot,
        previous_event_sha256=event.previous_event_sha256, created_at=created_at,
    ))
    try:
        db.add(event)
        db.flush()
        if not _acquire_active_target_gate(
            registry_version=request.expected_registry_version, db=db, archived_at=created_at,
        ):
            db.rollback()
            rerecords = db.query(CivitaiSourceAliasRegistryRecord).filter_by(
                registry_version=request.expected_registry_version,
            ).all()
            if len(rerecords) == 1 and rerecords[0].archived_at is not None and verify_source_alias_history_chain(request.expected_registry_version, db=db) is None:
                return _archive_result("conflict", "already_archived")
            return _archive_result("corrupt", "archive_write_failed")
        db.commit()
    except IntegrityError:
        db.rollback()
        reread = db.query(CivitaiSourceAlias).filter_by(normalized_key=current_key).all()
        if len(reread) == 1 and reread[0].alias_kind == "primary":
            rerecords = db.query(CivitaiSourceAliasRegistryRecord).filter_by(registry_version=request.expected_registry_version).all()
            if len(rerecords) == 1 and rerecords[0].archived_at is not None and verify_source_alias_history_chain(request.expected_registry_version, db=db) is None:
                return _archive_result("conflict", "already_archived")
        return _archive_result("corrupt", "archive_write_failed")
    except Exception:
        db.rollback()
        return _archive_result("corrupt", "archive_write_failed")
    return _archive_result(
        "success", "archived", record=record_view, archived_at=_utc(created_at),
        event=CivitaiSourceAliasHistoryEventView(
            id=event.id, registry_version=event.registry_version, operation="archive", before_aliases=snapshot,
            after_aliases=snapshot, previous_event_sha256=event.previous_event_sha256, event_sha256=event.event_sha256,
            created_at=_utc(created_at),
        ),
    )
