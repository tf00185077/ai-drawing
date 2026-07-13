"""Frozen CIV-SA-A internal source-alias registry contracts; no HTTP/MCP surface."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_serializer, model_validator

from app.schemas.generation_recipe import GenerationRecipe, RecipeSource


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


class CivitaiSourceAliasRepointTarget(_StrictModel):
    """Caller-supplied immutable replacement content only; lifecycle evidence is backend-owned."""
    source_identity: CivitaiSourceAliasImmutableIdentity
    acquisition_evidence_snapshot: dict[str, Any]
    acquisition_evidence_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-fA-F]{64}$")]
    parent_recipe_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-fA-F]{64}$")]
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
    def evidence_hash_must_match_snapshot(self) -> "CivitaiSourceAliasRepointTarget":
        if canonical_sha256(self.acquisition_evidence_snapshot) != self.acquisition_evidence_sha256:
            raise ValueError("acquisition_evidence_sha256 does not match canonical snapshot")
        return self


class CivitaiSourceAliasRepointRequest(_StrictModel):
    current_primary_alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    expected_registry_version: Annotated[int, Field(strict=True, ge=1)]
    replacement: CivitaiSourceAliasRepointTarget

    @field_validator("current_primary_alias")
    @classmethod
    def require_nonblank_primary_alias(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("current_primary_alias must not be blank")
        return value


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


class CivitaiSourceAliasRepointTransitionEventView(_StrictModel):
    id: int
    from_registry_version: int
    to_registry_version: int
    aliases: dict[str, Any]
    from_record_sha256: str
    to_record_sha256: str
    source_history_tail_sha256: str | None = None
    previous_repoint_event_sha256: str | None = None
    event_sha256: str
    created_at: datetime


class CivitaiSourceAliasRepointResult(_StrictModel):
    status: Literal["success", "rejected", "conflict", "missing", "corrupt"]
    code: str
    from_record: CivitaiSourceAliasRegistryView | None = None
    to_record: CivitaiSourceAliasRegistryView | None = None
    event: CivitaiSourceAliasRepointTransitionEventView | None = None


class CivitaiSourceAliasRepointResponse(CivitaiSourceAliasRepointResult):
    """CIV-SA-O typed HTTP representation of one audited repoint transition."""


class CivitaiSourceAliasDomainResult(_StrictModel):
    status: Literal["success", "rejected", "conflict", "missing", "corrupt", "archived", "repointed"]
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


class CivitaiSourceAliasExplicitVersionResolveRequest(_StrictModel):
    """CIV-SA-Q internal explicit immutable registry-version selection intent."""

    alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    registry_version: Annotated[int, Field(strict=True, ge=1)]

    @field_validator("alias")
    @classmethod
    def require_nonblank_alias(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("alias must not be blank")
        return value


class CivitaiSourceAliasParentSelector(_StrictModel):
    """CIV-SA-T caller intent: one literal alias and, optionally, one audited version."""

    alias: Annotated[str, Field(strict=True, min_length=1, max_length=512)]
    registry_version: Annotated[int | None, Field(strict=True, ge=1)] = None

    @field_validator("alias")
    @classmethod
    def require_nonblank_alias(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("alias must not be blank")
        return value


class CivitaiSourceAliasLineageIdentity(_StrictModel):
    """The frozen, serializable immutable source projection carried in lineage."""

    provider: Literal["civitai"] = "civitai"
    image_id: Annotated[int | None, Field(strict=True, gt=0)] = None
    media_url: Annotated[str | None, Field(strict=True)] = None

    @model_validator(mode="after")
    def require_image_or_supported_media(self) -> "CivitaiSourceAliasLineageIdentity":
        if self.image_id is not None:
            return self
        if self.media_url is None:
            raise ValueError("source identity requires image_id or immutable media_url")
        CivitaiSourceAliasImmutableIdentity.model_validate({"provider": self.provider, "media_url": self.media_url}, strict=True)
        return self

    @model_serializer
    def serialize_immutable_projection(self) -> dict[str, object]:
        value: dict[str, object] = {"provider": self.provider}
        if self.image_id is not None:
            value["image_id"] = self.image_id
        else:
            value["media_url"] = self.media_url  # validated non-null above
        return value


class CivitaiSourceAliasLineageBinding(_StrictModel):
    """The immutable alias record that supplied one materialized Parent Recipe."""

    requested_alias: str
    matched_alias: CivitaiSourceAliasView
    registry_version: Annotated[int, Field(strict=True, ge=1)]
    source_identity: CivitaiSourceAliasLineageIdentity
    acquisition_evidence_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    parent_recipe_sha256: Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
    registry_created_at: datetime

    @field_validator("registry_created_at")
    @classmethod
    def require_utc_registry_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("registry_created_at must be UTC-aware")
        return value.astimezone(timezone.utc)


class CivitaiSourceAliasMaterializedParent(_StrictModel):
    """CIV-SA-T read-only materialization result; failures intentionally carry no target."""

    status: Literal["success", "rejected", "missing", "corrupt", "archived", "repointed"]
    code: str
    parent_recipe: GenerationRecipe | None = None
    parent_recipe_sha256: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$")] = None
    alias_binding: CivitaiSourceAliasLineageBinding | None = None

    @model_validator(mode="after")
    def require_complete_success_or_empty_failure(self) -> "CivitaiSourceAliasMaterializedParent":
        values = (self.parent_recipe, self.parent_recipe_sha256, self.alias_binding)
        if self.status == "success":
            if any(value is None for value in values):
                raise ValueError("successful materialization requires a parent recipe and complete alias binding")
        elif any(value is not None for value in values):
            raise ValueError("failed materialization must not expose a parent recipe or partial alias binding")
        return self


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
