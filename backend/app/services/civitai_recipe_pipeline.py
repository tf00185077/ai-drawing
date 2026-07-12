"""CIV-F thin orchestration over the already-owned CIV-A through CIV-E services."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

import httpx

from app.schemas.generation_recipe import GenerationRecipe, assess_reproduction
from app.services.civitai_acquisition import CivitaiTransportResponse, acquire_civitai_recipe
from app.services.civitai_embedded_metadata import extract_embedded_metadata
from app.services.civitai_resource_resolution import (
    LocalResourceLedgerEntry,
    ResolutionEntry,
    ResourceResolutionReport,
    resolve_recipe_resources,
)
from app.services.civitai_recipe_gallery import canonical_sha256
from app.services.civitai_recipe_workflow_compiler import compile_generation_recipe_workflow


class CivitaiHttpTransport:
    """The smallest production transport adapter; acquisition owns retry/redaction."""

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> CivitaiTransportResponse:
        response = httpx.get(url, params=params, headers=headers, timeout=20.0, follow_redirects=True)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"body": response.text}
        return CivitaiTransportResponse(response.status_code, payload, dict(response.headers))

    def get_bytes(self, url: str) -> CivitaiTransportResponse:
        response = httpx.get(url, timeout=20.0, follow_redirects=True)
        return CivitaiTransportResponse(response.status_code, response.content, dict(response.headers))


def import_recipe(locator: int | str, *, embedded_image: bytes | None = None, transport: Any | None = None) -> dict[str, Any]:
    embedded_metadata = extract_embedded_metadata(embedded_image) if embedded_image is not None else None
    acquisition = acquire_civitai_recipe(locator, transport=transport or CivitaiHttpTransport(), embedded_metadata=embedded_metadata)
    if acquisition.recipe is None:
        raise ValueError("acquisition returned no recipe")
    raw = acquisition.to_dict()
    return {
        "raw_acquisition_payload": raw["raw_api_payload"],
        "acquisition": raw,
        "recipe": acquisition.recipe.model_dump(mode="json", exclude_none=True),
        "reproduction_report": assess_reproduction(acquisition.recipe).model_dump(mode="json"),
    }


def inspect_recipe(recipe: GenerationRecipe) -> dict[str, Any]:
    """Pure CIV-A assessment: no file, network, compiler, queue, or database access."""
    report = assess_reproduction(recipe)
    return {
        "recipe": recipe.model_dump(mode="json", exclude_none=True),
        "reproduction_report": report.model_dump(mode="json"),
        "confirmed": [item.model_dump(mode="json", exclude_none=True) for item in recipe.confirmed],
        "inferred": [item.model_dump(mode="json", exclude_none=True) for item in recipe.inferred],
        "missing": [item.model_dump(mode="json", exclude_none=True) for item in recipe.missing],
    }


def _resolution_aware_reproduction_report(recipe: GenerationRecipe, report: ResourceResolutionReport) -> dict[str, Any]:
    """Keep CIV-A assessment authoritative, but never claim exact replay without resolved local locks."""
    reproduction = dict(inspect_recipe(recipe)["reproduction_report"])
    resolution_verified = all(entry.status == "resolved" and entry.hash_verified for entry in report.entries)
    requirements = dict(reproduction.get("requirements") or {})
    requirements["resource_resolution"] = resolution_verified
    reproduction["requirements"] = requirements
    if not resolution_verified:
        caveats = list(reproduction.get("caveats") or [])
        if "resource_resolution" not in caveats:
            caveats.append("resource_resolution")
        reproduction["caveats"] = caveats
        if reproduction.get("level") == "exact_ready":
            reproduction["level"] = "workflow_ready_but_runtime_may_differ"
    return reproduction


def resolve_recipe(recipe: GenerationRecipe, *, ledger: list[LocalResourceLedgerEntry], strict: bool) -> dict[str, Any]:
    report = resolve_recipe_resources(recipe.resources, ledger, strict=strict)
    return {"report": report.to_dict(), "reproduction_report": _resolution_aware_reproduction_report(recipe, report)}


def report_from_payload(payload: Mapping[str, Any]) -> ResourceResolutionReport:
    entries = [ResolutionEntry(**dict(item)) for item in payload.get("entries", [])]
    return ResourceResolutionReport(
        strict=bool(payload.get("strict")), ready=bool(payload.get("ready")),
        entries=entries, resource_lock=[dict(item) for item in payload.get("resource_lock", [])],
    )


def build_recipe(recipe: GenerationRecipe, *, resource_report: ResourceResolutionReport, model_family: str, input_bindings: Mapping[str, Any]) -> dict[str, Any]:
    compiled = compile_generation_recipe_workflow(recipe, resource_report, model_family=model_family, input_bindings=input_bindings)
    workflow = compiled.workflow
    workflow_sha256 = canonical_sha256(workflow)
    recipe_payload = recipe.model_dump(mode="json", exclude_none=True)
    recipe_payload["workflow"] = {
        "reference": "civ-d:compiled-workflow", "snapshot": workflow, "snapshot_sha256": workflow_sha256,
    }
    built_recipe = GenerationRecipe.model_validate(recipe_payload)
    input_hashes: list[dict[str, Any]] = []
    for index, recipe_input in enumerate(built_recipe.inputs):
        binding = input_bindings.get(recipe_input.reference)
        if not isinstance(binding, Mapping) or not isinstance(binding.get("local_path"), str) or not binding["local_path"]:
            from app.services.civitai_recipe_workflow_compiler import RecipeCompileError
            raise RecipeCompileError({"code": "input_binding_local_path_missing", "canonical_field": f"inputs[{index}]", "message": "recipe input requires a local_path binding for provenance"})
        input_hashes.append({
            "reference": recipe_input.reference, "sha256": recipe_input.sha256,
            "required": True, "local_path": binding["local_path"],
        })
    return {
        "recipe": built_recipe.model_dump(mode="json", exclude_none=True),
        "workflow": workflow,
        "workflow_sha256": workflow_sha256,
        "input_hashes": input_hashes,
        "resource_locks": resource_report.resource_lock,
        "manifest": compiled.manifest,
        "input_bindings": dict(input_bindings),
        "reproduction_report": assess_reproduction(built_recipe).model_dump(mode="json"),
    }
