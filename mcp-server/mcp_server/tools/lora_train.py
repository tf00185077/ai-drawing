"""
LoRA training MCP tools.

These tools are thin clients for the backend-owned LoRA training workflow.
Results are JSON-serializable dicts so agents can branch without scraping
human-readable strings. Dataset preparation/curation stays available through
the backend HTTP API; the MCP surface keeps only the decision-and-train loop.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import quote

import httpx

from mcp_server.server import _get_client, mcp


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
        "folder",
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
        "job_id",
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
        "job_id",
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
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "cancel_requested_at",
    }
)


def _safe_validation_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    location = _safe_location(entry.get("loc"))
    if location is not None:
        sanitized["loc"] = location
    error_type = _safe_identifier(entry.get("type"))
    if error_type is not None:
        sanitized["type"] = error_type
    context = entry.get("ctx")
    if isinstance(context, dict):
        safe_context = {
            key: safe_value
            for key, value in context.items()
            if key in _SAFE_VALIDATION_CONTEXT_KEYS
            and (safe_value := _safe_constraint_value(value)) is not None
        }
        if safe_context:
            sanitized["ctx"] = safe_context
    return sanitized


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.\[\]-]{1,128}$")


def _safe_identifier(value: Any) -> str | None:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
        return None
    return value


def _safe_location(value: Any) -> str | list[str | int] | None:
    if isinstance(value, str):
        return _safe_identifier(value)
    if not isinstance(value, (list, tuple)):
        return None
    result: list[str | int] = []
    for item in value:
        if isinstance(item, int):
            result.append(item)
        else:
            safe_item = _safe_identifier(item)
            if safe_item is None:
                return None
            result.append(safe_item)
    return result


def _safe_constraint_value(value: Any) -> bool | int | float | str | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_identifier(value)


def _safe_identifier_list(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    result = [_safe_identifier(item) for item in value]
    if any(item is None for item in result):
        return None
    return [item for item in result if item is not None]


def _safe_issue_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key in ("location", "path", "field"):
        safe_value = _safe_location(entry.get(key))
        if safe_value is not None:
            sanitized[key] = safe_value
    for key in ("type", "code", "suggestion"):
        safe_value = _safe_identifier(entry.get(key))
        if safe_value is not None:
            sanitized[key] = safe_value
    for key in ("accepted_forms", "accepted_values", "fields"):
        safe_value = _safe_identifier_list(entry.get(key))
        if safe_value is not None:
            sanitized[key] = safe_value
    constraints = entry.get("constraints")
    if isinstance(constraints, dict):
        safe_constraints = {
            key: safe_value
            for key, value in constraints.items()
            if (safe_key := _safe_identifier(key)) is not None
            and (safe_value := _safe_constraint_value(value)) is not None
        }
        if safe_constraints:
            sanitized["constraints"] = safe_constraints
    return sanitized


def _safe_error_details(details: Any) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    sanitized: dict[str, Any] = {}
    validation_errors = details.get("validation_errors")
    if isinstance(validation_errors, list):
        sanitized["validation_errors"] = [
            safe
            for entry in validation_errors
            if isinstance(entry, dict)
            and (safe := _safe_validation_entry(entry))
        ]
    issues = details.get("issues")
    if isinstance(issues, list):
        sanitized["issues"] = [
            safe
            for entry in issues
            if isinstance(entry, dict)
            and (safe := _safe_issue_entry(entry))
        ]
    for key in ("fields", "accepted_forms", "accepted_values"):
        safe_value = _safe_identifier_list(details.get(key))
        if safe_value is not None:
            sanitized[key] = safe_value
    return sanitized


def _safe_error_code(value: Any, fallback: str) -> str:
    return _safe_identifier(value) or fallback


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
        except ValueError:
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


@mcp.tool()
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


@mcp.tool()
def lora_training_decision_preflight(
    folder: str,
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


@mcp.tool()
def lora_train_start(
    folder: str,
    *,
    expected_dataset_hash: str,
    expected_profile_hash: str,
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
        "expected_dataset_hash": expected_dataset_hash,
        "expected_profile_hash": expected_profile_hash,
        "recipe": recipe,
    }
    try:
        return _strict_backend_result(
            tool,
            _get_client().post("lora-train/start", json=body),
            _START_SUCCESS_FIELDS,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_train_job_status(job_id: str) -> dict[str, Any]:
    """Query one durable LoRA training job by job_id."""
    tool = "lora_train_job_status"
    try:
        return _strict_backend_result(
            tool,
            _get_client().get(f"lora-train/jobs/{quote(job_id)}"),
            _STATUS_SUCCESS_FIELDS,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_train_logs(job_id: str, lines: int = 100) -> dict[str, Any]:
    """Retrieve bounded logs for one LoRA training job."""
    tool = "lora_train_logs"
    params = {"lines": lines}
    try:
        return _backend_result(tool, _get_client().get(f"lora-train/jobs/{quote(job_id)}/logs", params=params))
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_train_cancel(job_id: str) -> dict[str, Any]:
    """Cancel a queued or running LoRA training job."""
    tool = "lora_train_cancel"
    try:
        return _backend_result(tool, _get_client().post(f"lora-train/jobs/{quote(job_id)}/cancel", json={}))
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_dataset_list() -> dict[str, Any]:
    """List LoRA training datasets with image/caption/hash/lock summary so an agent can choose work."""
    tool = "lora_dataset_list"
    try:
        return _backend_result(tool, _get_client().get("lora-train/datasets"))
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_dataset_inspect(folder: str) -> dict[str, Any]:
    """Inspect one LoRA dataset (agent-ready: profile summary, caption suitability, dataset/profile hashes)."""
    tool = "lora_dataset_inspect"
    try:
        path = quote(folder.strip().strip("/"), safe="/")
        return _backend_result(tool, _get_client().get(f"lora-train/datasets/{path}/agent-inspect"))
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
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
    """Run a backend smoke test for a completed, registered LoRA job.

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
        return _backend_result(
            tool,
            _get_client().post(f"lora-train/jobs/{quote(job_id)}/smoke-test", json=body),
            submitted=body,
        )
    except Exception as exc:
        return _backend_error(tool, exc)
