"""CIV-SA-AC-R8-AC1 offline verifier for one replacement-Backend alias-only Child."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_child_live_recovery_r8_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC-R8.alias-only-child-recovery.json"
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
R7 = {"evidence_file": "agent_runs/CIV-SA-AC-R7.alias-only-child-recovery.json", "evidence_file_sha256": "84314d59a639c21314da2c6bee6764cb3a4301479d41ee42b96aac683e7d5159", "evidence_sha256": "79ba0f08eee9553f0dfd4573c56fea8f3ddc0e8f161bb31c2595b59be6d2e541", "canonical_evidence_sha256": "79ba0f08eee9553f0dfd4573c56fea8f3ddc0e8f161bb31c2595b59be6d2e541"}
INTENT = {"source_alias": {"alias": ALIAS}, "directives": [{"field": "sampling.seed", "policy": "randomize"}], "model_family": "illustrious", "batch_size": 1}
REQUIRED = {"mcp_ping", "get_node_schema", "civitai_source_alias_resolve", "civitai_recipe_local_ledger", "civitai_recipe_resolve_local", "civitai_recipe_compatibility", "civitai_recipe_variant_generate", "get_generation_status", "get_gallery_image", "civitai_recipe_export"}
FORBIDDEN = {"civitai_recipe_import", "civitai_source_alias_search", "civitai_source_alias_list", "civitai_source_alias_remember", "civitai_source_alias_rename", "civitai_source_alias_archive", "civitai_source_alias_repoint", "civitai_source_alias_backfill_gallery", "civitai_resource_inspect", "civitai_resource_select", "civitai_resource_install", "civitai_recipe_run", "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status", "civitai_recipe_variation_set_export", "gallery_rerun", "generate_image", "generate_image_custom_workflow", "free_comfyui_memory"}
SECRETS=(("auth" + "orization"), "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")
REDACTION = {"portable": True, "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"]}


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mutate(document: dict, path: tuple[object, ...], value: object = "tampered") -> dict:
    result = deepcopy(document); cursor = result
    for part in path[:-1]: cursor = cursor[part]
    cursor[path[-1]] = value
    return result


def lineage_ok(document: dict) -> bool:
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
        if document["schema"] != "civ-sa-ac-r8.alias-only-child-recovery.v1" or document["stage"] != "CIV-SA-AC-R8": return False
        if document["evidence_sha256"] != canonical({k: v for k, v in document.items() if k != "evidence_sha256"}): return False
        if document["append_only_predecessors"] != {"civ_sa_ac_r7": R7} or document["adopted_binding"] != BINDING or document["r4_adopted_identity"] != IDENTITY or document["frozen_submission_intent"] != INTENT: return False
        catalog = document["deployment"]["formal_module_stdio_catalog"]
        if catalog["entrypoint"] != "python -m mcp_server.server" or catalog["tool_count"] != 75 or not REQUIRED <= set(catalog["listed_tools"]) or not all(catalog["required_tools"].get(tool) is True for tool in REQUIRED): return False
        calls = document["tool_call_ledger"]
        if [call["ordinal"] for call in calls] != list(range(1, len(calls) + 1)) or {call["tool"] for call in calls} & FORBIDDEN: return False
        if document["redaction"] != REDACTION or any(marker in json.dumps({k: v for k, v in document.items() if k != "redaction"}, sort_keys=True).lower() for marker in SECRETS): return False
        runtime, preflight, counts = document["preflight"]["runtime"], document["preflight"], document["counts"]
        ksampler = runtime["ksampler"]
        if runtime["live_inspection"] is not True or ksampler["sampler_name_type"] != "COMBO" or ksampler["scheduler_type"] != "COMBO" or not ksampler["sampler_name_options"] or not ksampler["scheduler_options"]: return False
        if runtime["capabilities_sha256"] != canonical(runtime["capabilities"]) or runtime["provenance_sha256"] != canonical(runtime["provenance"]): return False
        if preflight["exact_alias_resolve"] != {"request": {"alias": ALIAS}, "binding": BINDING} or preflight["ledger"]["unique_required_resources"] is not True or preflight["ledger"]["physical_identity"] != IDENTITY: return False
        if counts["batch_size"] != 1 or counts["variation_set_submissions"] != 0 or counts["other_generation_submissions"] != 0 or counts["retry_replacement_rerun_calls"] != 0 or counts["import_remember_calls"] != 0 or counts["search_calls"] != 0 or counts["registry_mutations"] != 0 or counts["ledger_mutations"] != 0: return False
        if document["status"] == "blocked":
            strict_calls = [call for call in calls if call["tool"] == "civitai_recipe_resolve_local"]
            compatibility_calls = [call for call in calls if call["tool"] == "civitai_recipe_compatibility"]
            return counts["submission_count"] == 0 and counts["artifact_count"] == 0 and document["variant_request"] is None and document["variant"] is None and document["gallery"] is None and document["terminal"] == {"status": "blocked", "blocker_code": "formal_preflight_gate_failed"} and sum(call["tool"] == "civitai_recipe_variant_generate" for call in calls) == 0 and len(strict_calls) == 1 and len(compatibility_calls) == 1 and preflight["strict_resolution"] == {} and preflight["compatibility"] == {} and strict_calls[0]["response_summary"]["error"]["code"] == "ReadTimeout" and compatibility_calls[0]["response_summary"]["error"]["code"] == "http_422" and document["canonical_digests"] == {"append_only_predecessors_sha256": canonical(document["append_only_predecessors"]), "adopted_binding_sha256": canonical(BINDING), "preflight_sha256": canonical(preflight), "tool_call_ledger_sha256": canonical(calls)}
        request = document["variant_request"]
        if document["status"] != "completed" or set(request) != {"source_alias", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}: return False
        if request["source_alias"] != INTENT["source_alias"] or request["directives"] != INTENT["directives"] or request["model_family"] != "illustrious": return False
        if counts["submission_count"] != 1 or counts["artifact_count"] != 1 or sum(call["tool"] == "civitai_recipe_variant_generate" for call in calls) != 1 or sum(call["tool"] == "get_generation_status" for call in calls) < 1 or sum(call["tool"] == "get_gallery_image" for call in calls) != 1 or sum(call["tool"] == "civitai_recipe_export" for call in calls) != 1 or document["terminal"] != {"status": "completed", "job_id": document["variant"]["job_id"]} or not lineage_ok(document): return False
        expected = {"append_only_predecessors_sha256": document["append_only_predecessors"], "adopted_binding_sha256": BINDING, "preflight_sha256": preflight, "tool_call_ledger_sha256": calls, "variant_request_sha256": request, "gallery_export_sha256": document["gallery"]["export"]}
        return all(document["canonical_digests"].get(key) == canonical(value) for key, value in expected.items()) and all(sha(value) for value in document["canonical_digests"].values())
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return False


def test_replacement_backend_completes_one_alias_only_lineage_bound_child() -> None:
    document = load()
    if EVIDENCE.is_file(): assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    for path in (("append_only_predecessors", "civ_sa_ac_r7", "evidence_file_sha256"), ("deployment", "formal_module_stdio_catalog", "tool_count"), ("preflight", "runtime", "ksampler", "sampler_name_options", 0), ("preflight", "compatibility", "compatible"), ("counts", "submission_count"), ("tool_call_ledger", 0, "ordinal"), ("canonical_digests", "preflight_sha256"), ("evidence_sha256",)):
        assert not verify(mutate(document, path)), path
