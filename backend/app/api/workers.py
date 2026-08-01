"""Paired NVIDIA Worker status surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.nvidia_worker import get_worker_client

router = APIRouter(prefix="/api/workers", tags=["NVIDIA Worker"])


@router.get("/status")
def worker_status() -> dict:
    settings = get_settings()
    configured = bool(settings.nvidia_worker_url and settings.nvidia_worker_token)
    if not configured:
        return {
            "configured": False,
            "reachable": False,
            "status": "not_paired",
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
