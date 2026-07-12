"""CIV-F request schemas; canonical recipe and resolution semantics stay in CIV-A/C."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.generation_recipe import GenerationRecipe


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CivitaiRecipeImportRequest(_StrictModel):
    locator: int | str
    # JSON boundary contract: standard base64, strictly decoded only at the backend.
    embedded_image_base64: str | None = None

    @field_validator("embedded_image_base64")
    @classmethod
    def validate_embedded_image_base64(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("embedded_image_base64 must be strict standard base64") from exc
        return value

    def embedded_image_bytes(self) -> bytes | None:
        return base64.b64decode(self.embedded_image_base64, validate=True) if self.embedded_image_base64 is not None else None


class CivitaiRecipeInspectRequest(_StrictModel):
    recipe: GenerationRecipe


class LocalResourceLedgerEntryPayload(_StrictModel):
    kind: str
    local_path: str
    sha256: str | None = None
    civitai_model_id: int | None = None
    civitai_model_version_id: int | None = None
    civitai_file_id: int | None = None
    air: str | None = None
    availability: bool = True
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class CivitaiRecipeResolveRequest(_StrictModel):
    recipe: GenerationRecipe
    ledger: list[LocalResourceLedgerEntryPayload] = Field(default_factory=list)
    strict: bool


class CivitaiRecipeResolveLocalRequest(_StrictModel):
    """Strict backend-owned resolver input: callers never provide a ledger."""
    recipe: GenerationRecipe


class ResolutionEntryPayload(_StrictModel):
    index: int
    status: str
    matched_by: list[str] = Field(default_factory=list)
    expected_identity: dict[str, Any] = Field(default_factory=dict)
    actual_identity: dict[str, Any] | None = None
    local_path: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    hash_verified: bool = False


class ResourceResolutionReportPayload(_StrictModel):
    strict: bool
    ready: bool
    entries: list[ResolutionEntryPayload] = Field(default_factory=list)
    resource_lock: list[dict[str, Any]] = Field(default_factory=list)


class CivitaiRecipeBuildRequest(_StrictModel):
    recipe: GenerationRecipe
    resource_report: ResourceResolutionReportPayload
    model_family: str
    input_bindings: dict[str, Any] = Field(default_factory=dict)


class CivitaiRecipeRunRequest(_StrictModel):
    build: dict[str, Any]
    runtime_provenance: dict[str, Any]
    queue_params: dict[str, Any] = Field(default_factory=dict)
