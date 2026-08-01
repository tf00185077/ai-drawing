"""Paired NVIDIA Worker status surface."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.services.nvidia_worker import get_worker_client
from app.services.nvidia_worker_update import worker_update_status

router = APIRouter(prefix="/api/workers", tags=["NVIDIA Worker"])


@router.post("/restart", status_code=202)
def restart_worker() -> dict:
    """Explicit Mac operator entry point; accepts no command or path selector."""
    try:
        return get_worker_client().request_restart()
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_restart_request_failed"}
        ) from error


@router.get("/restart/status")
def restart_worker_status(
    request_id: str = Query(..., min_length=1, max_length=64),
) -> dict:
    """Close the Mac restart loop with the exact Worker request correlation."""
    try:
        status = get_worker_client().restart_status(request_id)
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_restart_status_failed"}
        ) from error
    if (
        not isinstance(status, dict)
        or status.get("request_id") != request_id
        or status.get("state")
        not in {"queued", "restarting", "verifying", "ready", "failed", "timed_out"}
        or not isinstance(status.get("timestamp"), str)
        or not status["timestamp"]
    ):
        raise HTTPException(
            502, detail={"code": "worker_restart_status_invalid"}
        )
    return status


@router.get("/status")
def worker_status() -> dict:
    settings = get_settings()
    configured = bool(settings.nvidia_worker_url and settings.nvidia_worker_token)
    update = worker_update_status()
    auto_update = {
        "enabled": bool(getattr(settings, "nvidia_worker_auto_update", False)),
        "state": update["state"],
        "error_code": update["error_code"],
    }
    if not configured:
        return {
            "configured": False,
            "reachable": False,
            "status": "not_paired",
            "auto_update": auto_update,
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
            "auto_update": auto_update,
        }
    return {
        "configured": True,
        "reachable": True,
        "status": "ready",
        "worker": status,
        "auto_update": auto_update,
    }
