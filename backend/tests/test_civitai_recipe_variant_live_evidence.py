"""CIV-V-H-R11 evidence verifier: two completed children must stay provenance-bound."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "variant_live_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-V-H.live-acceptance.json"
FIELDS = ["base_prompt", "negative_prompt", "sampling.seed", "sampling.steps", "sampling.cfg", "sampling.sampler", "sampling.scheduler", "sampling.denoise", "sampling.width", "sampling.height"]
COMPONENTS = {"parent_recipe_sha256": "parent_recipe", "derived_recipe_sha256": "derived_recipe", "built_child_recipe_sha256": "built_child_recipe", "workflow_sha256": "workflow", "resource_lock_sha256": "resource_locks", "strict_resolution_snapshot_sha256": "strict_resolution_snapshot", "compatibility_snapshot_sha256": "compatibility_snapshot", "invalidated_evidence_sha256": "invalidated_evidence"}


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def verify(document: dict) -> bool:
    try:
        recovery = document["recovery_attempt"]
        export = recovery["formal_export"]["data"]
        if canonical({key: value for key, value in export.items() if key != "export_sha256"}) != export["export_sha256"]:
            return False
        members = export["members"]
        if len(members) != 2 or export["aggregate"]["status"] != "completed":
            return False
        seen = set()
        for member in members:
            lineage = member["gallery_export"]["variant_lineage"]
            gallery = member["gallery_identity"]
            if member["status"] != "completed" or gallery["job_id"] != member["job_id"]:
                return False
            if member["gallery_export"]["workflow_sha256"] != member["workflow_sha256"]:
                return False
            if canonical({key: value for key, value in lineage.items() if key != "lineage_sha256"}) != lineage["lineage_sha256"]:
                return False
            for digest, component in COMPONENTS.items():
                if canonical(member["provenance_components"][component]) != lineage[digest]:
                    return False
            for key in ("variant_id", "job_id", "parent_recipe_sha256", "derived_recipe_sha256", "built_child_recipe_sha256", "workflow_sha256", "resource_lock_sha256"):
                if member.get(key) != lineage.get(key):
                    return False
            token = (member["client_child_key"], member["variant_id"], member["job_id"], gallery["id"], gallery["image_path"])
            if token in seen:
                return False
            seen.add(token)
        deliveries = recovery["decision"]["gallery_deliveries"]
        if len(deliveries) != 2:
            return False
        if {row["job_id"] for row in deliveries} != {member["job_id"] for member in members}:
            return False
        text = json.dumps(document, sort_keys=True).lower()
        return not any(value in text for value in ("authorization", "cookie", "token=", "bearer ", "x-amz-signature"))
    except (KeyError, TypeError):
        return False


def test_r11_fixture_matches_evidence_preserves_r9_zero_submission_and_is_verifiable() -> None:
    document = fixture()
    assert document == json.loads(EVIDENCE.read_text())
    assert document["schema"] == "civ-v-h-r11.live-acceptance.v1"
    assert document["stage"] == "CIV-V-H-R11"
    r9 = next(row for row in document["history"] if row["attempt_id"] == "CIV-V-H-R9.execute.1.executor")
    assert r9["decision"]["submission_count"] == 0
    assert verify(document)


def test_r11_preflight_and_submission_have_two_exact_value_absent_preserve_children() -> None:
    recovery = fixture()["recovery_attempt"]
    preflight = recovery["preflight"]
    assert preflight["formal_stdio"]["tool_catalog_matches_server_catalog"] is True
    assert preflight["local_ledger"]["cardinality"] == 1
    assert preflight["physical_file"]["regular_file"] is True
    assert preflight["strict_resolution"]["ready"] is True
    assert preflight["compatibility"]["compatible"] is True
    for request in (preflight["local_canonical_request"], preflight["transported_mcp_json"], recovery["attempted_generate"]["request"]):
        assert len(request["children"]) == 2
        for child in request["children"]:
            assert [directive["field"] for directive in child["directives"]] == FIELDS
            assert child["directives"][0]["policy"] == "replace" and child["directives"][0]["value"]
            assert all(directive["policy"] == "preserve" and "value" not in directive for directive in child["directives"][1:])


def test_r11_mutation_matrix_fails_closed_for_every_bound_component() -> None:
    original = fixture()
    assert verify(original)
    paths = [
        ("formal_export", "data", "members", 0, "provenance_components", "parent_recipe"),
        ("formal_export", "data", "members", 0, "provenance_components", "derived_recipe"),
        ("formal_export", "data", "members", 0, "provenance_components", "built_child_recipe"),
        ("formal_export", "data", "members", 0, "provenance_components", "workflow"),
        ("formal_export", "data", "members", 0, "provenance_components", "resource_locks"),
        ("formal_export", "data", "members", 0, "provenance_components", "strict_resolution_snapshot"),
        ("formal_export", "data", "members", 0, "provenance_components", "compatibility_snapshot"),
        ("formal_export", "data", "members", 0, "provenance_components", "invalidated_evidence"),
        ("formal_export", "data", "members", 0, "gallery_export", "variant_lineage", "job_id"),
        ("formal_export", "data", "members", 0, "gallery_identity", "job_id"),
    ]
    for path in paths:
        changed = deepcopy(original); value = changed["recovery_attempt"]
        for key in path[:-1]: value = value[key]
        value[path[-1]] = "forged"
        assert not verify(changed), path
    swapped = deepcopy(original)
    members = swapped["recovery_attempt"]["formal_export"]["data"]["members"]
    members[0]["gallery_identity"], members[1]["gallery_identity"] = members[1]["gallery_identity"], members[0]["gallery_identity"]
    assert not verify(swapped)
    exported = deepcopy(original)
    exported["recovery_attempt"]["formal_export"]["data"]["aggregate"]["status"] = "queued"
    assert not verify(exported)


def test_r11_forbidden_side_effect_sentinels_and_delivery_language_are_bounded() -> None:
    recovery = fixture()["recovery_attempt"]
    decision = recovery["decision"]
    assert decision["formal_variation_set_generate_calls"] == 1
    for key in ("downloads", "third_child_submissions", "success_image_reruns", "member_replacements", "free_memory_calls", "raw_backend_generation_calls", "queue_or_comfy_prompt_calls"):
        assert decision[key] == 0
    for delivery in decision["gallery_deliveries"]:
        assert set(delivery) == {"parent_reference", "result", "flow_type", "control_source", "client_child_key", "job_id", "gallery_identity", "local_path"}
        assert delivery["flow_type"] == "txt2img"
        assert delivery["control_source"] == "Civitai Recipe variant"
