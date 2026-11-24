"""Read-only health and configured-worker visibility from authoritative Backend reads."""
from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mcp_server.client import HttpBackendClient
from mcp_server.config import get_mcp_settings


class _Status(BaseModel):
    model_config = ConfigDict(strict=True)


class _BackendStatus(_Status):
    status: Literal["healthy"]


class _ComfyUIStatus(_Status):
    mode: Literal["disabled", "external", "managed"]
    state: Literal["connected", "not_configured", "unreachable", "no_models", "degraded"]
    configured: bool
    reachable: bool
    model_count: int = Field(ge=0)
    checkpoint_count: int = Field(ge=0)
    diffusion_model_count: int = Field(ge=0)
    warnings: list[str]
    hint: str

    @model_validator(mode="after")
    def consistent_state(self):
        if self.configured != (self.state != "not_configured") or self.reachable != (self.state in {"connected", "no_models", "degraded"}):
            raise ValueError("Inconsistent ComfyUI status")
        return self


class _SystemStatus(_Status):
    application: Literal["healthy"]
    comfyui: _ComfyUIStatus


class _WorkerStatus(_Status):
    configured: bool
    reachable: bool
    status: Literal["not_configured", "ready", "unavailable"]
    url: str | None = None
    expected_hostname: str | None = None
    expected_protocol_version: int | None = Field(default=None, ge=1)
    hostname: str | None = None
    protocol_version: int | None = Field(default=None, ge=1)
    resolved_url: str | None = None
    last_error: str | None = None

    @model_validator(mode="after")
    def consistent_observation(self):
        observed = (self.hostname, self.protocol_version, self.resolved_url)
        if not self.configured:
            if self.reachable or self.status != "not_configured" or self.url is not None or any(value is not None for value in observed) or self.last_error is not None:
                raise ValueError("Inconsistent unconfigured worker status")
        elif not self.url or not self.url.strip() or self.expected_protocol_version is None:
            raise ValueError("Missing worker configuration")
        elif self.reachable:
            if self.status != "ready" or self.last_error is not None or not self.resolved_url or not self.resolved_url.strip() or self.protocol_version != self.expected_protocol_version:
                raise ValueError("Missing accepted worker observation")
            if self.expected_hostname and (not self.hostname or self.hostname.casefold() != self.expected_hostname.casefold()):
                raise ValueError("Worker observation does not match expected hostname")
        elif self.status != "unavailable" or not self.last_error or not self.last_error.strip() or any(value is not None for value in observed):
            raise ValueError("Failed worker probe must have a reason and no current observations")
        return self


_READ_HINT = "Inspect Backend availability and status/configuration, then retry this read; no job submission is needed."


def _read(client: HttpBackendClient, path: str, schema: type[_Status]) -> tuple[Any, dict[str, Any] | None]:
    """Validate each authoritative read independently; never expose raw error bodies."""
    try:
        return schema.model_validate(client.get(path)), None
    except httpx.HTTPStatusError as exc:
        code, message = "backend_http_error", f"HTTP {exc.response.status_code}: Backend status read failed."
    except httpx.RequestError:
        code, message = "backend_unavailable", "Backend status connection failed."
    except ValueError:
        code, message = "invalid_backend_status", "Backend status response is missing, invalid or inconsistent."
    except Exception:
        code, message = "tool_execution_failed", "Backend status read could not be completed."
    return None, {"code": code, "message": message, "hint": _READ_HINT}


def _client() -> HttpBackendClient:
    # /health is outside /api. All three reads share this configured Backend;
    # direct-admin MCP_COMFYUI_API_URL is deliberately unrelated to health.
    return HttpBackendClient(get_mcp_settings().backend_api_url, timeout=5.0)


def _not_observed(component: str, error: dict[str, Any]) -> dict[str, Any]:
    return {"configured": None, "reachable": False, "reason_code": "not_observed",
            "reason": f"{component} was not observed through the Backend; no failed dependency probe is established.",
            "read_error": error}


def health() -> dict[str, Any]:
    """Read Backend, Backend-local ComfyUI and worker reachability. Keep all three entries on failed/partial reads; no direct dependency fallback or readiness certification."""
    client = _client()
    _, error = _read(client, "/health", _BackendStatus)
    if error:
        return {"backend": {"reachable": False, "reason_code": error["code"], "reason": error["message"], "read_error": error},
                "comfyui": _not_observed("Backend-local ComfyUI", error),
                "worker": _not_observed("Worker", error)}

    data: dict[str, Any] = {"backend": {"reachable": True, "reason": None}}
    system, error = _read(client, "/api/system/status", _SystemStatus)
    if error:
        data["comfyui"] = _not_observed("Backend-local ComfyUI", error)
    else:
        comfyui = system.comfyui.model_dump()
        comfyui.update(reason=None if comfyui["reachable"] else
                       "Backend reports ComfyUI is not configured." if not comfyui["configured"] else "Backend reports its local ComfyUI probe failed.")
        if not comfyui["reachable"]:
            comfyui["reason_code"] = "reported_unreachable" if comfyui["configured"] else "not_configured"
        data["comfyui"] = comfyui

    worker, error = _read(client, "/api/workers/status", _WorkerStatus)
    if error:
        data["worker"] = _not_observed("Worker", error)
    else:
        data["worker"] = {"configured": worker.configured, "reachable": worker.reachable, "status": worker.status,
                          "reason": None if worker.reachable else worker.last_error if worker.configured else "Backend reports no worker is configured."}
        if not worker.reachable:
            data["worker"]["reason_code"] = "reported_unreachable" if worker.configured else "not_configured"
    return data


def list_workers() -> dict[str, Any]:
    """Read the one configured worker, even when unavailable. Separate configured/expected identity from accepted current observations. Only an authoritative unconfigured response yields an empty list."""
    status, error = _read(_client(), "/api/workers/status", _WorkerStatus)
    if error:
        return {"ok": False, "error": error}
    if not status.configured:
        return {"workers": []}
    worker = status.model_dump(exclude={"configured"})
    return {"workers": [worker]}
