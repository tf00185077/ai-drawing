"""CIV-V-F one-child immutable recipe variant facade."""
from __future__ import annotations

from copy import deepcopy
import re
import secrets
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from app.core.queue import QueueFullError, submit_audited_recipe
from app.schemas.civitai_recipe_derivation import CivitaiRecipeDerivationRequest
from app.schemas.civitai_recipe_variants import (
    CivitaiRecipeVariantGenerateRequest, CivitaiRecipeVariantGenerateResponse,
    CivitaiRecipeVariantLineage,
)
from app.schemas.civitai_source_aliases import CivitaiSourceAliasLineageBinding, CivitaiSourceAliasMaterializedParent
from app.schemas.generation_recipe import GenerationRecipe
from app.services.civitai_local_identity_ledger import ledger_payload, local_identity_ledger
from app.services.civitai_recipe_compatibility import preflight_recipe_compatibility
from app.services.civitai_recipe_derivation import RecipeDerivationError, derive_generation_recipe
from app.services.civitai_recipe_gallery import ProvenanceValidationError, build_recipe_provenance_bundle, canonical_sha256
from app.services.civitai_recipe_pipeline import build_recipe, report_from_payload, resolve_recipe
from app.services.civitai_recipe_workflow_compiler import RecipeCompileError
from app.services.civitai_source_alias_parent import materialize_source_alias_parent


class VariantFacadeError(ValueError):
    def __init__(self, phase: str, code: str, message: str = "variant generation rejected") -> None:
        self.phase, self.code, self.message = phase, code, message
        super().__init__(code)

    def detail(self) -> dict[str, str]:
        return {"phase": self.phase, "code": self.code, "message": self.message}


def validate_single_child_batch(workflow: Any) -> None:
    """Require explicit, integer batch_size=1 on every supported batch producer."""
    if not isinstance(workflow, Mapping):
        raise VariantFacadeError("batch_validation", "workflow_invalid")
    found: list[int] = []
    for node_id, node in workflow.items():
        if not isinstance(node, Mapping) or node.get("class_type") != "EmptyLatentImage":
            continue
        inputs = node.get("inputs")
        value = inputs.get("batch_size") if isinstance(inputs, Mapping) else None
        if isinstance(value, bool) or not isinstance(value, int):
            raise VariantFacadeError("batch_validation", "batch_size_invalid")
        if value != 1:
            raise VariantFacadeError("batch_validation", "batch_size_not_one")
        found.append(value)
    if not found:
        raise VariantFacadeError("batch_validation", "batch_size_missing")
    # The committed CIV-D compiler emits one source latent and one terminal image.
    # Extra branches would make a single immutable submission produce more than one child.
    if len(found) != 1:
        raise VariantFacadeError("batch_validation", "batch_source_ambiguous")
    save_images = [node for node in workflow.values() if isinstance(node, Mapping) and node.get("class_type") == "SaveImage"]
    if not save_images:
        raise VariantFacadeError("batch_validation", "image_output_missing")
    if len(save_images) > 1:
        raise VariantFacadeError("batch_validation", "image_output_ambiguous")


def _recipe_payload(recipe: Any) -> dict[str, Any]:
    return recipe.model_dump(mode="json", exclude_none=True)


def _lineage_digest(document: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in document.items() if key != "lineage_sha256"})


_OPAQUE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LINEAGE_COMPONENTS = {
    "parent_recipe_sha256": "parent_recipe",
    "derived_recipe_sha256": "derived_recipe",
    "built_child_recipe_sha256": "built_child_recipe",
    "workflow_sha256": "workflow",
    "resource_lock_sha256": "resource_locks",
    "strict_resolution_snapshot_sha256": "strict_resolution_snapshot",
    "compatibility_snapshot_sha256": "compatibility_snapshot",
    "invalidated_evidence_sha256": "invalidated_evidence",
}


def _validated_opaque_id(factory: Callable[[], str], name: str) -> str:
    try:
        value = factory()
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", f"{name}_factory_failed") from exc
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        raise VariantFacadeError("provenance_validation", f"{name}_invalid")
    return value


def _validate_lineage_bindings(lineage: Mapping[str, Any], components: Mapping[str, Any]) -> None:
    if _lineage_digest(dict(lineage)) != lineage.get("lineage_sha256"):
        raise VariantFacadeError("provenance_validation", "lineage_digest_mismatch")
    for lineage_field, component_name in _LINEAGE_COMPONENTS.items():
        if canonical_sha256(components[component_name]) != lineage.get(lineage_field):
            raise VariantFacadeError("provenance_validation", "lineage_binding_mismatch")


def _source_identity(recipe: Any) -> dict[str, Any]:
    source = recipe.source if hasattr(recipe, "source") else recipe.get("source")
    if isinstance(source, Mapping):
        image_id, media_url = source.get("image_id"), source.get("media_url")
    else:
        image_id, media_url = source.image_id, source.media_url
    if image_id is not None:
        return {"provider": "civitai", "image_id": image_id}
    if media_url is not None:
        return {"provider": "civitai", "media_url": media_url}
    raise VariantFacadeError("provenance_validation", "source_identity_invalid")


_SAFE_MATERIALIZER_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MATERIALIZER_STATUSES = {"success", "rejected", "missing", "corrupt", "archived", "repointed"}


def _materialize_alias_request(request: CivitaiRecipeVariantGenerateRequest, *, db: Any) -> tuple[CivitaiRecipeVariantGenerateRequest, CivitaiSourceAliasLineageBinding]:
    """Materialize exactly once; validate its boundary shape without revalidating its trusted Parent."""
    try:
        result = materialize_source_alias_parent(request.source_alias, db=db)
    except Exception:
        raise VariantFacadeError("source_alias_materialization", "materialization_failed") from None
    if not isinstance(result, CivitaiSourceAliasMaterializedParent):
        raise VariantFacadeError("source_alias_materialization", "materialization_invalid")

    status = getattr(result, "status", None)
    code = getattr(result, "code", None)
    parent = getattr(result, "parent_recipe", None)
    parent_sha256 = getattr(result, "parent_recipe_sha256", None)
    raw_binding = getattr(result, "alias_binding", None)
    if not isinstance(status, str) or status not in _MATERIALIZER_STATUSES or not isinstance(code, str) or _SAFE_MATERIALIZER_CODE.fullmatch(code) is None:
        raise VariantFacadeError("source_alias_materialization", "materialization_invalid")
    if status != "success":
        if parent is not None or parent_sha256 is not None or raw_binding is not None:
            raise VariantFacadeError("source_alias_materialization", "materialization_invalid")
        raise VariantFacadeError("source_alias_materialization", code)
    if not isinstance(parent, GenerationRecipe) or not isinstance(parent_sha256, str) or not isinstance(raw_binding, CivitaiSourceAliasLineageBinding):
        raise VariantFacadeError("source_alias_materialization", "materialization_invalid")

    try:
        # ``parent`` may carry verified confirmation evidence that normal public model
        # revalidation intentionally cannot reconstruct.  Preserve this exact trusted
        # object; only caller-owned request fields were validated at the HTTP boundary.
        parent_payload = _recipe_payload(parent)
        parent_sha = canonical_sha256(parent_payload)
        binding = CivitaiSourceAliasLineageBinding.model_validate(raw_binding.model_dump(mode="json"))
        if parent_sha != parent_sha256.lower() or binding.parent_recipe_sha256 != parent_sha:
            raise ValueError("parent hash mismatch")
        if binding.source_identity.model_dump(mode="json", exclude_none=True) != _source_identity(parent):
            raise ValueError("source identity mismatch")
        effective = request.model_copy(update={
            "parent_recipe": parent,
            "parent_recipe_sha256": parent_sha,
            "source_alias": None,
        })
        return effective, binding
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise VariantFacadeError("source_alias_materialization", "materialization_invalid") from None


def _build_validated_provenance(
    *,
    request: CivitaiRecipeVariantGenerateRequest,
    derivation: Any,
    snapshot: Any,
    report: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    build: Mapping[str, Any],
    workflow: Mapping[str, Any],
    variant_id_factory: Callable[[], str],
    job_id_factory: Callable[[], str],
    source_alias_binding: CivitaiSourceAliasLineageBinding | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], dict[str, Any]]:
    """Construct and validate every formal lineage binding in one fail-closed boundary."""
    try:
        child_recipe = derivation.child_recipe
        parent_payload = _recipe_payload(request.parent_recipe)
        derived_payload = _recipe_payload(child_recipe)
        applied_directives = [
            item.model_dump(mode="json", exclude_none=True) for item in derivation.applied_directives
        ]
        invalidated_evidence = derivation.invalidated_evidence
        resolution_snapshot = {"ledger": ledger_payload(snapshot), "report": dict(report)}
        build_recipe_payload = build.get("recipe")
        build_input_hashes = build.get("input_hashes", [])
        build_resource_locks = build.get("resource_locks")
        reproduction_report = build.get("reproduction_report")
        if not isinstance(reproduction_report, Mapping):
            raise TypeError("reproduction_report")
        reproduction_level = reproduction_report.get("level")
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", "phase_output_invalid") from exc

    try:
        bundle = build_recipe_provenance_bundle(
            recipe=build_recipe_payload,
            workflow=workflow,
            input_hashes=build_input_hashes,
            resource_locks=build_resource_locks,
            runtime_provenance=request.runtime_provenance.model_dump(mode="json"),
            reproduction_level=reproduction_level,
        )
    except ProvenanceValidationError as exc:
        raise VariantFacadeError("provenance_validation", exc.code) from exc
    if not isinstance(bundle, Mapping) or any(
        key not in bundle for key in ("recipe", "workflow", "input_hashes", "resource_locks")
    ):
        raise VariantFacadeError("provenance_validation", "phase_output_invalid")

    variant_id = _validated_opaque_id(variant_id_factory, "variant_id")
    job_id = _validated_opaque_id(job_id_factory, "job_id")
    components = {
        "parent_recipe": parent_payload,
        "derived_recipe": derived_payload,
        "built_child_recipe": bundle["recipe"],
        "workflow": bundle["workflow"],
        "resource_locks": bundle["resource_locks"],
        "strict_resolution_snapshot": resolution_snapshot,
        "compatibility_snapshot": dict(compatibility),
        "invalidated_evidence": invalidated_evidence,
    }
    try:
        digests = {
            lineage_field: canonical_sha256(components[component_name])
            for lineage_field, component_name in _LINEAGE_COMPONENTS.items()
        }
        if (
            request.parent_recipe_sha256.lower() != digests["parent_recipe_sha256"]
            or derivation.parent_recipe_sha256 != digests["parent_recipe_sha256"]
        ):
            raise VariantFacadeError("provenance_validation", "parent_recipe_hash_mismatch")
        if derivation.child_recipe_sha256 != digests["derived_recipe_sha256"]:
            raise VariantFacadeError("provenance_validation", "derived_recipe_hash_mismatch")
        lineage_document = {
            "schema_version": "1.1" if source_alias_binding is not None else "1.0",
            "variant_id": variant_id,
            "job_id": job_id,
            **digests,
            "applied_directives": applied_directives,
        }
        if source_alias_binding is not None:
            parent_identity = _source_identity(request.parent_recipe)
            child_identity = _source_identity(child_recipe)
            built_child_identity = _source_identity(bundle["recipe"])
            binding_identity = source_alias_binding.source_identity.model_dump(mode="json", exclude_none=True)
            if (
                source_alias_binding.parent_recipe_sha256 != digests["parent_recipe_sha256"]
                or binding_identity != parent_identity
                or binding_identity != child_identity
                or binding_identity != built_child_identity
            ):
                raise VariantFacadeError("provenance_validation", "source_alias_binding_mismatch")
            lineage_document["source_alias_binding"] = source_alias_binding.model_dump(mode="json")
        lineage_document["lineage_sha256"] = _lineage_digest(lineage_document)
    except VariantFacadeError:
        raise
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", "canonicalization_failed") from exc

    try:
        lineage = CivitaiRecipeVariantLineage.model_validate(lineage_document).model_dump(mode="json", exclude_none=True)
    except ValidationError as exc:
        raise VariantFacadeError("provenance_validation", "lineage_invalid") from exc
    try:
        _validate_lineage_bindings(lineage, components)
    except VariantFacadeError:
        raise
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", "canonicalization_failed") from exc

    queue_bundle = deepcopy(bundle)
    queue_bundle["variant_lineage"] = deepcopy(lineage)
    return queue_bundle, lineage, digests, components


def _fresh_execution_recipe(derived_recipe: Any, runtime: Any) -> Any:
    payload = _recipe_payload(derived_recipe)
    # Parent runtime/workflow are never executable child evidence. The compiler replaces
    # workflow, while the separately supplied digest-bound runtime is explicitly bound.
    payload["runtime"] = runtime.model_dump(mode="json", exclude_none=True)
    payload["workflow"] = None
    payload["confirmed"] = []
    payload["inferred"] = []
    payload["evidence_manifest"] = []
    return type(derived_recipe).model_validate(payload)


def _generate_one_variant(
    request: CivitaiRecipeVariantGenerateRequest,
    *,
    db: Any,
    variant_id_factory: Callable[[], str] | None = None,
    job_id_factory: Callable[[], str] | None = None,
    source_alias_binding: CivitaiSourceAliasLineageBinding | None = None,
) -> CivitaiRecipeVariantGenerateResponse:
    """Execute a validated direct or backend-materialized Parent without acquiring aliases."""
    try:
        derivation = derive_generation_recipe(CivitaiRecipeDerivationRequest(
            parent_recipe=request.parent_recipe, parent_recipe_sha256=request.parent_recipe_sha256,
            directives=request.directives,
        ))
    except RecipeDerivationError as exc:
        raise VariantFacadeError("derive", exc.code, exc.field) from exc
    except Exception as exc:
        raise VariantFacadeError("derive", "derivation_failed") from exc
    if not hasattr(derivation, "child_recipe"):
        raise VariantFacadeError("provenance_validation", "phase_output_invalid")
    child_recipe = derivation.child_recipe

    # Always obtain a fresh, backend-owned ledger snapshot, including all-preserve variants.
    try:
        snapshot = local_identity_ledger(db)
        if not hasattr(snapshot, "entries") or not hasattr(snapshot, "metadata"):
            raise VariantFacadeError("provenance_validation", "phase_output_invalid")
        resolution = resolve_recipe(child_recipe, ledger=snapshot.entries, strict=True)
        if not isinstance(resolution, Mapping):
            raise VariantFacadeError("provenance_validation", "phase_output_invalid")
        report = resolution.get("report")
        if not isinstance(report, Mapping):
            raise VariantFacadeError("provenance_validation", "phase_output_invalid")
        if report.get("ready") is not True:
            raise VariantFacadeError("resolve_local", "local_resource_resolution_failed")
    except VariantFacadeError:
        raise
    except Exception as exc:
        raise VariantFacadeError("resolve_local", "local_resource_resolution_failed", exc.__class__.__name__) from exc
    try:
        compatibility = preflight_recipe_compatibility(
            child_recipe, report, requested_model_family=request.model_family,
            runtime_capabilities=request.runtime_capabilities.model_dump(mode="json"),
        )
        if not isinstance(compatibility, Mapping):
            raise VariantFacadeError("provenance_validation", "phase_output_invalid")
        if compatibility.get("compatible") is not True:
            diagnostics = compatibility.get("diagnostics", [])
            code = next((item.get("code") for item in diagnostics if isinstance(item, Mapping) and item.get("code")), "incompatible")
            raise VariantFacadeError("compatibility", str(code))
    except VariantFacadeError:
        raise
    except Exception as exc:
        raise VariantFacadeError("compatibility", "compatibility_failed", exc.__class__.__name__) from exc

    try:
        execution_recipe = _fresh_execution_recipe(child_recipe, request.runtime_provenance)
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", "phase_output_invalid") from exc
    try:
        build = build_recipe(
            execution_recipe, resource_report=report_from_payload(report), model_family=request.model_family,
            input_bindings={reference: binding.model_dump(mode="json") for reference, binding in request.input_bindings.items()},
        )
    except RecipeCompileError as exc:
        raise VariantFacadeError("build", str(exc.diagnostic.get("code", "build_failed"))) from exc
    except Exception as exc:
        raise VariantFacadeError("build", "build_failed", exc.__class__.__name__) from exc

    if not isinstance(build, Mapping):
        raise VariantFacadeError("provenance_validation", "phase_output_invalid")
    workflow = build.get("workflow")
    validate_single_child_batch(workflow)
    try:
        queue_bundle, lineage, digests, components = _build_validated_provenance(
            request=request,
            derivation=derivation,
            snapshot=snapshot,
            report=report,
            compatibility=compatibility,
            build=build,
            workflow=workflow,
            variant_id_factory=variant_id_factory or (lambda: secrets.token_urlsafe(32)),
            job_id_factory=job_id_factory or (lambda: secrets.token_urlsafe(24)),
            source_alias_binding=source_alias_binding,
        )
    except VariantFacadeError:
        raise
    except Exception as exc:
        raise VariantFacadeError("provenance_validation", "provenance_validation_failed") from exc
    variant_id = lineage["variant_id"]
    job_id = lineage["job_id"]
    try:
        submitted_job_id = submit_audited_recipe({"workflow": queue_bundle["workflow"], "recipe_provenance": queue_bundle}, job_id=job_id)
    except QueueFullError as exc:
        raise VariantFacadeError("queue", "queue_full") from exc
    except Exception as exc:
        raise VariantFacadeError("queue", "queue_submission_failed", exc.__class__.__name__) from exc
    if submitted_job_id != job_id:
        raise VariantFacadeError("queue", "queue_job_identity_mismatch")
    return CivitaiRecipeVariantGenerateResponse(
        variant_id=variant_id, parent_recipe_sha256=digests["parent_recipe_sha256"],
        derived_recipe_sha256=digests["derived_recipe_sha256"],
        built_child_recipe_sha256=digests["built_child_recipe_sha256"],
        workflow_sha256=digests["workflow_sha256"],
        resource_lock_sha256=digests["resource_lock_sha256"], job_id=job_id, status="queued",
        derivation={"applied_directives": lineage["applied_directives"], "invalidated_evidence_sha256": lineage["invalidated_evidence_sha256"]},
        compatibility={"status": compatibility.get("status"), "snapshot_sha256": lineage["compatibility_snapshot_sha256"]},
        provenance_components=components,
    )


def generate_one_variant(
    request: CivitaiRecipeVariantGenerateRequest,
    *,
    db: Any,
    variant_id_factory: Callable[[], str] | None = None,
    job_id_factory: Callable[[], str] | None = None,
) -> CivitaiRecipeVariantGenerateResponse:
    """Public single-child facade: it alone materializes a caller-selected alias."""
    source_alias_binding: CivitaiSourceAliasLineageBinding | None = None
    if request.source_alias is not None:
        request, source_alias_binding = _materialize_alias_request(request, db=db)
    return _generate_one_variant(
        request, db=db, variant_id_factory=variant_id_factory, job_id_factory=job_id_factory,
        source_alias_binding=source_alias_binding,
    )


def generate_one_variant_from_materialized_parent(
    request: CivitaiRecipeVariantGenerateRequest,
    *,
    parent_recipe: GenerationRecipe,
    parent_recipe_sha256: str,
    source_alias_binding: CivitaiSourceAliasLineageBinding,
    db: Any,
    variant_id_factory: Callable[[], str] | None = None,
    job_id_factory: Callable[[], str] | None = None,
) -> CivitaiRecipeVariantGenerateResponse:
    """Internal-only child boundary for a variation set's already materialized Parent."""
    try:
        parent_payload = _recipe_payload(parent_recipe)
        parent_sha = canonical_sha256(parent_payload)
        binding = CivitaiSourceAliasLineageBinding.model_validate(source_alias_binding.model_dump(mode="json"))
        if (
            request.source_alias is None
            or parent_sha != parent_recipe_sha256.lower()
            or binding.parent_recipe_sha256 != parent_sha
            or binding.source_identity.model_dump(mode="json", exclude_none=True) != _source_identity(parent_recipe)
        ):
            raise ValueError("trusted parent mismatch")
        effective = request.model_copy(update={
            "parent_recipe": parent_recipe,
            "parent_recipe_sha256": parent_sha,
            "source_alias": None,
        })
    except (AttributeError, TypeError, ValueError, ValidationError):
        raise VariantFacadeError("source_alias_materialization", "materialization_invalid") from None
    return _generate_one_variant(
        effective, db=db, variant_id_factory=variant_id_factory, job_id_factory=job_id_factory,
        source_alias_binding=binding,
    )
