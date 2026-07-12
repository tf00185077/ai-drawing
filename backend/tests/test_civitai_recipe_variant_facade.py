"""CIV-V-F single-child facade: deterministic, offline orchestration tests."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

SHA = {letter: letter * 64 for letter in "abcdef"}


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parent_recipe() -> dict:
    return {
        "schema_version": "1.0", "source": {"provider": "civitai", "image_id": 1},
        "base_prompt": "parent", "negative_prompt": "negative",
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": SHA["a"]}],
        "sampling": {"seed": 1, "steps": 20, "cfg": 7, "sampler": "euler", "scheduler": "normal", "denoise": 1, "width": 512, "height": 512},
        "passes": [{"name": "base", "inherits_from": "recipe.sampling"}],
    }


def directives() -> list[dict]:
    return [
        {"field": "base_prompt", "policy": "preserve"}, {"field": "negative_prompt", "policy": "preserve"},
        {"field": "sampling.seed", "policy": "preserve"}, {"field": "sampling.steps", "policy": "preserve"},
        {"field": "sampling.cfg", "policy": "preserve"}, {"field": "sampling.sampler", "policy": "preserve"},
        {"field": "sampling.scheduler", "policy": "preserve"}, {"field": "sampling.denoise", "policy": "preserve"},
        {"field": "sampling.width", "policy": "preserve"}, {"field": "sampling.height", "policy": "preserve"},
    ]


def runtime_capabilities() -> dict:
    value = {
        "engine": "comfyui", "engine_version": "1.0",
        "node_types": ["CLIPTextEncode", "CheckpointLoaderSimple", "EmptyLatentImage", "KSampler", "SaveImage", "VAEDecode"],
        "sampler_names": ["euler"], "scheduler_names": ["normal"],
    }
    value["snapshot_sha256"] = canonical(value)
    return value


def runtime_provenance() -> dict:
    """A complete digest-bound runtime identity for the variant trust boundary."""
    from app.schemas.generation_recipe import RuntimeProvenance, canonical_runtime_lock_document

    capabilities = runtime_capabilities()
    value = {
        "engine": capabilities["engine"],
        "engine_version": capabilities["engine_version"],
        "reference": "runtime:one",
        "node_versions": {node_type: canonical({"node_type": node_type}) for node_type in capabilities["node_types"]},
        "package_versions": {"comfyui": canonical({"package": "comfyui", "version": "1.0"})},
        "runtime_settings": {"execution": "local"},
        "inspection_snapshot": {"snapshot_sha256": capabilities["snapshot_sha256"], "engine": capabilities["engine"], "engine_version": capabilities["engine_version"], "node_types": capabilities["node_types"]},
        "resource_locks": [],
    }
    runtime = RuntimeProvenance.model_validate(value)
    value["runtime_lock_sha256"] = canonical(canonical_runtime_lock_document(runtime))
    return value


def body() -> dict:
    from app.schemas.generation_recipe import GenerationRecipe
    recipe = parent_recipe()
    canonical_recipe = GenerationRecipe.model_validate(recipe).model_dump(mode="json", exclude_none=True)
    return {"parent_recipe": recipe, "parent_recipe_sha256": canonical(canonical_recipe), "directives": directives(), "model_family": "sdxl", "runtime_capabilities": runtime_capabilities(), "runtime_provenance": runtime_provenance(), "input_bindings": {}}


def test_frozen_request_rejects_every_downstream_artifact_before_orchestration() -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    forbidden = ["ledger", "resource_locks", "build", "workflow", "queue_params", "batch_size", "credentials", "job_id", "gallery_id", "variant_id", "child_recipe_sha256", "lineage"]
    for field in forbidden:
        candidate = body() | {field: {"authorization": "Bearer test-secret"}}
        with pytest.raises(ValidationError):
            CivitaiRecipeVariantGenerateRequest.model_validate(candidate)


@pytest.mark.parametrize("mutate", [
    lambda value: value["runtime_provenance"].pop("runtime_lock_sha256"),
    lambda value: value["runtime_provenance"].__setitem__("runtime_lock_sha256", "f" * 64),
    lambda value: value["runtime_provenance"]["node_versions"].pop("KSampler"),
    lambda value: value["runtime_provenance"].__setitem__("engine", "ComfyUI"),
    lambda value: value["runtime_capabilities"].__setitem__("snapshot_sha256", "e" * 64),
])
def test_request_rejects_unbound_or_incomplete_digest_runtime_before_orchestration(mutate) -> None:
    """AC1: no minimal runtime shell may reach derive/resolve/build/queue."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    candidate = body()
    mutate(candidate)
    with pytest.raises(ValidationError):
        CivitaiRecipeVariantGenerateRequest.model_validate(candidate)


def test_request_accepts_complete_digest_bound_runtime_identity() -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    assert CivitaiRecipeVariantGenerateRequest.model_validate(body()).runtime_provenance.runtime_lock_sha256


@pytest.mark.parametrize("mutate", [
    lambda value: value["runtime_provenance"]["node_versions"].__setitem__("KSampler", "not-a-digest"),
    lambda value: value["runtime_provenance"]["inspection_snapshot"].pop("snapshot_sha256"),
    lambda value: value["runtime_provenance"]["inspection_snapshot"].__setitem__("snapshot_sha256", "e" * 64),
    lambda value: value["runtime_provenance"]["inspection_snapshot"].__setitem__("engine", "other-engine"),
    lambda value: value["runtime_provenance"]["inspection_snapshot"].__setitem__("engine_version", "other-version"),
    lambda value: value["runtime_provenance"]["inspection_snapshot"].__setitem__("node_types", ["KSampler"]),
])
def test_request_rejects_noncanonical_or_unbound_runtime_node_identity(mutate) -> None:
    """AC1: every runtime identity field is bound before any orchestration phase."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest

    candidate = body()
    mutate(candidate)
    with pytest.raises(ValidationError):
        CivitaiRecipeVariantGenerateRequest.model_validate(candidate)


def test_http_validation_is_redacted_structured_and_never_enters_orchestration(monkeypatch) -> None:
    """The public facade must not let FastAPI echo rejected credentials in a 422."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import civitai_recipes

    touched: list[object] = []
    monkeypatch.setattr(civitai_recipes, "generate_one_variant", lambda *_args, **_kwargs: touched.append(True))
    app = FastAPI()
    app.include_router(civitai_recipes.router)
    response = TestClient(app).post(
        "/api/civitai-recipes/variants/generate-one",
        json=body() | {"credentials": {"authorization": "Bearer secret-sentinel", "password": "secret-sentinel"}},
    )

    encoded = response.text.lower()
    assert response.status_code == 422
    assert response.json()["detail"]["phase"] == "validation"
    assert response.json()["detail"]["code"] == "request_invalid"
    assert "secret-sentinel" not in encoded and "bearer secret" not in encoded
    assert touched == []


def test_lineage_schema_rejects_unknown_and_requires_all_immutable_fields() -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantLineage

    lineage = {
        "schema_version": "1.0", "variant_id": "variant", "job_id": "job",
        "parent_recipe_sha256": SHA["a"], "derived_recipe_sha256": SHA["b"], "built_child_recipe_sha256": SHA["c"],
        "applied_directives": [], "invalidated_evidence_sha256": SHA["d"],
        "strict_resolution_snapshot_sha256": SHA["e"], "compatibility_snapshot_sha256": SHA["f"],
        "workflow_sha256": SHA["a"], "resource_lock_sha256": SHA["b"], "lineage_sha256": SHA["c"],
    }
    assert CivitaiRecipeVariantLineage.model_validate(lineage).variant_id == "variant"
    with pytest.raises(ValidationError):
        CivitaiRecipeVariantLineage.model_validate(lineage | {"caller_lock": {}})


def test_orchestrates_all_preserve_freshly_in_fixed_order_and_submits_exactly_once(monkeypatch) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    events: list[str] = []
    request = CivitaiRecipeVariantGenerateRequest.model_validate(body())
    recipe = request.parent_recipe.model_dump(mode="json", exclude_none=True)
    report = {"strict": True, "ready": True, "entries": [{"index": 0, "status": "resolved", "matched_by": ["sha256"], "expected_identity": {"sha256": SHA["a"]}, "actual_identity": {"actual_sha256": SHA["a"], "model_family": "sdxl"}, "local_path": "/locked/base.safetensors", "diagnostics": {}, "hash_verified": True}], "resource_lock": [{"index": 0, "kind": "checkpoint", "sha256": SHA["a"], "local_path": "/locked/base.safetensors", "model_family": "sdxl"}]}
    workflow = {
        "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    built_recipe = deepcopy(recipe); built_recipe["runtime"] = request.runtime_provenance.model_dump(mode="json", exclude_none=True); built_recipe["workflow"] = {"reference": "civ-d:compiled-workflow", "snapshot": workflow, "snapshot_sha256": canonical(workflow)}

    class Snapshot:
        entries = []
        metadata = {"schema_version": "test", "snapshot": "fresh"}
    monkeypatch.setattr(variants, "derive_generation_recipe", lambda _request: (events.append("derive") or type("D", (), {"child_recipe": request.parent_recipe, "parent_recipe_sha256": request.parent_recipe_sha256, "child_recipe_sha256": canonical(recipe), "applied_directives": [], "invalidated_evidence": {}})()))
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: (events.append("resolve") or Snapshot()))
    monkeypatch.setattr(variants, "resolve_recipe", lambda *_args, **_kwargs: {"report": report})
    monkeypatch.setattr(variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: (events.append("compatibility") or {"compatible": True, "status": "compatible", "diagnostics": []}))
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: (events.append("build") or {"recipe": built_recipe, "workflow": workflow, "input_hashes": [], "resource_locks": report["resource_lock"], "reproduction_report": {"level": "workflow_ready_but_runtime_may_differ"}}))
    monkeypatch.setattr(variants, "build_recipe_provenance_bundle", lambda **kwargs: (events.append("provenance") or {"schema_version": "1.0", "recipe": kwargs["recipe"], "recipe_sha256": canonical(kwargs["recipe"]), "workflow": kwargs["workflow"], "workflow_sha256": canonical(kwargs["workflow"]), "input_hashes": [], "resource_locks": kwargs["resource_locks"], "runtime_provenance": kwargs["runtime_provenance"], "reproduction_level": kwargs["reproduction_level"]}))
    submissions: list[dict] = []
    monkeypatch.setattr(variants, "submit_audited_recipe", lambda params, *, job_id: (events.append("queue") or submissions.append(params) or job_id))

    result = variants.generate_one_variant(request, db=object(), variant_id_factory=lambda: "opaque-variant")

    assert events == ["derive", "resolve", "compatibility", "build", "provenance", "queue"]
    assert result.status == "queued" and result.variant_id == "opaque-variant" and result.job_id
    assert len(submissions) == 1 and set(submissions[0]) == {"workflow", "recipe_provenance"}
    assert submissions[0]["recipe_provenance"]["variant_lineage"]["variant_id"] == "opaque-variant"


@pytest.mark.parametrize("value", [None, True, 1.0, "1", 0, -1, 2])
def test_batch_gate_rejects_missing_or_non_one_semantics(value: object) -> None:
    from app.services.civitai_recipe_variants import VariantFacadeError, validate_single_child_batch

    workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": value}}}
    with pytest.raises(VariantFacadeError) as error:
        validate_single_child_batch(workflow)
    assert error.value.phase == "batch_validation"


def test_batch_gate_rejects_multiple_latent_or_image_outputs() -> None:
    from app.services.civitai_recipe_variants import VariantFacadeError, validate_single_child_batch

    for workflow in (
        {
            "1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}},
            "2": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}},
            "3": {"class_type": "SaveImage", "inputs": {}},
        },
        {
            "1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}},
            "2": {"class_type": "SaveImage", "inputs": {}},
            "3": {"class_type": "SaveImage", "inputs": {}},
        },
    ):
        with pytest.raises(VariantFacadeError) as error:
            validate_single_child_batch(workflow)
        assert error.value.phase == "batch_validation"


@pytest.mark.parametrize("phase", ["compatibility", "provenance_validation", "queue"])
def test_pre_submit_boundary_exceptions_are_redacted_and_never_return_partial_lineage(monkeypatch, phase: str) -> None:
    """Expected pre-submit exceptions get a stable phase without leaking diagnostics."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    request = CivitaiRecipeVariantGenerateRequest.model_validate(body())
    recipe = request.parent_recipe.model_dump(mode="json", exclude_none=True)
    report = {"strict": True, "ready": True, "entries": [], "resource_lock": []}
    monkeypatch.setattr(variants, "derive_generation_recipe", lambda _request: type("D", (), {"child_recipe": request.parent_recipe, "parent_recipe_sha256": request.parent_recipe_sha256, "child_recipe_sha256": canonical(recipe), "applied_directives": [], "invalidated_evidence": {}})())
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: type("Snapshot", (), {"entries": [], "metadata": {}})())
    monkeypatch.setattr(variants, "resolve_recipe", lambda *_args, **_kwargs: {"report": report})
    monkeypatch.setattr(variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: {"compatible": True, "status": "compatible", "diagnostics": []})
    workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "2": {"class_type": "SaveImage", "inputs": {}}}
    built = deepcopy(recipe); built["runtime"] = request.runtime_provenance.model_dump(mode="json", exclude_none=True); built["workflow"] = {"reference": "civ-d:compiled-workflow", "snapshot": workflow, "snapshot_sha256": canonical(workflow)}
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: {"recipe": built, "workflow": workflow, "input_hashes": [], "resource_locks": [], "reproduction_report": {"level": "workflow_ready_but_runtime_may_differ"}})
    monkeypatch.setattr(variants, "build_recipe_provenance_bundle", lambda **kwargs: {"recipe": kwargs["recipe"], "workflow": kwargs["workflow"], "workflow_sha256": canonical(kwargs["workflow"]), "resource_locks": [], "input_hashes": [], "runtime_provenance": kwargs["runtime_provenance"], "reproduction_level": kwargs["reproduction_level"]})
    submitted: list[object] = []
    monkeypatch.setattr(variants, "submit_audited_recipe", lambda *_args, **_kwargs: submitted.append(True))
    if phase == "compatibility":
        monkeypatch.setattr(variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Bearer secret-sentinel")))
    elif phase == "provenance_validation":
        monkeypatch.setattr(variants, "build_recipe_provenance_bundle", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("password=secret-sentinel")))
    else:
        monkeypatch.setattr(variants, "submit_audited_recipe", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("token=secret-sentinel")))

    with pytest.raises(variants.VariantFacadeError) as error:
        variants.generate_one_variant(request, db=object())
    assert error.value.phase == phase
    assert "secret-sentinel" not in error.value.message.lower()
    assert submitted == []


@pytest.mark.parametrize("bad_result", [object(), type("D", (), {})()])
def test_malformed_derivation_output_is_fail_closed_before_resolution(monkeypatch, bad_result: object) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    request = CivitaiRecipeVariantGenerateRequest.model_validate(body())
    touched: list[str] = []
    monkeypatch.setattr(variants, "derive_generation_recipe", lambda _request: bad_result)
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: touched.append("resolve"))
    monkeypatch.setattr(variants, "submit_audited_recipe", lambda *_args, **_kwargs: touched.append("queue"))

    with pytest.raises(variants.VariantFacadeError) as error:
        variants.generate_one_variant(request, db=object())
    assert error.value.detail() == {"phase": "provenance_validation", "code": "phase_output_invalid", "message": "variant generation rejected"}
    assert touched == []


def test_malformed_build_output_is_fail_closed_before_batch_or_queue(monkeypatch) -> None:
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    request = CivitaiRecipeVariantGenerateRequest.model_validate(body())
    recipe = request.parent_recipe.model_dump(mode="json", exclude_none=True)
    touched: list[str] = []
    monkeypatch.setattr(variants, "derive_generation_recipe", lambda _request: type("D", (), {"child_recipe": request.parent_recipe, "parent_recipe_sha256": request.parent_recipe_sha256, "child_recipe_sha256": canonical(recipe), "applied_directives": [], "invalidated_evidence": {}})())
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: type("Snapshot", (), {"entries": [], "metadata": {}})())
    monkeypatch.setattr(variants, "resolve_recipe", lambda *_args, **_kwargs: {"report": {"ready": True}})
    monkeypatch.setattr(variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: {"compatible": True, "status": "compatible", "diagnostics": []})
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(variants, "submit_audited_recipe", lambda *_args, **_kwargs: touched.append("queue"))

    with pytest.raises(variants.VariantFacadeError) as error:
        variants.generate_one_variant(request, db=object())
    assert error.value.phase == "provenance_validation" and error.value.code == "phase_output_invalid"
    assert touched == []


def _install_facade_harness(monkeypatch, request_body: dict | None = None):
    """Install complete deterministic phase doubles while retaining real provenance code."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    request = CivitaiRecipeVariantGenerateRequest.model_validate(request_body or body())
    recipe = request.parent_recipe.model_dump(mode="json", exclude_none=True)
    report = {
        "strict": True,
        "ready": True,
        "entries": [{
            "index": 0,
            "status": "resolved",
            "matched_by": ["sha256"],
            "expected_identity": {"sha256": SHA["a"]},
            "actual_identity": {"actual_sha256": SHA["a"], "model_family": "sdxl"},
            "local_path": "/locked/base.safetensors",
            "diagnostics": {},
            "hash_verified": True,
        }],
        "resource_lock": [{
            "index": 0,
            "kind": "checkpoint",
            "sha256": SHA["a"],
            "local_path": "/locked/base.safetensors",
            "model_family": "sdxl",
        }],
    }
    workflow = {
        "1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }
    built_recipe = deepcopy(recipe)
    built_recipe["runtime"] = request.runtime_provenance.model_dump(mode="json", exclude_none=True)
    built_recipe["workflow"] = {
        "reference": "civ-d:compiled-workflow",
        "snapshot": workflow,
        "snapshot_sha256": canonical(workflow),
    }
    snapshot = SimpleNamespace(entries=[], metadata={"schema_version": "test", "snapshot": "fresh"})
    derivation = SimpleNamespace(
        child_recipe=request.parent_recipe,
        parent_recipe_sha256=request.parent_recipe_sha256,
        child_recipe_sha256=canonical(recipe),
        applied_directives=[],
        invalidated_evidence={},
    )
    compatibility = {"compatible": True, "status": "compatible", "diagnostics": []}
    build = {
        "recipe": built_recipe,
        "workflow": workflow,
        "input_hashes": [],
        "resource_locks": report["resource_lock"],
        "reproduction_report": {"level": "workflow_ready_but_runtime_may_differ"},
    }
    events: list[str] = []
    submissions: list[dict] = []
    monkeypatch.setattr(variants, "derive_generation_recipe", lambda _request: (events.append("derive") or derivation))
    monkeypatch.setattr(variants, "local_identity_ledger", lambda _db: (events.append("resolve_local") or snapshot))
    monkeypatch.setattr(variants, "resolve_recipe", lambda *_args, **_kwargs: {"report": report})
    monkeypatch.setattr(
        variants,
        "preflight_recipe_compatibility",
        lambda *_args, **_kwargs: (events.append("compatibility") or compatibility),
    )
    monkeypatch.setattr(variants, "build_recipe", lambda *_args, **_kwargs: (events.append("build") or build))
    monkeypatch.setattr(
        variants,
        "submit_audited_recipe",
        lambda params, *, job_id: (events.append("single_submit") or submissions.append(params) or job_id),
    )
    return SimpleNamespace(
        variants=variants,
        request=request,
        recipe=recipe,
        report=report,
        workflow=workflow,
        built_recipe=built_recipe,
        snapshot=snapshot,
        derivation=derivation,
        compatibility=compatibility,
        build=build,
        events=events,
        submissions=submissions,
    )


def test_all_formal_lineage_digests_are_constructed_after_batch_inside_provenance_boundary(monkeypatch) -> None:
    """AC2 RED: no formal Parent/Child digest may be reused from the derive boundary."""
    harness = _install_facade_harness(monkeypatch)
    original_batch = harness.variants.validate_single_child_batch
    original_hash = harness.variants.canonical_sha256
    batch_complete = False
    digest_calls: list[object] = []

    def batch(workflow):
        nonlocal batch_complete
        original_batch(workflow)
        batch_complete = True

    def digest(value):
        assert batch_complete, "formal lineage digest escaped the provenance_validation boundary"
        digest_calls.append(value)
        return original_hash(value)

    monkeypatch.setattr(harness.variants, "validate_single_child_batch", batch)
    monkeypatch.setattr(harness.variants, "canonical_sha256", digest)

    result = harness.variants.generate_one_variant(
        harness.request,
        db=object(),
        variant_id_factory=lambda: "variant-one",
    )

    assert result.status == "queued"
    assert len(digest_calls) >= 9
    assert len(harness.submissions) == 1


@pytest.mark.parametrize(
    ("factory_name", "factory", "expected_code"),
    [
        ("variant_id_factory", lambda: (_ for _ in ()).throw(RuntimeError("Bearer variant-secret")), "variant_id_factory_failed"),
        ("job_id_factory", lambda: (_ for _ in ()).throw(RuntimeError("token=job-secret")), "job_id_factory_failed"),
        ("variant_id_factory", lambda: "   ", "variant_id_invalid"),
        ("job_id_factory", lambda: "bad job id", "job_id_invalid"),
    ],
)
def test_identity_factory_and_malformed_id_fail_closed_without_partial_lineage(
    monkeypatch, factory_name: str, factory, expected_code: str,
) -> None:
    """AC2 RED: both opaque identities are created and validated in provenance_validation."""
    harness = _install_facade_harness(monkeypatch)
    factories = {"variant_id_factory": lambda: "variant-one"}
    factories[factory_name] = factory

    with pytest.raises(harness.variants.VariantFacadeError) as raised:
        harness.variants.generate_one_variant(harness.request, db=object(), **factories)

    assert raised.value.detail() == {
        "phase": "provenance_validation",
        "code": expected_code,
        "message": "variant generation rejected",
    }
    assert harness.submissions == []
    assert "single_submit" not in harness.events


@pytest.mark.parametrize("phase", ["derive", "resolve_local", "compatibility", "build"])
def test_malformed_phase_outputs_share_stable_provenance_validation_failure(monkeypatch, phase: str) -> None:
    """AC2 RED: malformed collaborator output is not misreported as a phase policy decision."""
    harness = _install_facade_harness(monkeypatch)
    if phase == "derive":
        monkeypatch.setattr(harness.variants, "derive_generation_recipe", lambda _request: object())
    elif phase == "resolve_local":
        monkeypatch.setattr(harness.variants, "resolve_recipe", lambda *_args, **_kwargs: object())
    elif phase == "compatibility":
        monkeypatch.setattr(harness.variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: object())
    else:
        monkeypatch.setattr(harness.variants, "build_recipe", lambda *_args, **_kwargs: object())

    with pytest.raises(harness.variants.VariantFacadeError) as raised:
        harness.variants.generate_one_variant(
            harness.request,
            db=object(),
            variant_id_factory=lambda: "variant-one",
        )

    assert raised.value.detail() == {
        "phase": "provenance_validation",
        "code": "phase_output_invalid",
        "message": "variant generation rejected",
    }
    assert harness.submissions == []


@pytest.mark.parametrize(
    "binding",
    [
        "parent_recipe_sha256",
        "derived_recipe_sha256",
        "built_child_recipe_sha256",
        "workflow_sha256",
        "resource_lock_sha256",
        "strict_resolution_snapshot_sha256",
        "compatibility_snapshot_sha256",
        "invalidated_evidence_sha256",
        "lineage_sha256",
    ],
)
def test_each_canonical_binding_mutation_fails_before_queue_or_partial_lineage(monkeypatch, binding: str) -> None:
    """AC4 RED: strict validation independently binds all nine canonical documents."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantLineage

    harness = _install_facade_harness(monkeypatch)
    original_validate = CivitaiRecipeVariantLineage.model_validate

    def mutate(_cls, value):
        parsed = original_validate(value)
        payload = parsed.model_dump(mode="json")
        payload[binding] = "0" * 64
        if binding != "lineage_sha256":
            payload["lineage_sha256"] = canonical({
                key: item for key, item in payload.items() if key != "lineage_sha256"
            })
        return parsed.model_copy(update=payload)

    monkeypatch.setattr(CivitaiRecipeVariantLineage, "model_validate", classmethod(mutate))

    with pytest.raises(harness.variants.VariantFacadeError) as raised:
        harness.variants.generate_one_variant(
            harness.request,
            db=object(),
            variant_id_factory=lambda: "variant-one",
        )

    assert raised.value.phase == "provenance_validation"
    assert raised.value.code in {"lineage_binding_mismatch", "lineage_digest_mismatch"}
    assert harness.submissions == []


def test_schema_rejection_installs_every_orchestration_spy_and_touches_none(monkeypatch) -> None:
    """AC4: request rejection is proven ahead of every backend-owned phase."""
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
    from app.services import civitai_recipe_variants as variants

    touched: list[str] = []
    for name in (
        "derive_generation_recipe",
        "local_identity_ledger",
        "resolve_recipe",
        "preflight_recipe_compatibility",
        "build_recipe",
        "validate_single_child_batch",
        "build_recipe_provenance_bundle",
        "submit_audited_recipe",
    ):
        monkeypatch.setattr(variants, name, lambda *_args, _name=name, **_kwargs: touched.append(_name))

    for field in (
        "ledger", "resource_locks", "build", "workflow", "queue_params", "batch_size",
        "credentials", "job_id", "gallery_id", "variant_id", "child_recipe_sha256", "lineage", "unknown",
    ):
        with pytest.raises(ValidationError):
            CivitaiRecipeVariantGenerateRequest.model_validate(body() | {field: "Bearer forbidden-secret"})
    assert touched == []


def test_exact_phase_order_includes_batch_provenance_and_one_submit(monkeypatch) -> None:
    harness = _install_facade_harness(monkeypatch)
    original_batch = harness.variants.validate_single_child_batch
    original_provenance = harness.variants._build_validated_provenance

    def batch(workflow):
        harness.events.append("batch")
        return original_batch(workflow)

    def provenance(**kwargs):
        harness.events.append("provenance_lineage")
        return original_provenance(**kwargs)

    monkeypatch.setattr(harness.variants, "validate_single_child_batch", batch)
    monkeypatch.setattr(harness.variants, "_build_validated_provenance", provenance)
    harness.variants.generate_one_variant(
        harness.request,
        db=object(),
        variant_id_factory=lambda: "variant-one",
        job_id_factory=lambda: "job-one",
    )
    assert harness.events == [
        "derive", "resolve_local", "compatibility", "build", "batch",
        "provenance_lineage", "single_submit",
    ]
    assert len(harness.submissions) == 1


def test_all_preserve_stale_parent_evidence_cannot_bypass_fresh_resolve_compatibility_or_build(monkeypatch) -> None:
    from app.schemas.generation_recipe import GenerationRecipe

    candidate = body()
    stale_workflow = {"stale": {"class_type": "SaveImage", "inputs": {}}}
    candidate["parent_recipe"]["workflow"] = {
        "reference": "parent:stale-workflow",
        "snapshot": stale_workflow,
        "snapshot_sha256": canonical(stale_workflow),
    }
    candidate["parent_recipe"]["runtime"] = {
        "engine": "stale-engine", "engine_version": "0", "reference": "parent:stale-runtime",
    }
    canonical_parent = GenerationRecipe.model_validate(candidate["parent_recipe"]).model_dump(mode="json", exclude_none=True)
    candidate["parent_recipe_sha256"] = canonical(canonical_parent)
    harness = _install_facade_harness(monkeypatch, candidate)

    harness.variants.generate_one_variant(
        harness.request,
        db=object(),
        variant_id_factory=lambda: "variant-one",
        job_id_factory=lambda: "job-one",
    )
    assert harness.events == ["derive", "resolve_local", "compatibility", "build", "single_submit"]
    queued = harness.submissions[0]["recipe_provenance"]
    assert queued["workflow"] == harness.workflow
    assert queued["workflow"] != stale_workflow
    assert queued["runtime_provenance"] == runtime_provenance()


@pytest.mark.parametrize(
    ("failed_phase", "expected_phase", "expected_code", "expected_events"),
    [
        ("derive", "derive", "derive_failed", ["derive"]),
        ("resolve_local", "resolve_local", "local_resource_resolution_failed", ["derive", "resolve_local"]),
        ("compatibility", "compatibility", "compatibility_failed", ["derive", "resolve_local", "compatibility"]),
        ("build", "build", "build_failed", ["derive", "resolve_local", "compatibility", "build"]),
        ("batch", "batch_validation", "batch_size_not_one", ["derive", "resolve_local", "compatibility", "build", "batch"]),
        ("provenance_lineage", "provenance_validation", "canonicalization_failed", ["derive", "resolve_local", "compatibility", "build", "batch", "provenance_lineage"]),
        ("single_submit", "queue", "queue_full", ["derive", "resolve_local", "compatibility", "build", "batch", "provenance_lineage", "single_submit"]),
    ],
)
def test_every_phase_failure_short_circuits_all_later_phases(
    monkeypatch, failed_phase: str, expected_phase: str, expected_code: str, expected_events: list[str],
) -> None:
    from app.core.queue import QueueFullError
    from app.services.civitai_recipe_derivation import RecipeDerivationError

    harness = _install_facade_harness(monkeypatch)
    original_batch = harness.variants.validate_single_child_batch
    original_provenance = harness.variants._build_validated_provenance

    def batch(workflow):
        harness.events.append("batch")
        if failed_phase == "batch":
            workflow = deepcopy(workflow)
            workflow["1"]["inputs"]["batch_size"] = 2
        return original_batch(workflow)

    def provenance(**kwargs):
        harness.events.append("provenance_lineage")
        if failed_phase == "provenance_lineage":
            monkeypatch.setattr(harness.variants, "canonical_sha256", lambda _value: (_ for _ in ()).throw(ValueError("secret")))
        return original_provenance(**kwargs)

    monkeypatch.setattr(harness.variants, "validate_single_child_batch", batch)
    monkeypatch.setattr(harness.variants, "_build_validated_provenance", provenance)
    if failed_phase == "derive":
        monkeypatch.setattr(harness.variants, "derive_generation_recipe", lambda _request: (harness.events.append("derive") or (_ for _ in ()).throw(RecipeDerivationError("derive_failed"))))
    elif failed_phase == "resolve_local":
        monkeypatch.setattr(harness.variants, "local_identity_ledger", lambda _db: (harness.events.append("resolve_local") or (_ for _ in ()).throw(RuntimeError("secret"))))
    elif failed_phase == "compatibility":
        monkeypatch.setattr(harness.variants, "preflight_recipe_compatibility", lambda *_args, **_kwargs: (harness.events.append("compatibility") or (_ for _ in ()).throw(RuntimeError("secret"))))
    elif failed_phase == "build":
        monkeypatch.setattr(harness.variants, "build_recipe", lambda *_args, **_kwargs: (harness.events.append("build") or (_ for _ in ()).throw(RuntimeError("secret"))))
    elif failed_phase == "single_submit":
        monkeypatch.setattr(harness.variants, "submit_audited_recipe", lambda *_args, **_kwargs: (harness.events.append("single_submit") or (_ for _ in ()).throw(QueueFullError())))

    with pytest.raises(harness.variants.VariantFacadeError) as raised:
        harness.variants.generate_one_variant(
            harness.request,
            db=object(),
            variant_id_factory=lambda: "variant-one",
            job_id_factory=lambda: "job-one",
        )
    assert (raised.value.phase, raised.value.code) == (expected_phase, expected_code)
    assert harness.events == expected_events
    assert harness.submissions == []


@pytest.mark.parametrize(
    ("workflow", "expected_code"),
    [
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "2": {"class_type": "SaveImage", "inputs": {}}}, None),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_invalid"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": True}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_invalid"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1.0}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_invalid"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": "1"}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_invalid"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 0}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_not_one"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": -1}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_not_one"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 2}}, "2": {"class_type": "SaveImage", "inputs": {}}}, "batch_size_not_one"),
        ({"1": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "2": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}}, "3": {"class_type": "SaveImage", "inputs": {}}}, "batch_source_ambiguous"),
    ],
)
def test_complete_explicit_batch_matrix(workflow: dict, expected_code: str | None) -> None:
    from app.services.civitai_recipe_variants import VariantFacadeError, validate_single_child_batch

    if expected_code is None:
        validate_single_child_batch(workflow)
        return
    with pytest.raises(VariantFacadeError) as raised:
        validate_single_child_batch(workflow)
    assert raised.value.detail()["phase"] == "batch_validation"
    assert raised.value.code == expected_code


def test_batch_diagnostics_never_echo_untrusted_node_id_secret_sentinels() -> None:
    from app.services.civitai_recipe_variants import VariantFacadeError, validate_single_child_batch

    workflow = {
        "Bearer bearer-sentinel?token=token-query-sentinel&password=password-sentinel": {
            "class_type": "EmptyLatentImage", "inputs": {"batch_size": 2},
        },
        "2": {"class_type": "SaveImage", "inputs": {}},
    }
    with pytest.raises(VariantFacadeError) as raised:
        validate_single_child_batch(workflow)
    assert raised.value.detail() == {
        "phase": "batch_validation",
        "code": "batch_size_not_one",
        "message": "variant generation rejected",
    }


def test_submitted_lineage_independently_recomputes_all_nine_canonical_bindings(monkeypatch) -> None:
    from app.services.civitai_local_identity_ledger import ledger_payload

    harness = _install_facade_harness(monkeypatch)
    harness.variants.generate_one_variant(
        harness.request,
        db=object(),
        variant_id_factory=lambda: "variant-one",
        job_id_factory=lambda: "job-one",
    )
    bundle = harness.submissions[0]["recipe_provenance"]
    lineage = bundle["variant_lineage"]
    expected = {
        "parent_recipe_sha256": canonical(harness.recipe),
        "derived_recipe_sha256": canonical(harness.recipe),
        "built_child_recipe_sha256": canonical(bundle["recipe"]),
        "workflow_sha256": canonical(bundle["workflow"]),
        "resource_lock_sha256": canonical(bundle["resource_locks"]),
        "strict_resolution_snapshot_sha256": canonical({
            "ledger": ledger_payload(harness.snapshot), "report": harness.report,
        }),
        "compatibility_snapshot_sha256": canonical(harness.compatibility),
        "invalidated_evidence_sha256": canonical({}),
    }
    assert {key: lineage[key] for key in expected} == expected
    assert lineage["lineage_sha256"] == canonical({
        key: value for key, value in lineage.items() if key != "lineage_sha256"
    })


def test_identical_successes_have_distinct_immutable_identities_and_queue_full_preserves_first(monkeypatch) -> None:
    from app.core.queue import QueueFullError

    harness = _install_facade_harness(monkeypatch)
    variant_ids = iter(("variant-one", "variant-two", "variant-three"))
    job_ids = iter(("job-one", "job-two", "job-three"))
    first = harness.variants.generate_one_variant(
        harness.request, db=object(), variant_id_factory=lambda: next(variant_ids), job_id_factory=lambda: next(job_ids),
    )
    frozen_first = deepcopy(harness.submissions[0])
    second = harness.variants.generate_one_variant(
        harness.request, db=object(), variant_id_factory=lambda: next(variant_ids), job_id_factory=lambda: next(job_ids),
    )
    frozen_second = deepcopy(harness.submissions[1])
    assert (first.variant_id, first.job_id) != (second.variant_id, second.job_id)
    assert harness.submissions[0] == frozen_first
    assert harness.submissions[1] == frozen_second
    assert frozen_first["recipe_provenance"] is not frozen_second["recipe_provenance"]

    monkeypatch.setattr(
        harness.variants,
        "submit_audited_recipe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(QueueFullError()),
    )
    with pytest.raises(harness.variants.VariantFacadeError) as raised:
        harness.variants.generate_one_variant(
            harness.request, db=object(), variant_id_factory=lambda: next(variant_ids), job_id_factory=lambda: next(job_ids),
        )
    assert raised.value.detail()["code"] == "queue_full"
    assert len(harness.submissions) == 2
    assert harness.submissions[0] == frozen_first


@pytest.mark.parametrize(
    "sentinel_payload",
    [
        {"authorization": "authorization-sentinel"},
        {"value": "Bearer bearer-sentinel"},
        {"value": "https://example.invalid/?token=token-query-sentinel"},
        {"password": "password-sentinel"},
        {"secret": "secret-sentinel"},
    ],
)
def test_backend_validation_redacts_complete_secret_sentinel_matrix(monkeypatch, sentinel_payload: dict) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import civitai_recipes

    touched: list[object] = []
    monkeypatch.setattr(civitai_recipes, "generate_one_variant", lambda *_args, **_kwargs: touched.append(True))
    app = FastAPI()
    app.include_router(civitai_recipes.router)
    response = TestClient(app).post(
        "/api/civitai-recipes/variants/generate-one",
        json=body() | {"credentials": sentinel_payload},
    )
    encoded = response.text.lower()
    assert response.status_code == 422
    for sentinel in (
        "authorization-sentinel", "bearer-sentinel", "token-query-sentinel",
        "password-sentinel", "secret-sentinel",
    ):
        assert sentinel not in encoded
    assert touched == []


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    [
        ("variant_factory", "variant_id_factory_failed"),
        ("job_factory", "job_id_factory_failed"),
        ("canonicalization", "canonicalization_failed"),
        ("malformed_output", "phase_output_invalid"),
        ("malformed_provenance", "phase_output_invalid"),
        ("pydantic", "lineage_invalid"),
    ],
)
def test_every_provenance_fault_leaves_zero_queue_zero_gallery_and_no_partial_lineage(
    monkeypatch, fault: str, expected_code: str,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.database import Base
    from app.db.models import GeneratedImage
    from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantLineage

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    harness = _install_facade_harness(monkeypatch)
    variant_factory = lambda: "variant-one"
    job_factory = lambda: "job-one"
    if fault == "variant_factory":
        variant_factory = lambda: (_ for _ in ()).throw(RuntimeError("Bearer secret"))
    elif fault == "job_factory":
        job_factory = lambda: (_ for _ in ()).throw(RuntimeError("?token=secret"))
    elif fault == "canonicalization":
        monkeypatch.setattr(harness.variants, "canonical_sha256", lambda _value: (_ for _ in ()).throw(ValueError("password=secret")))
    elif fault == "malformed_output":
        monkeypatch.setattr(harness.variants, "build_recipe", lambda *_args, **_kwargs: object())
    elif fault == "malformed_provenance":
        monkeypatch.setattr(harness.variants, "build_recipe_provenance_bundle", lambda **_kwargs: object())
    else:
        original_validate = CivitaiRecipeVariantLineage.model_validate
        monkeypatch.setattr(
            CivitaiRecipeVariantLineage,
            "model_validate",
            classmethod(lambda _cls, _value: original_validate({})),
        )
    try:
        with pytest.raises(harness.variants.VariantFacadeError) as raised:
            harness.variants.generate_one_variant(
                harness.request,
                db=db,
                variant_id_factory=variant_factory,
                job_id_factory=job_factory,
            )
        assert raised.value.detail() == {
            "phase": "provenance_validation",
            "code": expected_code,
            "message": "variant generation rejected",
        }
        assert harness.submissions == []
        assert db.query(GeneratedImage).count() == 0
        assert set(raised.value.detail()) == {"phase", "code", "message"}
    finally:
        db.close()
