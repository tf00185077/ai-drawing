"""CIV-V-G durable variation-set lifecycle: deterministic/offline contract tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from runpy import run_path

import pytest


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def variant_body() -> dict:
    return run_path(str(Path(__file__).with_name("test_civitai_recipe_variant_facade.py")))["body"]()


def variant_directives() -> list[dict]:
    return run_path(str(Path(__file__).with_name("test_civitai_recipe_variant_facade.py")))["directives"]()


def test_existing_build_http_route_remains_registered() -> None:
    """CIV-V-G-AC7: variation-set route insertion must not remove the existing build API."""
    from app.main import app

    routes = {(method, getattr(route, "path", None)) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("POST", "/api/civitai-recipes/build") in routes


def test_create_1_to_8_ordered_members_and_reject_duplicate_or_executable_fields_without_side_effects() -> None:
    """CIV-V-G-AC1: facade owns identity and delegates one child at a time."""
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest

    base = variant_body()
    base.pop("directives")
    request = CivitaiRecipeVariationSetCreateRequest.model_validate(base | {"children": [
        {"client_child_key": "first", "directives": variant_directives()}, {"client_child_key": "second", "directives": variant_directives()},
    ]})
    assert [child.client_child_key for child in request.children] == ["first", "second"]
    for bad in (
        base | {"children": [{"client_child_key": "same", "directives": []}, {"client_child_key": "same", "directives": []}]},
        base | {"children": [{"client_child_key": "one", "directives": [], "job_id": "forged"}]},
        base | {"children": [{"client_child_key": "one", "directives": [], "workflow": {}}]},
        base | {"children": [{"client_child_key": "one", "directives": [], "batch_size": 2}]},
    ):
        with pytest.raises(Exception):
            CivitaiRecipeVariationSetCreateRequest.model_validate(bad)


def test_controlled_facade_failure_is_normalized_durable_and_later_members_continue(monkeypatch) -> None:
    """CIV-V-G-AC2: an individual failure is evidence, not rollback or a fake identity."""
    from app.services import civitai_recipe_variation_sets as sets
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest

    calls: list[str] = []
    outcomes = iter((
        {"variant_id": "v1", "job_id": "j1", "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64, "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64},
        sets.VariantFacadeError(
            "submission",
            "queue_submission_failed",
            "Authorization: local-secret-sentinel; Cookie: cookie-sentinel; "
            "token=token-sentinel; https://cdn.example/x?X-Amz-Signature=signed-sentinel",
        ),
        {"variant_id": "v3", "job_id": "j3", "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64, "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64},
    ))
    def submit(request, **kwargs):
        calls.append("called")
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(sets, "generate_one_variant", submit)
    store = sets.InMemoryVariationSetStore()
    base = variant_body()
    base.pop("directives")
    request = CivitaiRecipeVariationSetCreateRequest.model_validate(base | {"children": [
        {"client_child_key": "a", "directives": variant_directives()},
        {"client_child_key": "b", "directives": variant_directives()},
        {"client_child_key": "c", "directives": variant_directives()},
    ]})
    result = sets.create_variation_set(request, db=store, variation_set_id_factory=lambda: "set-1")
    assert calls == ["called", "called", "called"]
    assert [item["outcome"] for item in result["members"]] == ["submitted", "failed", "submitted"]
    failed = result["members"][1]
    assert "variant_id" not in failed and "job_id" not in failed
    assert "sentinel" not in json.dumps(result).lower()
    stored = sets.get_variation_set("set-1", db=store)
    assert [member["client_child_key"] for member in stored["members"]] == ["a", "b", "c"]
    assert "sentinel" not in json.dumps(stored).lower()
    exported = sets.export_variation_set("set-1", db=store, queue_status=lambda _job: {"status": "queued"})
    assert "sentinel" not in json.dumps(exported).lower()


def test_unexpected_submission_failure_is_redacted_durable_and_later_members_continue(monkeypatch) -> None:
    """CIV-V-G-AC2: façade failures are evidence too, never a rollback escape hatch."""
    from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
    from app.services import civitai_recipe_variation_sets as sets

    submissions = iter((RuntimeError("Authorization: secret-sentinel"), {"variant_id": "v", "job_id": "j", "derived_recipe_sha256": "a" * 64, "built_child_recipe_sha256": "b" * 64, "workflow_sha256": "c" * 64, "resource_lock_sha256": "d" * 64}))
    def submit(*_args, **_kwargs):
        value = next(submissions)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(sets, "generate_one_variant", submit)
    base = variant_body(); base.pop("directives")
    request = CivitaiRecipeVariationSetCreateRequest.model_validate(base | {"children": [
        {"client_child_key": "bad", "directives": variant_directives()},
        {"client_child_key": "later", "directives": variant_directives()},
    ]})
    response = sets.create_variation_set(request, db=sets.InMemoryVariationSetStore(), variation_set_id_factory=lambda: "set-unexpected")
    assert [item["outcome"] for item in response["members"]] == ["failed", "submitted"]
    assert "secret-sentinel" not in json.dumps(response).lower()


def test_cancel_targets_only_active_members_is_idempotent_and_preserves_failed_history() -> None:
    """CIV-V-G-AC4: only active jobs receive cancel; successful cancellation is terminal once."""
    from app.services import civitai_recipe_variation_sets as sets

    store = sets.InMemoryVariationSetStore()
    store.create("set-cancel", "a" * 64, [
        {"ordinal": 0, "client_child_key": "active", "variant_id": "v0", "job_id": "j0"},
        {"ordinal": 1, "client_child_key": "failed", "variant_id": "v1", "job_id": "j1"},
    ])
    store.append_event("set-cancel", 0, "submission_succeeded", {"status": "queued"})
    store.append_event("set-cancel", 1, "submission_failed", {"code": "queue_failed"})
    calls: list[str] = []
    cancelled = sets.cancel_variation_set("set-cancel", db=store, queue_status=lambda job: {"status": "queued"}, cancel=lambda job: calls.append(job), gallery_lookup=lambda _job: None)
    repeated = sets.cancel_variation_set("set-cancel", db=store, queue_status=lambda job: {"status": "queued"}, cancel=lambda job: calls.append(job), gallery_lookup=lambda _job: None)
    assert calls == ["j0"]
    assert cancelled["aggregate"]["status"] == repeated["aggregate"]["status"] == "partially_cancelled"
    assert [event["type"] for event in repeated["members"][0]["events"]][-2:] == ["cancel_attempt", "cancelled"]
    assert repeated["members"][1]["status"] == "failed"


def test_aggregate_eight_states_counts_only_durable_members_and_terminal_events_are_append_only() -> None:
    """CIV-V-G-AC3: member counts never include the aggregate label; terminal observations persist."""
    from app.services import civitai_recipe_variation_sets as sets

    store = sets.InMemoryVariationSetStore()
    store.create("set", "a" * 64, [
        {"ordinal": 0, "client_child_key": "failed", "variant_id": "v0", "job_id": "j0"},
        {"ordinal": 1, "client_child_key": "gallery", "variant_id": "v1", "job_id": "j1"},
        {"ordinal": 2, "client_child_key": "queued", "variant_id": "v2", "job_id": "j2"},
    ])
    store.append_event("set", 0, "submission_succeeded", {"status": "queued"})
    store.append_event("set", 1, "submission_succeeded", {"status": "queued"})
    store.append_event("set", 2, "submission_succeeded", {"status": "queued"})

    def queue(job_id: str):
        return {"status": {"j0": "failed", "j1": "running", "j2": "queued"}[job_id]}

    view = sets.get_variation_set("set", db=store, queue_status=queue, gallery_lookup=lambda job: object() if job == "j1" else None)
    assert view["aggregate"]["status"] == "queued"
    assert view["aggregate"]["counts"] == {
        "submitting": 0, "queued": 1, "running": 0, "partially_failed": 0,
        "completed": 1, "failed": 1, "cancelled": 0, "partially_cancelled": 0,
    }
    assert sum(view["aggregate"]["counts"].values()) == 3
    assert [event["type"] for event in view["members"][0]["events"]] == ["submission_succeeded", "failed"]
    assert [event["type"] for event in view["members"][1]["events"]] == ["submission_succeeded", "completed"]

    # Simulate restart/queue eviction: terminal evidence must survive and must not be rewritten.
    after_eviction = sets.get_variation_set("set", db=store, queue_status=lambda _job: {"status": "queued"}, gallery_lookup=lambda _job: None)
    assert [member["status"] for member in after_eviction["members"]] == ["failed", "completed", "queued"]
    assert sum(after_eviction["aggregate"]["counts"].values()) == 3


def test_export_recomputes_canonical_hash_and_rejects_each_member_lineage_history_or_gallery_mutation() -> None:
    """CIV-V-G-AC5: export is self-verifying and does not synthesize gallery provenance."""
    from app.services import civitai_recipe_variation_sets as sets

    store = sets.InMemoryVariationSetStore()
    store.create("set", "a" * 64, [{"ordinal": 0, "client_child_key": "one", "variant_id": "v", "job_id": "j", "derived_recipe_sha256": "b" * 64, "built_child_recipe_sha256": "c" * 64, "workflow_sha256": "d" * 64, "resource_lock_sha256": "e" * 64}])
    store.append_event("set", 0, "submission_succeeded", {"status": "queued"})
    document = sets.export_variation_set("set", db=store, queue_status=lambda _job: {"status": "queued"}, gallery_export=lambda _job: None)
    assert document["export_sha256"] == canonical({key: value for key, value in document.items() if key != "export_sha256"})
    for key in ("derived_recipe_sha256", "events", "gallery_export"):
        tampered = json.loads(json.dumps(document))
        if key == "events": tampered["members"][0][key].append({"type": "forged"})
        elif key == "gallery_export": tampered["members"][0][key] = {"forged": True}
        else: tampered["members"][0][key] = "f" * 64
        assert sets.verify_variation_set_export(tampered) is False


def test_export_redacts_gallery_signed_url_before_hashing_and_remains_self_verifying() -> None:
    """CIV-V-G-AC5/AC7: output sanitization precedes the canonical export digest."""
    from app.services import civitai_recipe_variation_sets as sets

    store = sets.InMemoryVariationSetStore()
    store.create("set-redacted", "a" * 64, [{
        "ordinal": 0, "client_child_key": "one", "variant_id": "v", "job_id": "j",
        "derived_recipe_sha256": "b" * 64, "built_child_recipe_sha256": "c" * 64,
        "workflow_sha256": "d" * 64, "resource_lock_sha256": "e" * 64,
    }])
    store.append_event("set-redacted", 0, "submission_succeeded", {"status": "queued"})
    document = sets.export_variation_set(
        "set-redacted", db=store, queue_status=lambda _job: {"status": "queued"},
        gallery_export=lambda _job: {
            "Authorization": "local-secret-sentinel",
            "nested": {"cookie": "cookie-sentinel"},
            "signed_url": "https://cdn.example/file?X-Amz-Signature=signed-sentinel&token=token-sentinel",
        },
    )
    rendered = json.dumps(document).lower()
    assert "sentinel" not in rendered
    assert sets.verify_variation_set_export(document) is True
    assert document["export_sha256"] == canonical({key: value for key, value in document.items() if key != "export_sha256"})
    tampered = json.loads(json.dumps(document))
    tampered["members"][0]["gallery_export"]["signed_url"] = "https://cdn.example/file?X-Amz-Signature=forged"
    assert sets.verify_variation_set_export(tampered) is False


def test_export_preserves_job_bound_gallery_identity_and_audited_component_documents() -> None:
    """Owner RED: a completed set export must carry independently recomputable evidence."""
    from app.services import civitai_recipe_variation_sets as sets

    components = {
        "parent_recipe": {"parent": True}, "derived_recipe": {"child": True},
        "built_child_recipe": {"built": True}, "workflow": {"1": {"class_type": "SaveImage"}},
        "resource_locks": [{"sha256": "a" * 64}], "strict_resolution_snapshot": {"ready": True},
        "compatibility_snapshot": {"status": "compatible"},
        "invalidated_evidence": [{"field": "base_prompt"}],
    }
    store = sets.InMemoryVariationSetStore()
    store.create("set-proof", "a" * 64, [{"ordinal": 0, "client_child_key": "one", "variant_id": "v", "job_id": "job-one", "provenance_components": components}])
    store.append_event("set-proof", 0, "submission_succeeded", {"status": "queued"})
    document = sets.export_variation_set(
        "set-proof", db=store, queue_status=lambda _job: {"status": "queued"},
        gallery_export=lambda _job: {"recipe": {"built": True}},
        gallery_identity=lambda _job: {"id": 42, "job_id": "job-one", "image_path": "day/result.png"},
    )
    member = document["members"][0]
    assert member["gallery_identity"] == {"id": 42, "job_id": "job-one", "image_path": "day/result.png"}
    assert member["provenance_components"] == components
    assert sets.verify_variation_set_export(document) is True
