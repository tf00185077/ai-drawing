"""Pure, offline CIV-V-B child Recipe derivation service."""
from __future__ import annotations

from copy import deepcopy
import secrets
from typing import Any, Callable

from pydantic import ValidationError

from app.schemas.civitai_recipe_derivation import (
    AppliedDirective,
    CivitaiRecipeDerivationRequest,
    CivitaiRecipeDerivationResponse,
    DerivationRequirements,
    RecipeDerivationDirective,
)
from app.schemas.generation_recipe import MAX_SIGNED_64_BIT_SEED, GenerationRecipe
from app.services.civitai_recipe_gallery import canonical_sha256


class RecipeDerivationError(ValueError):
    """Stable fail-closed CIV-V-B service failure."""

    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code)


def _recipe_snapshot(recipe: GenerationRecipe) -> dict[str, Any]:
    return recipe.model_dump(mode="json", exclude_none=True)


def _parent_value(snapshot: dict[str, Any], field: str) -> Any:
    if field.startswith("sampling."):
        sampling = snapshot.get("sampling")
        return sampling.get(field.removeprefix("sampling.")) if isinstance(sampling, dict) else None
    return snapshot.get(field)


def _set_child_value(snapshot: dict[str, Any], field: str, value: Any) -> None:
    if field.startswith("sampling."):
        sampling = snapshot.setdefault("sampling", {})
        if not isinstance(sampling, dict):
            raise RecipeDerivationError("canonical_field_invalid", field)
        sampling[field.removeprefix("sampling.")] = value
    else:
        snapshot[field] = value


def _validate_replace_value(parent_snapshot: dict[str, Any], directive: RecipeDerivationDirective) -> Any:
    value = directive.value
    expected_types: dict[str, tuple[type, ...]] = {
        "base_prompt": (str,), "negative_prompt": (str,),
        "sampling.seed": (int,), "sampling.steps": (int,),
        "sampling.cfg": (int, float), "sampling.sampler": (str,),
        "sampling.scheduler": (str,), "sampling.denoise": (int, float),
        "sampling.width": (int,), "sampling.height": (int,),
    }
    if value is not None and (isinstance(value, bool) or not isinstance(value, expected_types[directive.field])):
        raise RecipeDerivationError("replace_value_invalid", directive.field)
    candidate = deepcopy(parent_snapshot)
    _set_child_value(candidate, directive.field, value)
    try:
        validated = GenerationRecipe.model_validate(candidate)
    except ValidationError as exc:
        raise RecipeDerivationError("replace_value_invalid", directive.field) from exc
    return _parent_value(_recipe_snapshot(validated), directive.field)


def _random_seed(default_random_seed: Callable[[], int]) -> int:
    value = default_random_seed()
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SIGNED_64_BIT_SEED:
        raise RecipeDerivationError("random_seed_invalid", "sampling.seed")
    return value


def derive_generation_recipe(
    request: CivitaiRecipeDerivationRequest,
    *,
    random_seed: Callable[[], int] | None = None,
) -> CivitaiRecipeDerivationResponse:
    """Derive one child snapshot without resolving, compiling, persisting, or queuing."""
    parent_snapshot = _recipe_snapshot(request.parent_recipe)
    parent_sha256 = canonical_sha256(parent_snapshot)
    if request.parent_recipe_sha256.lower() != parent_sha256:
        raise RecipeDerivationError("parent_recipe_hash_mismatch", "parent_recipe_sha256")

    child_snapshot = deepcopy(parent_snapshot)
    applied: list[AppliedDirective] = []
    changed_fields: list[str] = []
    seed_factory = random_seed or (lambda: secrets.randbelow(1 << 63))

    for directive in request.directives:
        parent_value = deepcopy(_parent_value(parent_snapshot, directive.field))
        if directive.policy == "preserve":
            child_value = deepcopy(parent_value)
        elif directive.policy == "replace":
            child_value = _validate_replace_value(parent_snapshot, directive)
            _set_child_value(child_snapshot, directive.field, child_value)
            changed_fields.append(directive.field)
        else:
            child_value = _random_seed(seed_factory)
            _set_child_value(child_snapshot, directive.field, child_value)
            changed_fields.append(directive.field)
        applied.append(AppliedDirective(
            field=directive.field, policy=directive.policy,
            parent_value=parent_value, child_value=deepcopy(child_value),
        ))

    if changed_fields:
        invalidated_evidence = {
            "workflow": deepcopy(parent_snapshot.get("workflow")),
            "runtime": deepcopy(parent_snapshot.get("runtime")),
            "confirmed": deepcopy(parent_snapshot.get("confirmed", [])),
            "inferred": deepcopy(parent_snapshot.get("inferred", [])),
            "evidence_manifest": deepcopy(parent_snapshot.get("evidence_manifest", [])),
            "invalidated_fields": sorted(changed_fields),
        }
        child_snapshot["workflow"] = None
        child_snapshot["runtime"] = None
        child_snapshot["confirmed"] = []
        child_snapshot["inferred"] = []
        child_snapshot["evidence_manifest"] = []
        requirements = DerivationRequirements(
            resolve_required=False, build_required=True,
            reason_codes=["content_or_sampling_changed", "audited_workflow_invalidated"],
        )
        try:
            child_recipe = GenerationRecipe.model_validate(child_snapshot)
        except ValidationError as exc:
            raise RecipeDerivationError("child_recipe_invalid") from exc
    else:
        invalidated_evidence = {}
        requirements = DerivationRequirements(resolve_required=False, build_required=False)
        child_recipe = request.parent_recipe

    child_snapshot = _recipe_snapshot(child_recipe)
    return CivitaiRecipeDerivationResponse(
        child_recipe=child_recipe,
        parent_recipe_sha256=parent_sha256,
        child_recipe_sha256=canonical_sha256(child_snapshot),
        applied_directives=applied,
        invalidated_evidence=invalidated_evidence,
        requirements=requirements,
    )
