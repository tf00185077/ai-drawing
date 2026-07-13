"""Frozen CIV-SA-A internal source-alias registry contracts; no HTTP/MCP surface."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.generation_recipe import RecipeSource


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CivitaiSourceAliasImmutableIdentity(RecipeSource):
    """A recipe-validated Civitai source narrowed to an immutable image/media target."""

    @model_validator(mode="after")
    def require_immutable_image_identity(self) -> "CivitaiSourceAliasImmutableIdentity":
        if self.image_id is not None:
            return self
        if self.media_url is None:
            raise ValueError("source identity requires image_id or immutable media_url")
        parsed = urlparse(self.media_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"image.civitai.com", "images.civitai.com"}
            or not parsed.path
            or parsed.path == "/"
        ):
            raise ValueError("immutable media_url must be a supported Civitai image CDN identity")
        return self


class CivitaiSourceAliasRememberRequest(_StrictModel):
    primary_alias: str = Field(min_length=1, max_length=512)
    alternate_aliases: list[str] = Field(default_factory=list, max_length=32)
    source_identity: CivitaiSourceAliasImmutableIdentity
    acquisition_evidence_snapshot: dict[str, Any]
    acquisition_evidence_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    parent_recipe_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    thumbnail_url: HttpUrl | None = None
    thumbnail_path: str | None = Field(default=None, max_length=1024)
    user_note: str | None = Field(default=None, max_length=4096)
    approved_tags: list[str] = Field(default_factory=list, max_length=64)
    prompt_summary: str | None = Field(default=None, max_length=4096)

    @field_validator("acquisition_evidence_sha256", "parent_recipe_sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        value = value.lower()
        if _SHA256.fullmatch(value) is None:
            raise ValueError("must be a 64-character hexadecimal SHA-256")
        return value

    @field_validator("thumbnail_path", "user_note", "prompt_summary")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("optional text must not be blank when supplied")
        return value

    @field_validator("approved_tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("approved_tags must be nonblank and unique")
        return normalized

    @model_validator(mode="after")
    def evidence_hash_must_match_snapshot(self) -> "CivitaiSourceAliasRememberRequest":
        if canonical_sha256(self.acquisition_evidence_snapshot) != self.acquisition_evidence_sha256:
            raise ValueError("acquisition_evidence_sha256 does not match canonical snapshot")
        return self


class CivitaiSourceAliasView(_StrictModel):
    original_alias: str
    normalized_key: str
    kind: Literal["primary", "alternate"]


class CivitaiSourceAliasRegistryView(_StrictModel):
    registry_version: int
    source_identity: dict[str, Any]
    acquisition_evidence_snapshot: dict[str, Any]
    acquisition_evidence_sha256: str
    parent_recipe_sha256: str
    thumbnail_url: str | None = None
    thumbnail_path: str | None = None
    user_note: str | None = None
    approved_tags: list[str] = Field(default_factory=list)
    prompt_summary: str | None = None
    created_at: datetime


class CivitaiSourceAliasDomainResult(_StrictModel):
    status: Literal["success", "rejected", "conflict", "missing", "corrupt", "archived"]
    code: str
    record: CivitaiSourceAliasRegistryView | None = None
    alias: CivitaiSourceAliasView | None = None


class CivitaiSourceAliasRenameRequest(_StrictModel):
    current_primary_alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    new_primary_alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    expected_registry_version: Annotated[int, Field(strict=True, ge=1)]


class CivitaiSourceAliasHistoryEventView(_StrictModel):
    id: int
    registry_version: int
    operation: Literal["rename", "archive"]
    before_aliases: dict[str, Any]
    after_aliases: dict[str, Any]
    previous_event_sha256: str | None = None
    event_sha256: str
    created_at: datetime


class CivitaiSourceAliasRenameResult(_StrictModel):
    status: Literal["success", "rejected", "conflict", "missing", "corrupt"]
    code: str
    record: CivitaiSourceAliasRegistryView | None = None
    new_primary: CivitaiSourceAliasView | None = None
    preserved_old_alternate: CivitaiSourceAliasView | None = None
    alternate_aliases: list[CivitaiSourceAliasView] = Field(default_factory=list)
    event: CivitaiSourceAliasHistoryEventView | None = None


class CivitaiSourceAliasRenameResponse(CivitaiSourceAliasRenameResult):
    """CIV-SA-J typed HTTP representation of one audited rename result."""


class CivitaiSourceAliasArchiveRequest(_StrictModel):
    """CIV-SA-I strict internal archive intent; callers cannot supply lifecycle evidence."""

    current_primary_alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    expected_registry_version: Annotated[int, Field(strict=True, ge=1)]


class CivitaiSourceAliasArchiveResult(_StrictModel):
    status: Literal["success", "rejected", "conflict", "missing", "corrupt"]
    code: str
    record: CivitaiSourceAliasRegistryView | None = None
    archived_at: datetime | None = None
    event: CivitaiSourceAliasHistoryEventView | None = None


class CivitaiSourceAliasArchiveResponse(CivitaiSourceAliasArchiveResult):
    """CIV-SA-L typed HTTP representation of one audited archive result."""


class CivitaiSourceAliasResolveRequest(_StrictModel):
    """One unmodified human alias input for the committed exact resolver."""

    alias: str = Field(max_length=512)


class CivitaiSourceAliasResolveResponse(CivitaiSourceAliasRegistryView):
    """The audited registry binding plus the persisted alias that matched it."""

    matched_alias: CivitaiSourceAliasView


class CivitaiSourceAliasRegistryEntry(_StrictModel):
    """One validated registry binding with its complete alias namespace view."""

    primary_alias: CivitaiSourceAliasView
    alternate_aliases: list[CivitaiSourceAliasView] = Field(default_factory=list)
    record: CivitaiSourceAliasRegistryView


class CivitaiSourceAliasRegistryListResult(_StrictModel):
    """CIV-SA-E offline registry listing result; corrupt storage never yields entries."""

    status: Literal["success", "rejected", "corrupt"]
    code: str
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    entries: list[CivitaiSourceAliasRegistryEntry] = Field(default_factory=list)


class CivitaiSourceAliasSearchCandidate(CivitaiSourceAliasRegistryEntry):
    """A scored read-only discovery candidate, deliberately never a resolution target."""

    score: int = Field(ge=0)
    matched_fields: list[Literal[
        "primary_alias", "alternate_aliases", "approved_tags", "user_note", "source_metadata", "prompt_summary",
    ]] = Field(default_factory=list)


class CivitaiSourceAliasRegistrySearchResult(_StrictModel):
    """CIV-SA-E offline search result; candidates require explicit later selection."""

    status: Literal["success", "rejected", "corrupt"]
    code: str
    normalized_query: str | None = None
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    candidates: list[CivitaiSourceAliasSearchCandidate] = Field(default_factory=list)


class SourceAliasRegistryListResponse(CivitaiSourceAliasRegistryListResult):
    """CIV-SA-F typed HTTP representation of the audited CIV-SA-E list result."""


class SourceAliasRegistrySearchRequest(_StrictModel):
    """CIV-SA-F strict candidate-search request; no selection intent is accepted."""

    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SourceAliasRegistrySearchResponse(CivitaiSourceAliasRegistrySearchResult):
    """CIV-SA-F typed HTTP representation of CIV-SA-E candidates only."""
