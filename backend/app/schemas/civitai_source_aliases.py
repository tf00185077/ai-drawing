"""Frozen CIV-SA-A internal source-alias registry contracts; no HTTP/MCP surface."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Literal

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
    status: Literal["success", "rejected", "conflict", "missing", "corrupt"]
    code: str
    record: CivitaiSourceAliasRegistryView | None = None
    alias: CivitaiSourceAliasView | None = None
