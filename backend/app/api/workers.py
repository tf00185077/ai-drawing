"""Open NVIDIA Worker PowerShell control and URL-only discovery status."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.services.nvidia_worker import get_worker_client

router = APIRouter(prefix="/api/workers", tags=["NVIDIA Worker"])


class PowerShellCommandRequest(BaseModel):
    script: str
    working_directory: str | None = None


@router.post("/powershell/commands", status_code=202)
def submit_powershell_command(request: PowerShellCommandRequest) -> dict:
    try:
        return get_worker_client().submit_powershell(
            request.script,
            working_directory=request.working_directory,
        )
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_powershell_submit_failed"}
        ) from error


@router.get("/powershell/commands/{command_id:path}")
def powershell_command_status(command_id: str) -> dict:
    try:
        return get_worker_client().powershell_status(command_id)
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_powershell_status_failed"}
        ) from error


@router.post("/powershell/commands/{command_id:path}/cancel")
def cancel_powershell_command(command_id: str) -> dict:
    try:
        return get_worker_client().cancel_powershell(command_id)
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_powershell_cancel_failed"}
        ) from error


@router.get("/status")
def worker_status() -> dict:
    settings = get_settings()
    configured = bool(settings.nvidia_worker_url)
    # Configuration is authoritative even when the current probe fails. Never
    # populate observations from the discovery cache or expected identity.
    visibility = {
        "url": settings.nvidia_worker_url.rstrip("/") if configured else None,
        "expected_hostname": getattr(settings, "nvidia_worker_hostname", "") or None,
        "expected_protocol_version": getattr(settings, "nvidia_worker_protocol_version", 2),
        "hostname": None,
        "protocol_version": None,
        "resolved_url": None,
        "last_error": None,
    }
    if not configured:
        return {
            **visibility,
            "configured": False,
            "reachable": False,
            "status": "not_configured",
        }
    try:
        # Use the same discovery-aware runtime factory as generation. This
        # keeps status and every Worker HTTP endpoint on one resolved URL.
        client = get_worker_client()
        status = client.health()
    except Exception as error:
        return {
            **visibility,
            "configured": True,
            "reachable": False,
            "status": "unavailable",
            "error_type": type(error).__name__,
            "last_error": "Worker status probe failed; inspect Backend NVIDIA_WORKER_URL, expected hostname/protocol and worker availability, then retry this read.",
        }
    return {
        **visibility,
        "configured": True,
        "reachable": True,
        "status": "ready",
        "worker": status,
        "hostname": status.get("hostname"),
        "protocol_version": status.get("protocol_version"),
        # This request-local client has just accepted the probe. Its base_url
        # includes any existing discovery resolution used by that same call.
        "resolved_url": client.base_url,
    }
