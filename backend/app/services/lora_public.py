"""LoRA-only public failures and structured logs. Never serialize an exception."""
from __future__ import annotations

import json
import math
import re


_GROUPS = {
    "admission": "admission_uncertain",
    "dataset": "dataset_not_found invalid_dataset_folder dataset_locked dataset_hash_mismatch profile_hash_mismatch dataset_validation_failed dataset_profile_invalid model_family_mismatch missing_caption empty_caption trigger_token_missing backup_not_found ai_cleanup_not_configured",
    "recipe": "recipe_missing recipe_validation_failed recipe_hash_mismatch recipe_field_conflict recipe_context_unavailable server_recipe_policy_invalid unsupported_network_module unsupported_model_family unsupported_mixed_precision unsupported_runtime_precision invalid_output_name output_config_hash_mismatch unreportable_training_option run_cache_not_isolatable",
    "preparation": "legacy_output_unknown output_allocation_conflict output_path_too_long unsafe_run_path output_ownership_mismatch sd_scripts_path_missing sd_scripts_path_not_directory train_script_missing checkpoint_not_found training_component_changed trainer_capability_changed training_parameters_write_failed run_preparation_failed duplicate_folder",
    "validation": "output_missing invalid_lora_output output_hash_changed",
    "registration": "lora_registration_not_configured lora_registration_conflict lora_copy_hash_mismatch lora_registration_failed",
    "operation": "job_not_found job_not_cancellable job_cancel_failed log_not_found log_read_failed smoke_test_precondition_failed smoke_test_submit_failed generation_queue_full completion_callback_failed worker_initialization_failed trainer_cleanup_failed dataset_unlock_failed",
    "execution": "unexpected_error kohya_failed cancelled",
}
_CLASSIFICATION = {code: group for group, codes in _GROUPS.items() for code in codes.split()}
_HINTS = {
    "admission": "Check the recorded canonical job_id first; do not resubmit this training request automatically.",
    "dataset": "repair the dataset or wait for its lock, then rerun decision preflight",
    "recipe": "correct recipe fields (including required Anima Qwen3 for Anima) and rerun decision preflight",
    "preparation": "check the configured trainer resources and run folder; rerun decision preflight before a new job",
    "validation": "inspect the declared final artifact; preserve this run and do not publish an unverified file",
    "registration": "check publication configuration and ownership; preserve this run and retry only for the same job and verified content",
    "operation": "check the job identifier and current state before retrying the operation",
    "execution": "preserve the run and check trainer readiness; reconcile the job before retrying",
}
_PHASES = frozenset("request queued preflight prepared training registering registration_failed completed failed cancelled unknown".split())
_HASH_FIELDS = frozenset("expected_dataset_hash current_dataset_hash dataset_hash expected_profile_hash current_profile_hash expected_recipe_hash current_recipe_hash".split())
_FIELD_PARTS = frozenset("model family checkpoint anima qwen3 vae t5_tokenizer_path network_module network_dim network_alpha scope train_text_encoder dataset trigger_token resolution batch_size keep_tokens shuffle_caption num_repeats enable_bucket bucket_no_upscale min_bucket_reso max_bucket_reso bucket_reso_steps optimization epochs learning_rate denoiser_learning_rate text_encoder_learning_rates gradient_accumulation_steps optimizer_type optimizer_args lr_scheduler lr_scheduler_args warmup mode value seed mixed_precision caching cache_latents cache_text_encoder_outputs cache_to_disk execution max_data_loader_n_workers persistent_data_loader_workers save_every_n_epochs recipe schema_version expected_recipe_hash".split())
_ISSUE_TYPES = frozenset("missing extra_forbidden unsupported_value unsupported_field unknown_field conflicting_aliases alias_conflict bucket_invariant value_error int_type bool_type string_type literal_error greater_than_equal less_than_equal".split())


def _field(value):
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    return value if all(part in _FIELD_PARTS for part in parts) else None


def safe_details(details):
    """Keep repair coordinates/digests; free text, nested exceptions and paths are omitted."""
    if not isinstance(details, dict):
        return {}
    result = {k: v for k, v in details.items() if k in _HASH_FIELDS and isinstance(v, str) and re.fullmatch(r"[a-f0-9]{64}", v)}
    for key in ("issues", "validation_errors"):
        if isinstance(details.get(key), list):
            items = []
            for entry in details[key]:
                if not isinstance(entry, dict):
                    continue
                item = {}
                for name in ("location", "field"):
                    value = _field(entry.get(name))
                    if value:
                        item[name] = value
                if isinstance(entry.get("type"), str) and entry["type"] in _ISSUE_TYPES:
                    item["type"] = entry["type"]
                if item:
                    items.append(item)
            result[key] = items
    return result


def failure(code=None, *, phase="unknown", details=None, fallback="unexpected_error"):
    """Closed code vocabulary and fixed copy, independent of exception message/hint/type name."""
    code = code if isinstance(code, str) and code in _CLASSIFICATION else fallback
    group = _CLASSIFICATION[code]
    phase = phase if isinstance(phase, str) and phase in _PHASES else "unknown"
    hint = _HINTS[group]
    return {
        "code": code,
        "message": f"LoRA {group} failure ({code})",
        "hint": hint,
        "details": {**safe_details(details), "classification": group, "phase": phase, "hint": hint},
    }


_EVENTS = frozenset("queued dequeued started progress cancelled cancellation_requested registered completed failed callback_failed cleanup_failed".split())
_LOG_PREFIX = "[lora-event] "


def event_line(event, *, code=None, phase="unknown", progress=None, epoch=None, total_epochs=None):
    event = event if event in _EVENTS else "failed"
    data = {"event": event}
    if code is not None:
        data.update(failure(code, phase=phase))
    if event == "progress":
        if isinstance(progress, (float, int)) and math.isfinite(progress):
            data["progress"] = max(0, min(progress, 1))
        for name, value in (("epoch", epoch), ("total_epochs", total_epochs)):
            if isinstance(value, int) and 0 <= value <= 1_000_000_000:
                data[name] = value
    return _LOG_PREFIX + json.dumps(data, sort_keys=True)


def public_log_line(line):
    """Old raw logs stay on disk; only reconstruct known events at the read boundary."""
    if isinstance(line, str) and line.startswith(_LOG_PREFIX):
        try:
            value = json.loads(line[len(_LOG_PREFIX):])
            if isinstance(value, dict) and value.get("event") in _EVENTS:
                details = value.get("details") or {}
                return event_line(value["event"], code=value.get("code"), phase=details.get("phase", "unknown"), progress=value.get("progress"), epoch=value.get("epoch"), total_epochs=value.get("total_epochs"))
        except (ValueError, TypeError, AttributeError):
            pass
    return "<redacted unstructured trainer/legacy log line>"
