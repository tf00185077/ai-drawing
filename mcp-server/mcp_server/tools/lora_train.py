"""
LoRA training MCP tools.

These tools are thin clients for the backend-owned LoRA training workflow.
Results are JSON-serializable dicts so agents can branch without scraping
human-readable strings. Dataset preparation/curation stays available through
the backend HTTP API; the MCP surface keeps only the decision-and-train loop.
"""
from __future__ import annotations

import re
import math
from typing import Any, Literal
from urllib.parse import quote

import httpx

from mcp_server.client import get_backend_client as _get_client
from mcp_server import lora_public


_SAFE_VALIDATION_CONTEXT_KEYS = frozenset(
    {
        "expected",
        "ge",
        "gt",
        "le",
        "lt",
        "max_length",
        "min_length",
        "multiple_of",
    }
)

_PREFLIGHT_SUCCESS_FIELDS = frozenset(
    {

        "output_name",
        "output_config_hash",
        "output_name_preview",
        "output_allocation_notice",        "folder",
        "decision",
        "reasons",
        "blocking_issues",
        "warnings",
        "next_actions",
        "dataset_hash",
        "profile_hash",
        "normalized_trigger_token",
        "requested_recipe",
        "effective_recipe",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "execution_evidence",
        "recipe_hash",
        "policy_rationale",
        "start_payload",
    }
)

_START_SUCCESS_FIELDS = frozenset(
    {

        "output_name",
        "output_config_hash",
        "resolved_output_name",
        "output_serial",
        "run_locator",
        "validation_status",
        "registration_status",
        "output_sha256",        "job_id",
        "status",
        "stage",
        "dataset_hash",
        "profile_hash",
        "normalized_trigger_token",
        "recipe_schema_version",
        "recipe_hash",
        "requested_recipe",
        "effective_recipe",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "execution_evidence",
        "message",
    }
)

_STATUS_SUCCESS_FIELDS = frozenset(
    {

        "output_name",
        "output_config_hash",
        "resolved_output_name",
        "output_serial",
        "run_locator",
        "validation_status",
        "registration_status",
        "output_sha256",        "job_id",
        "folder",
        "status",
        "stage",
        "progress",
        "current_epoch",
        "total_epochs",
        "dataset_hash",
        "profile_hash",
        "normalized_trigger_token",
        "log_path",
        "log_tail_lines",
        "log_truncated",
        "output_path",
        "registered_lora_name",
        "registration_error",
        "error_code",
        "error_message",
        "error_details",
        "recipe_schema_version",
        "recipe_hash",
        "requested_recipe",
        "effective_recipe",
        "requested_scope",
        "effective_scope",
        "field_sources",
        "step_plan",
        "component_identities",
        "capability",
        "execution_evidence",
        "params",
        "smoke_test_status",
        "smoke_test_job_id",
        "smoke_test_artifact",
        "smoke_test_error",
        "smoke_test_error_code",
        "smoke_test_hint",
        "smoke_test_artifact_id",
        "smoke_test_image_id",
        "smoke_test_artifact_url",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "cancel_requested_at",
    }
)


# Closed LoRA diagnostic vocabulary, mirrored from the recipe/transport contract.
# Backend remains an independently deployed component; never import its modules here.
_DIAGNOSTIC_BASE_FIELDS = frozenset(
    'allowUnverifiedCheckpoint allow_unverified_checkpoint animaQwen3 animaT5TokenizerPath animaVae '
    'anima_qwen3 anima_t5_tokenizer_path anima_vae batch batchSize batch_size body bucketNoUpscale '
    'bucketResoSteps bucket_no_upscale bucket_reso_steps cacheLatents cacheTextEncoderOutputs '
    'cacheToDisk cache_latents cache_text_encoder_outputs cache_to_disk caching caching.cache_latents '
    'caching.cache_text_encoder_outputs caching.cache_to_disk caching.latent_cache_to_disk '
    'caching.text_encoder_cache_to_disk checkpoint classTokens class_tokens dataset '
    'dataset.batch_size dataset.bucket_no_upscale dataset.bucket_reso_steps dataset.enable_bucket '
    'dataset.keep_tokens dataset.max_bucket_reso dataset.min_bucket_reso dataset.num_repeats '
    'dataset.resolution dataset.shuffle_caption dataset.trigger_token denoiserLearningRate '
    'denoiser_learning_rate diffusion_model dit_lr enableBucket enable_bucket epochs execution '
    'execution.final_only execution.max_data_loader_n_workers '
    'execution.persistent_data_loader_workers execution.save_every_n_epochs execution_target '
    'expectedRecipeHash expected_dataset_hash expected_output_config_hash expected_profile_hash '
    'expected_recipe_hash family folder gradientAccumulation gradientAccumulationSteps '
    'gradient_accumulation gradient_accumulation_steps instanceToken instance_token keepTokens '
    'keep_tokens learningRate learning_rate lrScheduler lrSchedulerArgs lrWarmupSteps lr_scheduler '
    'lr_scheduler_args lr_warmup_steps maxBucketReso maxDataLoaderNWorkers max_bucket_reso '
    'max_data_loader_n_workers minBucketReso min_bucket_reso mixedPrecision mixed_precision model '
    'model.allow_unverified_checkpoint model.anima model.anima.qwen3 model.anima.t5_tokenizer_path '
    'model.anima.vae model.checkpoint model.family model.network_alpha model.network_dim '
    'model.network_module modelFamily model_family negative_prompt networkAlpha networkDim '
    'networkModule network_alpha network_dim network_module numRepeats num_repeats optimization '
    'optimization.denoiser_learning_rate optimization.epochs optimization.gradient_accumulation_steps '
    'optimization.learning_rate optimization.lr_scheduler optimization.lr_scheduler_args '
    'optimization.mixed_precision optimization.optimizer_args optimization.optimizer_type '
    'optimization.seed optimization.seed.mode optimization.seed.source optimization.seed.value '
    'optimization.text_encoder_learning_rates optimization.warmup optimization.warmup.mode '
    'optimization.warmup.resolved_steps optimization.warmup.value optimizer optimizerArgs '
    'optimizerType optimizer_args optimizer_type output_name persistentDataLoaderWorkers '
    'persistentWorkers persistent_data_loader_workers policy precision prompt qwen3 recipe resolution '
    'saveCadence saveEveryNEpochs save_cadence save_every_n_epochs scheduler schedulerArgs '
    'scheduler_args schemaVersion schema_version scope scope.denoiser_kind scope.native_scope_flag '
    'scope.train_denoiser scope.train_text_encoder scope.verification_status seed server '
    'server.caption_extension server.gradient_checkpointing '
    'server.launcher_num_cpu_threads_per_process server.save_model_as server.shuffle_caption '
    'shuffleCaption shuffle_caption t5TokenizerPath t5_tokenizer_path textEncoderLearningRates '
    'textEncoderLr text_encoder text_encoder_learning_rates text_encoder_lr trainTextEncoder '
    'train_text_encoder trainableScope trainable_scope triggerToken trigger_token unet_lr vae version '
    'warmup warmupRatio warmup_ratio workers '
    .split()
)
_DIAGNOSTIC_FIELDS = _DIAGNOSTIC_BASE_FIELDS | frozenset(prefix + '.' + field for prefix in ('recipe', 'body', 'body.recipe', 'policy') for field in _DIAGNOSTIC_BASE_FIELDS if field not in {'body', 'recipe', 'policy'})
_DIAGNOSTIC_FORMS = frozenset(
    'allowUnverifiedCheckpoint allow_unverified_checkpoint anima animaQwen3 animaT5TokenizerPath '
    'animaVae anima_qwen3 anima_t5_tokenizer_path anima_vae batch batchSize batch_size '
    'bucketNoUpscale bucketResoSteps bucket_no_upscale bucket_reso_steps cacheLatents '
    'cacheTextEncoderOutputs cacheToDisk cache_latents cache_text_encoder_outputs cache_to_disk '
    'caching checkpoint classTokens class_tokens dataset denoiserLearningRate denoiser_learning_rate '
    'dit_lr enableBucket enable_bucket epochs execution expectedRecipeHash expected_recipe_hash '
    'family gradientAccumulation gradientAccumulationSteps gradient_accumulation '
    'gradient_accumulation_steps instanceToken instance_token keepTokens keep_tokens learningRate '
    'learning_rate lrScheduler lrSchedulerArgs lrWarmupSteps lr_scheduler lr_scheduler_args '
    'lr_warmup_steps maxBucketReso maxDataLoaderNWorkers max_bucket_reso max_data_loader_n_workers '
    'minBucketReso min_bucket_reso mixedPrecision mixed_precision model modelFamily model_family '
    'networkAlpha networkDim networkModule network_alpha network_dim network_module numRepeats '
    'num_repeats optimization optimizer optimizerArgs optimizerType optimizer_args optimizer_type '
    'persistentDataLoaderWorkers persistentWorkers persistent_data_loader_workers precision qwen3 '
    'resolution saveCadence saveEveryNEpochs save_cadence save_every_n_epochs scheduler schedulerArgs '
    'scheduler_args schemaVersion schema_version scope seed shuffleCaption shuffle_caption '
    't5TokenizerPath t5_tokenizer_path textEncoderLearningRates textEncoderLr '
    'text_encoder_learning_rates text_encoder_lr trainTextEncoder train_text_encoder trainableScope '
    'trainable_scope triggerToken trigger_token unet_lr vae version warmup warmupRatio warmup_ratio '
    'workers '
    .split()
) | frozenset({'JSON object', 'JSON-object string'})
_DIAGNOSTIC_SUGGESTIONS = _DIAGNOSTIC_FORMS | frozenset(field.rsplit('.', 1)[-1] for field in _DIAGNOSTIC_BASE_FIELDS)
_DIAGNOSTIC_ENUMS = frozenset(
    'sd15 sdxl anima no fp16 bf16 fixed random caller preflight_policy server_policy derived steps '
    'ratio unet dit verified unverified unavailable cuda mps cpu unknown source_contract '
    'runtime_verified safetensors networks.lora networks.lora_anima AdamW AdamW8bit Adafactor '
    'constant constant_with_warmup cosine cosine_with_restarts linear polynomial local worker '
    .split()
)
_DIAGNOSTIC_EXPECTATIONS = _DIAGNOSTIC_ENUMS | frozenset({
    "'sd15', 'sdxl' or 'anima'", "'no', 'fp16' or 'bf16'", "'fixed' or 'random'",
    "'caller', 'preflight_policy' or 'server_policy'", "'steps' or 'ratio'",
    "'verified', 'unverified' or 'unavailable'", "'local' or 'worker'",
    "'lora-training-recipe/v1'",
})
_DIAGNOSTIC_TYPES = frozenset(
    'missing extra_forbidden unsupported_value unsupported_field unknown_field conflicting_aliases '
    'alias_conflict bucket_invariant value_error int_type int_parsing bool_type bool_parsing '
    'string_type literal_error greater_than greater_than_equal less_than less_than_equal '
    'string_too_long string_too_short too_long too_short multiple_of finite_number float_type '
    'float_parsing list_type tuple_type dict_type model_type json_invalid invalid_json '
    'object_required invalid_value incompatible_value required_value invalid_count '
    'unsupported_capability '
    .split()
)


def _safe_member(value: Any, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _field_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    # Only optimizer/scheduler and text-encoder-rate collections have indices.
    plain = re.sub(r'\[(\d+)\]', r'.\1', value)
    parts = plain.split('.')
    fields = []
    for index, part in enumerate(parts):
        if part.isdecimal():
            if (len(part) > 7 or int(part) > 1_000_000 or index != len(parts) - 1
                    or index == 0 or parts[index - 1] not in {'optimizer_args', 'lr_scheduler_args', 'text_encoder_learning_rates'}):
                return None
        else:
            fields.append(part)
    return value if '.'.join(fields) in _DIAGNOSTIC_FIELDS else None


def _safe_location(value: Any) -> str | list[str | int] | None:
    if isinstance(value, str):
        return _field_path(value)
    if not isinstance(value, (list, tuple)) or not value:
        return None
    for item in value:
        if type(item) is int:
            if not 0 <= item <= 1_000_000:
                return None
        elif not isinstance(item, str):
            return None
    coordinate = '.'.join(str(item) for item in value)
    return list(value) if _field_path(coordinate) else None


def _safe_constraint_value(key: str, value: Any) -> int | float | str | None:
    if key == 'expected':
        return _safe_member(value, _DIAGNOSTIC_EXPECTATIONS)
    if key in {'max_length', 'min_length'}:
        return value if type(value) is int and 0 <= value <= 1_000_000 else None
    if key not in {'ge', 'gt', 'le', 'lt', 'multiple_of'}:
        return None
    if type(value) not in {int, float} or not 0 <= value <= 2**32 or not math.isfinite(value):
        return None
    return value if key != 'multiple_of' or value > 0 else None


def _safe_constraints(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: safe for key, item in value.items()
            if key in _SAFE_VALIDATION_CONTEXT_KEYS and (safe := _safe_constraint_value(key, item)) is not None}


def _safe_diagnostic_list(value: Any, kind: str) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    if kind in {'fields', 'accepted_fields'}:
        return [item for item in value if _field_path(item) is not None]
    allowed = _DIAGNOSTIC_FORMS if kind == 'accepted_forms' else _DIAGNOSTIC_ENUMS
    return [item for item in value if _safe_member(item, allowed) is not None]


def _safe_validation_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    location = _safe_location(entry.get('loc'))
    if location is not None:
        sanitized['loc'] = location
    error_type = _safe_member(entry.get('type'), _DIAGNOSTIC_TYPES)
    if error_type is not None:
        sanitized['type'] = error_type
    context = _safe_constraints(entry.get('ctx'))
    if context:
        sanitized['ctx'] = context
    return sanitized


def _safe_issue_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key in ('location', 'path', 'field'):
        safe = _safe_location(entry.get(key))
        if safe is not None:
            sanitized[key] = safe
    for key, allowed in (('type', _DIAGNOSTIC_TYPES), ('code', lora_public.ERROR_CODES | _DIAGNOSTIC_TYPES), ('suggestion', _DIAGNOSTIC_SUGGESTIONS)):
        safe = _safe_member(entry.get(key), allowed)
        if safe is not None:
            sanitized[key] = safe
    for key in ('accepted_forms', 'accepted_values', 'fields', 'accepted_fields'):
        safe = _safe_diagnostic_list(entry.get(key), key)
        if safe:
            sanitized[key] = safe
    constraints = _safe_constraints(entry.get('constraints'))
    if constraints:
        sanitized['constraints'] = constraints
    return sanitized


def _safe_error_details(details: Any) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for key, project in (('validation_errors', _safe_validation_entry), ('issues', _safe_issue_entry)):
        entries = details.get(key)
        if isinstance(entries, list):
            sanitized[key] = [safe for entry in entries if isinstance(entry, dict) and (safe := project(entry))]
    for key in ('fields', 'accepted_fields', 'accepted_forms', 'accepted_values'):
        safe = _safe_diagnostic_list(details.get(key), key)
        if safe:
            sanitized[key] = safe
    return sanitized


def _safe_error_code(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value in lora_public.ERROR_CODES else fallback


def _http_error_copy(status_code: int) -> tuple[str, str]:
    if status_code == 404:
        return (
            "Backend could not find the requested LoRA resource",
            "check the identifier or folder and rerun decision preflight",
        )
    if status_code == 409:
        return (
            "Backend rejected the LoRA request",
            "rerun decision preflight with current state before retrying",
        )
    if status_code == 422:
        return (
            "backend request validation failed",
            "correct the listed fields and retry",
        )
    if status_code >= 500:
        return (
            "Backend could not complete the LoRA request",
            "check Backend health and logs before retrying",
        )
    return (
        "Backend rejected the LoRA request",
        "correct the referenced fields and rerun decision preflight",
    )


def _error(
    tool: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    hint: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "classification": "backend_failure",
        "phase": "request",
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
            "details": details or {},
        },
    }


def _backend_error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status_code = exc.response.status_code
        try:
            payload = exc.response.json()
        except (ValueError, RecursionError):
            payload = {}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        if status_code == 422 and isinstance(detail, list):
            validation_errors = [
                _safe_validation_entry(entry)
                for entry in detail
                if isinstance(entry, dict)
            ]
            code = "request_validation_failed"
            message, hint = _http_error_copy(status_code)
            details = {"validation_errors": validation_errors}
        elif isinstance(detail, dict):
            code = _safe_error_code(detail.get("code"), f"http_{status_code}")
            message, hint = _http_error_copy(status_code)
            details = _safe_error_details(detail.get("details"))
        else:
            code = f"http_{status_code}"
            message, hint = _http_error_copy(status_code)
            details = {}
        result = _error(tool, code, message, details, hint=hint)
        result["status_code"] = status_code
        if status_code == 503 and code == "admission_uncertain":
            result["classification"] = "admission_uncertain"
            result["error"]["message"] = "A training submission may already exist; scheduling is unconfirmed"
            result["error"]["hint"] = "Check the recorded canonical job_id first; do not resubmit this training request automatically."
            job_id = detail.get("job_id") if isinstance(detail, dict) else None
            if isinstance(job_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
                result["job_id"] = job_id
                result["error"]["job_id"] = job_id
        return result
    return _error(
        tool,
        "backend_unavailable",
        "Backend is unavailable",
        {"where": "backend"},
        hint="check Backend availability and retry when it is reachable",
    )


def _failure_from_backend_payload(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    errors = payload.get("errors")
    first_error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
    code = _safe_error_code(
        payload.get("error_code") or first_error.get("code"),
        "backend_failed",
    )
    details = _safe_error_details(payload.get("details"))
    if not details and first_error:
        safe_issue = _safe_issue_entry(first_error)
        if safe_issue:
            details = {"issues": [safe_issue]}
    return _error(
        tool,
        code,
        "Backend reported a LoRA operation failure",
        details,
        hint="repair the cause identified by the error code before retrying",
    )


def _backend_result(tool: str, payload: dict[str, Any], submitted: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload.get("ok") is False:
        result = _failure_from_backend_payload(tool, payload)
    else:
        result = {"ok": True, "tool": tool}
        result.update(payload)
        result["ok"] = True
        result["tool"] = tool
    if submitted is not None:
        result["submitted"] = submitted
    return result


def _strict_backend_result(
    tool: str,
    payload: dict[str, Any],
    allowed_fields: frozenset[str],
) -> dict[str, Any]:
    if payload.get("ok") is False:
        return _failure_from_backend_payload(tool, payload)
    payload = lora_public.status(payload)
    return {
        "ok": True,
        "tool": tool,
        **{
            key: payload[key]
            for key in sorted(allowed_fields)
            if key in payload
        },
    }


def _compact(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


def caption_image(image_path: str) -> dict[str, Any]:
    """Generate one caption through the backend LLM caption endpoint."""
    tool = "caption_image"
    try:
        client = _get_client()
        resp = client.post(f"lora-docs/caption-llm/{quote(image_path.strip().strip('/'), safe='/')}")
        caption_text = resp.get("content", "")
        if not caption_text:
            return _error(tool, "empty_caption", "LLM returned an empty caption", {"response": resp})
        return _backend_result(tool, {"content": caption_text})
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_training_decision_preflight(
    folder: str,
    output_name: str,
    trigger_token: str | None = None,
    expected_dataset_hash: str | None = None,
    expected_profile_hash: str | None = None,
    recipe: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Run non-starting preflight with optional recipe object or JSON object string aliases."""
    tool = "lora_training_decision_preflight"
    body = _compact(
        {
            "folder": folder,
            "output_name": output_name,
            "trigger_token": trigger_token,
            "expected_dataset_hash": expected_dataset_hash,
            "expected_profile_hash": expected_profile_hash,
            "recipe": recipe,
        }
    )
    try:
        return _strict_backend_result(
            tool,
            _get_client().post("lora-train/datasets/training-decision-preflight", json=body),
            _PREFLIGHT_SUCCESS_FIELDS,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_train_start(
    folder: str,
    output_name: str,
    *,
    expected_dataset_hash: str,
    expected_profile_hash: str,
    expected_output_config_hash: str | None = None,
    recipe: dict[str, Any] | str,
) -> dict[str, Any]:
    """Start from folder, both approval hashes, and a recipe object or JSON object string.

    The Backend is the sole normalization authority. Documented snake/camel
    aliases and lossless scalar coercions are forwarded unchanged; success
    returns the canonical requested/effective recipe identity.
    """
    tool = "lora_train_start"
    body = {
        "folder": folder,
        "output_name": output_name,
        "expected_output_config_hash": expected_output_config_hash,
        "expected_dataset_hash": expected_dataset_hash,
        "expected_profile_hash": expected_profile_hash,
        "recipe": recipe,
    }
    try:
        return _strict_backend_result(
            tool,
            _get_client().post("lora-train/start", json=_compact(body)),
            _START_SUCCESS_FIELDS,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_train_job_status(job_id: str) -> dict[str, Any]:
    """Read a durable training job and reconcile its smoke image; never submits."""
    tool = "lora_train_job_status"
    try:
        return _strict_backend_result(
            tool,
            _get_client().get(f"lora-train/jobs/{quote(job_id)}"),
            _STATUS_SUCCESS_FIELDS,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_train_logs(job_id: str, lines: int = 100) -> dict[str, Any]:
    """Retrieve bounded logs for one LoRA training job."""
    tool = "lora_train_logs"
    params = {"lines": lines}
    try:
        return _backend_result(tool, lora_public.logs(_get_client().get(f"lora-train/jobs/{quote(job_id)}/logs", params=params)))
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_train_cancel(job_id: str) -> dict[str, Any]:
    """Cancel a queued or running LoRA training job."""
    tool = "lora_train_cancel"
    try:
        return _backend_result(tool, _get_client().post(f"lora-train/jobs/{quote(job_id)}/cancel", json={}))
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_dataset_list() -> dict[str, Any]:
    """List LoRA training datasets with image/caption/hash/lock summary so an agent can choose work."""
    tool = "lora_dataset_list"
    try:
        return _backend_result(tool, _get_client().get("lora-train/datasets"))
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_dataset_inspect(folder: str) -> dict[str, Any]:
    """Inspect one LoRA dataset (agent-ready: profile summary, caption suitability, dataset/profile hashes)."""
    tool = "lora_dataset_inspect"
    try:
        path = quote(folder.strip().strip("/"), safe="/")
        return _backend_result(tool, _get_client().get(f"lora-train/datasets/{path}/agent-inspect"))
    except Exception as exc:
        return _backend_error(tool, exc)


def lora_train_smoke_test(
    job_id: str,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    checkpoint: str | None = None,
    execution_target: Literal["local", "worker"] = "local",
) -> dict[str, Any]:
    """Submit once, or return the existing smoke job/result for this training job.

    For Anima (diffusion-model family) jobs the diffusion_model / text_encoder / vae
    overrides take precedence; unset values are derived from the training job params.
    """
    tool = "lora_train_smoke_test"
    body = _compact(
        {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "diffusion_model": diffusion_model,
            "text_encoder": text_encoder,
            "vae": vae,
            "checkpoint": checkpoint,
            "execution_target": execution_target,
        }
    )
    try:
        payload = _get_client().post(f"lora-train/jobs/{quote(job_id)}/smoke-test", json=body)
        if payload.get('ok') is False:
            return _failure_from_backend_payload(tool, payload)
        public = lora_public.smoke(payload)
        allowed = {'job_id','registered_lora_name','smoke_test_status','generation_job_id',
                   'artifact','artifact_id','image_id','artifact_url','error','error_code','hint'}
        result = {key:value for key,value in public.items() if key in allowed}
        if result.get('registered_lora_name'):
            result['registered_lora_name'] = lora_public.locator(result['registered_lora_name'])
        return _backend_result(tool, result, submitted=body)
    except Exception as exc:
        return _backend_error(tool, exc)
