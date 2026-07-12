"""CIV-F thin, structured MCP wrappers for backend-owned Civitai recipe contracts."""
from __future__ import annotations

import base64
from typing import Any

import httpx

from mcp_server.server import _get_client, mcp


def _error(tool: str, code: str, message: str, details: dict[str, Any] | None = None, *, status_code: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "tool": tool, "error": {"code": code, "message": message, "details": details or {}}}
    if status_code is not None:
        result["status_code"] = status_code
    return result


def _backend_error(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            payload = exc.response.json()
        except ValueError:
            payload = {"detail": exc.response.text}
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            code = str(detail.get("code") or f"http_{exc.response.status_code}")
            message = str(detail.get("message") or detail.get("error") or exc)
            details = {key: value for key, value in detail.items() if key not in {"code", "message", "error"}}
        else:
            # FastAPI validation errors are often list[dict]; retain their exact
            # diagnostic structure rather than collapsing it into a message.
            code, message, details = f"http_{exc.response.status_code}", str(detail or exc), {"detail": detail}
        return _error(tool, code, message, details, status_code=exc.response.status_code)
    return _error(tool, exc.__class__.__name__, str(exc), {"where": "backend"})


def _result(tool: str, payload: dict[str, Any], next_step: str) -> dict[str, Any]:
    if payload.get("ok") is False:
        return _error(tool, str(payload.get("error_code") or "backend_failed"), str(payload.get("error_message") or payload.get("message") or "backend returned ok=false"), {"response": payload})
    return {"ok": True, "tool": tool, "data": payload, "next": next_step}


def _post(tool: str, endpoint: str, body: dict[str, Any], next_step: str) -> dict[str, Any]:
    try:
        return _result(tool, _get_client().post(endpoint, json=body), next_step)
    except Exception as exc:
        return _backend_error(tool, exc)


@mcp.tool()
def civitai_recipe_import(locator: int | str, embedded_image: bytes | str | None = None) -> dict[str, Any]:
    """Acquire a Civitai locator into raw acquisition evidence, GenerationRecipe 1.0, and reproduction diagnostics."""
    body: dict[str, Any] = {"locator": locator}
    if embedded_image is not None:
        if isinstance(embedded_image, str):
            try:
                image_bytes = base64.b64decode(embedded_image, validate=True)
            except (ValueError, TypeError) as exc:
                return _error(
                    "civitai_recipe_import", "invalid_embedded_image_base64",
                    "embedded_image must be valid base64 when sent over JSON/MCP",
                    {"where": "mcp_input", "error_type": exc.__class__.__name__},
                )
        else:
            image_bytes = embedded_image
        body["embedded_image_base64"] = base64.b64encode(image_bytes).decode("ascii")
    return _post("civitai_recipe_import", "civitai-recipes/import", body, "inspect the recipe, then resolve its local resources")


@mcp.tool()
def civitai_recipe_inspect(recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate a GenerationRecipe 1.0 without network, disk writes, or queue submission."""
    return _post("civitai_recipe_inspect", "civitai-recipes/inspect", {"recipe": recipe}, "resolve only against a caller-supplied local ledger")


@mcp.tool()
def civitai_recipe_resolve(recipe: dict[str, Any], ledger: list[dict[str, Any]], strict: bool = True) -> dict[str, Any]:
    """Resolve ordered recipe resources against a caller-provided local ledger; strict failures stay errors."""
    return _post("civitai_recipe_resolve", "civitai-recipes/resolve", {"recipe": recipe, "ledger": ledger, "strict": strict}, "if strict resolution succeeds, build the SDXL/Illustrious workflow")


@mcp.tool()
def civitai_recipe_build(recipe: dict[str, Any], resource_report: dict[str, Any], model_family: str, input_bindings: dict[str, Any]) -> dict[str, Any]:
    """Compile a strict resolved SDXL/Illustrious recipe into a locked ComfyUI workflow."""
    return _post("civitai_recipe_build", "civitai-recipes/build", {"recipe": recipe, "resource_report": resource_report, "model_family": model_family, "input_bindings": input_bindings}, "submit the returned build artifact with runtime provenance")


@mcp.tool()
def civitai_recipe_run(build: dict[str, Any], runtime_provenance: dict[str, Any], queue_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a CIV-E provenance bundle from a successful build, then submit the existing custom-workflow queue."""
    return _post("civitai_recipe_run", "civitai-recipes/run", {"build": build, "runtime_provenance": runtime_provenance, "queue_params": queue_params or {}}, "call get_generation_status with the returned job_id")


@mcp.tool()
def civitai_recipe_export(image_id: int) -> dict[str, Any]:
    """Export the existing gallery recipe bundle with recipe/workflow/input/resource/runtime hashes intact."""
    tool = "civitai_recipe_export"
    try:
        payload = _get_client().get(f"gallery/{image_id}/export", params={"format": "recipe"})
        return _result(tool, payload, "the exported bundle can be audited or rerun through the gallery contract")
    except Exception as exc:
        return _backend_error(tool, exc)
