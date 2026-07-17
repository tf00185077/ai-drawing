"""HTTP request and response DTOs for the Prompt Library API."""

from __future__ import annotations

from pydantic import Field

from app.core.prompt_library_models import (
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


class CombinationSummary(StrictModel):
    id: Slug
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
    id: Slug
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


class EntryWriteRequest(CategoryWriteRequest):
    prompt: str = Field(min_length=1)


class CombinationWriteRequest(CategoryWriteRequest):
    legacy_template: bool = False
    positive: list[PromptFragment] = Field(default_factory=list)
    negative: list[PromptFragment] = Field(default_factory=list)


class CombinationSaveIntent(CombinationWriteRequest):
    id: Slug


class ArchiveRequest(ConcurrencyToken):
    resource_type: ResourceType
    resource_id: Slug
    polarity: Polarity | None = None
    category_id: Slug | None = None


class ComposeRequest(StrictModel):
    combination_id: Slug | None = None
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
