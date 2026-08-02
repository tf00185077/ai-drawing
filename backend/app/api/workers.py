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
    if not configured:
        return {
            "configured": False,
            "reachable": False,
            "status": "not_configured",
        }
    try:
        # Use the same discovery-aware runtime factory as generation. This
        # keeps status and every Worker HTTP endpoint on one resolved URL.
        status = get_worker_client().health()
    except Exception as error:
        return {
            "configured": True,
            "reachable": False,
            "status": "unavailable",
            "error_type": type(error).__name__,
        }
    return {
        "configured": True,
        "reachable": True,
        "status": "ready",
        "worker": status,
    }
