"""CIV-F thin, structured MCP wrappers for backend-owned Civitai recipe contracts."""
from __future__ import annotations

import base64
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, PositiveInt, model_validator

from mcp_server.server import _get_client, mcp


class _StrictResourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


ResourceKind = Literal["checkpoint", "lora", "vae", "embedding", "controlnet", "upscaler"]


class CivitaiResourceSource(_StrictResourceModel):
    provider: Literal["civitai"]
    civitai_model_id: PositiveInt | None = None


class CivitaiResourceCandidate(_StrictResourceModel):
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


class CivitaiResourceSelectedDescriptor(_StrictResourceModel):
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


_SECRET_KEY_NAMES = frozenset({
    "authorization", "api_key", "apikey", "access_token", "token", "secret", "password",
})
_SECRET_QUERY_VALUE = re.compile(
    r"([?&](?:authorization|api_key|apikey|access_token|token|secret|password)=)[^&#\s]*",
    re.IGNORECASE,
)
_BEARER_VALUE = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)


def _redact_secrets(value: Any) -> Any:
    """Treat backend payloads as untrusted: retain their shape but never forward credentials."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower().replace("-", "_") in _SECRET_KEY_NAMES
            else _redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _BEARER_VALUE.sub("Bearer [REDACTED]", _SECRET_QUERY_VALUE.sub(r"\1[REDACTED]", value))
    return value


def _error(tool: str, code: str, message: str, details: dict[str, Any] | None = None, *, status_code: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "error": _redact_secrets({"code": code, "message": message, "details": details or {}}),
    }
    if status_code is not None:
        result["status_code"] = status_code
    return result


def _backend_error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {"detail": exc.response.text}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            code = str(detail.get("code") or f"http_{exc.response.status_code}")
            message = str(detail.get("message") or detail.get("error") or exc)
            details = {key: value for key, value in detail.items() if key not in {"code", "message", "error"}}
        else:
            # FastAPI validation errors are often list[dict]; retain their exact
            # diagnostic structure rather than collapsing it into a message.
            code, message, details = f"http_{exc.response.status_code}", str(detail or exc), {"detail": detail}
        return _error(tool, code, message, details, status_code=exc.response.status_code)
    return _error(tool, exc.__class__.__name__, str(exc), {"where": "backend"})


def _result(tool: str, payload: dict[str, Any], next_step: str) -> dict[str, Any]:
    payload = _redact_secrets(payload)
    if payload.get("ok") is False:
        return _error(tool, str(payload.get("error_code") or "backend_failed"), str(payload.get("error_message") or payload.get("message") or "backend returned ok=false"), {"response": payload})
    return {"ok": True, "tool": tool, "data": payload, "next": next_step}


def _post(tool: str, endpoint: str, body: dict[str, Any], next_step: str) -> dict[str, Any]:
    try:
        return _result(tool, _get_client().post(endpoint, json=body), next_step)
    except Exception as exc:
        return _backend_error(tool, exc)


def _resource_payload(value: Any) -> Any:
    return value.model_dump() if isinstance(value, BaseModel) else value


@mcp.tool()
def civitai_resource_inspect(locator: int | str) -> dict[str, Any]:
    """Inspect one Civitai model/version locator into redacted deterministic candidate files."""
    return _post("civitai_resource_inspect", "civitai-recipes/resource-inspect", {"locator": locator}, "select one exact candidate before guarded installation")


@mcp.tool()
def civitai_resource_select(inspect: CivitaiResourceInspectResponse, selectors: ResourceSelectors) -> dict[str, Any]:
    """Fail closed unless exact Civitai identity selectors select exactly one inspected file."""
    return _post("civitai_resource_select", "civitai-recipes/resource-select", {"inspect": _resource_payload(inspect), "selectors": _resource_payload(selectors)}, "install the selected descriptor into its compatible backend storage root")


@mcp.tool()
def civitai_resource_install(selected: CivitaiResourceSelectedDescriptor, storage_root: Literal["checkpoints", "loras", "vae", "embeddings", "controlnet", "upscale_models"], overwrite: Literal[False] = False) -> dict[str, Any]:
    """Guardedly install one selected descriptor; caller paths and credentials are never accepted."""
    return _post("civitai_resource_install", "civitai-recipes/resource-install", {"selected": _resource_payload(selected), "storage_root": storage_root, "overwrite": overwrite}, "query local ledger then resolve recipes strictly")


@mcp.tool()
def civitai_recipe_import(locator: int | str, embedded_image: bytes | str | None = None) -> dict[str, Any]:
    """Acquire a Civitai locator into raw acquisition evidence, GenerationRecipe 1.0, and reproduction diagnostics."""
    body: dict[str, Any] = {"locator": locator}
    if embedded_image is not None:
        if isinstance(embedded_image, str):
            try:
                image_bytes = base64.b64decode(embedded_image, validate=True)
            except (ValueError, TypeError) as exc:
                return _error(
                    "civitai_recipe_import", "invalid_embedded_image_base64",
                    "embedded_image must be valid base64 when sent over JSON/MCP",
                    {"where": "mcp_input", "error_type": exc.__class__.__name__},
                )
        else:
            image_bytes = embedded_image
        body["embedded_image_base64"] = base64.b64encode(image_bytes).decode("ascii")
    return _post("civitai_recipe_import", "civitai-recipes/import", body, "inspect the recipe, then resolve its local resources")


@mcp.tool()
def civitai_recipe_inspect(recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate a GenerationRecipe 1.0 without network, disk writes, or queue submission."""
    return _post("civitai_recipe_inspect", "civitai-recipes/inspect", {"recipe": recipe}, "resolve only against a caller-supplied local ledger")


@mcp.tool()
def civitai_recipe_resolve(recipe: dict[str, Any], ledger: list[dict[str, Any]], strict: bool = True) -> dict[str, Any]:
    """Resolve ordered recipe resources against a caller-provided local ledger; strict failures stay errors."""
    return _post("civitai_recipe_resolve", "civitai-recipes/resolve", {"recipe": recipe, "ledger": ledger, "strict": strict}, "if strict resolution succeeds, build the SDXL/Illustrious workflow")


@mcp.tool()
def civitai_recipe_local_ledger(
    kind: str | None = None,
    civitai_model_id: int | None = None,
    civitai_model_version_id: int | None = None,
    civitai_file_id: int | None = None,
    air: str | None = None,
    sha256: str | None = None,
    availability: bool | None = None,
) -> dict[str, Any]:
    """Query the backend-owned local Civitai identity ledger with exact-match filters only."""
    params = {
        key: value for key, value in {
            "kind": kind,
            "civitai_model_id": civitai_model_id,
            "civitai_model_version_id": civitai_model_version_id,
            "civitai_file_id": civitai_file_id,
            "air": air,
            "sha256": sha256,
            "availability": availability,
        }.items() if value is not None
    }
    tool = "civitai_recipe_local_ledger"
    try:
        return _result(tool, _get_client().get("civitai-recipes/local-ledger", params=params), "resolve a recipe strictly against this backend-owned local ledger")
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def civitai_recipe_resolve_local(recipe: dict[str, Any]) -> dict[str, Any]:
    """Strictly resolve a recipe using only one backend-owned local ledger snapshot."""
    return _post("civitai_recipe_resolve_local", "civitai-recipes/resolve-local", {"recipe": recipe}, "if strict resolution succeeds, build the SDXL/Illustrious workflow")


@mcp.tool()
def civitai_recipe_compatibility(recipe: dict[str, Any], resource_report: dict[str, Any], model_family: Literal["sdxl", "illustrious"], runtime_capabilities: dict[str, Any]) -> dict[str, Any]:
    """Pure fail-closed CIV-V-E compatibility preflight; incompatible is structured data, not a build."""
    return _post("civitai_recipe_compatibility", "civitai-recipes/compatibility", {"recipe": recipe, "resource_report": resource_report, "model_family": model_family, "runtime_capabilities": runtime_capabilities}, "build only after compatible=true; incompatible results require audited evidence repair")


@mcp.tool()
def civitai_recipe_build(recipe: dict[str, Any], resource_report: dict[str, Any], model_family: str, input_bindings: dict[str, Any]) -> dict[str, Any]:
    """Compile a strict resolved SDXL/Illustrious recipe into a locked ComfyUI workflow."""
    return _post("civitai_recipe_build", "civitai-recipes/build", {"recipe": recipe, "resource_report": resource_report, "model_family": model_family, "input_bindings": input_bindings}, "submit the returned build artifact with runtime provenance")


@mcp.tool()
def civitai_recipe_run(build: dict[str, Any], runtime_provenance: dict[str, Any], queue_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a CIV-E provenance bundle from a successful build, then submit the existing custom-workflow queue."""
    return _post("civitai_recipe_run", "civitai-recipes/run", {"build": build, "runtime_provenance": runtime_provenance, "queue_params": queue_params or {}}, "call get_generation_status with the returned job_id")


class CivitaiVariantDirective(_StrictResourceModel):
    field: Literal["base_prompt", "negative_prompt", "sampling.seed", "sampling.steps", "sampling.cfg", "sampling.sampler", "sampling.scheduler", "sampling.denoise", "sampling.width", "sampling.height"]
    policy: Literal["preserve", "replace", "randomize"]
    value: str | int | float | bool | None = None


VariantResourceKind = Literal["checkpoint", "diffusion_model", "text_encoder", "vae", "lora", "embedding", "controlnet", "upscaler", "detailer", "other"]
VariantEvidenceSource = Literal["civitai_api", "embedded_metadata", "workflow_snapshot", "runtime_inspection", "importer", "user_supplied"]


class CivitaiVariantSource(_StrictResourceModel):
    provider: Literal["civitai"]
    url: str | None = None
    image_id: PositiveInt | None = None
    post_id: PositiveInt | None = None
    model_id: PositiveInt | None = None
    model_version_id: PositiveInt | None = None
    media_url: str | None = None


class CivitaiVariantResourceReference(_StrictResourceModel):
    kind: VariantResourceKind
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    civitai_model_id: PositiveInt | None = None
    civitai_model_version_id: PositiveInt | None = None
    civitai_file_id: PositiveInt | None = None
    air: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_identity(self):
        if not any((self.sha256, self.civitai_model_id, self.civitai_model_version_id, self.civitai_file_id, self.air)):
            raise ValueError("resource reference requires immutable identity")
        return self


class CivitaiVariantResource(CivitaiVariantResourceReference):
    name: str = Field(min_length=1)
    strength_model: float | None = Field(default=None, ge=0, le=2)
    strength_clip: float | None = Field(default=None, ge=0, le=2)
    clip_skip: int | None = Field(default=None, ge=1, le=24)


class CivitaiVariantSampling(_StrictResourceModel):
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    steps: int | None = Field(default=None, ge=1, le=1000)
    cfg: float | None = Field(default=None, ge=0, le=100)
    sampler: str | None = None
    scheduler: str | None = None
    denoise: float | None = Field(default=None, ge=0, le=1)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class CivitaiVariantPass(_StrictResourceModel):
    name: str = Field(min_length=1)
    ksampler_node_id: str | None = Field(default=None, min_length=1)
    sampling: CivitaiVariantSampling = Field(default_factory=CivitaiVariantSampling)
    scale: float | None = Field(default=None, gt=0)
    upscale_model: str | None = None
    upscale_resource: CivitaiVariantResourceReference | None = None
    inherits_from: str | None = None
    notes: str | None = None


class CivitaiVariantInput(_StrictResourceModel):
    reference: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    kind: str = Field(min_length=1)


class CivitaiVariantControl(_StrictResourceModel):
    kind: str = Field(min_length=1)
    input_ref: str | None = None
    model: str | None = None
    resource: CivitaiVariantResourceReference | None = None
    preprocessor: str | None = None
    weight: float | None = Field(default=None, ge=0, le=2)
    start_percent: float | None = Field(default=None, ge=0, le=1)
    end_percent: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_window(self):
        if self.start_percent is not None and self.end_percent is not None and self.start_percent > self.end_percent:
            raise ValueError("control window is invalid")
        return self


class CivitaiVariantDetailer(_StrictResourceModel):
    kind: str = Field(min_length=1)
    model: str | None = None
    resource: CivitaiVariantResourceReference | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    denoise: float | None = Field(default=None, ge=0, le=1)


class CivitaiVariantPostprocess(_StrictResourceModel):
    kind: str = Field(min_length=1)
    model: str | None = None
    resource: CivitaiVariantResourceReference | None = None
    scale: float | None = Field(default=None, gt=0)
    params: dict[str, Any] = Field(default_factory=dict)


class CivitaiVariantWorkflowBinding(_StrictResourceModel):
    canonical_field: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    input_name: str = Field(min_length=1)
    resource: CivitaiVariantResourceReference


class CivitaiVariantWorkflow(_StrictResourceModel):
    reference: str = Field(min_length=1)
    snapshot: dict[str, Any] = Field(min_length=1)
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    operation_bindings: list[CivitaiVariantWorkflowBinding] = Field(default_factory=list)


class CivitaiVariantRuntimeLock(_StrictResourceModel):
    node_id: str = Field(min_length=1)
    input_name: str = Field(min_length=1)
    resource: CivitaiVariantResourceReference

    @model_validator(mode="after")
    def require_sha(self):
        if self.resource.sha256 is None:
            raise ValueError("runtime lock requires sha256")
        return self


class CivitaiVariantEvidenceAssertion(_StrictResourceModel):
    canonical_field: str = Field(min_length=1)
    path: str = ""
    extractor: Literal["json_pointer"] = "json_pointer"
    value: Any | None = None


class CivitaiVariantEvidenceManifest(_StrictResourceModel):
    identity: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    payload: dict[str, Any]
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    assertions: list[CivitaiVariantEvidenceAssertion] = Field(default_factory=list)


class CivitaiVariantEvidenceRecord(_StrictResourceModel):
    canonical_field: str = Field(min_length=1)
    source: VariantEvidenceSource
    reference: str = Field(min_length=1)
    snapshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    note: str | None = None


class CivitaiVariantMissing(_StrictResourceModel):
    canonical_field: str = Field(min_length=1)
    criticality: Literal["critical", "important", "optional"]
    reason: str = Field(min_length=1)


class CivitaiVariantInspectionSnapshot(_StrictResourceModel):
    snapshot_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    engine: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    node_types: list[str]


class CivitaiVariantRuntimeProvenance(_StrictResourceModel):
    engine: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    runtime_lock_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    node_versions: dict[str, str]
    package_versions: dict[str, str] = Field(default_factory=dict)
    runtime_settings: dict[str, Any] = Field(default_factory=dict)
    inspection_snapshot: CivitaiVariantInspectionSnapshot
    resource_locks: list[CivitaiVariantRuntimeLock] = Field(default_factory=list)


class CivitaiVariantParentRecipe(_StrictResourceModel):
    schema_version: Literal["1.0"]
    source: CivitaiVariantSource
    base_prompt: str | None = None
    negative_prompt: str | None = None
    resources: list[CivitaiVariantResource] = Field(default_factory=list)
    sampling: CivitaiVariantSampling | None = None
    passes: list[CivitaiVariantPass] = Field(default_factory=list)
    inputs: list[CivitaiVariantInput] = Field(default_factory=list)
    controls: list[CivitaiVariantControl] = Field(default_factory=list)
    detailers: list[CivitaiVariantDetailer] = Field(default_factory=list)
    postprocess: list[CivitaiVariantPostprocess] = Field(default_factory=list)
    workflow: CivitaiVariantWorkflow | None = None
    runtime: CivitaiVariantRuntimeProvenance | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    confirmed: list[CivitaiVariantEvidenceRecord] = Field(default_factory=list)
    inferred: list[CivitaiVariantEvidenceRecord] = Field(default_factory=list)
    missing: list[CivitaiVariantMissing] = Field(default_factory=list)
    evidence_manifest: list[CivitaiVariantEvidenceManifest] = Field(default_factory=list)


class CivitaiVariantRuntimeCapabilities(_StrictResourceModel):
    engine: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    node_types: list[str]
    sampler_names: list[str]
    scheduler_names: list[str]
    snapshot_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class CivitaiVariantInputBinding(_StrictResourceModel):
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    local_path: str = Field(min_length=1)


@mcp.tool()
def civitai_recipe_variant_generate(parent_recipe: CivitaiVariantParentRecipe, parent_recipe_sha256: str, directives: list[CivitaiVariantDirective], model_family: Literal["sdxl", "illustrious"], runtime_capabilities: CivitaiVariantRuntimeCapabilities, runtime_provenance: CivitaiVariantRuntimeProvenance, input_bindings: dict[str, CivitaiVariantInputBinding]) -> dict[str, Any]:
    """Derive, fresh-resolve, compatibility-check, build, validate, and queue exactly one immutable Child variant."""
    return _post(
        "civitai_recipe_variant_generate", "civitai-recipes/variants/generate-one",
        {"parent_recipe": _resource_payload(parent_recipe), "parent_recipe_sha256": parent_recipe_sha256,
         "directives": [_resource_payload(item) for item in directives], "model_family": model_family,
         "runtime_capabilities": _resource_payload(runtime_capabilities),
         "runtime_provenance": _resource_payload(runtime_provenance),
         "input_bindings": {reference: _resource_payload(binding) for reference, binding in input_bindings.items()}},
        "call get_generation_status using the returned immutable child job_id",
    )


@ mcp.tool()
def civitai_recipe_export(image_id: int) -> dict[str, Any]:
    """Export the existing gallery recipe bundle with recipe/workflow/input/resource/runtime hashes intact."""
    tool = "civitai_recipe_export"
    try:
        payload = _get_client().get(f"gallery/{image_id}/export", params={"format": "recipe"})
        return _result(tool, payload, "the exported bundle can be audited or rerun through the gallery contract")
    except Exception as exc:
        return _backend_error(tool, exc)
