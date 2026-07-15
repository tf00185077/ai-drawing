"""CIV-C offline resource identity resolution against a local resource ledger."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.schemas.generation_recipe import RecipeResource, ResourceKind
from app.services.civitai_acquisition import redact_secrets


_IDENTITY_FIELDS = (
    "civitai_model_id",
    "civitai_model_version_id",
    "civitai_file_id",
    "air",
    "sha256",
)


@dataclass(frozen=True)
class LocalResourceLedgerEntry:
    kind: ResourceKind | str
    local_path: Path | str
    sha256: str | None = None
    civitai_model_id: int | None = None
    civitai_model_version_id: int | None = None
    civitai_file_id: int | None = None
    air: str | None = None
    model_family: str | None = None
    availability: bool = True
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def normalized_kind(self) -> str:
        return self.kind.value if isinstance(self.kind, ResourceKind) else str(self.kind)


@dataclass
class ResolutionEntry:
    index: int
    status: str
    matched_by: list[str]
    expected_identity: dict[str, Any]
    actual_identity: dict[str, Any] | None
    local_path: str | None
    diagnostics: dict[str, Any]
    hash_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return redact_secrets(asdict(self))


@dataclass
class ResourceResolutionReport:
    strict: bool
    ready: bool
    entries: list[ResolutionEntry]
    resource_lock: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return redact_secrets({
            "strict": self.strict,
            "ready": self.ready,
            "entries": [entry.to_dict() for entry in self.entries],
            "resource_lock": self.resource_lock,
        })


def _digest(path: Path) -> str:
    from app.services.file_digest_cache import sha256_for

    return sha256_for(path)


def _identity(value: RecipeResource | LocalResourceLedgerEntry) -> dict[str, Any]:
    return {field: getattr(value, field) for field in _IDENTITY_FIELDS if getattr(value, field) is not None}


def _values_match(field: str, actual: Any, expected: Any) -> bool:
    if field == "sha256" and isinstance(actual, str) and isinstance(expected, str):
        return actual.lower() == expected.lower()
    return actual == expected


def _candidate_matches(expected: dict[str, Any], candidate: LocalResourceLedgerEntry) -> bool:
    return all(_values_match(field, getattr(candidate, field), value) for field, value in expected.items())


def _candidate_conflicts(expected: dict[str, Any], candidate: LocalResourceLedgerEntry) -> bool:
    return any(
        getattr(candidate, field) is not None and not _values_match(field, getattr(candidate, field), value)
        for field, value in expected.items()
    )


def _entry_for(index: int, resource: RecipeResource, ledger: Iterable[LocalResourceLedgerEntry]) -> ResolutionEntry:
    expected = _identity(resource)
    same_kind = [entry for entry in ledger if entry.normalized_kind() == resource.kind.value]
    # A mutable display name is deliberately not an identity component.  Without a
    # supplied immutable component there is nothing to intersect against the ledger.
    if not expected:
        return ResolutionEntry(
            index=index, status="missing", matched_by=[], expected_identity={},
            actual_identity=None, local_path=None,
            diagnostics={"candidate_count": len(same_kind), "reason": "no immutable identity components"},
        )
    matches = [entry for entry in same_kind if _candidate_matches(expected, entry)]
    conflicts = [entry for entry in same_kind if _candidate_conflicts(expected, entry)]
    if not matches:
        return ResolutionEntry(
            index=index,
            status="mismatch" if conflicts else "missing",
            matched_by=[], expected_identity=expected, actual_identity=None, local_path=None,
            diagnostics=redact_secrets({"candidate_count": len(same_kind), "conflicting_candidate_count": len(conflicts)}),
        )
    if len(matches) != 1:
        return ResolutionEntry(
            index=index, status="ambiguous", matched_by=list(expected), expected_identity=expected,
            actual_identity=None, local_path=None,
            diagnostics=redact_secrets({"matching_candidate_count": len(matches)}),
        )
    candidate = matches[0]
    actual = _identity(candidate)
    if candidate.model_family is not None:
        actual["model_family"] = candidate.model_family
    path = Path(candidate.local_path)
    base_diagnostics = redact_secrets(dict(candidate.diagnostics))
    if not candidate.availability:
        return ResolutionEntry(
            index=index, status="unavailable", matched_by=list(expected), expected_identity=expected,
            actual_identity=actual, local_path=str(path), diagnostics={**base_diagnostics, "availability": False},
        )
    if not path.is_file():
        return ResolutionEntry(
            index=index, status="mismatch", matched_by=list(expected), expected_identity=expected,
            actual_identity=actual, local_path=str(path), diagnostics={**base_diagnostics, "file": "missing"},
        )
    actual_digest = _digest(path)
    expected_sha = expected.get("sha256")
    ledger_sha = candidate.sha256.lower() if candidate.sha256 else None
    verified = expected_sha is not None and ledger_sha == expected_sha and actual_digest == expected_sha
    if (ledger_sha is not None and actual_digest != ledger_sha) or (expected_sha is not None and actual_digest != expected_sha):
        return ResolutionEntry(
            index=index, status="mismatch", matched_by=list(expected), expected_identity=expected,
            actual_identity={**actual, "actual_sha256": actual_digest}, local_path=str(path),
            diagnostics={**base_diagnostics, "hash_verified": False}, hash_verified=False,
        )
    return ResolutionEntry(
        index=index, status="resolved", matched_by=list(expected), expected_identity=expected,
        actual_identity={**actual, "actual_sha256": actual_digest}, local_path=str(path),
        diagnostics={**base_diagnostics, "hash_verified": verified, "sha256_required": expected_sha is not None},
        hash_verified=verified,
    )


def resolve_recipe_resources(
    resources: Iterable[RecipeResource],
    ledger: Iterable[LocalResourceLedgerEntry],
    *,
    strict: bool,
    secrets: tuple[str, ...] = (),
) -> ResourceResolutionReport:
    """Resolve ordered recipe resources fail-closed on identity ambiguity or mismatch."""
    materialized_ledger = list(ledger)
    # Materialize resources once for a deterministic lock preserving original order.
    resource_list = list(resources)
    entries = [_entry_for(index, resource, materialized_ledger) for index, resource in enumerate(resource_list)]
    for entry in entries:
        entry.diagnostics = redact_secrets(entry.diagnostics, secrets=secrets)
    resource_lock = [
        {
            "index": entry.index,
            "kind": resource_list[entry.index].kind.value,
            "local_path": entry.local_path,
            "sha256": resource_list[entry.index].sha256,
            **{field: getattr(resource_list[entry.index], field) for field in _IDENTITY_FIELDS[:-1]
               if getattr(resource_list[entry.index], field) is not None},
            **({"model_family": entry.actual_identity["model_family"]}
               if entry.actual_identity is not None and entry.actual_identity.get("model_family") is not None else {}),
        }
        for entry in entries
        if entry.status == "resolved" and entry.hash_verified
    ]
    ready = (all(entry.status == "resolved" and entry.hash_verified for entry in entries) if strict else True)
    return ResourceResolutionReport(strict=strict, ready=ready, entries=entries, resource_lock=resource_lock)
