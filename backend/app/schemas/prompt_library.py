"""HTTP request and response DTOs for the Prompt Library API."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.core.prompt_library_models import (
    CombinationId,
    Polarity,
    PromptCategory,
    PromptCombination,
    PromptEntry,
    PromptEntryRef,
    PromptFragment,
    PromptLibraryManifest,
    ResourceType,
    Slug,
    StrictModel,
)
from app.schemas.prompt_library_migration import (
    BlockingDocumentDiagnostic,
    ProvenanceResolutionRequest,
)


class PromptWarning(StrictModel):
    code: str
    message: str
    hint: str
    ref: PromptEntryRef | None = None
    details: dict[str, object] = Field(default_factory=dict)


class PromptLibraryDiagnostic(StrictModel):
    code: str
    message: str
    hint: str
    path: str
    details: dict[str, object] = Field(default_factory=dict)


class CategorySummary(StrictModel):
    id: Slug
    polarity: Polarity
    name_zh: str
    description_zh: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int
    revision: int
    archived: bool
    entry_count: int
    etag: str
    parent_id: Slug | None = None


class CombinationSummary(StrictModel):
    id: CombinationId
    name_zh: str
    description_zh: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int
    revision: int
    archived: bool
    legacy_template: bool
    positive_prompt_snapshot: str
    negative_prompt_snapshot: str
    etag: str


class CatalogResponse(StrictModel):
    manifest: PromptLibraryManifest
    categories: list[CategorySummary] = Field(default_factory=list)
    combinations: list[CombinationSummary] = Field(default_factory=list)
    diagnostics: list[PromptLibraryDiagnostic] = Field(default_factory=list)


class SearchHit(StrictModel):
    resource_type: ResourceType
    id: CombinationId
    polarity: Polarity | None = None
    category_id: Slug | None = None
    name_zh: str
    description_zh: str
    prompt: str | None = None
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    archived: bool
    score: int
    matched_fields: list[str] = Field(default_factory=list)


class SearchResponse(StrictModel):
    results: list[SearchHit] = Field(default_factory=list)


class ConcurrencyToken(StrictModel):
    expected_revision: int = Field(ge=0)
    expected_etag: str | None = None


class CategoryWriteRequest(ConcurrencyToken):
    name_zh: str = Field(min_length=1)
    description_zh: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order: int = Field(default=10, ge=0)
    parent_id: Slug | None = None


class EntryWriteRequest(CategoryWriteRequest):
    prompt: str = Field(min_length=1)


class CombinationWriteRequest(CategoryWriteRequest):
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)
    source_combination_id: CombinationId | None = None
    document_context_token: str | None = None
    literal_conversion_token: str | None = None
    provenance_resolutions: list[ProvenanceResolutionRequest] = Field(
        default_factory=list
    )


class CombinationSaveIntent(CombinationWriteRequest):
    id: CombinationId


class ArchiveRequest(ConcurrencyToken):
    resource_type: ResourceType
    resource_id: CombinationId
    polarity: Polarity | None = None
    category_id: Slug | None = None


RestoreResourceType = Literal["category", "entry"]


class RestoreRequest(ConcurrencyToken):
    resource_type: RestoreResourceType
    resource_id: Slug
    polarity: Polarity
    category_id: Slug | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> "RestoreRequest":
        if self.resource_type == "entry" and self.category_id is None:
            raise ValueError("category_id is required for entry restore")
        if self.resource_type == "category" and self.category_id is not None:
            raise ValueError("category_id is not allowed for category restore")
        return self


class ComposeRequest(StrictModel):
    combination_id: CombinationId | None = None
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)
    save_as: CombinationSaveIntent | None = None


class VersionedCategory(StrictModel):
    category: PromptCategory
    etag: str


class VersionedCombination(StrictModel):
    combination: PromptCombination
    etag: str
    repaired: bool = False
    warnings: list[PromptWarning] = Field(default_factory=list)
    blocking_diagnostics: list[BlockingDocumentDiagnostic] = Field(
        default_factory=list
    )
    document_context_token: str | None = None


class LiteralConversionAcknowledgeRequest(StrictModel):
    document_context_token: str


class LiteralConversionAcknowledgeResponse(StrictModel):
    literal_conversion_token: str
    diagnostic_ids: list[str]


class ComposeResponse(StrictModel):
    positive_prompt: str
    negative_prompt: str
    positive: list[PromptFragment]
    negative: list[PromptFragment]
    warnings: list[PromptWarning]
    snapshot_repaired: bool
    saved_combination: VersionedCombination | None = None


class WriteResponse(StrictModel):
    category: VersionedCategory | None = None
    combination: VersionedCombination | None = None
    entry: PromptEntry | None = None
    entry_revision: int | None = None
    affected_combinations: list[str] = Field(default_factory=list)
