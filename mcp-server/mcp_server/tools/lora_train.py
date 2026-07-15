"""
LoRA training MCP tools.

These tools are thin clients for the backend-owned LoRA training workflow.
Results are JSON-serializable dicts so agents can branch without scraping
human-readable strings. Dataset preparation/curation stays available through
the backend HTTP API; the MCP surface keeps only the decision-and-train loop.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from mcp_server.server import _get_client, mcp


def _error(tool: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _backend_error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status_code = exc.response.status_code
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {"detail": exc.response.text}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            code = str(detail.get("code") or f"http_{status_code}")
            message = str(detail.get("message") or detail.get("error") or exc)
            details = detail.get("details")
            if not isinstance(details, dict):
                details = {k: v for k, v in detail.items() if k not in {"code", "message", "error"}}
        else:
            code = f"http_{status_code}"
            message = str(detail or exc)
            details = {}
        result = _error(tool, code, message, details)
        result["status_code"] = status_code
        return result
    return _error(tool, exc.__class__.__name__, str(exc), {"where": "backend"})


def _failure_from_backend_payload(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    errors = payload.get("errors")
    first_error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
    code = str(payload.get("error_code") or first_error.get("code") or "backend_failed")
    message = str(
        payload.get("error_message")
        or first_error.get("message")
        or payload.get("message")
        or "backend returned ok=false"
    )
    result = {k: v for k, v in payload.items() if k not in {"ok", "error_code", "error_message"}}
    result.update(_error(tool, code, message, {"response": payload}))
    return result


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
) -> dict[str, Any]:
    """Run backend LoRA training decision preflight without starting training."""
    tool = "lora_training_decision_preflight"
    body = _compact(
        {
            "folder": folder,
            "trigger_token": trigger_token,
            "expected_dataset_hash": expected_dataset_hash,
            "expected_profile_hash": expected_profile_hash,
        }
    )
    try:
        return _backend_result(
            tool,
            _get_client().post("lora-train/datasets/training-decision-preflight", json=body),
            submitted=body,
        )
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_train_start(
    folder: str,
    checkpoint: str | None = None,
    epochs: int | None = None,
    class_tokens: str | None = None,
    resolution: int | None = None,
    keep_tokens: int | None = None,
    mixed_precision: str | None = None,
    network_module: str | None = None,
    network_dim: int | None = None,
    network_alpha: int | None = None,
    num_repeats: int | None = None,
    learning_rate: str | None = None,
    trigger_token: str | None = None,
    expected_dataset_hash: str | None = None,
    model_family: str | None = None,
    anima_qwen3: str | None = None,
    anima_vae: str | None = None,
    anima_t5_tokenizer_path: str | None = None,
    sdxl: bool | None = None,
) -> dict[str, Any]:
    """Start a backend-managed LoRA training job."""
    tool = "lora_train_start"
    body = _compact(
        {
            "folder": folder,
            "checkpoint": checkpoint,
            "epochs": epochs,
            "class_tokens": class_tokens.strip() if class_tokens else None,
            "resolution": resolution,
            "keep_tokens": keep_tokens,
            "mixed_precision": mixed_precision,
            "network_module": network_module,
            "network_dim": network_dim,
            "network_alpha": network_alpha,
            "num_repeats": num_repeats,
            "learning_rate": learning_rate,
            "trigger_token": trigger_token,
            "expected_dataset_hash": expected_dataset_hash,
            "model_family": model_family,
            "anima_qwen3": anima_qwen3,
            "anima_vae": anima_vae,
            "anima_t5_tokenizer_path": anima_t5_tokenizer_path,
            "sdxl": sdxl,
        }
    )
    try:
        return _backend_result(tool, _get_client().post("lora-train/start", json=body), submitted=body)
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def lora_train_job_status(job_id: str) -> dict[str, Any]:
    """Query one durable LoRA training job by job_id."""
    tool = "lora_train_job_status"
    try:
        return _backend_result(tool, _get_client().get(f"lora-train/jobs/{quote(job_id)}"))
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
