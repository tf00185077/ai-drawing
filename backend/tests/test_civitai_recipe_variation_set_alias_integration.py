"""CIV-SA-W audited source-alias integration for durable variation sets."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


_helpers = run_path(str(Path(__file__).with_name("test_civitai_recipe_variant_alias_integration.py")))
direct_body = _helpers["direct_body"]
alias_body = _helpers["alias_body"]
parent_recipe = _helpers["parent_recipe"]
binding = _helpers["binding"]
variant_directives = _helpers["directives"]


def set_body(*, alias: bool = False, version: int | None = None, children: int = 2) -> dict:
    source = alias_body(version=version) if alias else direct_body()
    source.pop("directives")
    source["children"] = [
        {"client_child_key": f"child-{ordinal}", "directives": variant_directives()}
        for ordinal in range(children)
    ]
    return source


def _materialized(parent: dict | None = None, *, requested_alias: str = "Sunset Hero", version: int = 1):
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasMaterializedParent
    from app.schemas.generation_recipe import GenerationRecipe
    from app.services.civitai_recipe_gallery import canonical_sha256

    recipe = GenerationRecipe.model_validate(parent or parent_recipe())
    payload = recipe.model_dump(mode="json", exclude_none=True)
    sha = canonical_sha256(payload)
    return CivitaiSourceAliasMaterializedParent.model_validate({
        "status": "success", "code": "materialized", "parent_recipe": payload,
        "parent_recipe_sha256": sha,
        "alias_binding": binding(payload, requested_alias=requested_alias, version=version),
    })


def test_variation_set_request_accepts_exactly_one_parent_source() -> None:
    """CIV-SA-W-AC1: strict schema/HTTP has one common parent source and no caller binding."""
    from app.api import civitai_recipes
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest

    schema = CivitaiRecipeVariationSetCreateRequest.model_json_schema()
    branches = schema["allOf"][-1]["oneOf"]
    assert {tuple(branch.get("required", [])) for branch in branches} == {
        ("parent_recipe", "parent_recipe_sha256"), ("source_alias",),
    }
    assert schema["additionalProperties"] is False
    assert CivitaiRecipeVariationSetCreateRequest.model_validate(set_body()).parent_recipe is not None
    assert CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True)).source_alias.alias == "Sunset Hero"

    neither = set_body(); neither.pop("parent_recipe"); neither.pop("parent_recipe_sha256")
    partial_recipe = set_body(); partial_recipe.pop("parent_recipe")
    partial_sha = set_body(); partial_sha.pop("parent_recipe_sha256")
    invalid = [
        neither, partial_recipe, partial_sha, set_body() | {"source_alias": {"alias": "Sunset Hero"}},
        set_body(alias=True, version=None) | {"source_alias": {"alias": " "}},
        set_body(alias=True) | {"source_alias": {"alias": "x" * 513}},
        *[set_body(alias=True) | {"source_alias": {"alias": "x", "registry_version": value}}
          for value in (True, "1", 1.0, 0, -1)],
    ]
    for key in ("alias_binding", "registry_record", "source_identity", "evidence", "candidate", "search", "lineage", "variation_set_id", "member", "build", "queue", "gallery"):
        invalid.append(set_body(alias=True) | {key: {"secret": "must-not-reach-service"}})
    for value in invalid:
        with pytest.raises(ValidationError):
            CivitaiRecipeVariationSetCreateRequest.model_validate(value)

    app = FastAPI(); app.include_router(civitai_recipes.router)
    for value in invalid[:4]:
        response = TestClient(app).post("/api/civitai-recipes/variation-sets", json=value)
        assert response.status_code == 422
        assert response.json()["detail"]["phase"] == "validation"
        assert response.json()["detail"]["code"] == "request_invalid"
        assert "must-not-reach-service" not in response.text


def test_variation_set_alias_materializes_once_before_persistence_and_submits_ordered_children(monkeypatch) -> None:
    """CIV-SA-W-AC2: one immutable materialization feeds every trusted child in ordinal order."""
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
    from app.services import civitai_recipe_variation_sets as sets

    request = CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True, children=3))
    output = _materialized()
    calls: list[object] = []
    trusted: list[tuple[object, str, object, str]] = []
    monkeypatch.setattr(sets, "materialize_source_alias_parent", lambda selector, *, db: (calls.append(selector), output)[1])

    def submit(child, *, parent_recipe, parent_recipe_sha256, source_alias_binding, db):
        trusted.append((parent_recipe, parent_recipe_sha256, source_alias_binding, child.directives[0].field))
        ordinal = len(trusted) - 1
        return {"variant_id": f"variant-{ordinal}", "job_id": f"job-{ordinal}",
                "parent_recipe_sha256": parent_recipe_sha256,
                "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64,
                "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64}
    monkeypatch.setattr(sets, "generate_one_variant_from_materialized_parent", submit)

    store = sets.InMemoryVariationSetStore()
    result = sets.create_variation_set(request, db=store, variation_set_id_factory=lambda: "alias-set")
    assert len(calls) == 1 and calls[0] is request.source_alias
    assert [item["outcome"] for item in result["members"]] == ["submitted", "submitted", "submitted"]
    assert [item[3] for item in trusted] == ["base_prompt", "base_prompt", "base_prompt"]
    assert all(item[0] is output.parent_recipe for item in trusted)
    assert all(item[1] == output.parent_recipe_sha256 for item in trusted)
    assert all(item[2] == output.alias_binding for item in trusted)
    assert [member["ordinal"] for member in store.sets["alias-set"]["members"]] == [0, 1, 2]
    # The same one-shot boundary receives both current and historical explicit selectors;
    # service code must not resolve either form itself.
    for version in (1, 2):
        explicit = CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True, version=version, children=1))
        explicit_output = _materialized(version=version)
        before = len(calls)
        monkeypatch.setattr(sets, "materialize_source_alias_parent", lambda selector, *, db, _result=explicit_output: (calls.append(selector), _result)[1])
        sets.create_variation_set(explicit, db=sets.InMemoryVariationSetStore(), variation_set_id_factory=lambda _version=version: f"alias-explicit-{_version}")
        assert len(calls) == before + 1
        assert calls[-1].model_dump(mode="json") == {"alias": "Sunset Hero", "registry_version": version}



def test_variation_set_alias_binding_is_identical_in_every_member_lineage_status_and_export(monkeypatch) -> None:
    """CIV-SA-W-AC3: durable binding agrees with every v1.1 Gallery lineage or export closes."""
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
    from app.services import civitai_recipe_variation_sets as sets
    from app.services.civitai_recipe_gallery import canonical_sha256

    request = CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True, children=2, version=1))
    output = _materialized()
    durable_binding = output.alias_binding.model_dump(mode="json")
    monkeypatch.setattr(sets, "materialize_source_alias_parent", lambda *_args, **_kwargs: output)
    def submit(_child, *, parent_recipe, parent_recipe_sha256, source_alias_binding, db):
        # The set/member records must already bind the shared Parent before any Child call.
        assert all(member["parent_recipe_sha256"] == parent_recipe_sha256 for member in db.sets["set-binding"]["members"])
        assert all(member["source_alias_binding"] == source_alias_binding.model_dump(mode="json") for member in db.sets["set-binding"]["members"])
        ordinal = len([member for member in db.sets.get("set-binding", {}).get("members", []) if member.get("job_id")])
        return {"variant_id": f"variant-{ordinal}", "job_id": f"job-{ordinal}",
                "parent_recipe_sha256": parent_recipe_sha256,
                "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64,
                "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64}
    monkeypatch.setattr(sets, "generate_one_variant_from_materialized_parent", submit)
    store = sets.InMemoryVariationSetStore()
    sets.create_variation_set(request, db=store, variation_set_id_factory=lambda: "set-binding")
    # Parent SHA and binding are durable before a child has completed; no response may
    # backfill this identity later.
    durable_members = store.sets["set-binding"]["members"]
    assert all(member["parent_recipe_sha256"] == output.parent_recipe_sha256 for member in durable_members)
    assert all(member["source_alias_binding"] == durable_binding for member in durable_members)
    def gallery(job_id: str):
        lineage = {"schema_version": "1.1", "job_id": job_id, "parent_recipe_sha256": output.parent_recipe_sha256,
                   "source_alias_binding": deepcopy(durable_binding)}
        lineage["lineage_sha256"] = canonical_sha256(lineage)
        return {"variant_lineage": lineage}
    status = sets.get_variation_set("set-binding", db=store, queue_status=lambda _job: {"status": "queued"})
    assert all(member["source_alias_binding"] == durable_binding for member in status["members"])
    assert all(member["parent_recipe_sha256"] == output.parent_recipe_sha256 for member in status["members"])
    document = sets.export_variation_set("set-binding", db=store, queue_status=lambda _job: {"status": "queued"}, gallery_export=gallery)
    assert all(member["source_alias_binding"] == durable_binding for member in document["members"])
    assert sets.verify_variation_set_export(document) is True
    for mutation in (
        lambda member: member.pop("parent_recipe_sha256"),
        lambda member: member.update(parent_recipe_sha256="f" * 64),
        lambda member: member["source_alias_binding"].update(registry_version=99),
    ):
        broken_store = deepcopy(store)
        mutation(broken_store.sets["set-binding"]["members"][0])
        with pytest.raises(sets.VariationSetError) as broken:
            sets.export_variation_set("set-binding", db=broken_store, queue_status=lambda _job: {"status": "queued"}, gallery_export=gallery)
        assert broken.value.detail() == {"phase": "provenance_validation", "code": "provenance_validation", "message": "variation set operation rejected"}

    # Gallery v1.1 lineage is also authoritative evidence that this was an alias
    # member. Removing only the durable binding must not downgrade it to v1.0.
    missing_binding_store = deepcopy(store)
    missing_binding_store.sets["set-binding"]["members"][0].pop("source_alias_binding")
    with pytest.raises(sets.VariationSetError) as missing_binding:
        sets.export_variation_set(
            "set-binding",
            db=missing_binding_store,
            queue_status=lambda _job: {"status": "completed"},
            gallery_export=gallery,
        )
    assert missing_binding.value.detail() == {
        "phase": "provenance_validation",
        "code": "provenance_validation",
        "message": "variation set operation rejected",
    }

    with pytest.raises(sets.VariationSetError) as broken:
        sets.export_variation_set("set-binding", db=store, queue_status=lambda _job: {"status": "queued"}, gallery_export=lambda job: gallery(job) | {"variant_lineage": {**gallery(job)["variant_lineage"], "source_alias_binding": {**durable_binding, "registry_version": 99}}})
    assert broken.value.detail()["phase"] == "provenance_validation"


def test_variation_set_alias_failure_matrix_has_zero_set_or_generation_side_effects_and_preserves_direct_parent_path(monkeypatch) -> None:
    """CIV-SA-W-AC4: materialization failures are pre-ID/pre-persistence; direct remains v1.0."""
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
    from app.schemas.civitai_source_aliases import CivitaiSourceAliasMaterializedParent
    from app.services import civitai_recipe_variation_sets as sets

    store = sets.InMemoryVariationSetStore(); materialize_calls: list[object] = []; child_calls: list[object] = []; factories: list[object] = []
    monkeypatch.setattr(sets, "generate_one_variant_from_materialized_parent", lambda *_args, **_kwargs: child_calls.append(True))
    failure_cases = (
        ("rejected", "invalid_selector"), ("missing", "not_found"),
        ("corrupt", "non_unique_alias"), ("archived", "target_archived"),
        ("repointed", "explicit_registry_version_required"),
        ("missing", "registry_version_not_found"), ("corrupt", "registry_version_mismatch"),
    )
    for status, code in failure_cases:
        before = deepcopy(store.sets)
        monkeypatch.setattr(sets, "materialize_source_alias_parent", lambda *_args, _status=status, _code=code, **_kwargs: (materialize_calls.append(_code), CivitaiSourceAliasMaterializedParent(status=_status, code=_code))[1])
        with pytest.raises(sets.VariationSetError) as raised:
            sets.create_variation_set(CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True, version=1 if "version" in code else None)), db=store, variation_set_id_factory=lambda: factories.append(True))
        assert raised.value.detail() == {"phase": "source_alias_materialization", "code": code, "message": "variation set operation rejected"}
        assert store.sets == before
    malformed = (
        SimpleNamespace(),
        CivitaiSourceAliasMaterializedParent.model_construct(status="success", code="materialized", parent_recipe={}),
        CivitaiSourceAliasMaterializedParent.model_construct(status="success", code="materialized", parent_recipe_sha256="a" * 64, alias_binding={}),
        CivitaiSourceAliasMaterializedParent.model_construct(status="missing", code="not_found", parent_recipe={}),
    )
    for result in malformed:
        before = deepcopy(store.sets)
        monkeypatch.setattr(sets, "materialize_source_alias_parent", lambda *_args, _result=result, **_kwargs: _result)
        with pytest.raises(sets.VariationSetError) as raised:
            sets.create_variation_set(CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=True)), db=store, variation_set_id_factory=lambda: factories.append(True))
        assert raised.value.detail() == {"phase": "source_alias_materialization", "code": "materialization_invalid", "message": "variation set operation rejected"}
        assert store.sets == before
    assert len(materialize_calls) == len(failure_cases) and child_calls == [] and factories == [] and store.sets == {}

    direct = CivitaiRecipeVariationSetCreateRequest.model_validate(set_body(alias=False, children=1))
    monkeypatch.setattr(sets, "generate_one_variant", lambda *_args, **_kwargs: {"variant_id": "v", "job_id": "j", "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64, "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64})
    result = sets.create_variation_set(direct, db=store, variation_set_id_factory=lambda: "direct-set")
    assert result["variation_set_id"] == "direct-set"
    assert "source_alias_binding" not in store.sets["direct-set"]["members"][0]
