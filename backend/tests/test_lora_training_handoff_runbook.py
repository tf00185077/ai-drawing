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

    approval_gate = contract["approval_gate"]
    assert approval_gate["requires_explicit_user_training_request"] is True
    assert approval_gate["specific_lora_target_required"] is True
    assert approval_gate["pre_start_report_is_non_executing"] is True
    assert "lora_train_start" in approval_gate["forbidden_before_approval"]

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
        "selected_training_parameters",
        "known_risks",
        "lora_target_name",
        "explicit_user_training_intent",
    } <= required_fields

    must_state = "\n".join(contract["pre_start_report"]["must_state"])
    assert "does not start training" in must_state
    assert "Do not call lora_train_start" in must_state
    assert "explicitly asks to train this specific LoRA" in must_state


def test_execution_sequence_uses_existing_tools_and_never_starts_before_approval():
    contract = _load_contract()
    sequence = contract["execution_sequence"]
    tools = [step["tool"] for step in sequence]

    expected_order = [
        "lora_training_decision_preflight",
        "lora_train_start",
        "lora_train_job_status",
        "lora_train_logs",
        "registration_review",
        "lora_train_smoke_test",
    ]
    positions = [tools.index(tool) for tool in expected_order]
    assert positions == sorted(positions)

    start_step = next(step for step in sequence if step["tool"] == "lora_train_start")
    assert {
        "explicit_user_training_request",
        "specific_lora_target",
        "selected_training_parameters",
        "expected_dataset_hash",
        "expected_profile_hash_verified_by_preflight",
    } <= set(start_step["requires"])
    assert "expected_dataset_hash" in start_step["submitted_fields"]

    source_fields = contract["source_fields"]
    assert {
        "decision",
        "reasons",
        "dataset_hash",
        "profile_hash",
        "suggested_params",
    } <= set(source_fields["decision_preflight"])
    assert {
        "output_path",
        "registered_lora_name",
        "registration_error",
        "smoke_test_status",
        "smoke_test_artifact",
        "error_code",
        "error_message",
    } <= set(source_fields["job_status"])


def test_terminal_reports_and_recovery_cover_completed_failed_cancelled_and_stale_hashes():
    contract = _load_contract()
    terminal = contract["terminal_report"]

    assert {
        "job_id",
        "final_status",
        "dataset_folder",
        "dataset_hash",
        "profile_hash",
        "selected_training_parameters",
        "recommended_next_actions",
    } <= set(terminal["required_common_fields"])
    assert {
        "output_path",
        "registered_lora_name",
        "smoke_test_status",
        "generated_artifact_reference",
        "registration_error",
    } <= set(terminal["completed_required_fields"])
    assert {
        "error_or_cancellation_reason",
        "recent_log_summary",
        "logs_error_summary",
        "error_code",
        "error_message",
    } <= set(terminal["failed_required_fields"])
    assert {
        "error_or_cancellation_reason",
        "recent_log_summary",
        "logs_error_summary",
    } <= set(terminal["cancelled_required_fields"])

    recovery = contract["recovery"]
    assert {"failed", "cancelled", "stale_hash", "smoke_test_failed"} <= set(recovery)
    assert "Do not retry automatically." in recovery["failed"]
    assert any("new explicit user training request" in step for step in recovery["cancelled"])
    assert "Stop before lora_train_start." in recovery["stale_hash"]
    assert any("wait for explicit approval again" in step for step in recovery["stale_hash"])
