"""CIV-F request schemas; canonical recipe and resolution semantics stay in CIV-A/C."""
from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PositiveInt, field_validator, model_validator

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


class ResolutionExpectedIdentityPayload(_StrictModel):
    sha256: str | None = None
    civitai_model_id: int | None = None
    civitai_model_version_id: int | None = None
    civitai_file_id: int | None = None
    air: str | None = None


class ResolutionActualIdentityPayload(_StrictModel):
    actual_sha256: str | None = None
    sha256: str | None = None
    model_family: str | None = None
    civitai_model_id: int | None = None
    civitai_model_version_id: int | None = None
    civitai_file_id: int | None = None
    air: str | None = None


class ResolutionEntryPayload(_StrictModel):
    index: int
    status: str
    matched_by: list[str] = Field(default_factory=list)
    expected_identity: ResolutionExpectedIdentityPayload = Field(default_factory=ResolutionExpectedIdentityPayload)
    actual_identity: ResolutionActualIdentityPayload | None = None
    local_path: str | None = None
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)
    hash_verified: bool = False


class ResourceLockPayload(_StrictModel):
    index: int
    kind: str
    sha256: str | None = None
    local_path: str | None = None
    model_family: str | None = None
    civitai_model_id: int | None = None
    civitai_model_version_id: int | None = None
    civitai_file_id: int | None = None
    air: str | None = None


class ResourceResolutionReportPayload(_StrictModel):
    strict: bool
    ready: bool
    entries: list[ResolutionEntryPayload] = Field(default_factory=list)
    resource_lock: list[ResourceLockPayload] = Field(default_factory=list)


class RuntimeCapabilitiesPayload(_StrictModel):
    engine: str
    engine_version: str
    node_types: list[str]
    sampler_names: list[str]
    scheduler_names: list[str]
    snapshot_sha256: str


class CompatibilityDiagnosticPayload(_StrictModel):
    canonical_field: str
    code: str
    message: str


class CompatibilityLocalIdentityPayload(_StrictModel):
    local_path: str | None = None


class CompatibilityResourceDecisionPayload(_StrictModel):
    recipe_index: int
    kind: str
    sha256: str | None = None
    resolved_local_identity: CompatibilityLocalIdentityPayload
    declared_model_family: Literal["sdxl", "illustrious", "unknown"]
    required_node_types: list[str]
    compatible: bool
    diagnostics: list[CompatibilityDiagnosticPayload]


class CivitaiRecipeCompatibilityResponse(_StrictModel):
    status: Literal["compatible", "incompatible"]
    compatible: bool
    requested_model_family: Literal["sdxl", "illustrious"]
    compiler_contract: str
    runtime_snapshot_sha256: str | None = None
    resources: list[CompatibilityResourceDecisionPayload]
    diagnostics: list[CompatibilityDiagnosticPayload]


class CivitaiRecipeCompatibilityRequest(_StrictModel):
    """Frozen CIV-V-E preflight input; deliberately excludes build/queue/path controls."""
    recipe: GenerationRecipe
    resource_report: ResourceResolutionReportPayload
    model_family: Literal["sdxl", "illustrious"]
    runtime_capabilities: RuntimeCapabilitiesPayload


class CivitaiRecipeBuildRequest(_StrictModel):
    recipe: GenerationRecipe
    resource_report: ResourceResolutionReportPayload
    model_family: str
    input_bindings: dict[str, Any] = Field(default_factory=dict)


class CivitaiRecipeRunRequest(_StrictModel):
    build: dict[str, Any]
    runtime_provenance: dict[str, Any]
    queue_params: dict[str, Any] = Field(default_factory=dict)


class _StrictResourceModel(_StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CivitaiResourceInspectRequest(_StrictResourceModel):
    locator: int | str


ResourceKind = Literal["checkpoint", "lora", "vae", "embedding", "controlnet", "upscaler"]


class CivitaiResourceSource(_StrictResourceModel):
    provider: Literal["civitai"]
    civitai_model_id: PositiveInt | None = None


class CivitaiResourceCandidate(_StrictResourceModel):
    """The complete inspect descriptor; unsafe evidence remains representable for diagnostics."""
    civitai_model_id: PositiveInt | None = None
    civitai_model_version_id: PositiveInt | None = None
    civitai_file_id: PositiveInt | None = None
    resource_kind: ResourceKind | Literal["other"]
    name: str
    download_url_identity: str | None = None
    sha256: str | None = None
    byte_size: int | None = None
    availability: bool
    scan_status: str
    license: JsonValue | None = None
    usage_restrictions: JsonValue | None = None
    air: str | None = None
    model_family: str | None = None


class CivitaiResourceSelectedDescriptor(_StrictResourceModel):
    """Exactly one selection-ready candidate; service revalidates canonical semantics."""
    civitai_model_id: PositiveInt
    civitai_model_version_id: PositiveInt
    civitai_file_id: PositiveInt
    resource_kind: ResourceKind
    name: str
    download_url_identity: str
    sha256: str
    byte_size: PositiveInt
    availability: bool
    scan_status: str
    license: JsonValue
    usage_restrictions: JsonValue
    air: str | None
    model_family: str | None


class CivitaiResourceInspectResponse(_StrictResourceModel):
    status: Literal["completed"]
    source: CivitaiResourceSource
    model_family: str | None = None
    candidates: list[CivitaiResourceCandidate]


class ResourceSelectors(_StrictResourceModel):
    civitai_model_id: PositiveInt | None = None
    civitai_model_version_id: PositiveInt | None = None
    civitai_file_id: PositiveInt | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    resource_kind: ResourceKind | None = None

    @model_validator(mode="after")
    def require_one_selector(self) -> "ResourceSelectors":
        if not any(value is not None for value in self.__dict__.values()):
            raise ValueError("at least one exact selector is required")
        return self


class CivitaiResourceSelectRequest(_StrictResourceModel):
    inspect: CivitaiResourceInspectResponse
    selectors: ResourceSelectors


class CivitaiResourceInstallRequest(_StrictResourceModel):
    selected: CivitaiResourceSelectedDescriptor
    storage_root: Literal["checkpoints", "loras", "vae", "embeddings", "controlnet", "upscale_models"]
    overwrite: Literal[False] = False
