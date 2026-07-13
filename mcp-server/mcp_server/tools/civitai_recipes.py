"""CIV-F thin, structured MCP wrappers for backend-owned Civitai recipe contracts."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, JsonValue, PositiveInt, field_validator, model_validator

from mcp_server.server import _get_client, mcp


class _StrictResourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _canonical_sha256(value: JsonValue) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


class CivitaiSourceAliasRepointIdentity(_StrictResourceModel):
    """Caller-controlled immutable Civitai identity; lifecycle fields are excluded."""

    provider: Literal["civitai"]
    url: str | None = None
    image_id: PositiveInt | None = None
    post_id: PositiveInt | None = None
    model_id: PositiveInt | None = None
    model_version_id: PositiveInt | None = None
    media_url: str | None = None

    @model_validator(mode="after")
    def require_immutable_image_identity(self) -> "CivitaiSourceAliasRepointIdentity":
        if self.image_id is not None:
            return self
        if self.media_url is None:
            raise ValueError("source_identity requires image_id or a supported Civitai image CDN media_url")
        parsed = urlparse(self.media_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"image.civitai.com", "images.civitai.com"}
            or not parsed.path
            or parsed.path == "/"
        ):
            raise ValueError("media_url must be a supported Civitai image CDN HTTPS identity")
        return self


class CivitaiSourceAliasRepointReplacement(_StrictResourceModel):
    """Strict immutable replacement content forwarded once to backend-owned repoint lifecycle."""

    source_identity: CivitaiSourceAliasRepointIdentity
    acquisition_evidence_snapshot: dict[str, JsonValue]
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
    def require_nonblank_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("optional text must not be blank when supplied")
        return value

    @field_validator("approved_tags")
    @classmethod
    def require_unique_nonblank_tags(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("approved_tags must be trimmed, nonblank, and unique")
        return normalized

    @model_validator(mode="after")
    def require_matching_evidence_hash(self) -> "CivitaiSourceAliasRepointReplacement":
        if _canonical_sha256(self.acquisition_evidence_snapshot) != self.acquisition_evidence_sha256:
            raise ValueError("acquisition_evidence_sha256 does not match canonical JSON evidence snapshot")
        return self


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
    "authorization", "api_key", "apikey", "access_token", "token", "secret", "password", "cookie",
})
_SECRET_QUERY_VALUE = re.compile(
    r"([?&](?:authorization|api_key|apikey|access_token|token|secret|password|cookie|signature|sig|policy|expires|x-amz-[^=&#\s]+)=)[^&#\s]*",
    re.IGNORECASE,
)
_SECRET_INLINE_VALUE = re.compile(
    r"\b(authorization|api[_-]?key|access[_-]?token|token|secret|password|cookie)\s*[:=]\s*[^,;\s]+",
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
        value = _SECRET_QUERY_VALUE.sub(r"\1[REDACTED]", value)
        value = _SECRET_INLINE_VALUE.sub(lambda match: f"{match.group(1)}: [REDACTED]", value)
        return _BEARER_VALUE.sub("Bearer [REDACTED]", value)
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
def civitai_recipe_import(locator: int | str, embedded_image: bytes | str | None = None, remember_alias: str | None = None) -> dict[str, Any]:
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
    if remember_alias is not None:
        body["remember_alias"] = remember_alias
    return _post("civitai_recipe_import", "civitai-recipes/import", body, "inspect the recipe, then resolve its local resources")


@mcp.tool()
def civitai_source_alias_resolve(alias: str) -> dict[str, Any]:
    """Resolve one remembered source alias into its immutable audited binding."""
    return _post(
        "civitai_source_alias_resolve",
        "civitai-recipes/source-aliases/resolve",
        {"alias": alias},
        "use the immutable audited source binding as-is; do not search or rebuild it",
    )


@mcp.tool()
def civitai_source_alias_resolve_explicit_version(
    alias: Annotated[str, Field(strict=True, min_length=1, max_length=512, pattern=r".*\S.*")],
    registry_version: Annotated[int, Field(strict=True, ge=1)],
) -> dict[str, Any]:
    """Resolve one alias at the caller-selected immutable audited registry version."""
    return _post(
        "civitai_source_alias_resolve_explicit_version",
        "civitai-recipes/source-aliases/resolve-explicit-version",
        {"alias": alias, "registry_version": registry_version},
        "use the caller-selected immutable audited registry binding as-is; do not search, build, queue, or generate",
    )


# FastMCP's generated function-argument base otherwise ignores extra keys. This
# tool's frozen facade must reject them at the formal MCP boundary.  Lightweight
# test doubles only implement ``tool()`` and deliberately expose no tool manager;
# they do not serve MCP requests, so leave their registration untouched.
_tool_manager = getattr(mcp, "_tool_manager", None)
if _tool_manager is not None:
    _explicit_version_tool = _tool_manager._tools["civitai_source_alias_resolve_explicit_version"]

    class _ExplicitVersionResolveArguments(_explicit_version_tool.fn_metadata.arg_model):
        model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    _explicit_version_tool.fn_metadata.arg_model = _ExplicitVersionResolveArguments
    _explicit_version_tool.parameters = _ExplicitVersionResolveArguments.model_json_schema()


@mcp.tool()
def civitai_source_alias_rename(
    current_primary_alias: Annotated[str, Field(min_length=1, max_length=512)],
    new_primary_alias: Annotated[str, Field(min_length=1, max_length=512)],
    expected_registry_version: Annotated[int, Field(ge=1)],
) -> dict[str, Any]:
    """Rename one primary source alias through the backend-owned audited lifecycle."""
    return _post(
        "civitai_source_alias_rename",
        "civitai-recipes/source-aliases/rename",
        {
            "current_primary_alias": current_primary_alias,
            "new_primary_alias": new_primary_alias,
            "expected_registry_version": expected_registry_version,
        },
        "use the returned audited lifecycle evidence as-is; do not archive, repoint, build, or queue",
    )


@mcp.tool()
def civitai_source_alias_archive(
    current_primary_alias: Annotated[str, Field(min_length=1, max_length=512)],
    expected_registry_version: Annotated[int, Field(ge=1)],
) -> dict[str, Any]:
    """Archive one primary source alias through the backend-owned terminal audited lifecycle."""
    return _post(
        "civitai_source_alias_archive",
        "civitai-recipes/source-aliases/archive",
        {
            "current_primary_alias": current_primary_alias,
            "expected_registry_version": expected_registry_version,
        },
        "use the returned terminal audited archive evidence as-is; do not unarchive, repoint, build, or queue",
    )


@mcp.tool()
def civitai_source_alias_repoint(
    current_primary_alias: Annotated[str, Field(min_length=1, max_length=512)],
    expected_registry_version: Annotated[int, Field(ge=1)],
    replacement: CivitaiSourceAliasRepointReplacement,
) -> dict[str, Any]:
    """Explicitly repoint one primary alias to typed immutable content through backend audit lifecycle."""
    return _post(
        "civitai_source_alias_repoint",
        "civitai-recipes/source-aliases/repoint",
        {
            "current_primary_alias": current_primary_alias,
            "expected_registry_version": expected_registry_version,
            "replacement": CivitaiSourceAliasRepointReplacement.model_validate(replacement).model_dump(mode="json", exclude_unset=True),
        },
        "use the returned audited explicit-repoint evidence as-is; bare alias use still requires an explicit registry version and does not resolve, build, or queue automatically",
    )


@mcp.tool()
def civitai_source_alias_list(
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """List backend-audited remembered Civitai source aliases without resolving them."""
    tool = "civitai_source_alias_list"
    try:
        return _result(
            tool,
            _get_client().get("civitai-recipes/source-aliases", params={"limit": limit, "offset": offset}),
            "search candidate aliases or exact-resolve one alias only when the caller selects it",
        )
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def civitai_source_alias_search(
    query: Annotated[str, Field(min_length=1, max_length=512)],
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """Search backend-ranked source-alias candidates without selecting or resolving a candidate."""
    return _post(
        "civitai_source_alias_search",
        "civitai-recipes/source-aliases/search",
        {"query": query, "limit": limit, "offset": offset},
        "present the audited candidates; exact-resolve only an alias explicitly selected by the caller",
    )


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


class CivitaiVariantSourceAliasSelector(_StrictResourceModel):
    """Opaque backend-owned source-alias selector for a single Child variant."""

    alias: str = Field(min_length=1, max_length=512, pattern=r".*\S.*")
    registry_version: int | None = Field(default=None, ge=1)


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


class CivitaiVariationSetChild(_StrictResourceModel):
    client_child_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    directives: list[CivitaiVariantDirective]


def _variant_directive_payload(directive: CivitaiVariantDirective | dict[str, Any]) -> dict[str, Any]:
    """Preserve field absence across MCP JSON instead of inventing ``value: null``."""
    return CivitaiVariantDirective.model_validate(directive).model_dump(exclude_none=True)


def _variation_set_child_payload(child: CivitaiVariationSetChild) -> dict[str, Any]:
    return {
        "client_child_key": child.client_child_key,
        "directives": [_variant_directive_payload(item) for item in child.directives],
    }


def _validate_variation_set_children(children: list[CivitaiVariationSetChild]) -> None:
    keys = [child.client_child_key for child in children]
    if len(keys) != len(set(keys)):
        raise ValueError("client_child_key must be unique within a variation set request")


@ mcp.tool()
def civitai_recipe_variant_generate(
    directives: list[CivitaiVariantDirective],
    model_family: Literal["sdxl", "illustrious"],
    runtime_capabilities: CivitaiVariantRuntimeCapabilities,
    runtime_provenance: CivitaiVariantRuntimeProvenance,
    input_bindings: dict[str, CivitaiVariantInputBinding],
    parent_recipe: CivitaiVariantParentRecipe | None = None,
    parent_recipe_sha256: Annotated[str | None, Field(strict=True, pattern=r"^[0-9a-fA-F]{64}$")] = None,
    source_alias: CivitaiVariantSourceAliasSelector | None = None,
) -> dict[str, Any]:
    """Derive, fresh-resolve, compatibility-check, build, validate, and queue exactly one immutable Child variant."""
    has_parent_recipe = parent_recipe is not None
    has_parent_sha256 = parent_recipe_sha256 is not None
    has_source_alias = source_alias is not None
    if has_parent_recipe != has_parent_sha256 or has_source_alias == (has_parent_recipe and has_parent_sha256):
        return _error(
            "civitai_recipe_variant_generate", "invalid_parent_source",
            "provide exactly one complete parent source: direct parent_recipe plus parent_recipe_sha256, or source_alias",
            {"where": "mcp_input"},
        )
    if directives is None or model_family is None or runtime_capabilities is None or runtime_provenance is None or input_bindings is None:
        return _error("civitai_recipe_variant_generate", "invalid_generation_inputs", "all generation inputs are required", {"where": "mcp_input"})
    body: dict[str, Any] = {
        "directives": [_variant_directive_payload(item) for item in directives],
        "model_family": model_family,
        "runtime_capabilities": _resource_payload(runtime_capabilities),
        "runtime_provenance": _resource_payload(runtime_provenance),
        "input_bindings": {reference: _resource_payload(binding) for reference, binding in input_bindings.items()},
    }
    if has_source_alias:
        try:
            selector = CivitaiVariantSourceAliasSelector.model_validate(source_alias)
        except Exception as exc:
            return _error("civitai_recipe_variant_generate", "invalid_source_alias", str(exc), {"where": "mcp_input"})
        body["source_alias"] = selector.model_dump(exclude_none=True)
    else:
        body["parent_recipe"] = _resource_payload(parent_recipe)
        body["parent_recipe_sha256"] = parent_recipe_sha256
    return _post(
        "civitai_recipe_variant_generate", "civitai-recipes/variants/generate-one", body,
        "call get_generation_status using the returned immutable child job_id",
    )


# FastMCP's generated function-argument base otherwise permits extra keys and
# cannot express the parent-source XOR. Keep the public tool typed while making
# both the formal boundary and direct wrapper fail closed before transport.
_variant_tool_manager = getattr(mcp, "_tool_manager", None)
if _variant_tool_manager is not None:
    _single_variant_tool = _variant_tool_manager._tools["civitai_recipe_variant_generate"]

    class _SingleVariantArguments(_single_variant_tool.fn_metadata.arg_model):
        model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

        @model_validator(mode="after")
        def require_exactly_one_parent_source(self) -> "_SingleVariantArguments":
            has_parent_recipe = self.parent_recipe is not None
            has_parent_sha256 = self.parent_recipe_sha256 is not None
            has_source_alias = self.source_alias is not None
            if has_parent_recipe != has_parent_sha256 or has_source_alias == (has_parent_recipe and has_parent_sha256):
                raise ValueError("provide exactly one complete parent source")
            return self

    _single_variant_tool.fn_metadata.arg_model = _SingleVariantArguments
    _single_variant_schema = _SingleVariantArguments.model_json_schema()
    _single_variant_schema["additionalProperties"] = False
    _single_variant_schema["required"] = ["directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"]
    _single_variant_schema["oneOf"] = [
        {"required": ["parent_recipe", "parent_recipe_sha256"], "not": {"required": ["source_alias"]}},
        {"required": ["source_alias"], "not": {"anyOf": [{"required": ["parent_recipe"]}, {"required": ["parent_recipe_sha256"]}]}},
    ]
    _single_variant_tool.parameters = _single_variant_schema


@ mcp.tool()
def civitai_recipe_variation_set_generate(
    children: Annotated[list[CivitaiVariationSetChild], Field(min_length=1, max_length=8)],
    model_family: Literal["sdxl", "illustrious"],
    runtime_capabilities: CivitaiVariantRuntimeCapabilities,
    runtime_provenance: CivitaiVariantRuntimeProvenance,
    input_bindings: dict[str, CivitaiVariantInputBinding],
    parent_recipe: CivitaiVariantParentRecipe | None = None,
    parent_recipe_sha256: Annotated[str | None, Field(strict=True, pattern=r"^[0-9a-fA-F]{64}$")] = None,
    source_alias: CivitaiVariantSourceAliasSelector | None = None,
) -> dict[str, Any]:
    """Create one durable ordered set from one direct Parent or opaque source-alias selector."""
    has_parent_recipe = parent_recipe is not None
    has_parent_sha256 = parent_recipe_sha256 is not None
    has_source_alias = source_alias is not None
    if has_parent_recipe != has_parent_sha256 or has_source_alias == (has_parent_recipe and has_parent_sha256):
        return _error(
            "civitai_recipe_variation_set_generate", "invalid_parent_source",
            "provide exactly one complete parent source: direct parent_recipe plus parent_recipe_sha256, or source_alias",
            {"where": "mcp_input"},
        )
    try:
        typed_children = [CivitaiVariationSetChild.model_validate(child) for child in children]
        _validate_variation_set_children(typed_children)
    except Exception as exc:
        return _error("civitai_recipe_variation_set_generate", "invalid_children", str(exc), {"where": "mcp_input"})
    body: dict[str, Any] = {
        "children": [_variation_set_child_payload(child) for child in typed_children],
        "model_family": model_family,
        "runtime_capabilities": _resource_payload(runtime_capabilities),
        "runtime_provenance": _resource_payload(runtime_provenance),
        "input_bindings": {key: _resource_payload(value) for key, value in input_bindings.items()},
    }
    if has_source_alias:
        try:
            selector = CivitaiVariantSourceAliasSelector.model_validate(source_alias)
        except Exception as exc:
            return _error("civitai_recipe_variation_set_generate", "invalid_source_alias", str(exc), {"where": "mcp_input"})
        body["source_alias"] = selector.model_dump(exclude_none=True)
    else:
        body["parent_recipe"] = _resource_payload(parent_recipe)
        body["parent_recipe_sha256"] = parent_recipe_sha256
    return _post(
        "civitai_recipe_variation_set_generate", "civitai-recipes/variation-sets", body,
        "use civitai_recipe_variation_set_status with the returned variation_set_id",
    )


# FastMCP's generated function-argument base otherwise permits extra keys and
# cannot express the parent-source XOR. Keep the public tool typed while making
# both the formal boundary and direct wrapper fail closed before transport.
_variation_set_tool_manager = getattr(mcp, "_tool_manager", None)
if _variation_set_tool_manager is not None:
    _variation_set_tool = _variation_set_tool_manager._tools["civitai_recipe_variation_set_generate"]

    class _VariationSetArguments(_variation_set_tool.fn_metadata.arg_model):
        model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

        @model_validator(mode="after")
        def require_exactly_one_parent_source(self) -> "_VariationSetArguments":
            has_parent_recipe = self.parent_recipe is not None
            has_parent_sha256 = self.parent_recipe_sha256 is not None
            has_source_alias = self.source_alias is not None
            if has_parent_recipe != has_parent_sha256 or has_source_alias == (has_parent_recipe and has_parent_sha256):
                raise ValueError("provide exactly one complete parent source")
            return self

    _variation_set_tool.fn_metadata.arg_model = _VariationSetArguments
    _variation_set_schema = _VariationSetArguments.model_json_schema()
    _variation_set_schema["additionalProperties"] = False
    _variation_set_schema["required"] = ["children", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"]
    _variation_set_schema["oneOf"] = [
        {"required": ["parent_recipe", "parent_recipe_sha256"], "not": {"required": ["source_alias"]}},
        {"required": ["source_alias"], "not": {"anyOf": [{"required": ["parent_recipe"]}, {"required": ["parent_recipe_sha256"]}]}},
    ]
    _variation_set_tool.parameters = _variation_set_schema


@ mcp.tool()
def civitai_recipe_variation_set_status(variation_set_id: str) -> dict[str, Any]:
    """Read a durable variation-set aggregate and append-only member evidence."""
    try:
        return _result("civitai_recipe_variation_set_status", _get_client().get(f"civitai-recipes/variation-sets/{variation_set_id}"), "inspect the aggregate and per-member evidence")
    except Exception as exc: return _backend_error("civitai_recipe_variation_set_status", exc)


@ mcp.tool()
def civitai_recipe_variation_set_cancel(variation_set_id: str) -> dict[str, Any]:
    """Cancel only active members of a durable variation set."""
    return _post("civitai_recipe_variation_set_cancel", f"civitai-recipes/variation-sets/{variation_set_id}/cancel", {}, "read status to observe the append-only cancel outcomes")


@ mcp.tool()
def civitai_recipe_variation_set_export(variation_set_id: str) -> dict[str, Any]:
    """Export canonical Parent/Child provenance, evidence history, and aggregate snapshot."""
    try:
        return _result("civitai_recipe_variation_set_export", _get_client().get(f"civitai-recipes/variation-sets/{variation_set_id}/export"), "verify export_sha256 before consuming the export")
    except Exception as exc: return _backend_error("civitai_recipe_variation_set_export", exc)


@ mcp.tool()
def civitai_recipe_export(image_id: int) -> dict[str, Any]:
    """Export the existing gallery recipe bundle with recipe/workflow/input/resource/runtime hashes intact."""
    tool = "civitai_recipe_export"
    try:
        payload = _get_client().get(f"gallery/{image_id}/export", params={"format": "recipe"})
        return _result(tool, payload, "the exported bundle can be audited or rerun through the gallery contract")
    except Exception as exc:
        return _backend_error(tool, exc)
