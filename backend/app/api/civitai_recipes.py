"""CIV-F HTTP contracts: only orchestration over CIV-A through CIV-E services."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.queue import QueueFullError, submit_custom
from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest, CivitaiRecipeVariantGenerateResponse
from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
from app.services.civitai_recipe_variation_sets import VariationSetError, cancel_variation_set, create_variation_set, export_variation_set, get_variation_set
from app.services.civitai_recipe_variants import VariantFacadeError, generate_one_variant
from app.schemas.civitai_source_aliases import (
    CivitaiSourceAliasArchiveRequest,
    CivitaiSourceAliasArchiveResponse,
    CivitaiSourceAliasRenameRequest,
    CivitaiSourceAliasRenameResponse,
    CivitaiSourceAliasResolveRequest,
    CivitaiSourceAliasResolveResponse,
    SourceAliasRegistryListResponse,
    SourceAliasRegistrySearchRequest,
    SourceAliasRegistrySearchResponse,
)
from app.services.civitai_source_alias_registry import (
    archive_source_alias,
    list_registry_sources,
    rename_primary_source_alias,
    resolve_source_alias_exact,
    search_registry_sources,
)
from app.schemas.civitai_recipes import (
    CivitaiRecipeCompatibilityRequest,
    CivitaiRecipeCompatibilityResponse,
    CivitaiRecipeBuildRequest,
    CivitaiRecipeImportRequest,
    CivitaiRecipeInspectRequest,
    CivitaiRecipeResolveRequest,
    CivitaiRecipeResolveLocalRequest,
    CivitaiRecipeRunRequest,
    CivitaiResourceInspectRequest,
    CivitaiResourceSelectRequest,
    CivitaiResourceInstallRequest,
)
from app.db.database import get_db
from app.services.civitai_local_identity_ledger import ledger_payload, local_identity_ledger
from app.services.civitai_acquisition import AcquisitionError, redact_secrets, parse_civitai_locator
from app.services.civitai_resource_install import inspect_civitai_resource, select_civitai_resource, install_civitai_resource
from app.config import get_settings
from app.services.civitai_recipe_gallery import ProvenanceValidationError, build_recipe_provenance_bundle
from app.services.civitai_recipe_pipeline import (
    build_recipe,
    import_recipe,
    inspect_recipe,
    report_from_payload,
    resolve_recipe,
    SourceAliasImportError,
)
from app.services.civitai_recipe_workflow_compiler import RecipeCompileError
from app.services.civitai_resource_resolution import LocalResourceLedgerEntry

router = APIRouter(prefix="/api/civitai-recipes", tags=["civitai-recipes"])
_default_route_class = router.route_class


def _detail(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return redact_secrets({"code": code, "message": message, **extra})


_BEARER_VALUE = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)
_TOKEN_QUERY_VALUE = re.compile(r"([?&](?:authorization|api_key|apikey|access_token|token|secret|password)=)[^&#\s]*", re.IGNORECASE)


def _compatibility_safe(value: Any) -> Any:
    """Validation errors may echo rejected scalar input outside sensitive-key maps."""
    redacted = redact_secrets(value)
    if isinstance(redacted, list):
        return [_compatibility_safe(item) for item in redacted]
    if isinstance(redacted, tuple):
        return tuple(_compatibility_safe(item) for item in redacted)
    if isinstance(redacted, dict):
        return {key: _compatibility_safe(item) for key, item in redacted.items()}
    if isinstance(redacted, str):
        return _BEARER_VALUE.sub("Bearer [REDACTED]", _TOKEN_QUERY_VALUE.sub(r"\1[REDACTED]", redacted))
    return redacted


class _CompatibilityValidationRoute(APIRoute):
    """Retain FastAPI's validation diagnostics while removing untrusted secrets."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                return JSONResponse(status_code=422, content={"detail": _compatibility_safe(exc.errors())})

        return redacted_handler


class _SourceAliasResolveValidationRoute(APIRoute):
    """Reject malformed resolve requests without exposing validation internals."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": _detail("invalid_alias", "source alias resolution failed")},
                )

        return redacted_handler


class _SourceAliasDiscoveryValidationRoute(APIRoute):
    """Keep discovery validation deterministic and free of untrusted diagnostics."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": _detail("source_alias_discovery_invalid", "source alias discovery request invalid")},
                )

        return redacted_handler


class _SourceAliasRenameValidationRoute(APIRoute):
    """Reject malformed rename intent without exposing rejected request values."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": _detail("source_alias_rename_invalid", "source alias rename failed")},
                )

        return redacted_handler


class _SourceAliasArchiveValidationRoute(APIRoute):
    """Reject malformed archive intent without exposing rejected request values."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": _detail("source_alias_archive_invalid", "source alias archive failed")},
                )

        return redacted_handler


class _VariantFacadeValidationRoute(APIRoute):
    """Fail closed with one stable, redacted facade diagnostic before orchestration."""

    def get_route_handler(self):  # type: ignore[override]
        handler = super().get_route_handler()

        async def redacted_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # The detailed Pydantic tree can contain raw rejected values.  This
                # frozen submission endpoint intentionally exposes only stable phase/code.
                _compatibility_safe(exc.errors())
                return JSONResponse(status_code=422, content={"detail": {
                    "phase": "validation", "code": "request_invalid",
                    "message": "variant request validation failed",
                }})

        return redacted_handler


@router.post("/resource-inspect")
def inspect_civitai_resource_route(request: CivitaiResourceInspectRequest) -> dict[str, Any]:
    try:
        locator = parse_civitai_locator(request.locator)
        if locator.kind != "model" or (locator.model_id is None and locator.model_version_id is None):
            raise AcquisitionError("unsupported_locator", "resource inspect requires a Civitai model or model-version locator")
        endpoint = f"https://civitai.com/api/v1/model-versions/{locator.model_version_id}" if locator.model_version_id else f"https://civitai.com/api/v1/models/{locator.model_id}"
        headers = {"Authorization": get_settings().civitai_authorization} if get_settings().civitai_authorization else {}
        response = httpx.get(endpoint, headers=headers, timeout=30.0)
        if response.status_code == 404:
            raise AcquisitionError("not_found", "Civitai resource was not found")
        response.raise_for_status()
        return inspect_civitai_resource(response.json())
    except AcquisitionError as exc:
        raise HTTPException(status_code=422, detail=_detail(exc.code, str(exc), provenance=exc.provenance)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=_detail("resource_inspect_failed", exc.__class__.__name__)) from exc


@router.post("/resource-select")
def select_civitai_resource_route(request: CivitaiResourceSelectRequest) -> dict[str, Any]:
    result = select_civitai_resource(request.inspect.model_dump(), request.selectors.model_dump(exclude_none=True))
    if result["status"] != "completed":
        raise HTTPException(status_code=409, detail=_detail(result["diagnostic"]["code"], "resource selection failed closed", diagnostic=result["diagnostic"]))
    return result


class _CivitaiDownloadTransport:
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        return httpx.get(url, headers=headers, timeout=60.0)


@router.post("/resource-install")
def install_civitai_resource_route(request: CivitaiResourceInstallRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if request.overwrite:
        raise HTTPException(status_code=422, detail=_detail("overwrite_forbidden", "CIV-V-D accepts overwrite=false only"))
    settings = get_settings()
    roots = {
        "checkpoints": Path(settings.comfyui_checkpoints_dir.split(",")[0]), "loras": Path(settings.comfyui_loras_dir.split(",")[0]),
        "vae": Path(settings.comfyui_vae_dir.split(",")[0]), "embeddings": Path(settings.comfyui_embeddings_dir.split(",")[0]),
        "controlnet": Path(settings.comfyui_controlnet_dir.split(",")[0]), "upscale_models": Path(settings.comfyui_upscale_models_dir.split(",")[0]),
    }
    result = install_civitai_resource(request.selected.model_dump(), request.storage_root, db=db, storage_roots=roots, transport=_CivitaiDownloadTransport(), authorization=settings.civitai_authorization)
    if result["status"] != "completed":
        raise HTTPException(status_code=409 if result["status"] == "blocked" else 500, detail=_detail(result.get("diagnostic", {}).get("code", "resource_install_failed"), "resource installation did not complete", diagnostic=result.get("diagnostic", {})))
    return redact_secrets(result)


router.route_class = _SourceAliasResolveValidationRoute


@router.post("/source-aliases/resolve", response_model=CivitaiSourceAliasResolveResponse)
def resolve_civitai_source_alias(
    request: CivitaiSourceAliasResolveRequest,
    db: Session = Depends(get_db),
) -> CivitaiSourceAliasResolveResponse:
    """Read one committed source alias without altering its audited registry binding."""
    result = resolve_source_alias_exact(request.alias, db=db)
    if result.status == "success" and result.record is not None and result.alias is not None:
        return CivitaiSourceAliasResolveResponse(
            matched_alias=result.alias,
            **result.record.model_dump(mode="python"),
        )
    if result.status == "missing":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_detail(result.code, "source alias resolution failed"),
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_detail("corrupt_registry", "source alias resolution failed"),
    )


router.route_class = _default_route_class


router.route_class = _SourceAliasDiscoveryValidationRoute


def _source_alias_discovery_result(result: Any, response_type: type[Any]) -> Any:
    """Map only frozen CIV-SA-E outcomes without exposing domain diagnostics."""
    if result.status == "success":
        return response_type.model_validate(result.model_dump(mode="python"))
    if result.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("source_alias_discovery_invalid", "source alias discovery request invalid"),
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_detail("source_alias_registry_corrupt", "source alias discovery unavailable"),
    )


@router.get("/source-aliases", response_model=SourceAliasRegistryListResponse)
def list_civitai_source_aliases(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SourceAliasRegistryListResponse:
    """Expose the committed CIV-SA-E audited list facade without changing its semantics."""
    return _source_alias_discovery_result(
        list_registry_sources(db=db, limit=limit, offset=offset), SourceAliasRegistryListResponse,
    )


@router.post("/source-aliases/search", response_model=SourceAliasRegistrySearchResponse)
def search_civitai_source_aliases(
    request: SourceAliasRegistrySearchRequest,
    db: Session = Depends(get_db),
) -> SourceAliasRegistrySearchResponse:
    """Expose CIV-SA-E ranked candidates only; this never chooses or resolves a target."""
    return _source_alias_discovery_result(
        search_registry_sources(request.query, db=db, limit=request.limit, offset=request.offset),
        SourceAliasRegistrySearchResponse,
    )


router.route_class = _default_route_class


router.route_class = _SourceAliasRenameValidationRoute


@router.post("/source-aliases/rename", response_model=CivitaiSourceAliasRenameResponse)
def rename_civitai_source_alias(
    request: CivitaiSourceAliasRenameRequest,
    db: Session = Depends(get_db),
) -> CivitaiSourceAliasRenameResponse:
    """Delegate one typed rename intent to the committed audited lifecycle core."""
    result = rename_primary_source_alias(request, db=db)
    if result.status == "success":
        return CivitaiSourceAliasRenameResponse.model_validate(result.model_dump(mode="python"))
    if result.status == "missing":
        status_code, code = status.HTTP_404_NOT_FOUND, result.code
    elif result.code in {"stale_registry_version", "target_archived"}:
        status_code, code = status.HTTP_409_CONFLICT, result.code
    elif result.status == "rejected":
        status_code, code = status.HTTP_422_UNPROCESSABLE_ENTITY, result.code
    elif result.status == "conflict":
        status_code, code = status.HTTP_409_CONFLICT, result.code
    else:
        status_code, code = status.HTTP_409_CONFLICT, "source_alias_registry_corrupt"
    raise HTTPException(status_code=status_code, detail=_detail(code, "source alias rename failed"))


router.route_class = _default_route_class


router.route_class = _SourceAliasArchiveValidationRoute


@router.post("/source-aliases/archive", response_model=CivitaiSourceAliasArchiveResponse)
def archive_civitai_source_alias(
    request: CivitaiSourceAliasArchiveRequest,
    db: Session = Depends(get_db),
) -> CivitaiSourceAliasArchiveResponse:
    """Delegate one typed archive intent to the committed audited lifecycle core."""
    result = archive_source_alias(request, db=db)
    if result.status == "success":
        return CivitaiSourceAliasArchiveResponse.model_validate(result.model_dump(mode="python"))
    if result.status == "missing":
        status_code, code = status.HTTP_404_NOT_FOUND, result.code
    elif result.status == "corrupt":
        status_code, code = status.HTTP_409_CONFLICT, "source_alias_registry_corrupt"
    elif result.status == "conflict" or result.code in {"stale_registry_version", "already_archived"}:
        status_code, code = status.HTTP_409_CONFLICT, result.code
    else:
        status_code, code = status.HTTP_422_UNPROCESSABLE_ENTITY, result.code
    raise HTTPException(status_code=status_code, detail=_detail(code, "source alias archive failed"))


router.route_class = _default_route_class


@router.post("/import")
def import_civitai_recipe(request: CivitaiRecipeImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return import_recipe(
            request.locator,
            embedded_image=request.embedded_image_bytes(),
            remember_alias=request.remember_alias,
            db=db,
        )
    except SourceAliasImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=_detail(exc.code, "source alias import failed")) from exc
    except AcquisitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_detail(exc.code, "civitai acquisition failed", provenance=exc.provenance)) from exc
    except Exception as exc:
        # Import fixtures and acquisition metadata are untrusted; never echo their contents.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_detail("embedded_metadata_invalid", "embedded metadata invalid")) from exc


@router.post("/inspect")
def inspect_civitai_recipe(request: CivitaiRecipeInspectRequest) -> dict[str, Any]:
    return inspect_recipe(request.recipe)


@router.post("/validate")
def validate_civitai_recipe(request: CivitaiRecipeInspectRequest) -> dict[str, Any]:
    return inspect_recipe(request.recipe)


@router.post("/resolve")
def resolve_civitai_recipe(request: CivitaiRecipeResolveRequest) -> dict[str, Any]:
    ledger = [LocalResourceLedgerEntry(**entry.model_dump()) for entry in request.ledger]
    result = resolve_recipe(request.recipe, ledger=ledger, strict=request.strict)
    report = result["report"]
    if request.strict and not report["ready"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_detail("resource_resolution_failed", "strict resource resolution did not produce verified locks", report=report))
    return result


@router.get("/local-ledger")
def query_local_civitai_ledger(
    kind: str | None = None,
    civitai_model_id: int | None = None,
    civitai_model_version_id: int | None = None,
    civitai_file_id: int | None = None,
    air: str | None = None,
    sha256: str | None = None,
    availability: bool | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Read a deterministic backend-owned local Civitai identity snapshot."""
    snapshot = local_identity_ledger(
        db, kind=kind, civitai_model_id=civitai_model_id,
        civitai_model_version_id=civitai_model_version_id, civitai_file_id=civitai_file_id,
        air=air, sha256=sha256, availability=availability,
    )
    return ledger_payload(snapshot)


@router.post("/resolve-local")
def resolve_local_civitai_recipe(
    request: CivitaiRecipeResolveLocalRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Strictly resolve against one backend-owned ledger snapshot only."""
    snapshot = local_identity_ledger(db)
    result = resolve_recipe(request.recipe, ledger=snapshot.entries, strict=True)
    report = result["report"]
    if not report["ready"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_detail(
                "local_resource_resolution_failed",
                "strict local resource resolution did not produce verified locks",
                report=report,
                snapshot=ledger_payload(snapshot)["snapshot"],
            ),
        )
    return {**result, "snapshot": ledger_payload(snapshot)["snapshot"]}


router.route_class = _CompatibilityValidationRoute


@router.post("/compatibility", response_model=CivitaiRecipeCompatibilityResponse)
def compatibility_civitai_recipe(request: CivitaiRecipeCompatibilityRequest) -> CivitaiRecipeCompatibilityResponse:
    """Pure CIV-V-E decision endpoint; incompatible is successful structured data."""
    from app.services.civitai_recipe_compatibility import preflight_recipe_compatibility
    decision = preflight_recipe_compatibility(
        request.recipe, request.resource_report.model_dump(),
        requested_model_family=request.model_family,
        runtime_capabilities=request.runtime_capabilities.model_dump(),
    )
    return CivitaiRecipeCompatibilityResponse.model_validate(decision)


router.route_class = _default_route_class


router.route_class = _VariantFacadeValidationRoute
@router.post("/variants/generate-one", response_model=CivitaiRecipeVariantGenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_one_civitai_recipe_variant(
    request: CivitaiRecipeVariantGenerateRequest,
    db: Session = Depends(get_db),
) -> CivitaiRecipeVariantGenerateResponse:
    """Create exactly one fresh, immutable Child submission from a canonical Parent."""
    try:
        return generate_one_variant(request, db=db)
    except VariantFacadeError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.code == "queue_full" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(
            status_code=code,
            detail=_compatibility_safe(_detail(exc.code, exc.message, phase=exc.phase)),
        ) from exc


router.route_class = _default_route_class


router.route_class = _VariantFacadeValidationRoute


def _variation_error(exc: VariationSetError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.code == "not_found" else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=code, detail=_compatibility_safe(_detail(exc.code, exc.message, phase=exc.phase)))


@router.post("/variation-sets", status_code=status.HTTP_202_ACCEPTED)
def create_civitai_recipe_variation_set(request: CivitaiRecipeVariationSetCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return create_variation_set(request, db=db)
    except VariationSetError as exc:
        raise _variation_error(exc) from exc


@router.get("/variation-sets/{variation_set_id}")
def get_civitai_recipe_variation_set(variation_set_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return get_variation_set(variation_set_id, db=db)
    except VariationSetError as exc:
        raise _variation_error(exc) from exc


@router.post("/variation-sets/{variation_set_id}/cancel")
def cancel_civitai_recipe_variation_set(variation_set_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return cancel_variation_set(variation_set_id, db=db)
    except VariationSetError as exc:
        raise _variation_error(exc) from exc


@router.get("/variation-sets/{variation_set_id}/export")
def export_civitai_recipe_variation_set(variation_set_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return export_variation_set(variation_set_id, db=db)
    except VariationSetError as exc:
        raise _variation_error(exc) from exc


router.route_class = _default_route_class


@router.post("/build")
def build_civitai_recipe(request: CivitaiRecipeBuildRequest) -> dict[str, Any]:
    try:
        return build_recipe(request.recipe, resource_report=report_from_payload(request.resource_report.model_dump(exclude_none=True)), model_family=request.model_family, input_bindings=request.input_bindings)
    except RecipeCompileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.diagnostic) from exc


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_civitai_recipe(request: CivitaiRecipeRunRequest) -> dict[str, Any]:
    if request.queue_params:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "audited_queue_overrides_forbidden",
                "audited recipe submissions do not permit queue-time overrides",
                rejected_keys=sorted(request.queue_params),
            ),
        )

    build = request.build
    try:
        bundle = build_recipe_provenance_bundle(
            recipe=build.get("recipe"), workflow=build.get("workflow"),
            input_hashes=build.get("input_hashes", []), resource_locks=build.get("resource_locks"),
            runtime_provenance=request.runtime_provenance,
            reproduction_level=build.get("reproduction_report", {}).get("level"),
        )
    except ProvenanceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.detail()) from exc
    params = dict(request.queue_params)
    params["workflow"] = bundle["workflow"]
    params["recipe_provenance"] = bundle
    try:
        job_id = submit_custom(params)
    except QueueFullError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_detail("queue_full", str(exc))) from exc
    return {
        "job_id": job_id,
        "status": "queued",
        "recipe_sha256": bundle["recipe_sha256"],
        "workflow_sha256": bundle["workflow_sha256"],
        "reproduction_level": bundle["reproduction_level"],
    }
