"""CIV-SA-AC-R4 offline verifier for one successful bounded checkpoint adoption."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
FIXTURE = ROOT / "fixtures" / "civitai" / "source_alias_resource_adoption_live_acceptance.json"
EVIDENCE = PROJECT_ROOT / "agent_runs" / "CIV-SA-AC-R4.checkpoint-ledger-adoption.json"
LOCATOR = "https://civitai.com/models/376130?modelVersionId=2940478"
IDENTITY = {
    "civitai_model_id": 376130,
    "civitai_model_version_id": 2940478,
    "civitai_file_id": 2819621,
    "resource_kind": "checkpoint",
    "name": "novaAnimeXL_ilV190.safetensors",
    "byte_size": 6939105596,
    "sha256": "fa486caafc330f133605d3c18b418d183812f14946631c6544bfb28730db6d6f",
}
PREDECESSORS = {
    "civ_sa_ac": {
        "evidence_file": "agent_runs/CIV-SA-AC.alias-only-child-live-acceptance.json",
        "evidence_sha256": "1aa19a6735bca4f66496921e674b40fb808ecfe10f7b06bedd8a17ee366c0bc8",
        "stage": "CIV-SA-AC",
        "status": "blocked",
        "submission_count": 0,
    },
    "civ_sa_ac_r1": {
        "evidence_file": "agent_runs/CIV-SA-AC-R1.checkpoint-ledger-adoption.json",
        "evidence_sha256": "af80a4f831075ba74a2ac0c256a47b762b190a9b59fa519ec79e41ad260901f7",
        "stage": "CIV-SA-AC-R1",
        "status": "blocked",
        "blocked_reason": "formal_resource_inspect_rejected_numeric_model_version_locator",
    },
    "civ_sa_ac_r2": {
        "evidence_file": "agent_runs/CIV-SA-AC-R2.checkpoint-ledger-adoption.json",
        "evidence_sha256": "704e9bfc85c92c7503f95037f4a1d03e32be7ae408b1d6b55e9ded9ea00a73c7",
        "stage": "CIV-SA-AC-R2",
        "status": "blocked",
        "blocked_reason": "formal_canonical_url_exact_select_rejected_unsafe_metadata_before_install",
    },
    "civ_sa_ac_r3": {
        "evidence_file": "agent_runs/CIV-SA-AC-R3.checkpoint-ledger-adoption.json",
        "evidence_sha256": "fe47f42e48c3fbfde36abeb06d81f1e4e07f1a564c578a20af1e0c1cb8a86488",
        "stage": "CIV-SA-AC-R3",
        "status": "blocked",
        "blocked_reason": "formal_existing_file_install_returned_http_500_without_ledger_row",
    },
}
COUNTS = {
    "alias_mutations": 0,
    "generation_submissions": 0,
    "gallery_calls": 0,
    "search_calls": 0,
    "overwrite_calls": 0,
    "additional_install_calls": 0,
    "downloads": 0,
    "transport_downloads": 0,
    "file_replacements": 0,
    "file_renames": 0,
    "file_mutations": 0,
    "direct_database_writes": 0,
    "resource_inspect_calls": 1,
    "resource_select_calls": 1,
    "resource_install_calls": 1,
    "local_ledger_reads": 1,
}
SECRET_MARKERS = ("authorization", "bearer ", "cookie", "token=", "password", "signature=", "x-amz-")


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


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
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _physical(value: object) -> bool:
    if not isinstance(value, dict) or value.get("regular_file") is not True:
        return False
    if value.get("byte_size") != IDENTITY["byte_size"] or value.get("sha256") != IDENTITY["sha256"]:
        return False
    filesystem = value.get("filesystem_identity")
    return isinstance(value.get("path"), str) and isinstance(filesystem, dict) and all(
        isinstance(filesystem.get(key), int) for key in ("device", "inode", "mtime_ns")
    )


def verify(document: dict) -> bool:
    """Fail closed on R4 adoption, immutable identity, ordinals, lineage, or redaction drift."""
    try:
        unsigned = {key: value for key, value in document.items() if key != "evidence_sha256"}
        if document["schema"] != "civ-sa-ac-r4.checkpoint-ledger-adoption.v1" or document["stage"] != "CIV-SA-AC-R4":
            return False
        if document["status"] != "completed" or document["evidence_sha256"] != canonical(unsigned):
            return False
        deployment = document["deployment"]
        if deployment["backend_healthy"] is not True or deployment["head"] != "3b4054faeff0e5bc471d0935781a803e09c356aa" or deployment["head_contains_3b4054f"] is not True:
            return False
        if deployment["formal_stdio_catalog"] != {
            "tool_count": 75,
            "required_tools": {
                "civitai_recipe_local_ledger": True,
                "civitai_resource_inspect": True,
                "civitai_resource_install": True,
                "civitai_resource_select": True,
            },
        }:
            return False
        if document["pre_formal_database_preflight"] != {
            "sqlite_quick_check": "ok",
            "downloaded_resources_schema_complete": True,
            "begin_immediate_then_rollback_succeeded": True,
            "disposable_copy_persistence_diagnosis": "succeeds",
        }:
            return False
        if document["canonical_locator"] != LOCATOR or document["frozen_immutable_identity"] != IDENTITY:
            return False
        physical = document["physical_identity"]
        if physical["pre"] != physical["post"] or not _physical(physical["pre"]):
            return False
        policy = document["authoritative_policy"]
        if policy != {
            "source": "civitai_model_permissions",
            "model_endpoint": "https://civitai.com/api/v1/models/376130",
            "selected_descriptor_policy": {
                "availability": True,
                "scan_status": "success",
                "license": {"allow_no_credit": True, "allow_different_license": True, "source": "civitai_model_permissions"},
                "usage_restrictions": {"allow_commercial_use": ["Image", "Rent", "RentCivit"], "allow_derivatives": True},
                "model_family": "Illustrious",
            },
        }:
            return False
        selected = {
            **IDENTITY,
            "air": None,
            "availability": True,
            "download_url_identity": "https://civitai.com/api/download/models/2940478",
            "scan_status": "success",
            "license": policy["selected_descriptor_policy"]["license"],
            "usage_restrictions": policy["selected_descriptor_policy"]["usage_restrictions"],
            "model_family": "Illustrious",
        }
        calls = document["formal_tool_call_ledger"]
        expected_calls = [
            {"ordinal": 1, "tool": "civitai_resource_inspect", "request": {"locator": LOCATOR}, "response": {"ok": True, "status": "completed", "matching_exact_file_sha_candidate_count": 1, "authoritative_model_policy_source": "civitai_model_permissions"}},
            {"ordinal": 2, "tool": "civitai_resource_select", "request": {"selectors": {"civitai_model_id": 376130, "civitai_model_version_id": 2940478, "civitai_file_id": 2819621, "sha256": IDENTITY["sha256"], "resource_kind": "checkpoint"}}, "response": {"ok": True, "status": "completed", "selected": selected}},
            {"ordinal": 3, "tool": "civitai_resource_install", "request": {"selected": selected, "storage_root": "checkpoints", "overwrite": False}, "response": {"ok": True, "status": "completed", "diagnostic_code": "adopted_existing", "ledger_id": 1, "final_path": physical["pre"]["path"], "byte_size": IDENTITY["byte_size"], "sha256": IDENTITY["sha256"]}},
            {"ordinal": 4, "tool": "civitai_recipe_local_ledger", "request": {"kind": "checkpoint", "civitai_model_id": 376130, "civitai_model_version_id": 2940478, "civitai_file_id": 2819621, "sha256": IDENTITY["sha256"], "availability": True}, "response": {"ok": True, "entry_count": 1, "available_identity_count": 1, "ledger_id": 1}},
        ]
        if calls != expected_calls:
            return False
        row = {
            "air": None,
            "availability": True,
            "civitai_file_id": 2819621,
            "civitai_model_id": 376130,
            "civitai_model_version_id": 2940478,
            "diagnostics": {"database_id": 1, "status": "installed"},
            "kind": "checkpoint",
            "local_path": physical["pre"]["path"],
            "model_family": "illustrious",
            "sha256": IDENTITY["sha256"],
        }
        if document["ledger_read_back"] != {"unique_available_identity": True, "entries": [row], "snapshot_row_count": 1}:
            return False
        if document["adoption"] != {"completed": True, "reason": "adopted_existing", "backend_ledger_id": 1}:
            return False
        if document["blocked_predecessors"] != PREDECESSORS or document["forbidden_side_effect_counts"] != COUNTS:
            return False
        digests = document["canonical_digests"]
        expected_digests = {
            "frozen_immutable_identity_sha256": canonical(IDENTITY),
            "physical_identity_sha256": canonical(physical),
            "authoritative_policy_sha256": canonical(policy),
            "formal_tool_call_ledger_sha256": canonical(calls),
            "ledger_read_back_sha256": canonical(document["ledger_read_back"]),
            "blocked_predecessors_sha256": canonical(PREDECESSORS),
        }
        if digests != expected_digests or not all(_sha(value) for value in digests.values()):
            return False
        inspected = {key: value for key, value in document.items() if key != "redaction"}
        if any(marker in json.dumps(inspected, sort_keys=True).lower() for marker in SECRET_MARKERS):
            return False
        return document["redaction"] == {
            "portable": True,
            "secret_fields_absent": ["authorization", "bearer", "cookie", "token", "password", "signature", "signed_url_secret"],
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def test_existing_checkpoint_adoption_is_identity_bound_zero_download_and_recomputable() -> None:
    """R4 records the sole formal successful adopted-existing sequence."""
    document = load()
    if EVIDENCE.is_file():
        assert document == json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert verify(document)
    assert document["physical_identity"]["pre"] == document["physical_identity"]["post"]
    assert document["forbidden_side_effect_counts"] == COUNTS


def test_existing_checkpoint_adoption_evidence_fails_closed_for_named_mutations() -> None:
    document = load()
    assert verify(document)
    for path in (
        ("canonical_locator",),
        ("frozen_immutable_identity", "civitai_file_id"),
        ("physical_identity", "pre", "path"),
        ("physical_identity", "post", "filesystem_identity", "inode"),
        ("authoritative_policy", "source"),
        ("authoritative_policy", "selected_descriptor_policy", "license", "source"),
        ("formal_tool_call_ledger", 0, "ordinal"),
        ("formal_tool_call_ledger", 1, "response", "selected", "sha256"),
        ("formal_tool_call_ledger", 2, "response", "diagnostic_code"),
        ("formal_tool_call_ledger", 3, "response", "entry_count"),
        ("ledger_read_back", "entries", 0, "local_path"),
        ("forbidden_side_effect_counts", "downloads"),
        ("forbidden_side_effect_counts", "resource_install_calls"),
        ("blocked_predecessors", "civ_sa_ac_r3", "evidence_sha256"),
        ("canonical_digests", "formal_tool_call_ledger_sha256"),
        ("redaction", "portable"),
        ("evidence_sha256",),
    ):
        assert not verify(mutate(document, path)), path
