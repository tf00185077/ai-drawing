"""CIV-V-B frozen canonical Recipe derivation contract."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest
from pydantic import ValidationError

from app.schemas.civitai_recipe_derivation import CivitaiRecipeDerivationRequest
from app.schemas.generation_recipe import (
    EvidenceRecord,
    GenerationRecipe,
    _build_recipe_from_trusted_evidence,
    _issue_trusted_provenance_capability,
)
from app.services.civitai_recipe_derivation import RecipeDerivationError, derive_generation_recipe


CANONICAL_FIELDS = (
    "base_prompt", "negative_prompt", "sampling.seed", "sampling.steps",
    "sampling.cfg", "sampling.sampler", "sampling.scheduler", "sampling.denoise",
    "sampling.width", "sampling.height",
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parent_recipe() -> dict:
    workflow = {"1": {"class_type": "KSampler", "inputs": {"seed": 7}}}
    manifest_document = {
        "identity": "parent-evidence", "reference": "parent:evidence",
        "payload": {"source": "parent"}, "assertions": [],
    }
    return {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 1},
        "base_prompt": "parent prompt",
        "negative_prompt": "lowres",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": "a" * 64}],
        "sampling": {
            "seed": 7, "steps": 20, "cfg": 7.0, "sampler": "euler",
            "scheduler": "normal", "denoise": 1.0, "width": 512, "height": 512,
        },
        "passes": [{"name": "base", "inherits_from": "recipe.sampling", "sampling": {}}],
        "inputs": [{"reference": "pose.png", "sha256": "b" * 64, "kind": "image"}],
        "controls": [{"kind": "pose", "input_ref": "pose.png"}],
        "detailers": [{"kind": "face", "model": "face.pt", "denoise": 0.25}],
        "postprocess": [{"kind": "upscale", "model": "4x.pth", "scale": 2}],
        "workflow": {"reference": "parent:workflow", "snapshot": workflow, "snapshot_sha256": _sha(workflow)},
        "runtime": {"engine": "ComfyUI", "engine_version": "1", "reference": "parent:runtime"},
        "raw": {"opaque": {"keep": True}},
        "confirmed": [{"canonical_field": "workflow", "source": "importer", "reference": "parent:workflow"}],
        "inferred": [{"canonical_field": "model_family", "source": "importer", "reference": "parent:inference"}],
        "evidence_manifest": [{**manifest_document, "sha256": _sha(manifest_document)}],
    }


def _directives(**overrides: dict) -> list[dict]:
    return [overrides.get(field, {"field": field, "policy": "preserve"}) for field in CANONICAL_FIELDS]


def _recipe_snapshot(recipe: dict | GenerationRecipe) -> dict:
    parsed = recipe if isinstance(recipe, GenerationRecipe) else GenerationRecipe.model_validate(recipe)
    return parsed.model_dump(mode="json", exclude_none=True)


def _request(parent: dict | GenerationRecipe, directives: list[dict], *, parent_hash: str | None = None) -> CivitaiRecipeDerivationRequest:
    return CivitaiRecipeDerivationRequest.model_validate({
        "parent_recipe": parent,
        "parent_recipe_sha256": parent_hash or _sha(_recipe_snapshot(parent)),
        "directives": directives,
    })


def test_preserve_only_is_hash_identical_and_requires_no_rebuild() -> None:
    parent = _parent_recipe()
    parent_snapshot = _recipe_snapshot(parent)
    before = json.dumps(parent, ensure_ascii=False, sort_keys=True)

    result = derive_generation_recipe(_request(parent, _directives()))

    child = result.child_recipe.model_dump(mode="json", exclude_none=True)
    assert child == parent_snapshot
    assert result.parent_recipe_sha256 == _sha(parent_snapshot)
    assert result.child_recipe_sha256 == _sha(child) == result.parent_recipe_sha256
    assert result.invalidated_evidence == {}
    assert result.requirements.model_dump() == {
        "resolve_required": False, "build_required": False, "reason_codes": [],
    }
    assert json.dumps(parent, ensure_ascii=False, sort_keys=True) == before


def test_preserve_only_keeps_trusted_parent_evidence_and_its_canonical_hash() -> None:
    parent_payload = _parent_recipe()
    parent = _build_recipe_from_trusted_evidence(
        parent_payload,
        capability=_issue_trusted_provenance_capability(
            EvidenceRecord.model_validate(item) for item in parent_payload["confirmed"]
        ),
    )
    parent_snapshot = _recipe_snapshot(parent)

    result = derive_generation_recipe(_request(parent, _directives()))

    assert result.parent_recipe_sha256 == _sha(parent_snapshot)
    assert result.child_recipe_sha256 == result.parent_recipe_sha256
    assert result.child_recipe.confirmed == parent.confirmed


def test_content_and_sampling_derivation_invalidates_audit_and_records_fixed_random_seed() -> None:
    parent = _parent_recipe()
    parent_snapshot = _recipe_snapshot(parent)
    result = derive_generation_recipe(
        _request(parent, _directives(
            **{
                "base_prompt": {"field": "base_prompt", "policy": "replace", "value": "child prompt"},
                "sampling.steps": {"field": "sampling.steps", "policy": "replace", "value": 31},
                "sampling.seed": {"field": "sampling.seed", "policy": "randomize"},
            }
        )),
        random_seed=lambda: 424242,
    )

    child = result.child_recipe.model_dump(mode="json", exclude_none=True)
    assert child["base_prompt"] == "child prompt"
    assert child["sampling"]["steps"] == 31
    assert child["sampling"]["seed"] == 424242
    by_field = {item.field: item for item in result.applied_directives}
    assert by_field["base_prompt"].model_dump() == {"field": "base_prompt", "policy": "replace", "parent_value": "parent prompt", "child_value": "child prompt"}
    assert by_field["sampling.steps"].model_dump() == {"field": "sampling.steps", "policy": "replace", "parent_value": 20, "child_value": 31}
    assert by_field["sampling.seed"].model_dump() == {"field": "sampling.seed", "policy": "randomize", "parent_value": 7, "child_value": 424242}
    assert child.get("workflow") is None
    assert child.get("runtime") is None
    assert child["confirmed"] == []
    assert child["inferred"] == []
    assert child["evidence_manifest"] == []
    assert result.invalidated_evidence["invalidated_fields"] == ["base_prompt", "sampling.seed", "sampling.steps"]
    for field in ("workflow", "runtime", "confirmed", "inferred", "evidence_manifest"):
        assert result.invalidated_evidence[field] == parent_snapshot[field]


def test_content_sampling_change_preserves_resources_and_requires_build_not_resolve() -> None:
    parent = _parent_recipe()
    parent_snapshot = _recipe_snapshot(parent)
    result = derive_generation_recipe(_request(parent, _directives(
        **{"sampling.cfg": {"field": "sampling.cfg", "policy": "replace", "value": 8.5}}
    )))
    child = result.child_recipe.model_dump(mode="json", exclude_none=True)

    for field in ("resources", "passes", "inputs", "controls", "detailers", "postprocess", "raw", "source"):
        assert child[field] == parent_snapshot[field]
    assert result.requirements.model_dump() == {
        "resolve_required": False,
        "build_required": True,
        "reason_codes": ["content_or_sampling_changed", "audited_workflow_invalidated"],
    }
    assert result.parent_recipe_sha256 == _sha(parent_snapshot)
    assert result.child_recipe_sha256 == _sha(child)
    assert result.parent_recipe_sha256 != result.child_recipe_sha256


def test_derivation_rejects_hash_directive_policy_and_value_violations() -> None:
    parent = _parent_recipe()
    valid = _directives()
    with pytest.raises(RecipeDerivationError, match="parent_recipe_hash_mismatch"):
        derive_generation_recipe(_request(parent, valid, parent_hash="0" * 64))

    violations = [
        _directives()[:-1],
        [*valid, {"field": "base_prompt", "policy": "preserve"}],
        [{**item, "field": "resources[0]"} if item["field"] == "base_prompt" else item for item in valid],
        [{**item, "policy": "unknown"} if item["field"] == "base_prompt" else item for item in valid],
        [{**item, "value": "not allowed"} if item["field"] == "base_prompt" else item for item in valid],
        [{**item, "policy": "randomize"} if item["field"] == "sampling.steps" else item for item in valid],
        [{**item, "policy": "replace"} if item["field"] == "sampling.steps" else item for item in valid],
        [{**item, "policy": "replace", "value": 0} if item["field"] == "sampling.steps" else item for item in valid],
    ]
    for directives in violations:
        with pytest.raises((ValidationError, RecipeDerivationError)):
            request = _request(parent, directives)
            derive_generation_recipe(request)

    request = _request(parent, _directives(**{
        "sampling.seed": {"field": "sampling.seed", "policy": "randomize"},
    }))
    with pytest.raises(RecipeDerivationError, match="random_seed_invalid"):
        derive_generation_recipe(request, random_seed=lambda: 2**63)

    assert parent == _parent_recipe()
