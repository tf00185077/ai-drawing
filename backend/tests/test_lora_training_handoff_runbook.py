import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "lora-training-agent-handoff-runbook.md"


def _load_contract() -> dict:
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    match = re.search(r"```json handoff-contract\n(.*?)\n```", text, flags=re.S)
    assert match, "runbook must include a machine-readable handoff-contract JSON block"
    return json.loads(match.group(1))


def test_pre_start_report_requires_hashes_decision_risks_and_explicit_intent():
    contract = _load_contract()
    assert contract["version"] == 4

    approval_gate = contract["approval_gate"]
    assert approval_gate["requires_explicit_user_training_request"] is True
    assert approval_gate["specific_lora_target_required"] is True
    assert approval_gate["pre_start_report_is_non_executing"] is True
    assert "lora_train_start" in approval_gate["forbidden_before_approval"]
    assert approval_gate["required_approval_identities"] == [
        "dataset_hash",
        "profile_hash",
        "recipe_hash",
    ]
    assert (
        approval_gate["recipe_hash_transport_path"]
        == "start_payload.recipe.expected_recipe_hash"
    )

    required_fields = set(contract["pre_start_report"]["required_fields"])
    assert {
        "dataset_folder",
        "dataset_type",
        "trigger_token",
        "model_family",
        "caption_profile",
        "caption_suitability_verdict",
        "training_decision",
        "reasons",
        "dataset_hash",
        "profile_hash",
        "human_readable_effective_summary",
        "known_risks",
        "lora_target_name",
        "explicit_user_training_intent",
        "recipe_schema_version",
        "recipe_hash_preview",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "runtime_capability",
        "requested_recipe",
        "effective_recipe",
    } <= required_fields

    must_state = "\n".join(contract["pre_start_report"]["must_state"])
    assert "does not start training" in must_state
    assert "Do not call lora_train_start" in must_state
    assert "explicitly asks to train this specific LoRA" in must_state


def test_non_train_preflight_is_reported_without_requesting_training_approval():
    contract = _load_contract()
    branches = contract["pre_start_report"]["decision_branches"]

    assert branches["train"]["requires_non_null_start_payload"] is True
    assert branches["train"]["request_training_approval"] is True
    for decision in ("needs_review", "do_not_train"):
        assert branches[decision]["emit_report"] is True
        assert branches[decision]["request_training_approval"] is False
        assert branches[decision]["allow_start"] is False


def test_execution_sequence_uses_existing_tools_and_never_starts_before_approval():
    contract = _load_contract()
    sequence = contract["execution_sequence"]
    assert [step["name"] for step in sequence] == [
        "decision_reverification",
        "pre_start_report",
        "training_start",
        "status_monitoring",
        "bounded_log_review",
        "registration_review",
        "smoke_test",
        "terminal_status_refresh",
    ]
    assert [step.get("tool") for step in sequence] == [
        "lora_training_decision_preflight",
        None,
        "lora_train_start",
        "lora_train_job_status",
        "lora_train_logs",
        None,
        "lora_train_smoke_test",
        "lora_train_job_status",
    ]

    start_step = next(step for step in sequence if step["tool"] == "lora_train_start")
    assert {
        "explicit_user_training_request",
        "specific_lora_target",
        "canonical_start_payload",
        "expected_dataset_hash",
        "expected_profile_hash",
    } <= set(start_step["requires"])
    assert set(start_step["submitted_fields"]) == {
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe",
    }

    source_fields = contract["source_fields"]
    assert {
        "decision",
        "reasons",
        "dataset_hash",
        "profile_hash",
        "requested_recipe",
        "effective_recipe",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "recipe_hash",
        "start_payload",
    } <= set(source_fields["decision_preflight"])
    assert {
        "output_path",
        "registered_lora_name",
        "registration_error",
        "smoke_test_status",
        "smoke_test_artifact",
        "error_code",
        "error_message",
        "error_details",
        "recipe_schema_version",
        "recipe_hash",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "execution_evidence",
    } <= set(source_fields["job_status"])
    assert "profile_hash" in source_fields["job_status"]

    status_step = next(
        step for step in sequence if step["tool"] == "lora_train_job_status"
    )
    assert {
        "recipe_schema_version",
        "recipe_hash",
        "effective_scope",
        "step_plan",
        "execution_evidence",
    } <= set(status_step["reports"])


def test_execution_contract_uses_actual_log_smoke_and_status_wire_fields():
    sequence = _load_contract()["execution_sequence"]

    log_step = next(step for step in sequence if step["name"] == "bounded_log_review")
    assert log_step["requires"] == ["job_id", "lines"]
    assert set(log_step["reports"]) == {"lines", "truncated", "log_path"}

    registration_step = next(
        step for step in sequence if step["name"] == "registration_review"
    )
    assert registration_step["tool"] is None
    assert registration_step["source"] == "terminal_lora_train_job_status"

    smoke_step = next(step for step in sequence if step["name"] == "smoke_test")
    assert {
        "smoke_test_status",
        "generation_job_id",
        "artifact",
        "error",
    } == set(smoke_step["reports"])

    refresh = next(
        step for step in sequence if step["name"] == "terminal_status_refresh"
    )
    assert "status" in refresh["reports"]
    assert "final_status" not in refresh["reports"]
    assert {
        "smoke_test_status",
        "smoke_test_job_id",
        "smoke_test_artifact",
        "smoke_test_error",
    } <= set(refresh["reports"])


def test_terminal_reports_and_recovery_cover_completed_failed_cancelled_and_stale_hashes():
    contract = _load_contract()
    terminal = contract["terminal_report"]

    assert {
        "job_id",
        "final_status",
        "dataset_folder",
        "dataset_hash",
        "profile_hash",
        "canonical_recipe_context",
        "recipe_schema_version",
        "recipe_hash",
        "requested_scope",
        "effective_scope",
        "execution_evidence",
        "recommended_next_actions",
    } <= set(terminal["required_common_fields"])
    assert {
        "output_path",
        "registered_lora_name",
        "smoke_test_status",
        "smoke_test_job_id",
        "smoke_test_artifact",
        "registration_error",
        "effective_seed",
        "optimizer_step_plan",
        "exact_argv_revision_evidence_status",
    } <= set(terminal["completed_required_fields"])
    assert {
        "error_or_cancellation_reason",
        "recent_log_summary",
        "logs_error_summary",
        "error_code",
        "error_message",
        "error_details",
        "execution_evidence_before_failure",
    } <= set(terminal["failed_required_fields"])
    assert {
        "error_or_cancellation_reason",
        "recent_log_summary",
        "logs_error_summary",
        "execution_evidence_before_cancellation",
    } <= set(terminal["cancelled_required_fields"])

    smoke = contract["smoke_lifecycle"]
    assert smoke["current_batch_guarantee"] == "submission_only"
    assert smoke["may_claim_generation_completed"] is False
    assert smoke["may_claim_generated_artifact"] is False
    assert set(smoke["submission_response_fields"]) == {
        "smoke_test_status",
        "generation_job_id",
        "artifact",
        "error",
    }
    assert set(smoke["persisted_status_fields"]) == {
        "smoke_test_status",
        "smoke_test_job_id",
        "smoke_test_artifact",
        "smoke_test_error",
    }

    recovery = contract["recovery"]
    assert {
        "failed",
        "cancelled",
        "stale_hash",
        "missing_approval_hash",
        "smoke_test_failed",
    } <= set(recovery)
    assert "Do not retry automatically." in recovery["failed"]
    assert any("new explicit user training request" in step for step in recovery["cancelled"])
    assert any("Do not retry lora_train_start" in step for step in recovery["stale_hash"])
    assert any("wait for explicit approval again" in step for step in recovery["stale_hash"])
    assert any(
        "Do not call lora_train_start" in step
        for step in recovery["missing_approval_hash"]
    )
    assert any(
        "new pre-start report" in step
        for step in recovery["missing_approval_hash"]
    )


def test_start_validation_recovery_preserves_structured_details_and_never_repairs_implicitly():
    contract = _load_contract()
    recovery = contract["recovery"]

    assert {
        "field_validation",
        "model_family_mismatch",
        "unsafe_dataset_path",
    } <= set(recovery)

    field_validation = "\n".join(recovery["field_validation"])
    assert all(field in field_validation for field in ("loc", "msg", "type"))
    assert "Do not retry" in field_validation
    assert "default" in field_validation

    family_mismatch = "\n".join(recovery["model_family_mismatch"])
    assert all(field in family_mismatch for field in ("code", "message", "details"))
    assert "Do not retry" in family_mismatch
    assert "substitute" in family_mismatch
    assert "new explicit approval" in family_mismatch

    unsafe_path = "\n".join(recovery["unsafe_dataset_path"])
    assert all(field in unsafe_path for field in ("code", "message", "details"))
    assert "Do not retry" in unsafe_path
    assert "rewrite" in unsafe_path
    assert "new explicit approval" in unsafe_path


def test_recipe_recovery_is_explicit_and_historical_status_never_invents_evidence():
    contract = _load_contract()
    recovery = contract["recovery"]

    assert {
        "recipe_validation_failed",
        "recipe_field_conflict",
        "incompatible_training_recipe",
        "unsupported_runtime_precision",
        "unsupported_network_module",
        "recipe_hash_mismatch",
        "legacy_training_fields_removed",
    } <= set(recovery)

    validation = "\n".join(recovery["recipe_validation_failed"])
    assert all(
        field in validation
        for field in ("location", "code", "message", "hint", "accepted_forms")
    )
    assert "submitted value" in validation

    conflict = "\n".join(recovery["recipe_field_conflict"])
    assert "Do not choose an alias silently" in conflict

    incompatible = "\n".join(recovery["incompatible_training_recipe"])
    assert "Do not disable" in incompatible
    assert "new preflight" in incompatible

    precision = "\n".join(recovery["unsupported_runtime_precision"])
    assert "capability" in precision
    assert "user approves" in precision
    assert "when available" in precision
    assert "unavailable" in precision

    validation_sources = "\n".join(recovery["recipe_validation_failed"])
    assert "blocking_issues" in validation_sources
    assert "error envelope" in validation_sources

    network_module = "\n".join(recovery["unsupported_network_module"])
    assert "when available" in network_module

    legacy = "\n".join(recovery["legacy_training_fields_removed"])
    assert "Do not translate" in legacy
    assert "exact start_payload" in legacy

    historical = contract["historical_job"]
    assert historical["v1_fields_may_be_null"] is True
    assert historical["legacy_params_are_context_only"] is True
    assert historical["missing_evidence_status"] == "unavailable"

    sources = contract["field_source_semantics"]
    assert "caller" in sources["caller"]
    assert "not necessarily" in sources["caller"]
    assert "server-owned constants" in sources["server_policy"]
