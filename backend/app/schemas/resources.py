"""Typed metadata on the existing resource row and its public read projection."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictFloat, StrictStr


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


# Internal DTOs above remain permissive enough to parse version-1 legacy rows.
LicenseField = Literal['allowNoCredit','allowCommercialUse','allowDerivatives','allowDifferentLicense']
LicensePermission = Literal['None','Image','Rent','Sell','RentCivit']
ParameterKey = Literal['sampler','scheduler','steps','cfg','width','height','clip_skip']
DiagnosticCode = Literal['invalid_base_model','missing_trigger_words','invalid_trigger_words',
    'invalid_trigger_word','invalid_recommendations','invalid_recommendation','conflicting_recommendation',
    'invalid_license_field','license_incomplete','invalid_declared_size','missing_declared_size',
    'malformed_legacy_notes','conflicting_legacy_identity','conflicting_legacy_metadata','invalid_metadata',
    'missing_metadata','no_matching_workflow','missing_provider_identity','invalid_provider_identity',
    'missing_or_invalid_sha256','path_unavailable','verification_unknown','duplicate_legacy_candidate']
DiagnosticField = Literal['resource_id','resource_name','resource_type','provider','source_url',
    'model_id','version_id','civitai_file_id','air','base_model','model_family','sha256','sha256_verified',
    'declared_size_bytes','measured_size_bytes','status','installed','local_path','path_available',
    'trigger_words','recommended_parameters','license','metadata_origin','metadata_version','diagnostics']
PublicName = Annotated[str, Field(max_length=200, pattern=r'^[^\x00-\x1f\x7f-\x9f]*$')]


class PublicDiagnostic(TypedMetadata):
    code: DiagnosticCode
    field: DiagnosticField


class PublicRecommendation(TypedMetadata):
    value: StrictInt | StrictFloat | Annotated[StrictStr, Field(max_length=64, pattern=r'^[A-Za-z0-9_+. -]+$')]
    source_field: Literal['sampler','scheduler','steps','cfg','width','height','clip_skip',
        'version.meta.sampler','version.meta.scheduler','version.meta.steps','version.meta.cfg',
        'version.meta.cfgScale','version.meta.width','version.meta.height','version.meta.clip_skip','version.meta.clipSkip',
        'file.metadata.sampler','file.metadata.scheduler','file.metadata.steps','file.metadata.cfg',
        'file.metadata.cfgScale','file.metadata.width','file.metadata.height','file.metadata.clip_skip','file.metadata.clipSkip']


class PublicLicenseSnapshot(TypedMetadata):
    values: dict[LicenseField, StrictBool | LicensePermission | list[LicensePermission]] = Field(default_factory=dict)
    missing_fields: list[LicenseField] = Field(default_factory=list)


class ResourceRecord(TypedMetadata):
    resource_id: int
    resource_name: PublicName
    resource_type: PublicName
    provider: PublicName | None
    source_url: str | None
    model_id: str | None
    version_id: str | None
    civitai_file_id: str | None
    air: PublicName | None
    base_model: PublicName | None
    model_family: Literal['sdxl'] | None
    sha256: str | None
    sha256_verified: bool | None
    declared_size_bytes: int | None
    measured_size_bytes: int | None
    status: str
    installed: bool
    local_path: str | None
    path_available: bool | None
    trigger_words: list[PublicName] = Field(max_length=32)
    recommended_parameters: dict[ParameterKey, PublicRecommendation]
    license: PublicLicenseSnapshot
    metadata_origin: Literal['civitai_provider','legacy_notes'] | None
    metadata_version: Literal[1] | None
    diagnostics: list[PublicDiagnostic]


class ResourceList(TypedMetadata):
    items: list[ResourceRecord]
    total: int
    limit: int
    offset: int
