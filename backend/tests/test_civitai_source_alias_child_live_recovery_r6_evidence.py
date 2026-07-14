"""CIV-SA-AC-R6-AC1 offline verifier for one bounded alias-only recovery."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_child_live_recovery_r6_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC-R6.alias-only-child-recovery.json"
ALIAS = "Violet Rooftop Parent AB"
BINDING = {
    "requested_alias": ALIAS, "resolved_alias": "violet rooftop parent ab",
    "matched_alias": {"original_alias": ALIAS, "normalized_key": "violet rooftop parent ab", "kind": "primary"},
    "registry_version": 1, "source_identity": {"provider": "civitai", "image_id": 130519340},
    "acquisition_evidence_sha256": "56155e437ed4bb2017e76420ec0f5e3efc932eedc750e1dc4f418e05f8442d63",
    "parent_recipe_sha256": "7737814089878228bd6decdd390d14396e7d0bf0f1fac9725e6593ba75ae0714",
    "registry_created_at": "2026-07-13T22:38:38.111398Z",
}
R5_EVIDENCE = "agent_runs/CIV-SA-AC-R5.alias-only-child-recovery.json"
R5_SHA256 = "3bbfaa3298acb6c9b284ad04aceee850df2c320dbf0ac7ba522e73b2d28c0445"
R5_FILE_SHA256 = "34a67fdffe14cf6a362d93ad3f56d6cd2e59cdaeaa667982c9903bda6ee931a0"
FORBIDDEN = {"civitai_recipe_import", "civitai_source_alias_search", "civitai_source_alias_list", "civitai_recipe_variation_set_generate", "civitai_recipe_run", "gallery_rerun", "generate_image", "generate_image_custom_workflow", "free_comfyui_memory"}
SECRET_MARKERS=("authorization", "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mutate(document: dict, path: tuple[object, ...], value: object = "tampered") -> dict:
    changed = deepcopy(document); cursor = changed
    for part in path[:-1]: cursor = cursor[part]
    cursor[path[-1]] = value
    return changed


def sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def verify(document: dict) -> bool:
    """Reject widened request shapes, forged live snapshots, and any retry side effect."""
    try:
        if document["schema"] != "civ-sa-ac-r6.alias-only-child-recovery.v1" or document["stage"] != "CIV-SA-AC-R6": return False
        if document["evidence_sha256"] != canonical({k: v for k, v in document.items() if k != "evidence_sha256"}): return False
        predecessor = document["append_only_predecessors"]
        if predecessor != {"civ_sa_ac_r5": {"evidence_file": R5_EVIDENCE, "evidence_file_sha256": R5_FILE_SHA256, "evidence_sha256": R5_SHA256, "canonical_evidence_sha256": R5_SHA256}}: return False
        if document["adopted_binding"] != BINDING: return False
        counts = document["counts"]
        zeros = {"submission_count": 0, "artifact_count": 0, "variation_set_submissions": 0, "other_generation_submissions": 0, "retry_replacement_rerun_calls": 0, "import_remember_calls": 0, "search_calls": 0, "registry_mutations": 0, "ledger_mutations": 0}
        if {k: counts.get(k) for k in zeros} != zeros or counts.get("batch_size") != 1: return False
        intent = {"source_alias": {"alias": ALIAS}, "directives": [{"field": "sampling.seed", "policy": "randomize"}], "model_family": "illustrious", "batch_size": 1}
        if document["frozen_submission_intent"] != intent or document["variant_request"] is not None or document["variant"] is not None or document["gallery"] is not None: return False
        ledger = document["tool_call_ledger"]
        if [x["ordinal"] for x in ledger] != list(range(1, len(ledger) + 1)) or {x["tool"] for x in ledger} & FORBIDDEN: return False
        # A repaired live facade must expose complete KSampler options before any compatibility/submission. This fresh stdio boundary did not.
        if document["status"] != "blocked" or document["terminal"] != {"status": "blocked", "blocker_code": "formal_stdio_catalog_incomplete_before_runtime_inspection"}: return False
        deployment = document["deployment"]
        if deployment["formal_stdio_catalog"] != {"tool_count": 1, "listed_tools": ["mcp_ping"]}: return False
        if ledger != [{"ordinal": 1, "session": "formal-preflight", "tool": "list_tools", "request": {}, "is_error": False, "response_summary": {"tool_count": 1, "listed_tools": ["mcp_ping"]}}]: return False
        preflight = document["preflight"]
        if preflight != {"runtime": {"live_inspection": False, "blocker_code": "formal_stdio_catalog_incomplete_before_runtime_inspection", "reason": "fresh stdio catalog exposed only mcp_ping; get_node_schema(KSampler) was unavailable, so sampler_name/scheduler COMBO options and runtime capabilities/provenance could not be constructed"}}: return False
        if document["canonical_digests"] != {"adopted_binding_sha256": canonical(BINDING), "append_only_predecessors_sha256": canonical(predecessor), "preflight_sha256": canonical(preflight), "tool_call_ledger_sha256": canonical(ledger)}: return False
        if any(not sha(v) for v in document["canonical_digests"].values()): return False
        if any(marker in json.dumps({k:v for k,v in document.items() if k != "redaction"}, sort_keys=True).lower() for marker in SECRET_MARKERS): return False
        return document["redaction"] == {"portable": True, "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"]}
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def test_repaired_live_capabilities_complete_one_alias_only_lineage_bound_child() -> None:
    document = load()
    if EVIDENCE.is_file(): assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    for path in (("append_only_predecessors", "civ_sa_ac_r5", "evidence_sha256"), ("adopted_binding", "parent_recipe_sha256"), ("deployment", "formal_stdio_catalog", "tool_count"), ("preflight", "runtime", "blocker_code"), ("counts", "submission_count"), ("frozen_submission_intent", "source_alias", "alias"), ("tool_call_ledger", 0, "tool"), ("canonical_digests", "preflight_sha256"), ("evidence_sha256",)):
        assert not verify(mutate(document, path)), path
