from __future__ import annotations

import json
from pathlib import Path

from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantLineage
from app.schemas.civitai_source_aliases import canonical_sha256
from app.services.civitai_source_alias_parent import canonicalize_source_alias_parent_recipe


FIXTURE = Path(__file__).parent / "fixtures/civitai/source_alias_child_live_recovery_r11_acceptance.json"


def test_r11_alias_only_child_live_recovery_evidence_is_complete_and_fail_closed() -> None:
    evidence = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert evidence["schema"] == "civ-sa-ac-r11.alias-only-child-live-recovery.v1"
    assert evidence["status"] == "completed"
    assert evidence["entrypoint"] == "python -m mcp_server.server"
    assert evidence["source_identity"] == {"provider": "civitai", "image_id": 130519340}

    history = evidence["append_only_history"]
    assert [(item["registry_version"], item["outcome"]) for item in history] == [
        (1, "parent_recipe_sha_mismatch"), (2, "parent_recipe_sha_mismatch"),
    ]
    assert all(item["generation_submitted"] is False for item in history)

    binding = evidence["binding"]
    assert binding["alias"] == "Violet Rooftop Parent AD"
    assert binding["registry_version"] == 3
    assert evidence["intent"]["source_alias"] == {"alias": binding["alias"]}
    assert evidence["intent"]["directives"] == [{"field": "sampling.seed", "policy": "randomize"}]
    assert evidence["intent"]["batch_size"] == 1

    preflight = evidence["formal_preflight"]
    assert preflight == {
        "tool_count": 75, "required_node_schema_count": 7,
        "strict_resolution_ready": True, "resource_hash_verified": True,
        "compatibility": "compatible", "backend_queue_before": 0, "comfyui_queue_before": 0,
    }

    ledger = evidence["formal_call_ledger"]
    calls = ledger["ordered_calls"]
    assert ledger["counts"] == {name: calls.count(name) for name in sorted(set(calls))}
    assert calls.count("civitai_recipe_variant_generate") == 1
    submission_index = calls.index("civitai_recipe_variant_generate")
    assert calls.index("civitai_source_alias_resolve") < calls.index("civitai_recipe_local_ledger")
    assert calls.index("civitai_recipe_local_ledger") < calls.index("civitai_recipe_resolve_local")
    assert calls.index("civitai_recipe_resolve_local") < calls.index("civitai_recipe_compatibility")
    assert calls.index("civitai_recipe_compatibility") < calls.index("generate_queue_status") < submission_index
    assert all(name == "get_generation_status" for name in calls[submission_index + 1 :])

    payloads = evidence["formal_payloads"]
    alias = payloads["alias_resolution"]
    assert alias["registry_version"] == binding["registry_version"]
    assert alias["source_identity"] == evidence["source_identity"]
    assert alias["acquisition_evidence_sha256"] == binding["acquisition_evidence_sha256"]
    assert canonical_sha256(alias["acquisition_evidence_snapshot"]) == binding["acquisition_evidence_sha256"]
    canonical_parent = canonicalize_source_alias_parent_recipe(
        alias["acquisition_evidence_snapshot"]["recipe"]
    ).model_dump(mode="json", exclude_none=True)
    assert canonical_sha256(canonical_parent) == binding["parent_recipe_sha256"] == alias["parent_recipe_sha256"]

    generation = evidence["generation"]
    status = payloads["generation_status"]
    assert generation["submission_count"] == 1
    assert generation["terminal_status"] == status["status"] == "completed"
    assert generation["job_id"] == status["job_id"]
    assert generation["artifact_count"] == len(status["artifacts"]) == 1
    assert status["image_id"] == evidence["readback"]["image_id"]

    artifact = payloads["gallery_artifact"]
    assert artifact["artifact_id"] == status["artifacts"][0]["id"] == 1
    assert artifact["job_id"] == generation["job_id"]
    assert artifact["file_size"] == evidence["readback"]["gallery_file_size"]
    assert artifact["gallery_path"] == status["artifacts"][0]["gallery_path"]
    assert artifact["mime_type"] == "image/png"

    export = payloads["gallery_export"]
    assert canonical_sha256(export) == evidence["readback"]["export_sha256"]
    assert canonical_sha256(export["recipe"]) == export["recipe_sha256"]
    assert canonical_sha256(export["workflow"]) == export["workflow_sha256"]
    assert export["gallery"] == {
        "id": evidence["readback"]["image_id"],
        "image_path": status["image_path"],
        "job_id": generation["job_id"],
    }
    lineage_payload = export["variant_lineage"]
    lineage = CivitaiRecipeVariantLineage.model_validate(lineage_payload)
    assert canonical_sha256({
        key: value for key, value in lineage_payload.items() if key != "lineage_sha256"
    }) == lineage_payload["lineage_sha256"]
    assert lineage.schema_version == "1.1"
    assert lineage.lineage_sha256 == evidence["readback"]["lineage_sha256"]
    assert lineage.job_id == generation["job_id"]
    assert lineage.variant_id == generation["variant_id"]
    assert lineage.parent_recipe_sha256 == binding["parent_recipe_sha256"]
    assert lineage.source_alias_binding is not None
    assert lineage.source_alias_binding.requested_alias == binding["alias"]
    assert lineage.source_alias_binding.registry_version == binding["registry_version"]
    assert lineage.source_alias_binding.parent_recipe_sha256 == binding["parent_recipe_sha256"]
    assert lineage.source_alias_binding.acquisition_evidence_sha256 == binding["acquisition_evidence_sha256"]

    assert evidence["readback"]["identity_checks"] and all(evidence["readback"]["identity_checks"].values())
    assert evidence["readback"]["formal_tools"] == [
        "gallery_list", "get_gallery_image", "get_gallery_artifact", "civitai_recipe_export",
    ]
    assert set(evidence["production_fixes"]) == {
        "route_specific_audited_resolution_timeout", "shared_sampler_runtime_canonicalization",
        "shared_source_alias_parent_canonicalization", "sparse_alias_directives_expand_to_preserve",
    }
    assert evidence["regression"] == {
        "backend_passed": 864, "mcp_passed": 192, "pipeline_passed": 46, "git_diff_check": "clean",
    }
    serialized = json.dumps(evidence, sort_keys=True).lower()
    assert all(marker not in serialized for marker in ("bearer ", "token=", "api_key", "password"))
    assert evidence["redaction"] == {"portable": True, "secrets_absent": True}
