"""Typed metadata on the existing resource row and its public read projection."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, StrictFloat, StrictStr


class TypedMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class MetadataDiagnostic(TypedMetadata):
    code: str
    field: str


class Recommendation(TypedMetadata):
    value: StrictInt | StrictFloat | StrictStr
    source_field: str


class LicenseSnapshot(TypedMetadata):
    values: dict[str, JsonValue] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class MeasuredEvidence(TypedMetadata):
    method: Literal['verified_bytes'] = 'verified_bytes'
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(ge=0, strict=True)
    mtime_ns: int = Field(strict=True)
    inode: int = Field(strict=True)


class ResourceMetadata(TypedMetadata):
    version: Literal[1] = 1
    origin: Literal['civitai_provider','legacy_notes']
    base_model: str | None = None
    declared_size_bytes: int | None = Field(default=None, ge=0, strict=True)
    trigger_words: list[str] = Field(default_factory=list)
    recommended_parameters: dict[str, Recommendation] = Field(default_factory=dict)
    license: LicenseSnapshot = Field(default_factory=LicenseSnapshot)
    source_evidence: dict[str, JsonValue] = Field(default_factory=dict)
    diagnostics: list[MetadataDiagnostic] = Field(default_factory=list)
    verification: MeasuredEvidence | None = None


class ResourceRecord(TypedMetadata):
    resource_id: int
    resource_name: str
    resource_type: str
    provider: str | None
    source_url: str | None
    model_id: str | None
    version_id: str | None
    civitai_file_id: str | None
    air: str | None
    base_model: str | None
    model_family: Literal['sdxl'] | None
    sha256: str | None
    sha256_verified: bool | None
    declared_size_bytes: int | None
    measured_size_bytes: int | None
    status: str
    installed: bool
    local_path: str | None
    path_available: bool | None
    trigger_words: list[str]
    recommended_parameters: dict[str, Recommendation]
    license: LicenseSnapshot
    metadata_origin: str | None
    metadata_version: int | None
    source_evidence: dict[str, JsonValue]
    diagnostics: list[MetadataDiagnostic]


class ResourceList(TypedMetadata):
    items: list[ResourceRecord]
    total: int
    limit: int
    offset: int
