"""CIV-SA-AC offline verifier for exactly one formal stdio alias-only child attempt."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_child_live_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC.alias-only-child-live-acceptance.json"
ALIAS = "Violet Rooftop Parent AB"
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
RESOLVED_RECORD = {
    "original_alias": ALIAS,
    "normalized_alias": "violet rooftop parent ab",
    "registry_version": 1,
    "source_identity": {"provider": "civitai", "image_id": 130519340},
    "acquisition_evidence_sha256": "56155e437ed4bb2017e76420ec0f5e3efc932eedc750e1dc4f418e05f8442d63",
    "parent_recipe_sha256": "7737814089878228bd6decdd390d14396e7d0bf0f1fac9725e6593ba75ae0714",
    "registry_created_at": "2026-07-13T22:38:38.111398Z",
}

AB_R2 = {
    "evidence_file": "agent_runs/CIV-SA-AB-R2.interrupted-import-adoption.json",
    "evidence_sha256": "82d038db65016f98becc999f09334d21451699a64c9c4b04cabf0b5cc436062c",
    "binding_sha256": "88d5fc2e963cbd07a4e0b81f91e20ddf688702b11869076cfb833c2f082746f4",
}
REQUIRED_TOOLS = {
    "civitai_source_alias_resolve", "civitai_recipe_local_ledger", "civitai_recipe_resolve_local",
    "civitai_recipe_compatibility", "civitai_recipe_variant_generate", "generate_queue_status",
    "get_generation_status", "gallery_list", "get_gallery_image", "civitai_recipe_export",
}
SECRET_MARKERS = ("authorization", "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")


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


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _digest(document: dict, field: str, payload: object) -> bool:
    return document.get("canonical_digests", {}).get(field) == canonical(payload)


def verify(document: dict) -> bool:
    """Fail closed on any unbound alias, preflight, lineage, or terminal-artifact fact."""
    try:
        unsigned = {key: value for key, value in document.items() if key != "evidence_sha256"}
        if document["schema"] != "civ-sa-ac.alias-only-child-live-acceptance.v1" or document["stage"] != "CIV-SA-AC":
            return False
        if document["evidence_sha256"] != canonical(unsigned):
            return False
        if document["ab_r2_append_only"] != AB_R2 or document["adopted_binding"] != BINDING:
            return False
        deployment = document["deployment"]
        if not deployment["head_contains_597e07d"] or deployment["backend_healthy"] is not True or deployment["comfyui_healthy"] is not True:
            return False
        catalog = deployment["formal_stdio_catalog"]
        if not isinstance(catalog["tool_count"], int) or catalog["tool_count"] < len(REQUIRED_TOOLS):
            return False
        if set(catalog["required_tools"]) != REQUIRED_TOOLS or any(catalog["required_tools"].values()) is False:
            return False
        preflight = document["preflight"]
        if preflight["exact_resolve"]["request"] != {"alias": ALIAS} or preflight["exact_resolve"]["binding"] != RESOLVED_RECORD:
            return False
        if not preflight["alias_target_state"] == {"archived": False, "repointed": False, "corrupt": False}:
            return False
        ledger_ok = preflight["ledger"]["unique_required_resources"] is True and preflight["ledger"]["regular_files_verified"] is True
        if ledger_ok and preflight["strict_resolution"]["ready"] is not True:
            return False
        if not ledger_ok and (preflight["strict_resolution"]["ready"] is not False or preflight["runtime"] != {"live_inspection": False, "blocker_code": "parent_resource_missing_from_backend_owned_local_ledger"} or preflight["compatibility"] is not None):
            return False
        runtime = preflight["runtime"]
        if ledger_ok and runtime["live_inspection"] is True:
            if preflight["compatibility"]["compatible"] is not True or not _sha(runtime["capabilities_sha256"]) or not _sha(runtime["provenance_sha256"]):
                return False
        elif ledger_ok and (preflight["compatibility"] is not None or runtime != {"live_inspection": False, "blocker_code": "formal_stdio_runtime_inspection_unavailable"}):
            return False
        request = document["variant_request"]
        terminal = document["terminal"]
        if terminal["status"] == "completed":
            if set(request) != {"source_alias", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}:
                return False
            if request["source_alias"] != {"alias": ALIAS} or request["directives"] != [{"field": "sampling.seed", "policy": "randomize"}]:
                return False
            if request["model_family"] != "illustrious" or not isinstance(request["input_bindings"], dict):
                return False
        elif request is not None or document["frozen_submission_intent"] != {"source_alias": {"alias": ALIAS}, "directives": [{"field": "sampling.seed", "policy": "randomize"}], "model_family": "illustrious", "batch_size": 1}:
            return False
        counts = document["counts"]
        if counts["variation_set_submissions"] != 0 or counts["other_generation_submissions"] != 0 or counts["batch_size"] != 1:
            return False
        terminal = document["terminal"]
        if terminal["status"] not in {"completed", "blocked"} or counts["submission_count"] not in {0, 1}:
            return False
        if terminal["status"] == "blocked":
            if counts["submission_count"] != 0 or document["variant"] is not None or document["gallery"] is not None:
                return False
        else:
            if counts["submission_count"] != 1 or not all(isinstance(document["variant"][key], str) and document["variant"][key] for key in ("variant_id", "job_id")):
                return False
            gallery = document["gallery"]
            lineage = gallery["export"]["variant_lineage"]
            if terminal != {"status": "completed", "job_id": document["variant"]["job_id"]}:
                return False
            if gallery["image"]["id"] != gallery["image_id"] or gallery["export"]["gallery"]["id"] != gallery["image_id"]:
                return False
            if gallery["image"]["job_id"] != document["variant"]["job_id"] or gallery["export"]["gallery"]["job_id"] != document["variant"]["job_id"]:
                return False
            if lineage["schema_version"] != "1.1" or lineage["source_alias_binding"] != BINDING:
                return False
            for field in ("parent_recipe_sha256", "derived_recipe_sha256", "built_child_recipe_sha256", "workflow_sha256", "resource_lock_sha256", "lineage_sha256"):
                if not _sha(lineage[field]):
                    return False
            if lineage["variant_id"] != document["variant"]["variant_id"] or lineage["job_id"] != document["variant"]["job_id"]:
                return False
            if lineage["parent_recipe_sha256"] != BINDING["parent_recipe_sha256"]:
                return False
            if document["variant"]["parent_recipe_sha256"] != BINDING["parent_recipe_sha256"]:
                return False
            for field, payload in (("parent_recipe_sha256", gallery["export"]["recipe"]), ("workflow_sha256", gallery["export"]["workflow"]), ("resource_lock_sha256", gallery["export"]["resource_locks"]), ("lineage_sha256", {key: value for key, value in lineage.items() if key != "lineage_sha256"})):
                if lineage[field] != canonical(payload):
                    return False
        ledger = document["tool_call_ledger"]
        if [item["ordinal"] for item in ledger] != list(range(1, len(ledger) + 1)):
            return False
        if ledger[0]["tool"] != "list_tools" or ledger[1]["tool"] != "mcp_ping" or ledger[2]["tool"] != "get_node_schema" or ledger[3]["tool"] != "civitai_source_alias_resolve":
            return False
        if sum(item["tool"] == "civitai_recipe_variant_generate" for item in ledger) != counts["submission_count"]:
            return False
        if any(item["tool"] in {"civitai_recipe_import", "civitai_source_alias_search", "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status", "civitai_recipe_variation_set_export", "free_comfyui_memory"} for item in ledger):
            return False
        if not all(_sha(value) for value in document["canonical_digests"].values()):
            return False
        if not _digest(document, "adopted_binding_sha256", BINDING) or not _digest(document, "preflight_sha256", preflight) or not _digest(document, "tool_call_ledger_sha256", ledger):
            return False
        if terminal["status"] == "completed" and not _digest(document, "gallery_export_sha256", document["gallery"]["export"]):
            return False
        inspected = {key: value for key, value in document.items() if key != "redaction"}
        text = json.dumps(inspected, sort_keys=True).lower()
        if any(marker in text for marker in SECRET_MARKERS):
            return False
        return document["redaction"] == {"portable": True, "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"]}
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def test_alias_only_child_live_preflight_reuses_adopted_binding_without_mutation() -> None:
    document = load()
    if EVIDENCE.is_file():
        assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    paths = [("adopted_binding", "requested_alias"), ("adopted_binding", "resolved_alias"), ("adopted_binding", "registry_version"), ("adopted_binding", "source_identity", "image_id"), ("adopted_binding", "acquisition_evidence_sha256"), ("adopted_binding", "parent_recipe_sha256"), ("adopted_binding", "registry_created_at"), ("preflight", "alias_target_state", "archived"), ("preflight", "ledger", "unique_required_resources"), ("preflight", "strict_resolution", "ready"), ("preflight", "runtime", "capabilities_sha256")]
    paths.append(("preflight", "compatibility", "compatible") if document["preflight"]["compatibility"] is not None else ("preflight", "compatibility"))
    for path in paths:
        assert not verify(mutate(document, path)), path


def test_alias_only_child_live_submission_is_single_bare_alias_and_batch_one() -> None:
    document = load()
    assert verify(document)
    request_root = "variant_request" if document["terminal"]["status"] == "completed" else "frozen_submission_intent"
    for path in ((request_root, "source_alias", "alias"), (request_root, "directives", 0, "field"), (request_root, "directives", 0, "policy"), (request_root, "model_family"), ("counts", "submission_count"), ("counts", "batch_size"), ("counts", "variation_set_submissions"), ("counts", "other_generation_submissions"), ("tool_call_ledger", 0, "ordinal")):
        assert not verify(mutate(document, path)), path


def test_alias_only_child_live_gallery_export_is_lineage_bound_and_recomputable() -> None:
    document = load()
    assert verify(document)
    if document["terminal"]["status"] == "completed":
        for path in (("variant", "variant_id"), ("variant", "job_id"), ("gallery", "image_id"), ("gallery", "image", "image_path"), ("gallery", "export", "variant_lineage", "schema_version"), ("gallery", "export", "variant_lineage", "source_alias_binding", "registry_version"), ("gallery", "export", "variant_lineage", "workflow_sha256"), ("gallery", "export", "variant_lineage", "resource_lock_sha256"), ("gallery", "export", "variant_lineage", "lineage_sha256")):
            assert not verify(mutate(document, path)), path


def test_alias_only_child_live_evidence_is_redacted_append_only_and_tamper_evident() -> None:
    document = load()
    assert verify(document)
    for path in (("ab_r2_append_only", "evidence_sha256"), ("deployment", "head_contains_597e07d"), ("deployment", "formal_stdio_catalog", "tool_count"), ("tool_call_ledger", 1, "tool"), ("terminal", "status"), ("canonical_digests", "tool_call_ledger_sha256"), ("redaction", "portable"), ("evidence_sha256",)):
        assert not verify(mutate(document, path)), path
