"""Paired NVIDIA Worker status surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.nvidia_worker import get_worker_client
from app.services.nvidia_worker_update import worker_update_status

router = APIRouter(prefix="/api/workers", tags=["NVIDIA Worker"])


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
