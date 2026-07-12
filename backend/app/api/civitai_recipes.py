"""CIV-F HTTP contracts: only orchestration over CIV-A through CIV-E services."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.core.queue import QueueFullError, submit_custom
from app.schemas.civitai_recipes import (
    CivitaiRecipeBuildRequest,
    CivitaiRecipeImportRequest,
    CivitaiRecipeInspectRequest,
    CivitaiRecipeResolveRequest,
    CivitaiRecipeRunRequest,
)
from app.services.civitai_acquisition import AcquisitionError, redact_secrets
from app.services.civitai_recipe_gallery import ProvenanceValidationError, build_recipe_provenance_bundle
from app.services.civitai_recipe_pipeline import (
    build_recipe,
    import_recipe,
    inspect_recipe,
    report_from_payload,
    resolve_recipe,
)
from app.services.civitai_recipe_workflow_compiler import RecipeCompileError
from app.services.civitai_resource_resolution import LocalResourceLedgerEntry

router = APIRouter(prefix="/api/civitai-recipes", tags=["civitai-recipes"])


def _detail(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return redact_secrets({"code": code, "message": message, **extra})


@router.post("/import")
def import_civitai_recipe(request: CivitaiRecipeImportRequest) -> dict[str, Any]:
    try:
        return import_recipe(request.locator, embedded_image=request.embedded_image_bytes())
    except AcquisitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_detail(exc.code, str(exc), provenance=exc.provenance)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_detail("embedded_metadata_invalid", str(exc))) from exc


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


@router.post("/build")
def build_civitai_recipe(request: CivitaiRecipeBuildRequest) -> dict[str, Any]:
    try:
        return build_recipe(request.recipe, resource_report=report_from_payload(request.resource_report.model_dump()), model_family=request.model_family, input_bindings=request.input_bindings)
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
