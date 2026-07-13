"""CIV-SA-U audited alias input integration for the single-variant facade."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parent_recipe(image_id: int = 123) -> dict:
    return {
        "schema_version": "1.0", "source": {"provider": "civitai", "image_id": image_id},
        "base_prompt": "parent", "negative_prompt": "negative",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": "a" * 64}],
        "sampling": {"seed": 1, "steps": 20, "cfg": 7, "sampler": "euler", "scheduler": "normal", "denoise": 1, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }


def directives() -> list[dict]:
    return [{"field": field, "policy": "preserve"} for field in (
        "base_prompt", "negative_prompt", "sampling.seed", "sampling.steps", "sampling.cfg",
        "sampling.sampler", "sampling.scheduler", "sampling.denoise", "sampling.width", "sampling.height",
    )]


def runtime_capabilities() -> dict:
    value = {"engine": "comfyui", "engine_version": "1.0", "node_types": ["EmptyLatentImage"], "sampler_names": ["euler"], "scheduler_names": ["normal"]}
    value["snapshot_sha256"] = canonical(value)
    return value


def runtime_provenance() -> dict:
    from app.schemas.generation_recipe import RuntimeProvenance, canonical_runtime_lock_document
    caps = runtime_capabilities()
    value = {
        "engine": caps["engine"], "engine_version": caps["engine_version"], "reference": "runtime:one",
        "node_versions": {"EmptyLatentImage": canonical({"node_type": "EmptyLatentImage"})},
        "inspection_snapshot": {"snapshot_sha256": caps["snapshot_sha256"], "engine": caps["engine"], "engine_version": caps["engine_version"], "node_types": caps["node_types"]},
    }
    value["runtime_lock_sha256"] = canonical(canonical_runtime_lock_document(RuntimeProvenance.model_validate(value)))
    return value


def direct_body() -> dict:
    from app.schemas.generation_recipe import GenerationRecipe
    recipe = parent_recipe()
    canonical_parent = GenerationRecipe.model_validate(recipe).model_dump(mode="json", exclude_none=True)
    return {"parent_recipe": recipe, "parent_recipe_sha256": canonical(canonical_parent), "directives": directives(), "model_family": "sdxl", "runtime_capabilities": runtime_capabilities(), "runtime_provenance": runtime_provenance(), "input_bindings": {}}


def alias_body(alias: str = "Sunset Hero", version: int | None = None) -> dict:
    result = direct_body()
    result.pop("parent_recipe")
    result.pop("parent_recipe_sha256")
    result["source_alias"] = {"alias": alias}
    if version is not None:
        result["source_alias"]["registry_version"] = version
    return result


def binding(recipe: dict, *, requested_alias: str = "Sunset Hero", version: int = 1) -> dict:
    return {
        "requested_alias": requested_alias,
        "matched_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "primary"},
        "registry_version": version,
        "source_identity": {"provider": "civitai", "image_id": recipe["source"]["image_id"]},
        "acquisition_evidence_sha256": "b" * 64,
        "parent_recipe_sha256": canonical(recipe),
        "registry_created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


def _install_success_harness(monkeypatch, *, materialized_recipe: dict | None = None):
    from app.schemas.generation_recipe import GenerationRecipe
    from app.services import civitai_recipe_variants as variants
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasMaterializedParent

    parent = GenerationRecipe.model_validate(materialized_recipe or parent_recipe())
    parent_payload = parent.model_dump(mode="json", exclude_none=True)
    parent_sha = canonical(parent_payload)
    alias_binding = binding(parent_payload)
    events: list[str] = []
    submissions: list[dict] = []
    materializer_calls: list[object] = []
    materialized_output_parents: list[object] = []
    report = {"ready": True, "resource_lock": []}
    workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "2": {"class_type": "SaveImage", "inputs": {}}}

    def materialize(selector, *, db):
        events.append("materialize")
        materializer_calls.append(selector)
        result = CivitaiSourceAliasMaterializedParent.model_validate({"status": "success", "code": "materialized", "parent_recipe": parent_payload, "parent_recipe_sha256": parent_sha, "alias_binding": alias_binding})
        materialized_output_parents.append(result.parent_recipe)
        return result
    monkeypatch.setattr(variants, "materialize_source_alias_parent", materialize)
    derived_parents: list[object] = []
    def derive(request):
        events.append("derive")
        derived_parents.append(request.parent_recipe)
        return SimpleNamespace(child_recipe=request.parent_recipe, parent_recipe_sha256=request.parent_recipe_sha256, child_recipe_sha256=parent_sha, applied_directives=[], invalidated_evidence={})
    monkeypatch.setattr(variants, "derive_generation_recipe", derive)
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: (events.append("resolve_local"), SimpleNamespace(entries=[], metadata={}))[1])
    monkeypatch.setattr(variants, "resolve_recipe", lambda *_args, **_kwargs: {"report": report})
    monkeypatch.setattr(variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: (events.append("compatibility"), {"compatible": True, "status": "compatible"})[1])
    built_recipe = deepcopy(parent_payload)
    built_recipe["runtime"] = runtime_provenance()
    built_recipe["workflow"] = {"reference": "compiled", "snapshot": workflow, "snapshot_sha256": canonical(workflow)}
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: (events.append("build"), {"recipe": built_recipe, "workflow": workflow, "input_hashes": [], "resource_locks": [], "reproduction_report": {"level": "workflow_ready_but_runtime_may_differ"}})[1])
    monkeypatch.setattr(variants, "build_recipe_provenance_bundle", lambda **kwargs: (events.append("provenance"), {"recipe": kwargs["recipe"], "recipe_sha256": canonical(kwargs["recipe"]), "workflow": kwargs["workflow"], "workflow_sha256": canonical(kwargs["workflow"]), "input_hashes": [], "resource_locks": [], "runtime_provenance": kwargs["runtime_provenance"], "reproduction_level": kwargs["reproduction_level"]})[1])
    monkeypatch.setattr(variants, "submit_audited_recipe", lambda params, *, job_id: (events.append("single_submit"), submissions.append(params), job_id)[2])
    return variants, events, submissions, materializer_calls, materialized_output_parents, parent, parent_payload, alias_binding, derived_parents


def test_single_variant_request_accepts_exactly_one_parent_source() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import civitai_recipes
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    schema = CivitaiRecipeVariantGenerateRequest.model_json_schema()
    branches = schema["allOf"][-1]["oneOf"]
    assert {tuple(branch.get("required", [])) for branch in branches} == {
        ("parent_recipe", "parent_recipe_sha256"), ("source_alias",),
    }
    assert branches[0]["not"] == {"required": ["source_alias"]}
    assert branches[1]["not"] == {"anyOf": [{"required": ["parent_recipe"]}, {"required": ["parent_recipe_sha256"]}]}
    assert schema["additionalProperties"] is False

    assert CivitaiRecipeVariantGenerateRequest.model_validate(direct_body()).parent_recipe is not None
    assert CivitaiRecipeVariantGenerateRequest.model_validate(alias_body()).source_alias.alias == "Sunset Hero"
    invalid = [
        {key: value for key, value in direct_body().items() if key != "parent_recipe"},
        {key: value for key, value in direct_body().items() if key != "parent_recipe_sha256"},
        direct_body() | {"source_alias": {"alias": "Sunset Hero"}},
        {key: value for key, value in direct_body().items() if key not in {"parent_recipe", "parent_recipe_sha256"}},
        alias_body(" "), alias_body("x" * 513),
        *[alias_body() | {"source_alias": {"alias": "x", "registry_version": value}} for value in (True, "1", 1.0, 0, -1)],
    ]
    for key in ("alias_binding", "registry_record", "source_identity", "evidence", "candidate", "search_score", "lineage", "build", "queue", "gallery"):
        invalid.append(alias_body() | {key: {"secret": "must-not-reach-orchestration"}})
    for value in invalid:
        with pytest.raises(ValidationError):
            CivitaiRecipeVariantGenerateRequest.model_validate(value)

    touched: list[object] = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(civitai_recipes, "generate_one_variant", lambda *_args, **_kwargs: touched.append(True))
    try:
        app = FastAPI()
        app.include_router(civitai_recipes.router)
        openapi_schema = app.openapi()["components"]["schemas"]["CivitaiRecipeVariantGenerateRequest"]
        assert openapi_schema["allOf"][-1]["oneOf"] == branches
        for invalid_body in invalid[:4]:
            response = TestClient(app).post("/api/civitai-recipes/variants/generate-one", json=invalid_body)
            assert response.status_code == 422
            assert response.json()["detail"]["phase"] == "validation"
            assert response.json()["detail"]["code"] == "request_invalid"
            assert "must-not-reach-orchestration" not in response.text
        assert touched == []
    finally:
        monkeypatch.undo()


def test_single_variant_alias_materializes_before_derivation_and_submits_once(monkeypatch) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    variants, events, submissions, calls, materialized_output_parents, _parent, parent, alias_binding, derived_parents = _install_success_harness(monkeypatch)
    for version in (None, 1):
        request = CivitaiRecipeVariantGenerateRequest.model_validate(alias_body(version=version))
        result = variants.generate_one_variant(request, db=object(), variant_id_factory=lambda: f"variant-{version}", job_id_factory=lambda: f"job-{version}")
        assert result.status == "queued"
    assert events == [
        "materialize", "derive", "resolve_local", "compatibility", "build", "provenance", "single_submit",
        "materialize", "derive", "resolve_local", "compatibility", "build", "provenance", "single_submit",
    ]
    assert len(calls) == len(submissions) == 2
    assert calls[0].model_dump(mode="json", exclude_none=True) == {"alias": "Sunset Hero"}
    assert calls[1].model_dump(mode="json", exclude_none=True) == {"alias": "Sunset Hero", "registry_version": 1}
    assert derived_parents == materialized_output_parents
    assert all(derived is materialized for derived, materialized in zip(derived_parents, materialized_output_parents, strict=True))
    lineage = submissions[0]["recipe_provenance"]["variant_lineage"]
    assert lineage["schema_version"] == "1.1"
    assert lineage["parent_recipe_sha256"] == alias_binding["parent_recipe_sha256"] == canonical(parent)


def test_single_variant_alias_binding_roundtrips_through_queue_gallery_and_export_validation(monkeypatch, tmp_path) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services.civitai_recipe_gallery import _validate_variant_lineage

    variants, _events, submissions, _calls, _materialized_output_parents, _materialized_parent, parent, alias_binding, _derived_parents = _install_success_harness(monkeypatch)
    variants.generate_one_variant(CivitaiRecipeVariantGenerateRequest.model_validate(alias_body(version=1)), db=object(), variant_id_factory=lambda: "variant", job_id_factory=lambda: "job")
    bundle = submissions[0]["recipe_provenance"]
    lineage = _validate_variant_lineage(bundle, bundle["variant_lineage"], job_id="job")
    assert lineage["source_alias_binding"] == {**alias_binding, "registry_created_at": "2026-01-01T00:00:00Z"}
    for field, value in (("requested_alias", "tampered"), ("registry_version", 2), ("source_identity", {"provider": "civitai", "image_id": 999}), ("acquisition_evidence_sha256", "f" * 64), ("parent_recipe_sha256", "e" * 64), ("registry_created_at", "2027-01-01T00:00:00Z")):
        broken = deepcopy(bundle["variant_lineage"])
        broken["source_alias_binding"][field] = value
        with pytest.raises(Exception):
            _validate_variant_lineage(bundle, broken, job_id="job")


def test_single_variant_alias_failure_matrix_has_zero_child_side_effects_and_preserves_legacy_parent_path(monkeypatch) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasMaterializedParent

    variants, events, submissions, _calls, _materialized_output_parents, _materialized_parent, _parent, _binding, _derived_parents = _install_success_harness(monkeypatch)
    for status, code in (("rejected", "invalid_selector"), ("missing", "not_found"), ("corrupt", "non_unique_alias"), ("archived", "target_archived"), ("repointed", "explicit_registry_version_required")):
        monkeypatch.setattr(variants, "materialize_source_alias_parent", lambda *_args, _status=status, _code=code, **_kwargs: CivitaiSourceAliasMaterializedParent(status=_status, code=_code))
        with pytest.raises(variants.VariantFacadeError) as raised:
            variants.generate_one_variant(CivitaiRecipeVariantGenerateRequest.model_validate(alias_body()), db=object())
        assert raised.value.detail() == {"phase": "source_alias_materialization", "code": code, "message": "variant generation rejected"}
        assert events == [] and submissions == []
    malformed = (
        CivitaiSourceAliasMaterializedParent.model_construct(),
        CivitaiSourceAliasMaterializedParent.model_construct(status={"bad": "status"}, code="invalid_selector"),
        CivitaiSourceAliasMaterializedParent.model_construct(status="success", code="materialized", parent_recipe={}),
        CivitaiSourceAliasMaterializedParent.model_construct(status="success", code="materialized", parent_recipe_sha256="a" * 64, alias_binding={}),
        CivitaiSourceAliasMaterializedParent.model_construct(status="missing", code={"untrusted": "code"}),
        CivitaiSourceAliasMaterializedParent.model_construct(status="rejected", code="invalid_selector", parent_recipe={}),
    )
    for result in malformed:
        monkeypatch.setattr(variants, "materialize_source_alias_parent", lambda *_args, _result=result, **_kwargs: _result)
        with pytest.raises(variants.VariantFacadeError) as raised:
            variants.generate_one_variant(CivitaiRecipeVariantGenerateRequest.model_validate(alias_body()), db=object())
        assert raised.value.detail() == {"phase": "source_alias_materialization", "code": "materialization_invalid", "message": "variant generation rejected"}
        assert events == [] and submissions == []
    variants.generate_one_variant(CivitaiRecipeVariantGenerateRequest.model_validate(direct_body()), db=object(), variant_id_factory=lambda: "variant", job_id_factory=lambda: "job")
    assert events == ["derive", "resolve_local", "compatibility", "build", "provenance", "single_submit"]


def test_lineage_v10_rejects_explicit_null_alias_binding() -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantLineage

    hashes = {
        "parent_recipe_sha256": "a" * 64,
        "derived_recipe_sha256": "b" * 64,
        "built_child_recipe_sha256": "c" * 64,
        "invalidated_evidence_sha256": "d" * 64,
        "strict_resolution_snapshot_sha256": "e" * 64,
        "compatibility_snapshot_sha256": "f" * 64,
        "workflow_sha256": "0" * 64,
        "resource_lock_sha256": "1" * 64,
    }
    v10 = {
        "schema_version": "1.0", "variant_id": "variant", "job_id": "job",
        **hashes, "applied_directives": [],
    }
    v10["lineage_sha256"] = canonical(v10)
    parsed = CivitaiRecipeVariantLineage.model_validate(v10)
    assert parsed.model_dump(mode="json", exclude_none=True) == v10
    assert "source_alias_binding" not in parsed.model_dump(mode="json", exclude_none=True)

    with pytest.raises(ValidationError):
        CivitaiRecipeVariantLineage.model_validate(v10 | {"source_alias_binding": None})
    with pytest.raises(ValidationError):
        CivitaiRecipeVariantLineage.model_validate({**v10, "schema_version": "1.1", "source_alias_binding": None})


def test_alias_binding_rejects_built_recipe_source_substitution_before_submit(monkeypatch) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    variants, events, submissions, _calls, _materialized_output_parents, _materialized_parent, parent, _binding, _derived_parents = _install_success_harness(monkeypatch)
    workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "2": {"class_type": "SaveImage", "inputs": {}}}
    substituted = deepcopy(parent)
    substituted["source"] = {"provider": "civitai", "image_id": 999}
    substituted["runtime"] = runtime_provenance()
    substituted["workflow"] = {"reference": "compiled", "snapshot": workflow, "snapshot_sha256": canonical(workflow)}
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: (
        events.append("build"),
        {"recipe": substituted, "workflow": workflow, "input_hashes": [], "resource_locks": [], "reproduction_report": {"level": "workflow_ready_but_runtime_may_differ"}},
    )[1])

    with pytest.raises(variants.VariantFacadeError) as raised:
        variants.generate_one_variant(
            CivitaiRecipeVariantGenerateRequest.model_validate(alias_body(version=1)),
            db=object(), variant_id_factory=lambda: "variant", job_id_factory=lambda: "job",
        )

    assert raised.value.detail() == {
        "phase": "provenance_validation", "code": "source_alias_binding_mismatch", "message": "variant generation rejected",
    }
    assert events == ["materialize", "derive", "resolve_local", "compatibility", "build", "provenance"]
    assert submissions == []
