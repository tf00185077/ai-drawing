"""Frozen CIV-SA-Y backend-only Gallery source-alias backfill contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.civitai_source_aliases import CivitaiSourceAliasRegistryView


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CivitaiSourceAliasGalleryBackfillRequest(_StrictModel):
    """Caller intent is deliberately limited to one Gallery row and an optional name."""

    gallery_image_id: int = Field(ge=1)
    primary_alias: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("primary_alias")
    @classmethod
    def primary_alias_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("primary_alias must contain a non-whitespace character")
        return value


class CivitaiSourceAliasBackfillCandidateView(_StrictModel):
    id: int
    gallery_image_id: int
    source_identity: dict[str, Any]
    acquisition_evidence_snapshot: dict[str, Any]
    acquisition_evidence_sha256: str
    parent_recipe_sha256: str
    thumbnail_path: str | None = None
    suggested_alias: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("created_at must be UTC-aware")
        return value.astimezone(timezone.utc)


class CivitaiSourceAliasGalleryBackfillResult(_StrictModel):
    status: Literal["named", "pending_name", "already_backfilled", "ineligible", "conflict", "corrupt"]
    code: str
    record: CivitaiSourceAliasRegistryView | None = None
    candidate: CivitaiSourceAliasBackfillCandidateView | None = None
    source_identity: dict[str, Any] | None = None
    acquisition_evidence_snapshot: dict[str, Any] | None = None
    acquisition_evidence_sha256: str | None = None
    parent_recipe_sha256: str | None = None

    @model_validator(mode="after")
    def require_complete_success_or_empty_failure(self) -> "CivitaiSourceAliasGalleryBackfillResult":
        target = (
            self.source_identity,
            self.acquisition_evidence_snapshot,
            self.acquisition_evidence_sha256,
            self.parent_recipe_sha256,
        )
        if self.status in {"named", "pending_name"}:
            if any(value is None for value in target):
                raise ValueError("successful backfill requires complete canonical target")
            if self.status == "named" and (self.record is None or self.candidate is not None):
                raise ValueError("named result requires only a registry record")
            if self.status == "pending_name" and (self.candidate is None or self.record is not None):
                raise ValueError("pending result requires only a candidate")
        elif self.status == "already_backfilled":
            if self.candidate is None or any(value is not None for value in target) or self.record is not None:
                raise ValueError("already_backfilled exposes only its durable candidate")
        elif self.record is not None or self.candidate is not None or any(value is not None for value in target):
            raise ValueError("failed backfill must not expose a partial target")
        return self
