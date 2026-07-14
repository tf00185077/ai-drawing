"""CIV-SA-AC-R5-AC1 offline verifier for the one alias-only recovery attempt."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_child_live_recovery_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC-R5.alias-only-child-recovery.json"
ALIAS = "Violet Rooftop Parent AB"
IDENTITY = {
    "kind": "checkpoint",
    "civitai_model_id": 376130,
    "civitai_model_version_id": 2940478,
    "civitai_file_id": 2819621,
    "sha256": "fa486caafc330f133605d3c18b418d183812f14946631c6544bfb28730db6d6f",
    "byte_size": 6939105596,
}
BINDING = {
    "requested_alias": ALIAS,
    "resolved_alias": "violet rooftop parent ab",
    "matched_alias": {"original_alias": ALIAS, "normalized_key": "violet rooftop parent ab", "kind": "primary"},
    "registry_version": 1,
    "source_identity": {"provider": "civitai", "image_id": 130519340},
    "acquisition_evidence_sha256": "56155e437ed4bb2017e76420ec0f5e3efc932eedc750e1dc4f418e05f8442d63",
    "parent_recipe_sha256": "7737814089878228bd6decdd390d14396e7d0bf0f1fac9725e6593ba75ae0714",
    "registry_created_at": "2026-07-13T22:38:38.111398Z",
}
REQUIRED_TOOLS = {
    "list_tools", "mcp_ping", "get_node_schema", "civitai_source_alias_resolve",
    "civitai_recipe_local_ledger", "civitai_recipe_resolve_local",
    "civitai_recipe_compatibility", "civitai_recipe_variant_generate",
    "generate_queue_status", "get_generation_status", "gallery_list",
    "get_gallery_image", "civitai_recipe_export",
}
FORBIDDEN_TOOLS = {
    "civitai_recipe_import", "civitai_source_alias_search", "civitai_source_alias_list",
    "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status",
    "civitai_recipe_variation_set_export", "civitai_resource_inspect",
    "civitai_resource_select", "civitai_resource_install", "free_comfyui_memory",
    "civitai_recipe_run", "gallery_rerun", "generate_image", "generate_image_custom_workflow",
}
SECRET_MARKERS=("authorization", "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mutate(document: dict, path: tuple[object, ...], value: object = "tampered") -> dict:
    changed = deepcopy(document)
    cursor = changed
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    return changed


def sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _digest(document: dict, name: str, payload: object) -> bool:
    return document["canonical_digests"].get(name) == canonical(payload)


def _ledger_identity_ok(ledger: dict) -> bool:
    try:
        entries = ledger["entries"]
        physical = ledger["physical_regular_file"]
        return (
            ledger["unique_available_identity"] is True
            and len(entries) == 1
            and {key: entries[0][key] for key in IDENTITY if key != "byte_size"} == {key: value for key, value in IDENTITY.items() if key != "byte_size"}
            and physical["regular_file"] is True
            and physical["byte_size"] == IDENTITY["byte_size"]
            and physical["sha256"] == IDENTITY["sha256"]
            and isinstance(physical["filesystem_identity"], dict)
            and all(isinstance(physical["filesystem_identity"].get(k), int) for k in ("device", "inode", "mtime_ns"))
        )
    except (KeyError, TypeError, IndexError):
        return False


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
    if exported["gallery"]["id"] != gallery["image_id"] or exported["gallery"]["job_id"] != variant["job_id"]:
        return False
    if not isinstance(image.get("image_path"), str) or image["image_path"] != exported["gallery"].get("image_path"):
        return False
    fields = (
        ("parent_recipe_sha256", exported["recipe"]),
        ("derived_recipe_sha256", lineage.get("derived_recipe")),
        ("built_child_recipe_sha256", lineage.get("built_child_recipe")),
        ("workflow_sha256", exported["workflow"]),
        ("resource_lock_sha256", exported["resource_locks"]),
        ("strict_resolution_snapshot_sha256", lineage.get("strict_resolution_snapshot")),
        ("compatibility_snapshot_sha256", lineage.get("compatibility_snapshot")),
        ("invalidated_evidence_sha256", lineage.get("invalidated_evidence")),
        ("lineage_sha256", {k: v for k, v in lineage.items() if k != "lineage_sha256"}),
    )
    return all(sha(lineage.get(name)) and lineage[name] == canonical(payload) for name, payload in fields) and lineage["parent_recipe_sha256"] == BINDING["parent_recipe_sha256"]


def verify(document: dict) -> bool:
    """Recompute every accepted R5 boundary; reject partial, forged, or widened evidence."""
    try:
        if document["schema"] != "civ-sa-ac-r5.alias-only-child-recovery.v1" or document["stage"] != "CIV-SA-AC-R5":
            return False
        unsigned = {key: value for key, value in document.items() if key != "evidence_sha256"}
        if document["evidence_sha256"] != canonical(unsigned):
            return False
        predecessors = document["append_only_predecessors"]
        if set(predecessors) != {"civ_sa_ab_r2", "civ_sa_ac_blocked", "civ_sa_ac_r4"}:
            return False
        if any(not sha(item.get("evidence_sha256")) or not sha(item.get("canonical_evidence_sha256")) for item in predecessors.values()):
            return False
        if document["adopted_binding"] != BINDING or document["r4_adopted_identity"] != IDENTITY:
            return False
        deployment = document["deployment"]
        if deployment["backend_healthy"] is not True or deployment["comfyui_healthy"] is not True:
            return False
        catalog = deployment["formal_stdio_catalog"]
        if not isinstance(catalog["tool_count"], int) or catalog["tool_count"] < len(REQUIRED_TOOLS) or set(catalog["required_tools"]) != REQUIRED_TOOLS or not all(catalog["required_tools"].values()):
            return False
        preflight = document["preflight"]
        if preflight["exact_alias_resolve"]["request"] != {"alias": ALIAS} or preflight["exact_alias_resolve"]["binding"] != BINDING:
            return False
        if not _ledger_identity_ok(preflight["ledger"]):
            return False
        if preflight["strict_resolution"].get("ready") is not True:
            return False
        if document["status"] == "completed" and preflight["compatibility"].get("compatible") is not True:
            return False
        if document["status"] == "blocked" and preflight["compatibility"] is not None:
            return False
        runtime = preflight["runtime"]
        if document["status"] == "completed":
            if runtime.get("live_inspection") is not True or not sha(runtime.get("capabilities_sha256")) or not sha(runtime.get("provenance_sha256")):
                return False
        elif document["status"] == "blocked":
            if runtime != {"live_inspection": False, "blocker_code": "live_runtime_capability_snapshot_unavailable_from_formal_stdio_get_node_schema", "inspected_node_types": ["KSampler", "CheckpointLoaderSimple", "CLIPTextEncode", "CLIPSetLastLayer", "EmptyLatentImage", "VAEDecode", "SaveImage"], "reason": "formal stdio get_node_schema redacts KSampler sampler_name and scheduler COMBO members; no authorized live capability snapshot/provenance can be constructed"}:
                return False
        else:
            return False
        counts = document["counts"]
        expected_zero_side_effects = {"variation_set_submissions": 0, "other_generation_submissions": 0, "import_remember_calls": 0, "search_calls": 0, "registry_mutations": 0, "ledger_mutations": 0, "retry_replacement_rerun_calls": 0}
        if {key: counts.get(key) for key in expected_zero_side_effects} != expected_zero_side_effects or counts.get("batch_size") != 1:
            return False
        intent = {"source_alias": {"alias": ALIAS}, "directives": [{"field": "sampling.seed", "policy": "randomize"}], "model_family": "illustrious", "batch_size": 1}
        if document["frozen_submission_intent"] != intent:
            return False
        ledger = document["tool_call_ledger"]
        if [call["ordinal"] for call in ledger] != list(range(1, len(ledger) + 1)) or {call["tool"] for call in ledger} & FORBIDDEN_TOOLS:
            return False
        if not {"list_tools", "mcp_ping", "get_node_schema", "civitai_source_alias_resolve", "civitai_recipe_local_ledger", "civitai_recipe_resolve_local", "generate_queue_status", "gallery_list"} <= {call["tool"] for call in ledger}:
            return False
        if document["status"] == "blocked":
            if counts.get("submission_count") != 0 or counts.get("artifact_count") != 0 or document["variant_request"] is not None or document["variant"] is not None or document["gallery"] is not None:
                return False
            if document["terminal"] != {"status": "blocked", "blocker_code": "live_runtime_capability_snapshot_unavailable_from_formal_stdio_get_node_schema"}:
                return False
            if preflight["compatibility"] is not None or runtime.get("live_inspection") is not False:
                return False
            if sum(call["tool"] == "civitai_recipe_variant_generate" for call in ledger) != 0:
                return False
        elif document["status"] == "completed":
            request = document["variant_request"]
            if counts.get("submission_count") != 1 or counts.get("artifact_count") != 1 or set(request) != {"source_alias", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}:
                return False
            if request["source_alias"] != {"alias": ALIAS} or request["directives"] != intent["directives"] or request["model_family"] != "illustrious" or not isinstance(request["input_bindings"], dict):
                return False
            if document["terminal"] != {"status": "completed", "job_id": document["variant"]["job_id"]} or not _lineage_ok(document):
                return False
            if sum(call["tool"] == "civitai_recipe_variant_generate" for call in ledger) != 1 or sum(call["tool"] == "get_gallery_image" for call in ledger) != 1 or sum(call["tool"] == "civitai_recipe_export" for call in ledger) != 1:
                return False
            if not _digest(document, "variant_request_sha256", request) or not _digest(document, "gallery_export_sha256", document["gallery"]["export"]):
                return False
        else:
            return False
        if not _digest(document, "adopted_binding_sha256", BINDING) or not _digest(document, "preflight_sha256", preflight) or not _digest(document, "tool_call_ledger_sha256", ledger):
            return False
        if not all(sha(value) for value in document["canonical_digests"].values()):
            return False
        inspected = {key: value for key, value in document.items() if key != "redaction"}
        if any(marker in json.dumps(inspected, sort_keys=True).lower() for marker in SECRET_MARKERS):
            return False
        return document["redaction"] == {"portable": True, "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"]}
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return False


def test_alias_only_child_after_ledger_adoption_completes_one_lineage_bound_artifact() -> None:
    document = load()
    if EVIDENCE.is_file():
        assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    paths = [
        ("adopted_binding", "registry_version"), ("r4_adopted_identity", "sha256"),
        ("preflight", "ledger", "physical_regular_file", "byte_size"),
        ("preflight", "runtime", "blocker_code"), ("counts", "submission_count"),
        ("tool_call_ledger", 0, "ordinal"), ("canonical_digests", "preflight_sha256"),
        ("evidence_sha256",),
    ]
    if document["status"] == "completed":
        paths += [
            ("preflight", "runtime", "capabilities_sha256"), ("variant_request", "source_alias", "alias"),
            ("variant_request", "directives", 0, "policy"), ("variant", "job_id"),
            ("gallery", "image", "image_path"), ("gallery", "export", "variant_lineage", "schema_version"),
            ("gallery", "export", "variant_lineage", "source_alias_binding", "parent_recipe_sha256"),
            ("canonical_digests", "gallery_export_sha256"),
        ]
    for path in paths:
        assert not verify(mutate(document, path)), path
