"""CIV-SA-A internal, offline source-alias registry service (no API/MCP side effects)."""
from __future__ import annotations

from datetime import timezone
import json
import re
import unicodedata
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError

from app.db.models import CivitaiSourceAlias, CivitaiSourceAliasRegistryRecord
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasDomainResult,
    CivitaiSourceAliasRegistryView,
    CivitaiSourceAliasRememberRequest,
    CivitaiSourceAliasView,
    CivitaiSourceAliasImmutableIdentity,
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
