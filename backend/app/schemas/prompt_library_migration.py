"""Typed contracts for the comma-atomic Prompt Library rollout."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.prompt_library_models import Polarity, StrictModel


MigrationState = Literal[
    "required",
    "applying",
    "incomplete",
    "validating",
    "rolled_back_required",
]


class CommaAtomicMigrationStatus(StrictModel):
    state: MigrationState | Literal["finalized"]
    marker_present: bool
    comma_atomic_ready: bool
    atomic_enforcement_active: bool
    run_id: str | None = None
    data_validated: bool = False


class CommaAtomicMarker(StrictModel):
    schema_version: Literal[1] = 1
    state: MigrationState
    run_id: str | None = None
    plan_hash: str | None = None
    data_validated: bool = False
    atomic_enforcement_active: bool = False


class CuratedAtomRecord(StrictModel):
    polarity: Polarity
    category_id: str
    source_entry_id: str
    source_prompt_sha256: str
    segment_index: int = Field(ge=0)
    raw_segment: str
    name_zh: str
    description_zh: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    derived_entry_id: str
    reviewed: Literal[True] = True


class LegacyRefLocator(StrictModel):
    polarity: Polarity
    category_id: str
    entry_id: str


class LegacyRefExpansion(StrictModel):
    source: LegacyRefLocator
    derived: list[LegacyRefLocator]


class MigrationDiagnostic(StrictModel):
    code: str
    message: str
    blocking: bool = True
    locator: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class MigrationInventory(StrictModel):
    source_entries: int
    comma_entries: int
    retained_entries: int
    derived_atoms: int
    final_entries: int
    blank_atoms: int
    combination_ids: list[str]
    combination_atoms: dict[str, int]


class MigrationReport(StrictModel):
    mode: Literal["audit", "dry-run", "validate"]
    inventory: MigrationInventory
    curation_records: int
    source_hashes: dict[str, str]
    target_hashes: dict[str, str]
    legacy_ref_expansions: list[LegacyRefExpansion] = Field(default_factory=list)
    planned_mutations: list[str] = Field(default_factory=list)
    diagnostics: list[MigrationDiagnostic] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
    plan_hash: str
    eligible: bool


class MigrationApplyRequest(StrictModel):
    plan_hash: str
    expected_source_hashes: dict[str, str]


class MigrationResumeRequest(StrictModel):
    run_id: str
    plan_hash: str


class MigrationRollbackRequest(StrictModel):
    run_id: str
    expected_post_hashes: dict[str, str]


class MigrationFinalizeRequest(StrictModel):
    run_id: str
    plan_hash: str


class MigrationMutationResult(StrictModel):
    action: Literal["apply", "resume", "rollback", "finalize"]
    run_id: str
    state: MigrationState | Literal["finalized"]
    changed_paths: list[str] = Field(default_factory=list)
    pre_hashes: dict[str, str] = Field(default_factory=dict)
    post_hashes: dict[str, str] = Field(default_factory=dict)


class BlockingDocumentDiagnostic(StrictModel):
    id: str
    code: Literal["legacy_reference_unresolved"] = "legacy_reference_unresolved"
    original_ref: LegacyRefLocator
    combination_id: str
    revision: int
    etag: str
    polarity: Polarity
    fallback_start_position: int = Field(ge=1)
    fallback_count: int = Field(ge=1)
    fallback_atom_hashes: list[str]
    blocking: Literal[True] = True


class DocumentContext(StrictModel):
    token: str
    combination_id: str
    revision: int
    etag: str
    diagnostic_ids: list[str] = Field(default_factory=list)
    atom_hashes: list[str] = Field(default_factory=list)


class LiteralConversionAcknowledgement(StrictModel):
    token: str
    document_context_token: str
    diagnostic_ids: list[str]


class ProvenanceResolutionRequest(StrictModel):
    document_context_token: str
    diagnostic_id: str
    action: Literal[
        "reviewed_mapping",
        "replacement_entries",
        "acknowledge_convert_to_literals",
    ]
    replacement_refs: list[LegacyRefLocator] = Field(default_factory=list)
