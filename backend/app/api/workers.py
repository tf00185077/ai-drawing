"""Paired NVIDIA Worker status surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.nvidia_worker import NvidiaWorkerClient

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
        status = NvidiaWorkerClient(
            settings.nvidia_worker_url,
            settings.nvidia_worker_token,
            settings.nvidia_worker_timeout,
        ).health()
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
