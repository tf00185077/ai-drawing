"""Civitai MCP tools — the best-effort "see it, make it mine" flow.

Four intent-level tools backed by /api/civitai/*:

- civitai_source_info:     preview a Civitai image's prompt/params/resources
- civitai_generate_like:   generate with that image's parameters and your prompt
- civitai_resource_acquire: download a model/LoRA to the local model library
- civitai_resource_status:  poll download progress / list recent resources

The backend owns all state; these tools only pass locators, prompts, and IDs.
"""
from __future__ import annotations

from typing import Any

import httpx

from mcp_server.server import _get_client, mcp


def _error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {"detail": exc.response.text}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            return {
                "ok": False,
                "tool": tool,
                "error": {
                    "code": str(detail.get("code") or f"http_{exc.response.status_code}"),
                    "message": str(detail.get("message") or detail),
                    "hint": detail.get("hint"),
                },
            }
        return {"ok": False, "tool": tool, "error": {"code": f"http_{exc.response.status_code}", "message": str(detail)}}
    return {"ok": False, "tool": tool, "error": {"code": exc.__class__.__name__, "message": str(exc)}}


def _result(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": tool, **payload}


@mcp.tool()
def civitai_source_info(source: str) -> dict[str, Any]:
    """Preview a Civitai image's generation parameters and local availability.

    source: a civitai.com/images/<id> URL or a bare image ID. Returns the
    original prompt/negative prompt/sampling settings, the resources it used,
    and a local plan (which checkpoint/LoRAs are available locally, what would
    be substituted, what could be downloaded). Read-only — call this first to
    discuss options with the user, then call civitai_generate_like.
    """
    tool = "civitai_source_info"
    try:
        return _result(tool, _get_client().get("civitai/source-info", params={"locator": source}))
    except Exception as exc:
        return _error(tool, exc)


@mcp.tool()
def civitai_generate_like(
    source: str,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    batch_size: int | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    checkpoint: str | None = None,
    download_missing: bool = True,
) -> dict[str, Any]:
    """Generate images based on a Civitai image's recipe, with your own prompt.

    source: civitai.com/images/<id> URL or bare image ID. prompt replaces the
    original positive prompt (omit it to reuse the original); sampler, steps,
    cfg, size, and negative prompt follow the source unless overridden. Missing
    models are downloaded automatically by default (status="acquiring_resources"
    with next_step instructions); pass download_missing=false to substitute the
    closest local model immediately. Generates a batch (default 4) because the
    source image is usually one hand-picked result out of many seeds — expect
    to pick a favourite and iterate. Returns job_id; poll get_generation_status.
    """
    tool = "civitai_generate_like"
    body: dict[str, Any] = {"locator": source, "download_missing": download_missing}
    optional = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "batch_size": batch_size,
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "width": width,
        "height": height,
        "checkpoint": checkpoint,
    }
    body.update({key: value for key, value in optional.items() if value is not None})
    try:
        return _result(tool, _get_client().post("civitai/generate-like", json=body))
    except Exception as exc:
        return _error(tool, exc)


@mcp.tool()
def civitai_resource_acquire(source: str) -> dict[str, Any]:
    """Download a Civitai model/LoRA to the local model library (external disk).

    source: a civitai.com/models/<id> URL (optionally with modelVersionId), a
    bare model ID, or a model-version ID. The download runs in the background
    and is verified against the published SHA-256; virus-scan failures are
    refused. Incomplete license metadata is recorded as a warning, not a
    blocker. Returns an acquisition_id — poll civitai_resource_status.
    """
    tool = "civitai_resource_acquire"
    try:
        return _result(tool, _get_client().post("civitai/resources/acquire", json={"locator": source}))
    except Exception as exc:
        return _error(tool, exc)


@mcp.tool()
def civitai_resource_status(acquisition_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    """Check Civitai download progress, or list recent local resources.

    With acquisition_id: that resource's status (downloading with percent /
    installed / failed). Without it: the most recent resources. A resource with
    status=installed is ready for generation.
    """
    tool = "civitai_resource_status"
    params: dict[str, Any] = {"limit": limit}
    if acquisition_id is not None:
        params["acquisition_id"] = acquisition_id
    try:
        return _result(tool, _get_client().get("civitai/resources/status", params=params))
    except Exception as exc:
        return _error(tool, exc)
