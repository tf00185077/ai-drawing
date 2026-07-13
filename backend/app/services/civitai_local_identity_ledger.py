"""Backend-owned, read-only local Civitai resource identity ledger."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DownloadedResource
from app.services.civitai_acquisition import redact_secrets
from app.services.civitai_resource_resolution import LocalResourceLedgerEntry


_ID_FIELDS = (
    ("model_id", "civitai_model_id"),
    ("version_id", "civitai_model_version_id"),
    ("civitai_file_id", "civitai_file_id"),
)
_AVAILABLE_STATUSES = frozenset({"available", "installed"})


@dataclass(frozen=True)
class LocalLedgerSnapshot:
    entries: list[LocalResourceLedgerEntry]
    metadata: dict[str, Any]


def _numeric_identity(value: Any, field: str, errors: list[dict[str, str]]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        errors.append({"field": field, "code": "malformed_persisted_numeric_identity"})
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    errors.append({"field": field, "code": "malformed_persisted_numeric_identity"})
    return None


def _availability(row: DownloadedResource) -> bool:
    return str(row.status or "").strip().lower() in _AVAILABLE_STATUSES


def _audited_model_family(row: DownloadedResource, errors: list[dict[str, str]]) -> str | None:
    """Read only the installer's redacted provider snapshot; never infer from names."""
    if not row.notes:
        return None
    try:
        snapshot = json.loads(row.notes)
    except (TypeError, json.JSONDecodeError):
        errors.append({"field": "notes.model_family", "code": "malformed_persisted_model_family"})
        return None
    value = snapshot.get("model_family") if isinstance(snapshot, dict) else None
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append({"field": "notes.model_family", "code": "malformed_persisted_model_family"})
        return None
    normalized = value.strip().casefold()
    if normalized == "illustrious" or normalized.startswith("illustrious "):
        return "illustrious"
    if normalized == "sdxl" or normalized.startswith("sdxl "):
        return "sdxl"
    errors.append({"field": "notes.model_family", "code": "unsupported_persisted_model_family"})
    return None


def _entry_from_row(row: DownloadedResource) -> LocalResourceLedgerEntry:
    errors: list[dict[str, str]] = []
    identities = {
        target: _numeric_identity(getattr(row, source), source, errors)
        for source, target in _ID_FIELDS
    }
    model_family = _audited_model_family(row, errors)
    diagnostics: dict[str, Any] = {"database_id": row.id, "status": row.status}
    if errors:
        diagnostics["identity_errors"] = errors
    return LocalResourceLedgerEntry(
        kind=row.resource_type,
        local_path=row.local_path or "",
        sha256=row.sha256,
        air=row.air,
        availability=_availability(row),
        model_family=model_family,
        diagnostics=diagnostics,
        **identities,
    )


def local_identity_ledger(
    db: Session,
    *,
    kind: str | None = None,
    civitai_model_id: int | None = None,
    civitai_model_version_id: int | None = None,
    civitai_file_id: int | None = None,
    air: str | None = None,
    sha256: str | None = None,
    availability: bool | None = None,
) -> LocalLedgerSnapshot:
    """Return one deterministic local snapshot; no network, writes, or URL exposure."""
    rows = db.query(DownloadedResource).order_by(DownloadedResource.id.asc()).all()
    entries: list[LocalResourceLedgerEntry] = []
    excluded_non_civitai_count = 0
    excluded_no_local_path_count = 0
    for row in rows:
        if str(row.provider or "").strip().lower() != "civitai":
            excluded_non_civitai_count += 1
            continue
        if not row.local_path:
            excluded_no_local_path_count += 1
            continue
        entry = _entry_from_row(row)
        if kind is not None and entry.normalized_kind() != kind:
            continue
        if civitai_model_id is not None and entry.civitai_model_id != civitai_model_id:
            continue
        if civitai_model_version_id is not None and entry.civitai_model_version_id != civitai_model_version_id:
            continue
        if civitai_file_id is not None and entry.civitai_file_id != civitai_file_id:
            continue
        if air is not None and entry.air != air:
            continue
        if sha256 is not None and (entry.sha256 or "").lower() != sha256.lower():
            continue
        if availability is not None and entry.availability is not availability:
            continue
        entries.append(entry)
    return LocalLedgerSnapshot(
        entries=entries,
        metadata={
            "row_count": len(entries),
            "excluded_non_civitai_count": excluded_non_civitai_count,
            "excluded_no_local_path_count": excluded_no_local_path_count,
            "availability_policy": "available is true only for downloaded_resources status installed or available",
        },
    )


def ledger_payload(snapshot: LocalLedgerSnapshot) -> dict[str, Any]:
    entries = []
    for entry in snapshot.entries:
        entries.append({
            "kind": entry.normalized_kind(),
            "local_path": str(entry.local_path),
            "sha256": entry.sha256,
            "civitai_model_id": entry.civitai_model_id,
            "civitai_model_version_id": entry.civitai_model_version_id,
            "civitai_file_id": entry.civitai_file_id,
            "air": entry.air,
            "model_family": entry.model_family,
            "availability": entry.availability,
            "diagnostics": dict(entry.diagnostics),
        })
    return redact_secrets({"entries": entries, "snapshot": snapshot.metadata})
