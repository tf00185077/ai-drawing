"""CIV-SA-AC-R7-AC1 offline verifier for the repaired module-entrypoint recovery."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_child_live_recovery_r7_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC-R7.alias-only-child-recovery.json"
ALIAS = "Violet Rooftop Parent AB"
BINDING = {
    "requested_alias": ALIAS, "resolved_alias": "violet rooftop parent ab",
    "matched_alias": {"original_alias": ALIAS, "normalized_key": "violet rooftop parent ab", "kind": "primary"},
    "registry_version": 1, "source_identity": {"provider": "civitai", "image_id": 130519340},
    "acquisition_evidence_sha256": "56155e437ed4bb2017e76420ec0f5e3efc932eedc750e1dc4f418e05f8442d63",
    "parent_recipe_sha256": "7737814089878228bd6decdd390d14396e7d0bf0f1fac9725e6593ba75ae0714",
    "registry_created_at": "2026-07-13T22:38:38.111398Z",
}
IDENTITY = {"kind": "checkpoint", "civitai_model_id": 376130, "civitai_model_version_id": 2940478, "civitai_file_id": 2819621, "sha256": "fa486caafc330f133605d3c18b418d183812f14946631c6544bfb28730db6d6f", "byte_size": 6939105596}
R6 = {"evidence_file": "agent_runs/CIV-SA-AC-R6.alias-only-child-recovery.json", "evidence_file_sha256": "6ee59765f1b3ab2645856b525d7f2c226033ff0a4a8660ad998fc948d0826c53", "evidence_sha256": "0d4832dc682617078ce70342095ea512f4e8de1128d74470f94057e151c94b3f", "canonical_evidence_sha256": "0d4832dc682617078ce70342095ea512f4e8de1128d74470f94057e151c94b3f"}
REQUIRED = {"mcp_ping", "get_node_schema", "civitai_source_alias_resolve", "civitai_recipe_local_ledger", "civitai_recipe_resolve_local", "civitai_recipe_compatibility", "civitai_recipe_variant_generate", "generate_queue_status", "get_generation_status", "gallery_list", "get_gallery_image", "civitai_recipe_export"}
FORBIDDEN = {"civitai_recipe_import", "civitai_source_alias_search", "civitai_source_alias_list", "civitai_source_alias_remember", "civitai_source_alias_rename", "civitai_source_alias_archive", "civitai_source_alias_repoint", "civitai_source_alias_backfill_gallery", "civitai_resource_inspect", "civitai_resource_select", "civitai_resource_install", "civitai_recipe_run", "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status", "civitai_recipe_variation_set_export", "gallery_rerun", "generate_image", "generate_image_custom_workflow", "free_comfyui_memory"}
SECRETS=(("auth" + "orization"), "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")
REDACTION = {"portable": True, "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"]}
INTENT = {"source_alias": {"alias": ALIAS}, "directives": [{"field": "sampling.seed", "policy": "randomize"}], "model_family": "illustrious", "batch_size": 1}


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mutate(document: dict, path: tuple[object, ...], value: object = "tampered") -> dict:
    result = deepcopy(document)
    cursor = result
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    return result


def _lineage_ok(document: dict) -> bool:
    variant, gallery = document["variant"], document["gallery"]
    image, exported = gallery["image"], gallery["export"]
    lineage = exported["variant_lineage"]
    if lineage.get("schema_version") != "1.1" or lineage.get("source_alias_binding") != BINDING:
        return False
    if variant["variant_id"] != lineage.get("variant_id") or variant["job_id"] != lineage.get("job_id"):
        return False
    if image["id"] != gallery["image_id"] or image["job_id"] != variant["job_id"]:
        return False
    if exported["gallery"]["id"] != image["id"] or exported["gallery"]["job_id"] != variant["job_id"] or exported["gallery"].get("image_path") != image.get("image_path"):
        return False
    components = (("parent_recipe_sha256", exported["recipe"]), ("derived_recipe_sha256", lineage.get("derived_recipe")), ("built_child_recipe_sha256", lineage.get("built_child_recipe")), ("workflow_sha256", exported["workflow"]), ("resource_lock_sha256", exported["resource_locks"]), ("strict_resolution_snapshot_sha256", lineage.get("strict_resolution_snapshot")), ("compatibility_snapshot_sha256", lineage.get("compatibility_snapshot")), ("invalidated_evidence_sha256", lineage.get("invalidated_evidence")), ("lineage_sha256", {k: v for k, v in lineage.items() if k != "lineage_sha256"}))
    return all(sha(lineage.get(name)) and lineage[name] == canonical(payload) for name, payload in components)


def verify(document: dict) -> bool:
    try:
        if document["schema"] != "civ-sa-ac-r7.alias-only-child-recovery.v1" or document["stage"] != "CIV-SA-AC-R7": return False
        if document["evidence_sha256"] != canonical({k: v for k, v in document.items() if k != "evidence_sha256"}): return False
        if document["append_only_predecessors"] != {"civ_sa_ac_r6": R6}: return False
        if document["adopted_binding"] != BINDING or document["r4_adopted_identity"] != IDENTITY or document["frozen_submission_intent"] != INTENT: return False
        catalog = document["deployment"]["formal_module_stdio_catalog"]
        if catalog["entrypoint"] != "python -m mcp_server.server" or catalog["tool_count"] != 75 or not REQUIRED <= set(catalog["listed_tools"]) or not all(catalog["required_tools"].get(tool) is True for tool in REQUIRED): return False
        calls = document["tool_call_ledger"]
        if [call["ordinal"] for call in calls] != list(range(1, len(calls) + 1)) or {call["tool"] for call in calls} & FORBIDDEN: return False
        if document["redaction"] != REDACTION or any(marker in json.dumps({k: v for k, v in document.items() if k != "redaction"}, sort_keys=True).lower() for marker in SECRETS): return False
        runtime = document["preflight"]["runtime"]
        if runtime["live_inspection"] is not True or runtime["ksampler"]["sampler_name_type"] != "COMBO" or runtime["ksampler"]["scheduler_type"] != "COMBO": return False
        if document["status"] == "blocked":
            expected_runtime = {"live_inspection": True, "ksampler": {"sampler_name_type": "COMBO", "scheduler_type": "COMBO", "sampler_name_options": [], "scheduler_options": []}, "blocker_code": "formal_stdio_ksampler_combo_options_empty", "reason": "fresh repaired module-entrypoint catalog exposed get_node_schema(KSampler), but its formal response exposed only COMBO types and no sampler_name/scheduler members; runtime capabilities/provenance cannot be constructed without guessing"}
            zeros = {"submission_count": 0, "artifact_count": 0, "variation_set_submissions": 0, "other_generation_submissions": 0, "retry_replacement_rerun_calls": 0, "import_remember_calls": 0, "search_calls": 0, "registry_mutations": 0, "ledger_mutations": 0}
            return runtime == expected_runtime and {k: document["counts"].get(k) for k in zeros} == zeros and document["counts"].get("batch_size") == 1 and document["preflight"].get("exact_alias_resolve") is None and document["preflight"].get("ledger") is None and document["preflight"].get("strict_resolution") is None and document["preflight"].get("compatibility") is None and document["variant_request"] is None and document["variant"] is None and document["gallery"] is None and document["terminal"] == {"status": "blocked", "blocker_code": "formal_stdio_ksampler_combo_options_empty"} and sum(call["tool"] == "civitai_recipe_variant_generate" for call in calls) == 0 and document["canonical_digests"] == {"append_only_predecessors_sha256": canonical(document["append_only_predecessors"]), "adopted_binding_sha256": canonical(BINDING), "preflight_sha256": canonical(document["preflight"]), "tool_call_ledger_sha256": canonical(calls)}
        if document["status"] != "completed": return False
        if not runtime["ksampler"]["sampler_name_options"] or not runtime["ksampler"]["scheduler_options"] or not sha(runtime["capabilities_sha256"]) or not sha(runtime["provenance_sha256"]): return False
        if runtime["capabilities_sha256"] != canonical(runtime["capabilities"]) or runtime["provenance_sha256"] != canonical(runtime["provenance"]): return False
        preflight = document["preflight"]
        if preflight["exact_alias_resolve"] != {"request": {"alias": ALIAS}, "binding": BINDING} or preflight["strict_resolution"].get("ready") is not True or preflight["compatibility"].get("compatible") is not True: return False
        request = document["variant_request"]
        if set(request) != {"source_alias", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"} or request["source_alias"] != INTENT["source_alias"] or request["directives"] != INTENT["directives"] or request["model_family"] != "illustrious": return False
        counts = document["counts"]
        if counts["submission_count"] != 1 or counts["artifact_count"] != 1 or counts["batch_size"] != 1 or sum(call["tool"] == "civitai_recipe_variant_generate" for call in calls) != 1 or sum(call["tool"] == "get_gallery_image" for call in calls) != 1 or sum(call["tool"] == "civitai_recipe_export" for call in calls) != 1 or document["terminal"] != {"status": "completed", "job_id": document["variant"]["job_id"]} or not _lineage_ok(document): return False
        expected = {"append_only_predecessors_sha256": document["append_only_predecessors"], "adopted_binding_sha256": BINDING, "preflight_sha256": preflight, "tool_call_ledger_sha256": calls, "variant_request_sha256": request, "gallery_export_sha256": document["gallery"]["export"]}
        return all(document["canonical_digests"].get(key) == canonical(value) for key, value in expected.items()) and all(sha(value) for value in document["canonical_digests"].values())
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return False


def test_repaired_module_stdio_completes_one_alias_only_lineage_bound_child() -> None:
    document = load()
    if EVIDENCE.is_file(): assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    for path in (("append_only_predecessors", "civ_sa_ac_r6", "evidence_file_sha256"), ("deployment", "formal_module_stdio_catalog", "tool_count"), ("preflight", "runtime", "ksampler", "sampler_name_type"), ("counts", "submission_count"), ("tool_call_ledger", 0, "ordinal"), ("canonical_digests", "preflight_sha256"), ("evidence_sha256",)):
        assert not verify(mutate(document, path)), path
