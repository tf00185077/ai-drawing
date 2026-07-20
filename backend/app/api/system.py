from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.system import SystemStatus
from app.services.dependency_status import get_system_status


router = APIRouter(prefix="/api/system", tags=["系統狀態"])


@router.get("/status", response_model=SystemStatus)
def system_status(settings: Settings = Depends(get_settings)) -> SystemStatus:
    """Return application health and optional ComfyUI dependency readiness."""
    return get_system_status(settings)
