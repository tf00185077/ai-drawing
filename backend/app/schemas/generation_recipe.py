"""Versioned, offline-safe foundation for auditable Civitai generation recipes.

This module deliberately contains no HTTP, database, or ComfyUI calls. Importers in
later CIV stages normalize their source payload into :class:`GenerationRecipe` before
resource resolution or workflow construction.
"""
from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
import hashlib
import json
import re
from typing import Any, Iterable, Literal, Mapping
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationInfo, field_validator, model_validator


RECIPE_SCHEMA_VERSION = "1.0"
# Recipes persist seeds through signed 64-bit database-compatible columns. Do not
# silently accept unsigned 64-bit values until that storage contract is versioned.
MAX_SIGNED_64_BIT_SEED = 9_223_372_036_854_775_807
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_CIVITAI_BROWSER_HOSTS = frozenset({"civitai.com", "www.civitai.com"})
_CIVITAI_CDN_HOSTS = frozenset({"image.civitai.com", "images.civitai.com"})


class _TrustedProvenanceCapability:
    """Non-serializable, record-scoped authority issued by an evidence boundary."""

    def __init__(self, identities: Iterable[tuple[str, str, str, str | None]]) -> None:
        self.identities = frozenset(identities)


def _is_civitai_image_or_media_identity_url(value: str | None) -> bool:
    """Return whether a URL identifies one generated image, not an acquisition model.

    Model and download URLs remain permitted recipe provenance because later stages need
    them to acquire resources. They cannot, however, identify the particular image whose
    generation is being reproduced. A post page is similarly non-unique unless paired
    with an image ID or an immutable Civitai CDN media URL.
    """
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    return bool(
        parsed.scheme == "https"
        and (
            host in _CIVITAI_BROWSER_HOSTS
            and re.fullmatch(r"/images/[1-9][0-9]*", path)
            or host in _CIVITAI_CDN_HOSTS
            and bool(path and path != "/")
        )
    )


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    """Return the stable identity digest for a JSON-compatible workflow snapshot."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _nonblank(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be blank")
    return normalized


def _json_pointer_get(payload: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer without permissive fallback behavior."""
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must be empty or start with '/'")
    current = payload
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise ValueError("JSON Pointer does not exist in evidence payload")
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ValueError("JSON Pointer does not exist in evidence payload")
    return current


class ReproductionLevel(StrEnum):
    """The strongest claim the recipe's recorded evidence supports."""

    EXACT_READY = "exact_ready"
    WORKFLOW_READY_BUT_RUNTIME_MAY_DIFFER = "workflow_ready_but_runtime_may_differ"
    APPROXIMATE_ONLY = "approximate_only"
    NOT_REPRODUCIBLE = "not_reproducible"


class EvidenceSource(StrEnum):
    CIVITAI_API = "civitai_api"
    EMBEDDED_METADATA = "embedded_metadata"
    WORKFLOW_SNAPSHOT = "workflow_snapshot"
    RUNTIME_INSPECTION = "runtime_inspection"
    IMPORTER = "importer"
    USER_SUPPLIED = "user_supplied"


class MissingCriticality(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class RecipeSource(BaseModel):
    """Civitai provenance identifiers; acquisition is intentionally a later stage."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["civitai"] = "civitai"
    url: str | None = None
    image_id: int | None = Field(default=None, gt=0)
    post_id: int | None = Field(default=None, gt=0)
    model_id: int | None = Field(default=None, gt=0)
    model_version_id: int | None = Field(default=None, gt=0)
    media_url: str | None = None

    @field_validator("url", "media_url")
    @classmethod
    def _validate_civitai_identity_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Civitai identity URL must not be blank")
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower()
        path = parsed.path
        is_browser_identity = host in {"civitai.com", "www.civitai.com"} and bool(
            re.fullmatch(r"/(?:images|posts)/[1-9][0-9]*", path.rstrip("/"))
            or re.fullmatch(r"/models/[1-9][0-9]*(?:/[A-Za-z0-9][A-Za-z0-9._~-]*)?", path)
            or re.fullmatch(r"/api/download/models/[1-9][0-9]*", path.rstrip("/"))
        )
        is_cdn_identity = host in {"image.civitai.com", "images.civitai.com"} and bool(path and path != "/")
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port or not (is_browser_identity or is_cdn_identity):
            raise ValueError("URL must be a supported HTTPS Civitai image, post, model, or CDN identity")
        return normalized

    @model_validator(mode="after")
    def _validate_identity_components_agree(self) -> RecipeSource:
        """Reject separately supplied Civitai IDs that contradict the browser URL."""
        if self.url is None:
            return self
        parsed = urlparse(self.url)
        path = parsed.path.rstrip("/")
        components: dict[str, int] = {}
        for field, pattern in (
            ("image_id", r"/images/([1-9][0-9]*)"),
            ("post_id", r"/posts/([1-9][0-9]*)"),
            ("model_id", r"/models/([1-9][0-9]*)(?:/[^/]+)?"),
            ("model_version_id", r"/api/download/models/([1-9][0-9]*)"),
        ):
            match = re.fullmatch(pattern, path)
            if match:
                components[field] = int(match.group(1))
        # Identity query parameters are security-sensitive provenance.  Do not pick
        # an arbitrary duplicate, and do not silently ignore malformed values: either
        # case would make the source identity ambiguous.  ``keep_blank_values`` also
        # prevents an explicit ``?modelId=`` from disappearing during parsing.
        query = parse_qs(parsed.query, keep_blank_values=True)
        for field, query_name in (("model_id", "modelId"), ("model_version_id", "modelVersionId")):
            values = query.get(query_name, [])
            if not values:
                continue
            if len(values) != 1:
                raise ValueError(f"{query_name} must appear exactly once when supplied")
            raw_value = values[0]
            if not re.fullmatch(r"[1-9][0-9]*", raw_value):
                raise ValueError(f"{query_name} must be a positive integer when supplied")
            value = int(raw_value)
            if field in components and components[field] != value:
                raise ValueError(f"{field} conflicts between URL path and query identity")
            components[field] = value
        for field, url_value in components.items():
            supplied = getattr(self, field)
            if supplied is not None and supplied != url_value:
                raise ValueError(f"{field} conflicts with URL identity")
        return self


class ResourceKind(StrEnum):
    CHECKPOINT = "checkpoint"
    DIFFUSION_MODEL = "diffusion_model"
    TEXT_ENCODER = "text_encoder"
    VAE = "vae"
    LORA = "lora"
    EMBEDDING = "embedding"
    CONTROLNET = "controlnet"
    UPSCALER = "upscaler"
    DETAILER = "detailer"
    OTHER = "other"


class RecipeResource(BaseModel):
    """An ordered resource reference, retaining identity evidence when available."""

    model_config = ConfigDict(extra="forbid")

    kind: ResourceKind
    name: str = Field(min_length=1)
    civitai_model_id: int | None = Field(default=None, gt=0)
    civitai_model_version_id: int | None = Field(default=None, gt=0)
    civitai_file_id: int | None = Field(default=None, gt=0)
    air: str | None = None
    sha256: str | None = None
    strength_model: float | None = Field(default=None, ge=0.0, le=2.0)
    strength_clip: float | None = Field(default=None, ge=0.0, le=2.0)
    clip_skip: int | None = Field(default=None, ge=1, le=24)

    @field_validator("name", "air")
    @classmethod
    def _strip_strings(cls, value: str | None) -> str | None:
        return _nonblank(value, "air or resource name")

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return normalized


class ResourceReference(BaseModel):
    """Stable dependency edge to a resource, never a mutable display filename."""

    model_config = ConfigDict(extra="forbid")

    kind: ResourceKind
    sha256: str | None = None
    civitai_model_id: int | None = Field(default=None, gt=0)
    civitai_model_version_id: int | None = Field(default=None, gt=0)
    civitai_file_id: int | None = Field(default=None, gt=0)
    air: str | None = None

    @field_validator("air")
    @classmethod
    def _validate_air(cls, value: str | None) -> str | None:
        return _nonblank(value, "air")

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return normalized

    @model_validator(mode="after")
    def _require_stable_identity(self) -> ResourceReference:
        if not any((
            self.sha256,
            self.civitai_model_id,
            self.civitai_model_version_id,
            self.civitai_file_id,
            self.air,
        )):
            raise ValueError(
                "resource reference requires sha256, a Civitai model/version/file ID, or AIR"
            )
        return self


class SamplingSettings(BaseModel):
    """Sampling fields shared by a base generation and optional follow-up passes."""

    model_config = ConfigDict(extra="forbid")

    # Signed 64-bit is the stable serialized/persistence contract for recipe seeds.
    seed: int | None = Field(default=None, ge=0, le=MAX_SIGNED_64_BIT_SEED)
    steps: int | None = Field(default=None, ge=1, le=1000)
    cfg: float | None = Field(default=None, ge=0.0, le=100.0)
    sampler: str | None = None
    scheduler: str | None = None
    denoise: float | None = Field(default=None, ge=0.0, le=1.0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class GenerationPass(BaseModel):
    """A named base, hires-fix, or other ordered generation pass."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    # Exact replay binds every declared pass to one concrete KSampler, rather than
    # relying on mutable JSON/dict insertion order.
    ksampler_node_id: str | None = Field(default=None, min_length=1)
    sampling: SamplingSettings = Field(default_factory=SamplingSettings)
    scale: float | None = Field(default=None, gt=0.0)
    upscale_model: str | None = None
    upscale_resource: ResourceReference | None = None
    inherits_from: str | None = None
    notes: str | None = None


class InputReference(BaseModel):
    """A source image/mask/etc. required by a recipe, pinned by content hash."""

    model_config = ConfigDict(extra="forbid")

    reference: str = Field(min_length=1)
    sha256: str
    kind: str = Field(min_length=1)

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return normalized


class ControlInput(BaseModel):
    """A ControlNet/IP-Adapter/etc. input without claiming unsupported semantics."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    input_ref: str | None = None
    model: str | None = None
    resource: ResourceReference | None = None
    preprocessor: str | None = None
    weight: float | None = Field(default=None, ge=0.0, le=2.0)
    start_percent: float | None = Field(default=None, ge=0.0, le=1.0)
    end_percent: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_window(self) -> "ControlInput":
        if self.start_percent is not None and self.end_percent is not None and self.start_percent > self.end_percent:
            raise ValueError("start_percent must be less than or equal to end_percent")
        return self


class DetailerSettings(BaseModel):
    """A detailer invocation recorded in its pipeline order."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    model: str | None = None
    resource: ResourceReference | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    denoise: float | None = Field(default=None, ge=0.0, le=1.0)


class PostprocessStep(BaseModel):
    """A postprocess operation (upscale, face restore, color, etc.)."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    model: str | None = None
    resource: ResourceReference | None = None
    scale: float | None = Field(default=None, gt=0.0)
    params: dict[str, Any] = Field(default_factory=dict)


class WorkflowOperationBinding(BaseModel):
    """Concrete workflow edge proving one declared recipe operation is executable."""

    model_config = ConfigDict(extra="forbid")

    canonical_field: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    input_name: str = Field(min_length=1)
    resource: ResourceReference


class WorkflowSnapshot(BaseModel):
    """Identifiable, structurally complete workflow evidence rather than a boolean claim."""

    model_config = ConfigDict(extra="forbid")

    reference: str = Field(min_length=1)
    snapshot: dict[str, Any] = Field(min_length=1)
    snapshot_sha256: str | None = None
    operation_bindings: list[WorkflowOperationBinding] = Field(default_factory=list)

    @field_validator("snapshot_sha256")
    @classmethod
    def _validate_snapshot_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("snapshot_sha256 must be a 64-character hexadecimal digest")
        return normalized


class WorkflowResourceLock(BaseModel):
    """Immutable edge from one workflow loader input to one resolved resource identity."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    input_name: str = Field(min_length=1)
    resource: ResourceReference

    @model_validator(mode="after")
    def _require_digest(self) -> "WorkflowResourceLock":
        if self.resource.sha256 is None:
            raise ValueError("workflow resource lock must include the resolved resource sha256")
        return self


class RuntimeProvenance(BaseModel):
    """Runtime identity needed to distinguish a workflow from its execution context."""

    model_config = ConfigDict(extra="forbid")

    engine: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    runtime_lock_sha256: str | None = None
    node_versions: dict[str, str] = Field(default_factory=dict)
    package_versions: dict[str, str] = Field(default_factory=dict)
    runtime_settings: dict[str, Any] = Field(default_factory=dict)
    inspection_snapshot: dict[str, Any] = Field(default_factory=dict)
    resource_locks: list["WorkflowResourceLock"] = Field(default_factory=list)

    @field_validator("runtime_lock_sha256")
    @classmethod
    def _validate_runtime_lock_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("runtime_lock_sha256 must be a 64-character hexadecimal digest")
        return normalized

    @field_validator("node_versions")
    @classmethod
    def _validate_node_versions(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for node_type, digest in value.items():
            digest = digest.strip().lower()
            if not node_type.strip() or not _SHA256_RE.fullmatch(digest):
                raise ValueError("node_versions must map non-empty node types to SHA-256 digests")
            normalized[node_type] = digest
        return normalized


def canonical_runtime_lock_document(runtime: RuntimeProvenance) -> dict[str, Any]:
    """The reproducibility-relevant runtime contract; references and snapshots are evidence, not lock inputs."""
    return {
        "engine": runtime.engine,
        "engine_version": runtime.engine_version,
        "node_versions": runtime.node_versions,
        "package_versions": runtime.package_versions,
        "runtime_settings": runtime.runtime_settings,
        "resource_locks": [lock.model_dump(exclude_none=True) for lock in runtime.resource_locks],
    }


class EvidenceAssertion(BaseModel):
    """One scoped canonical assertion in a digest-verified evidence manifest."""

    model_config = ConfigDict(extra="forbid")

    canonical_field: str = Field(min_length=1)
    path: str = Field(default="", description="RFC 6901 JSON Pointer within digest-bound payload")
    extractor: Literal["json_pointer"] = "json_pointer"
    # Kept only for backward-compatible parsing. It is never trusted for confirmation.
    value: Any | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        _json_pointer_get({}, value) if value == "" else None
        if value and not value.startswith("/"):
            raise ValueError("path must be an RFC 6901 JSON Pointer")
        return value


class EvidenceManifest(BaseModel):
    """Typed raw evidence: payload, canonical SHA-256, identity, and assertions."""

    model_config = ConfigDict(extra="forbid")

    identity: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    payload: dict[str, Any]
    sha256: str
    assertions: list[EvidenceAssertion] = Field(default_factory=list)

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return normalized


def canonical_evidence_manifest_document(manifest: EvidenceManifest) -> dict[str, Any]:
    """Digest all identity/reference/assertion metadata as well as the raw payload."""
    return {
        "identity": manifest.identity,
        "reference": manifest.reference,
        "payload": manifest.payload,
        "assertions": [
            {"canonical_field": assertion.canonical_field, "path": assertion.path, "extractor": assertion.extractor}
            for assertion in manifest.assertions
        ],
    }


class EvidenceRecord(BaseModel):
    """Typed provenance for one canonical field assertion, pinned to a snapshot/lock."""

    model_config = ConfigDict(extra="forbid")

    canonical_field: str = Field(min_length=1)
    source: EvidenceSource
    reference: str = Field(min_length=1)
    snapshot_sha256: str | None = None
    note: str | None = None

    @field_validator("snapshot_sha256")
    @classmethod
    def _validate_snapshot_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("snapshot_sha256 must be a 64-character hexadecimal digest")
        return normalized


class MissingRequirement(BaseModel):
    """A classified missing field; critical gaps always fail closed."""

    model_config = ConfigDict(extra="forbid")

    canonical_field: str = Field(min_length=1)
    criticality: MissingCriticality
    reason: str = Field(min_length=1)


_POSTPROCESS_RESOURCE_KINDS: dict[str, set[ResourceKind]] = {
    "upscale": {ResourceKind.UPSCALER},
    "face_restore": {ResourceKind.DETAILER},
    "face-restore": {ResourceKind.DETAILER},
    "detailer": {ResourceKind.DETAILER},
}


def _resolve_resource_reference(
    resources: list[RecipeResource],
    reference: ResourceReference,
    allowed_kinds: set[ResourceKind],
) -> list[RecipeResource]:
    """Resolve every supplied identity component and never fall back to a filename."""
    if reference.kind not in allowed_kinds:
        return []
    candidates = [resource for resource in resources if resource.kind is reference.kind]
    for field in ("sha256", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air"):
        value = getattr(reference, field)
        if value is not None:
            candidates = [resource for resource in candidates if getattr(resource, field) == value]
    return candidates


def _require_unique_resource_reference(
    resources: list[RecipeResource],
    reference: ResourceReference | None,
    allowed_kinds: set[ResourceKind],
    field: str,
) -> RecipeResource | None:
    if reference is None:
        return None
    candidates = _resolve_resource_reference(resources, reference, allowed_kinds)
    if len(candidates) != 1:
        raise ValueError(f"{field} must resolve to exactly one compatible RecipeResource")
    return candidates[0]


class GenerationRecipe(BaseModel):
    """Canonical, versioned recipe snapshot used by later importer/resolver stages."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = RECIPE_SCHEMA_VERSION
    source: RecipeSource
    base_prompt: str | None = None
    negative_prompt: str | None = None
    resources: list[RecipeResource] = Field(default_factory=list)
    sampling: SamplingSettings | None = None
    passes: list[GenerationPass] = Field(default_factory=list)
    inputs: list[InputReference] = Field(default_factory=list)
    controls: list[ControlInput] = Field(default_factory=list)
    detailers: list[DetailerSettings] = Field(default_factory=list)
    postprocess: list[PostprocessStep] = Field(default_factory=list)
    workflow: WorkflowSnapshot | None = None
    runtime: RuntimeProvenance | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    evidence_manifest: list[EvidenceManifest] = Field(default_factory=list)
    confirmed: list[EvidenceRecord] = Field(default_factory=list)
    inferred: list[EvidenceRecord] = Field(default_factory=list)
    missing: list[MissingRequirement] = Field(default_factory=list)
    # Not serialized: ordinary caller data cannot assert this capability. It is
    # attached only by the internal acquisition/inspection constructor below.
    _authoritative_evidence: frozenset[tuple[str, str, str, str | None]] = PrivateAttr(
        default_factory=frozenset
    )

    @model_validator(mode="after")
    def _validate_evidence_and_resource_identity(self, info: ValidationInfo) -> GenerationRecipe:
        # ``model_validate`` is a public trust boundary.  Only a non-serializable,
        # record-scoped capability supplied by an acquisition/metadata/inspection
        # boundary may leave a record confirmed; every other caller is demoted before
        # the canonical model (and therefore model_dump/API/DB use) is exposed.
        capability = (info.context or {}).get("provenance_capability")
        authorized = capability.identities if isinstance(capability, _TrustedProvenanceCapability) else frozenset()
        untrusted = [item for item in self.confirmed if _evidence_identity(item) not in authorized]
        if untrusted:
            self.confirmed = [item for item in self.confirmed if _evidence_identity(item) in authorized]
            self.inferred = [*self.inferred, *untrusted]
        confirmed = {item.canonical_field for item in self.confirmed}
        inferred = {item.canonical_field for item in self.inferred}
        overlap = confirmed & inferred
        if overlap:
            raise ValueError(
                "a canonical field cannot be present in both confirmed and inferred: "
                + ", ".join(sorted(overlap))
            )
        resource_hashes_by_name: dict[tuple[ResourceKind, str], str] = {}
        resource_identities: dict[tuple[ResourceKind, str], tuple[int | None, int | None, int | None, str | None]] = {}
        # A Civitai/AIR identifier is a global ledger key within its resource kind:
        # aliases may repeat the same complete tuple, never point at another digest.
        ledger: dict[str, tuple[str | None, int | None, int | None, int | None, str | None]] = {}
        for resource in self.resources:
            identity = (
                resource.sha256,
                resource.civitai_model_id,
                resource.civitai_model_version_id,
                resource.civitai_file_id,
                resource.air,
            )
            for label, value in (
                ("sha256", resource.sha256),
                ("civitai_model_id", resource.civitai_model_id),
                ("civitai_model_version_id", resource.civitai_model_version_id),
                ("civitai_file_id", resource.civitai_file_id),
                ("air", resource.air),
            ):
                if value is None:
                    continue
                key = f"{label}:{value}"
                prior = ledger.setdefault(key, identity)
                if prior != identity:
                    raise ValueError(f"conflicting global resource identity ledger for {label}={value}")
            if resource.sha256 is None:
                continue
            name_key = (resource.kind, resource.name)
            previous_hash = resource_hashes_by_name.setdefault(name_key, resource.sha256)
            if previous_hash != resource.sha256:
                raise ValueError(f"resource {resource.kind}:{resource.name} has different sha256 values")
            key = (resource.kind, resource.sha256)
            previous = resource_identities.setdefault(key, identity[1:])
            if previous != identity[1:]:
                raise ValueError(
                    f"ambiguous resource identity for {resource.kind} sha256={resource.sha256}"
                )
        for index, control in enumerate(self.controls):
            resolved = _require_unique_resource_reference(
                self.resources, control.resource, {ResourceKind.CONTROLNET}, f"controls[{index}].resource"
            )
            if control.model is not None and resolved is not None and control.model != resolved.name:
                raise ValueError(f"controls[{index}].model must equal its resolved resource name")
        for index, detailer in enumerate(self.detailers):
            resolved = _require_unique_resource_reference(
                self.resources, detailer.resource, {ResourceKind.DETAILER}, f"detailers[{index}].resource"
            )
            if detailer.model is not None and resolved is not None and detailer.model != resolved.name:
                raise ValueError(f"detailers[{index}].model must equal its resolved resource name")
        for index, postprocess in enumerate(self.postprocess):
            allowed_kinds = _POSTPROCESS_RESOURCE_KINDS.get(postprocess.kind.strip().lower())
            if postprocess.resource is not None:
                if allowed_kinds is None:
                    raise ValueError(f"postprocess[{index}].kind has no auditable resource-kind mapping")
                resolved = _require_unique_resource_reference(
                    self.resources, postprocess.resource, allowed_kinds, f"postprocess[{index}].resource"
                )
                if postprocess.model is not None and resolved is not None and postprocess.model != resolved.name:
                    raise ValueError(f"postprocess[{index}].model must equal its resolved resource name")
        for index, generation_pass in enumerate(self.passes):
            matched = _require_unique_resource_reference(
                self.resources,
                generation_pass.upscale_resource,
                {ResourceKind.UPSCALER},
                f"passes[{index}].upscale_resource",
            )
            if matched is not None and generation_pass.upscale_model is not None and matched.name != generation_pass.upscale_model:
                raise ValueError(f"passes[{index}].upscale_model must equal its resolved upscale_resource name")
        return self

    @property
    def loras(self) -> list[RecipeResource]:
        """LoRAs in source order, preserving loader order for later compilation."""
        return [resource for resource in self.resources if resource.kind is ResourceKind.LORA]


class ReproductionReport(BaseModel):
    """Deterministic, conservative assessment derived from recipe evidence."""

    model_config = ConfigDict(extra="forbid")

    level: ReproductionLevel
    missing: list[MissingRequirement] = Field(default_factory=list)
    critical_missing: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    requirements: dict[str, bool] = Field(default_factory=dict)


_MODEL_RESOURCE_KINDS = {
    ResourceKind.CHECKPOINT,
    ResourceKind.DIFFUSION_MODEL,
    ResourceKind.TEXT_ENCODER,
    ResourceKind.VAE,
    ResourceKind.LORA,
    ResourceKind.EMBEDDING,
    ResourceKind.CONTROLNET,
    ResourceKind.UPSCALER,
    ResourceKind.DETAILER,
}


_WORKFLOW_RESOURCE_LOADERS: dict[str, tuple[ResourceKind, str]] = {
    "CheckpointLoaderSimple": (ResourceKind.CHECKPOINT, "ckpt_name"),
    "CheckpointLoader": (ResourceKind.CHECKPOINT, "ckpt_name"),
    "UNETLoader": (ResourceKind.DIFFUSION_MODEL, "unet_name"),
    "CLIPLoader": (ResourceKind.TEXT_ENCODER, "clip_name"),
    "VAELoader": (ResourceKind.VAE, "vae_name"),
    "LoraLoader": (ResourceKind.LORA, "lora_name"),
    "LoraLoaderModelOnly": (ResourceKind.LORA, "lora_name"),
    "ControlNetLoader": (ResourceKind.CONTROLNET, "control_net_name"),
    "ControlNetLoaderAdvanced": (ResourceKind.CONTROLNET, "control_net_name"),
    "UpscaleModelLoader": (ResourceKind.UPSCALER, "model_name"),
    "UltralyticsDetectorProvider": (ResourceKind.DETAILER, "model_name"),
}

# Exact replay is fail-closed for custom nodes.  Every non-loader node allowed in
# an exact workflow is listed here; a future custom loader must add a typed
# resource contract above, rather than rely on input-name substring heuristics.
_KNOWN_NON_RESOURCE_NODES = frozenset({
    "KSampler", "CLIPTextEncode", "EmptyLatentImage", "EmptySD3LatentImage",
    "VAEEncode", "VAEEncodeForInpaint", "LatentUpscale", "VAEDecode", "SaveImage",
    "PreviewImage", "ControlNetApply", "ControlNetApplyAdvanced",
})


def _workflow_loader_dependencies(workflow: WorkflowSnapshot | None) -> list[tuple[str, ResourceKind, str, str]] | None:
    """Return recognised ``node_id, kind, input_name, resource_name`` loader edges."""
    if workflow is None:
        return None
    dependencies: list[tuple[str, ResourceKind, str, str]] = []
    for node_id, node in workflow.snapshot.items():
        if not isinstance(node, Mapping):
            return None
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(class_type, str) or not isinstance(inputs, Mapping):
            return None
        binding = _WORKFLOW_RESOURCE_LOADERS.get(class_type)
        if binding is None:
            if class_type not in _KNOWN_NON_RESOURCE_NODES:
                return None
            continue
        kind, input_name = binding
        resource_name = inputs.get(input_name)
        if not isinstance(resource_name, str) or not resource_name.strip():
            return None
        dependencies.append((str(node_id), kind, input_name, resource_name.strip()))
    return dependencies


def _resource_identity_tuple(resource: RecipeResource | ResourceReference) -> tuple[Any, ...]:
    """Identity used by every exact resource edge; partial references cannot weaken it."""
    return (
        resource.kind, resource.sha256, resource.civitai_model_id,
        resource.civitai_model_version_id, resource.civitai_file_id, resource.air,
    )


def _workflow_resources_are_exact(recipe: GenerationRecipe) -> bool:
    """Require immutable lock edges, not merely matching loader filenames."""
    dependencies = _workflow_loader_dependencies(recipe.workflow)
    if dependencies is None or recipe.runtime is None:
        return False
    for node_id, kind, input_name, resource_name in dependencies:
        matches = [
            resource for resource in recipe.resources
            if resource.kind is kind and resource.name == resource_name and resource.sha256 is not None
        ]
        if len(matches) != 1:
            return False
        resource = matches[0]
        locks = [
            lock for lock in recipe.runtime.resource_locks
            if lock.node_id == node_id and lock.input_name == input_name and lock.resource.kind is kind
        ]
        if len(locks) != 1 or _resource_identity_tuple(locks[0].resource) != _resource_identity_tuple(resource):
            return False
    return True


def _has_complete_sampling(recipe: GenerationRecipe) -> bool:
    sampling = recipe.sampling
    return sampling is not None and all(
        getattr(sampling, field) is not None
        for field in ("seed", "steps", "cfg", "sampler", "scheduler", "width", "height")
    )


def _passes_have_complete_sampling_contracts(recipe: GenerationRecipe) -> bool:
    """Bind every pass to one KSampler and compare its resolved contract field-by-field."""
    if recipe.workflow is None or not recipe.passes:
        return False
    nodes = recipe.workflow.snapshot
    resolved: dict[str, dict[str, Any]] = {}
    used_nodes: set[str] = set()
    fields = ("seed", "steps", "cfg", "sampler", "scheduler", "width", "height", "denoise")
    for pass_index, generation_pass in enumerate(recipe.passes):
        if not generation_pass.ksampler_node_id or generation_pass.ksampler_node_id in used_nodes:
            return False
        sampler = nodes.get(generation_pass.ksampler_node_id)
        if not isinstance(sampler, Mapping) or sampler.get("class_type") != "KSampler":
            return False
        used_nodes.add(generation_pass.ksampler_node_id)
        if generation_pass.inherits_from == "recipe.sampling":
            inherited = recipe.sampling.model_dump(exclude_none=True) if recipe.sampling else {}
        elif generation_pass.inherits_from:
            # Inheritance is ordered, acyclic, and may only point to a prior unique pass.
            inherited = resolved.get(generation_pass.inherits_from)
            if inherited is None:
                return False
        else:
            inherited = {}
        values = {**inherited, **generation_pass.sampling.model_dump(exclude_none=True)}
        if not all(values.get(field) is not None for field in fields):
            return False
        inputs = sampler.get("inputs")
        if not isinstance(inputs, Mapping):
            return False
        expected = {
            "seed": values["seed"], "steps": values["steps"], "cfg": values["cfg"],
            "sampler_name": values["sampler"], "scheduler": values["scheduler"], "denoise": values["denoise"],
        }
        if any(inputs.get(key) != value for key, value in expected.items()):
            return False
        latent = inputs.get("latent_image")
        if not isinstance(latent, list) or len(latent) < 2 or str(latent[0]) not in nodes:
            return False
        latent_node = nodes[str(latent[0])]
        latent_inputs = latent_node.get("inputs") if isinstance(latent_node, Mapping) else None
        if not isinstance(latent_inputs, Mapping):
            return False
        # Base latent must report the recipe dimensions. Follow-up passes may instead
        # consume an upstream VAE/image chain, which is topology-checked separately.
        if latent_node.get("class_type") in {"EmptyLatentImage", "EmptySD3LatentImage"} and (
            latent_inputs.get("width") != values["width"] or latent_inputs.get("height") != values["height"]
        ):
            return False
        is_followup = pass_index > 0 and (
            generation_pass.scale is not None
            or generation_pass.upscale_model is not None
            or generation_pass.upscale_resource is not None
        )
        if is_followup:
            # A hires/upscale pass must consume an upstream image/latent transform,
            # not silently restart from the base EmptyLatentImage.
            if latent_node.get("class_type") in {"EmptyLatentImage", "EmptySD3LatentImage"}:
                return False
            if latent_node.get("class_type") == "LatentUpscale":
                upstream = latent_inputs.get("samples")
                if not isinstance(upstream, list) or len(upstream) < 2:
                    return False
                upstream_node = nodes.get(str(upstream[0]))
                if not isinstance(upstream_node, Mapping) or upstream_node.get("class_type") != "KSampler":
                    return False
                if latent_inputs.get("width") != values["width"] or latent_inputs.get("height") != values["height"]:
                    return False
            if generation_pass.scale is not None:
                prior_values = next(reversed(resolved.values()), None)
                if prior_values is None or values["width"] != prior_values["width"] * generation_pass.scale or values["height"] != prior_values["height"] * generation_pass.scale:
                    return False
        resolved[generation_pass.name] = values
    return True


def _has_hash_for_every_model_resource(recipe: GenerationRecipe) -> bool:
    relevant = [resource for resource in recipe.resources if resource.kind in _MODEL_RESOURCE_KINDS]
    has_base_model = any(
        resource.kind in {ResourceKind.CHECKPOINT, ResourceKind.DIFFUSION_MODEL}
        for resource in relevant
    )
    return bool(relevant) and has_base_model and all(resource.sha256 for resource in relevant)


def _workflow_is_complete(workflow: WorkflowSnapshot | None) -> bool:
    if workflow is None or workflow.snapshot_sha256 != _canonical_json_sha256(workflow.snapshot):
        return False
    nodes = workflow.snapshot
    if not all(isinstance(node, Mapping) and isinstance(node.get("class_type"), str) and node["class_type"] and isinstance(node.get("inputs"), Mapping) for node in nodes.values()):
        return False

    def linked_node(value: Any) -> Mapping[str, Any] | None:
        if not isinstance(value, list) or len(value) < 2 or not isinstance(value[1], int):
            return None
        node = nodes.get(str(value[0]))
        return node if isinstance(node, Mapping) else None

    def traces_model(node: Mapping[str, Any], seen: set[int] | None = None) -> bool:
        if node.get("class_type") in {"CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader"}:
            return True
        if node.get("class_type") not in {"LoraLoader", "LoraLoaderModelOnly"}:
            return False
        upstream = linked_node(node["inputs"].get("model"))
        return upstream is not None and id(upstream) not in (seen or set()) and traces_model(upstream, (seen or set()) | {id(upstream)})

    def traces_conditioning(node: Mapping[str, Any], branch: str, seen: set[int] | None = None) -> bool:
        if node.get("class_type") == "CLIPTextEncode":
            return isinstance(node["inputs"].get("text"), str) and linked_node(node["inputs"].get("clip")) is not None
        if "ControlNetApply" not in str(node.get("class_type")):
            return False
        upstream = linked_node(node["inputs"].get(branch))
        return upstream is not None and id(upstream) not in (seen or set()) and traces_conditioning(upstream, branch, (seen or set()) | {id(upstream)})

    samplers = [(str(node_id), node) for node_id, node in nodes.items() if node.get("class_type") == "KSampler"]
    if not samplers:
        return False
    for _, sampler in samplers:
        inputs = sampler["inputs"]
        model = linked_node(inputs.get("model"))
        positive = linked_node(inputs.get("positive"))
        negative = linked_node(inputs.get("negative"))
        latent = linked_node(inputs.get("latent_image"))
        if model is None or positive is None or negative is None or latent is None:
            return False
        if not traces_model(model) or not traces_conditioning(positive, "positive") or not traces_conditioning(negative, "negative"):
            return False
        if latent.get("class_type") not in {"EmptyLatentImage", "EmptySD3LatentImage", "VAEEncode", "VAEEncodeForInpaint", "LatentUpscale"}:
            return False
    # A structurally valid sampler graph is not yet runnable: at least one terminal
    # sampler must decode through a VAE and reach a persisted output node.
    sampler_ids = {node_id for node_id, _ in samplers}
    terminal_sampler_ids = {
        node_id for node_id in sampler_ids
        if not any(str(value[0]) == node_id and node.get("class_type") == "KSampler"
                   for node in nodes.values() if isinstance(node, Mapping)
                   for value in (node.get("inputs", {}) or {}).values() if isinstance(value, list) and value)
    }
    decode_ids = {
        str(node_id) for node_id, node in nodes.items()
        if node.get("class_type") == "VAEDecode"
        and isinstance(node.get("inputs", {}).get("samples"), list)
        and str(node["inputs"]["samples"][0]) in terminal_sampler_ids
    }
    return bool(decode_ids) and any(
        node.get("class_type") == "SaveImage"
        and isinstance(node.get("inputs", {}).get("images"), list)
        and str(node["inputs"]["images"][0]) in decode_ids
        for node in nodes.values() if isinstance(node, Mapping)
    )


def _runtime_is_complete(runtime: RuntimeProvenance | None, workflow: WorkflowSnapshot | None) -> bool:
    if runtime is None or not runtime.runtime_lock_sha256 or not runtime.node_versions or not runtime.package_versions or not runtime.runtime_settings or not runtime.inspection_snapshot or workflow is None:
        return False
    if runtime.runtime_lock_sha256 != _canonical_json_sha256(canonical_runtime_lock_document(runtime)):
        return False
    required_types = {str(node.get("class_type")) for node in workflow.snapshot.values() if isinstance(node, Mapping)}
    return required_types.issubset(runtime.node_versions)


def _reference_matches(resources: list[RecipeResource], reference: ResourceReference | None, expected_kind: ResourceKind) -> bool:
    return reference is not None and len(_resolve_resource_reference(resources, reference, {expected_kind})) == 1


_EXTERNAL_RESOURCE_PARAM_KEYS = frozenset({
    "model",
    "modelname",
    "modelfile",
    "modelpath",
    "resource",
    "resourcename",
    "resourcefile",
    "resourcepath",
    "checkpoint",
    "checkpointname",
    "upscaler",
    "upscalemodel",
    "weights",
    "weightfile",
})


def _postprocess_declares_external_dependency(step: PostprocessStep) -> bool:
    """Detect opaque vendor params that name a model/resource dependency.

    ``params`` intentionally preserves vendor-specific metadata.  It must not become
    a bypass around the auditable ``resource`` reference when it names an external
    model file, checkpoint, upscaler, or weights.
    """
    if step.model is not None or step.resource is not None:
        return True

    def contains_resource_key(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested_value in value.items():
                normalized_key = re.sub(r"[-_\\s]", "", str(key).lower())
                if normalized_key in _EXTERNAL_RESOURCE_PARAM_KEYS and nested_value is not None:
                    return True
                if contains_resource_key(nested_value):
                    return True
        elif isinstance(value, list):
            return any(contains_resource_key(item) for item in value)
        return False

    return contains_resource_key(step.params)


def _dependency_gaps(recipe: GenerationRecipe) -> list[str]:
    input_refs = {input_ref.reference for input_ref in recipe.inputs}
    gaps: list[str] = []
    for index, control in enumerate(recipe.controls):
        if not control.input_ref or control.input_ref not in input_refs:
            gaps.append(f"controls[{index}].input_ref")
        if not _reference_matches(recipe.resources, control.resource, ResourceKind.CONTROLNET):
            gaps.append(f"controls[{index}].resource")
    for index, detailer in enumerate(recipe.detailers):
        if not _reference_matches(recipe.resources, detailer.resource, ResourceKind.DETAILER):
            gaps.append(f"detailers[{index}].resource")
    for index, postprocess in enumerate(recipe.postprocess):
        allowed_kinds = _POSTPROCESS_RESOURCE_KINDS.get(postprocess.kind.strip().lower())
        if not _postprocess_declares_external_dependency(postprocess):
            continue
        # An unknown postprocess kind with an external dependency cannot be
        # audited: it has no kind-compatible resource mapping to resolve.
        if allowed_kinds is None:
            gaps.append(f"postprocess[{index}].resource")
        elif postprocess.resource is None or len(
            _resolve_resource_reference(recipe.resources, postprocess.resource, allowed_kinds)
        ) != 1:
            gaps.append(f"postprocess[{index}].resource")
    for index, generation_pass in enumerate(recipe.passes):
        if generation_pass.upscale_model is not None or generation_pass.upscale_resource is not None:
            if generation_pass.upscale_resource is None or not _reference_matches(recipe.resources, generation_pass.upscale_resource, ResourceKind.UPSCALER):
                gaps.append(f"passes[{index}].upscale_resource")
    return gaps


def _has_auditable_source_identity(source: RecipeSource) -> bool:
    """Require an image-level Civitai identity, never merely an acquisition URL."""
    return bool(
        source.image_id
        or _is_civitai_image_or_media_identity_url(source.url)
        or _is_civitai_image_or_media_identity_url(source.media_url)
    )


def _canonical_evidence_value(recipe: GenerationRecipe, canonical_field: str) -> Any:
    """Return the exact canonical value an evidence assertion is allowed to attest."""
    if canonical_field == "source.identity":
        # An image ID, when present, is the stable image-level source identity. URLs
        # are acquisition/location provenance and may legitimately vary per importer.
        if recipe.source.image_id is not None:
            return {"image_id": recipe.source.image_id}
        return {
            key: value for key, value in recipe.source.model_dump(exclude_none=True).items()
            if key in {"url", "media_url"}
        }
    if canonical_field == "workflow":
        return recipe.workflow.snapshot if recipe.workflow else None
    if canonical_field == "sampling":
        return recipe.sampling.model_dump(exclude_none=True) if recipe.sampling else None
    if canonical_field == "conditioning":
        return {"base_prompt": recipe.base_prompt, "negative_prompt": recipe.negative_prompt}
    if canonical_field == "runtime":
        return canonical_runtime_lock_document(recipe.runtime) if recipe.runtime else None
    match = re.fullmatch(r"resources\[([0-9]+)\]\.identity", canonical_field)
    if match:
        index = int(match.group(1))
        return recipe.resources[index].model_dump(exclude_none=True) if index < len(recipe.resources) else None
    match = re.fullmatch(r"inputs\[([0-9]+)\]\.sha256", canonical_field)
    if match:
        index = int(match.group(1))
        return recipe.inputs[index].sha256 if index < len(recipe.inputs) else None
    match = re.fullmatch(r"(controls|detailers|postprocess)\[([0-9]+)\]\.resource", canonical_field)
    if match:
        values = getattr(recipe, match.group(1))
        index = int(match.group(2))
        resource = values[index].resource if index < len(values) else None
        return resource.model_dump(exclude_none=True) if resource else None
    match = re.fullmatch(r"passes\[([0-9]+)\]\.upscale_resource", canonical_field)
    if match:
        index = int(match.group(1))
        resource = recipe.passes[index].upscale_resource if index < len(recipe.passes) else None
        return resource.model_dump(exclude_none=True) if resource else None
    return None


def _evidence_snapshot_is_verified(recipe: GenerationRecipe, evidence: EvidenceRecord) -> bool:
    """Confirmation derives from a pointer into a re-hashed, metadata-bound manifest."""
    if evidence.snapshot_sha256 is None:
        return False
    for manifest in recipe.evidence_manifest:
        if manifest.reference != evidence.reference or manifest.sha256 != evidence.snapshot_sha256:
            continue
        if _canonical_json_sha256(canonical_evidence_manifest_document(manifest)) != manifest.sha256:
            continue
        if evidence.canonical_field == "runtime":
            if evidence.source is not EvidenceSource.RUNTIME_INSPECTION or recipe.runtime is None:
                continue
            if manifest.payload != recipe.runtime.inspection_snapshot:
                continue
        expected = _canonical_evidence_value(recipe, evidence.canonical_field)
        if expected is None:
            continue
        for assertion in manifest.assertions:
            if assertion.canonical_field != evidence.canonical_field:
                continue
            try:
                if _json_pointer_get(manifest.payload, assertion.path) == expected:
                    return True
            except ValueError:
                continue
    return False


def _evidence_identity(evidence: EvidenceRecord) -> tuple[str, str, str, str | None]:
    """Stable in-process key granted by a trusted boundary, never supplied by JSON."""
    return (
        evidence.canonical_field,
        evidence.source.value,
        evidence.reference,
        evidence.snapshot_sha256,
    )


def _has_authoritative_confirmation(recipe: GenerationRecipe, canonical_field: str) -> bool:
    """Confirmed evidence requires a digest-verified assertion from an acquisition boundary.

    A self-authored enum label cannot turn caller data into Civitai/API/inspection
    evidence. Importers and user submissions may be retained, but only as inferred.
    """
    if canonical_field == "runtime":
        allowed = {EvidenceSource.RUNTIME_INSPECTION}
    elif canonical_field == "source.identity":
        allowed = {EvidenceSource.CIVITAI_API, EvidenceSource.EMBEDDED_METADATA}
    elif canonical_field in {"workflow", "sampling", "conditioning"}:
        allowed = {EvidenceSource.EMBEDDED_METADATA, EvidenceSource.WORKFLOW_SNAPSHOT}
    else:
        allowed = {EvidenceSource.CIVITAI_API, EvidenceSource.EMBEDDED_METADATA, EvidenceSource.RUNTIME_INSPECTION}
    return any(
        evidence.canonical_field == canonical_field
        and _evidence_identity(evidence) in recipe._authoritative_evidence
        and evidence.source in allowed
        and _evidence_snapshot_is_verified(recipe, evidence)
        for evidence in recipe.confirmed
    )


def _confirmed_requirements(recipe: GenerationRecipe) -> dict[str, bool]:
    requirements = {
        "confirmed_source_identity": _has_authoritative_confirmation(recipe, "source.identity"),
        "confirmed_workflow": _has_authoritative_confirmation(recipe, "workflow"),
        "confirmed_sampling": _has_authoritative_confirmation(recipe, "sampling"),
        "confirmed_conditioning": _has_authoritative_confirmation(recipe, "conditioning"),
        "confirmed_runtime": _has_authoritative_confirmation(recipe, "runtime"),
    }
    for index, _ in enumerate(recipe.resources):
        requirements[f"confirmed_resources[{index}]"] = _has_authoritative_confirmation(recipe, f"resources[{index}].identity")
    for index, _ in enumerate(recipe.inputs):
        requirements[f"confirmed_inputs[{index}]"] = _has_authoritative_confirmation(recipe, f"inputs[{index}].sha256")
    for group, values, field in (("controls", recipe.controls, "resource"), ("detailers", recipe.detailers, "resource"), ("postprocess", recipe.postprocess, "resource"), ("passes", recipe.passes, "upscale_resource")):
        for index, value in enumerate(values):
            if getattr(value, field, None) is not None:
                requirements[f"confirmed_{group}[{index}]"] = _has_authoritative_confirmation(recipe, f"{group}[{index}].{field}")
    return requirements


def _workflow_declared_operations_are_exact(recipe: GenerationRecipe) -> bool:
    """Every enabled recipe operation needs a concrete, locked workflow input edge."""
    if recipe.workflow is None or recipe.runtime is None:
        return False
    required: list[tuple[str, ResourceReference | None]] = []
    for index, control in enumerate(recipe.controls):
        if control.resource is None:
            return False
        required.append((f"controls[{index}]", control.resource))
    for index, detailer in enumerate(recipe.detailers):
        if detailer.resource is None:
            return False
        required.append((f"detailers[{index}]", detailer.resource))
    for index, step in enumerate(recipe.postprocess):
        if _postprocess_declares_external_dependency(step):
            if step.resource is None:
                return False
            required.append((f"postprocess[{index}]", step.resource))
    for index, generation_pass in enumerate(recipe.passes):
        if generation_pass.upscale_model is not None or generation_pass.upscale_resource is not None:
            if generation_pass.upscale_resource is None:
                return False
            required.append((f"passes[{index}]", generation_pass.upscale_resource))
    for canonical_field, reference in required:
        bindings = [binding for binding in recipe.workflow.operation_bindings if binding.canonical_field == canonical_field]
        if len(bindings) != 1:
            return False
        binding = bindings[0]
        resource_matches = _resolve_resource_reference(recipe.resources, binding.resource, {binding.resource.kind})
        declared_matches = (
            _resolve_resource_reference(recipe.resources, reference, {reference.kind})
            if reference is not None else resource_matches
        )
        if len(resource_matches) != 1 or len(declared_matches) != 1 or resource_matches[0] != declared_matches[0]:
            return False
        resource = resource_matches[0]
        if _resource_identity_tuple(binding.resource) != _resource_identity_tuple(resource):
            return False
        if reference is not None and _resource_identity_tuple(reference) != _resource_identity_tuple(resource):
            return False
        node = recipe.workflow.snapshot.get(binding.node_id)
        inputs = node.get("inputs") if isinstance(node, Mapping) else None
        if not isinstance(inputs, Mapping) or inputs.get(binding.input_name) != resource_matches[0].name:
            return False
        locks = [
            lock for lock in recipe.runtime.resource_locks
            if lock.node_id == binding.node_id and lock.input_name == binding.input_name
        ]
        if len(locks) != 1 or _resource_identity_tuple(locks[0].resource) != _resource_identity_tuple(resource):
            return False
    return True


def assess_reproduction(recipe: GenerationRecipe) -> ReproductionReport:
    """Assess evidence conservatively; inferred values never establish exact replay."""
    dependency_gaps = _dependency_gaps(recipe)
    declared_critical = [item.canonical_field for item in recipe.missing if item.criticality is MissingCriticality.CRITICAL]
    critical_missing = list(dict.fromkeys([*declared_critical, *dependency_gaps]))
    requirements = {"source_identity": _has_auditable_source_identity(recipe.source),
                    "workflow": _workflow_is_complete(recipe.workflow), "workflow_resources": _workflow_resources_are_exact(recipe),
                    "workflow_declared_operations": _workflow_declared_operations_are_exact(recipe),
                    "sampling": _has_complete_sampling(recipe), "pass_sampling": _passes_have_complete_sampling_contracts(recipe),
                    "conditioning": recipe.base_prompt is not None and recipe.negative_prompt is not None,
                    "resource_hashes": _has_hash_for_every_model_resource(recipe), "inputs": all(item.sha256 for item in recipe.inputs),
                    "dependencies": not dependency_gaps, "runtime": _runtime_is_complete(recipe.runtime, recipe.workflow), **_confirmed_requirements(recipe)}
    if critical_missing:
        return ReproductionReport(level=ReproductionLevel.NOT_REPRODUCIBLE, missing=recipe.missing, critical_missing=critical_missing, caveats=["critical recipe evidence or dependency is missing"], requirements=requirements)
    exact_requirements = {name: value for name, value in requirements.items() if not name.startswith("confirmed_")}
    confirmed_requirements = {name: value for name, value in requirements.items() if name.startswith("confirmed_")}
    if all(exact_requirements.values()) and all(confirmed_requirements.values()) and not recipe.missing:
        return ReproductionReport(level=ReproductionLevel.EXACT_READY, requirements=requirements)
    if all(exact_requirements[name] for name in ("workflow", "sampling", "conditioning", "resource_hashes", "inputs", "dependencies")):
        return ReproductionReport(level=ReproductionLevel.WORKFLOW_READY_BUT_RUNTIME_MAY_DIFFER, missing=recipe.missing, caveats=[name for name, value in requirements.items() if not value], requirements=requirements)
    return ReproductionReport(level=ReproductionLevel.APPROXIMATE_ONLY, missing=recipe.missing, caveats=[name for name, value in requirements.items() if not value], requirements=requirements)


_KNOWN_FIELDS: dict[str, set[str]] = {
    "top": {
        "schema_version", "source", "base_prompt", "negative_prompt", "resources", "sampling",
        "passes", "inputs", "controls", "detailers", "postprocess", "workflow", "runtime",
        "raw", "evidence_manifest", "confirmed", "inferred", "missing",
    },
    "source": {"provider", "url", "image_id", "post_id", "model_id", "model_version_id", "media_url"},
    "resource": {"kind", "name", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air", "sha256", "strength_model", "strength_clip", "clip_skip"},
    "sampling": {"seed", "steps", "cfg", "sampler", "scheduler", "denoise", "width", "height"},
    "pass": {"name", "ksampler_node_id", "sampling", "scale", "upscale_model", "upscale_resource", "inherits_from", "notes"},
    "input": {"reference", "sha256", "kind"},
    "control": {"kind", "input_ref", "model", "resource", "preprocessor", "weight", "start_percent", "end_percent"},
    "detailer": {"kind", "model", "resource", "prompt", "negative_prompt", "denoise"},
    "postprocess": {"kind", "model", "resource", "scale", "params"},
    "workflow": {"reference", "snapshot", "snapshot_sha256", "operation_bindings"},
    "operation_binding": {"canonical_field", "node_id", "input_name", "resource"},
    "runtime": {"engine", "engine_version", "reference", "runtime_lock_sha256", "node_versions", "package_versions", "runtime_settings", "inspection_snapshot", "resource_locks"},
    "resource_lock": {"node_id", "input_name", "resource"},
    "resource_reference": {"kind", "sha256", "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "air"},
    "evidence": {"canonical_field", "source", "reference", "snapshot_sha256", "note"},
    "evidence_manifest": {"identity", "reference", "payload", "sha256", "assertions"},
    "evidence_assertion": {"canonical_field", "path", "value"},
    "missing": {"canonical_field", "criticality", "reason"},
}


def _normalize_recipe_payload(payload: Mapping[str, Any], *, preserve_confirmed: bool) -> dict[str, Any]:
    """Normalize known fields while losslessly retaining all importer payload metadata.

    Unknown top-level and nested values are removed from the strict canonical models,
    but the complete original payload is copied to ``raw.importer_payload`` and every
    relocation is listed in ``raw.normalization.unknown_fields``. This is the default
    importer contract: strict validation never silently discards vendor metadata.
    """
    original = deepcopy(dict(payload))
    normalized = deepcopy(dict(payload))
    unknown_paths: list[str] = []

    def clean(value: Any, category: str, path: str) -> Any:
        if not isinstance(value, Mapping):
            return value
        output = dict(value)
        for key in list(output):
            if key not in _KNOWN_FIELDS[category]:
                unknown_paths.append(f"{path}.{key}" if path else key)
                output.pop(key)
        return output

    normalized = clean(normalized, "top", "")
    normalized.setdefault("schema_version", RECIPE_SCHEMA_VERSION)
    for key, category in (("source", "source"), ("sampling", "sampling"), ("workflow", "workflow"), ("runtime", "runtime")):
        if normalized.get(key) is not None:
            normalized[key] = clean(normalized[key], category, key)
    if isinstance(normalized.get("workflow"), dict) and isinstance(normalized["workflow"].get("operation_bindings"), list):
        bindings = []
        for index, item in enumerate(normalized["workflow"]["operation_bindings"]):
            cleaned = clean(item, "operation_binding", f"workflow.operation_bindings[{index}]")
            if isinstance(cleaned, dict) and cleaned.get("resource") is not None:
                cleaned["resource"] = clean(cleaned["resource"], "resource_reference", f"workflow.operation_bindings[{index}].resource")
            bindings.append(cleaned)
        normalized["workflow"]["operation_bindings"] = bindings
    if isinstance(normalized.get("runtime"), dict) and isinstance(normalized["runtime"].get("resource_locks"), list):
        locks = []
        for index, item in enumerate(normalized["runtime"]["resource_locks"]):
            cleaned = clean(item, "resource_lock", f"runtime.resource_locks[{index}]")
            if isinstance(cleaned, dict) and cleaned.get("resource") is not None:
                cleaned["resource"] = clean(
                    cleaned["resource"], "resource_reference", f"runtime.resource_locks[{index}].resource"
                )
            locks.append(cleaned)
        normalized["runtime"]["resource_locks"] = locks
    if isinstance(normalized.get("evidence_manifest"), list):
        manifests = []
        for index, item in enumerate(normalized["evidence_manifest"]):
            cleaned = clean(item, "evidence_manifest", f"evidence_manifest[{index}]")
            if isinstance(cleaned, dict) and isinstance(cleaned.get("assertions"), list):
                cleaned["assertions"] = [
                    clean(assertion, "evidence_assertion", f"evidence_manifest[{index}].assertions[{assertion_index}]")
                    for assertion_index, assertion in enumerate(cleaned["assertions"])
                ]
            manifests.append(cleaned)
        normalized["evidence_manifest"] = manifests
    for key, category in (("resources", "resource"), ("inputs", "input"), ("controls", "control"), ("detailers", "detailer"), ("postprocess", "postprocess"), ("confirmed", "evidence"), ("inferred", "evidence"), ("missing", "missing")):
        if isinstance(normalized.get(key), list):
            normalized[key] = [clean(item, category, f"{key}[{index}]") for index, item in enumerate(normalized[key])]
    if isinstance(normalized.get("passes"), list):
        passes = []
        for index, item in enumerate(normalized["passes"]):
            cleaned = clean(item, "pass", f"passes[{index}]")
            if isinstance(cleaned, dict) and cleaned.get("sampling") is not None:
                cleaned["sampling"] = clean(cleaned["sampling"], "sampling", f"passes[{index}].sampling")
            if isinstance(cleaned, dict) and cleaned.get("upscale_resource") is not None:
                cleaned["upscale_resource"] = clean(cleaned["upscale_resource"], "resource_reference", f"passes[{index}].upscale_resource")
            passes.append(cleaned)
        normalized["passes"] = passes
    for key in ("controls", "detailers", "postprocess"):
        if isinstance(normalized.get(key), list):
            for index, item in enumerate(normalized[key]):
                if isinstance(item, dict) and item.get("resource") is not None:
                    item["resource"] = clean(item["resource"], "resource_reference", f"{key}[{index}].resource")

    source = normalized.get("source")
    if isinstance(source, dict):
        if isinstance(source.get("provider"), str):
            source["provider"] = source["provider"].strip().lower()
        for key in ("url", "media_url"):
            if isinstance(source.get(key), str):
                source[key] = source[key].strip()
        for key in ("image_id", "post_id", "model_id", "model_version_id"):
            value = source.get(key)
            if isinstance(value, str) and value.strip().isdigit():
                source[key] = int(value.strip())
    if isinstance(normalized.get("resources"), list):
        for resource in normalized["resources"]:
            if not isinstance(resource, dict):
                continue
            for key in ("name", "air"):
                if isinstance(resource.get(key), str):
                    resource[key] = resource[key].strip()
            if isinstance(resource.get("kind"), str):
                resource["kind"] = resource["kind"].strip().lower()
            if isinstance(resource.get("sha256"), str):
                resource["sha256"] = resource["sha256"].strip().lower()
    if isinstance(normalized.get("missing"), list):
        normalized["missing"] = [
            {"canonical_field": item, "criticality": "critical", "reason": "importer reported missing field"}
            if isinstance(item, str) else item
            for item in normalized["missing"]
        ]

    # ``confirmed`` is an authority claim, not importer metadata.  Public
    # normalization never preserves it; trusted boundaries use the private helper
    # and still need a record-scoped capability during model validation.
    if not preserve_confirmed:
        claimed_confirmed = normalized.get("confirmed")
        if isinstance(claimed_confirmed, list) and claimed_confirmed:
            normalized["confirmed"] = []
            existing_inferred = normalized.get("inferred")
            normalized["inferred"] = [
                *(existing_inferred if isinstance(existing_inferred, list) else []),
                *claimed_confirmed,
            ]

    raw = normalized.get("raw")
    raw_out = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {"original_raw": deepcopy(raw)}
    importer_payload = raw_out.get("importer_payload", original)
    if not isinstance(importer_payload, Mapping):
        importer_payload = original
    prior_unknown = raw_out.get("normalization", {}).get("unknown_fields", []) if isinstance(raw_out.get("normalization"), Mapping) else []
    raw_out["importer_payload"] = deepcopy(dict(importer_payload))
    raw_out["normalization"] = {"unknown_fields": list(dict.fromkeys([*prior_unknown, *unknown_paths]))}
    normalized["raw"] = raw_out
    return normalized


def normalize_recipe_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Public importer normalization; caller-provided confirmations are always inferred."""
    return _normalize_recipe_payload(payload, preserve_confirmed=False)


def _issue_trusted_provenance_capability(
    evidence: Iterable[EvidenceRecord],
) -> _TrustedProvenanceCapability:
    """Issue scoped authority after a trusted boundary has itself acquired each record.

    This is intentionally private: CIV-B/C/D boundary implementations must construct
    evidence from their API response, embedded bytes, or runtime inspection before
    issuing capability for exactly those records.  Serialized payload data cannot
    select a default authority context.
    """
    return _TrustedProvenanceCapability(_evidence_identity(item) for item in evidence)


def _build_recipe_from_trusted_evidence(
    payload: Mapping[str, Any], *, capability: _TrustedProvenanceCapability | None = None
) -> GenerationRecipe:
    """Internal acquisition/inspection boundary with explicit scoped authority."""
    if not isinstance(capability, _TrustedProvenanceCapability):
        raise PermissionError("trusted recipe construction requires an explicit provenance capability")
    recipe = GenerationRecipe.model_validate(
        _normalize_recipe_payload(payload, preserve_confirmed=True),
        context={"provenance_capability": capability},
    )
    recipe._authoritative_evidence = capability.identities
    return recipe
