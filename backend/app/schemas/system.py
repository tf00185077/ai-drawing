from typing import Literal

from pydantic import BaseModel, Field


ComfyUIMode = Literal["disabled", "external", "managed"]
ComfyUIState = Literal[
    "connected",
    "not_configured",
    "unreachable",
    "no_models",
    "degraded",
]


class ComfyUIStatus(BaseModel):
    mode: ComfyUIMode
    state: ComfyUIState
    configured: bool
    reachable: bool
    model_count: int = Field(ge=0)
    checkpoint_count: int = Field(ge=0)
    diffusion_model_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    hint: str


class SystemStatus(BaseModel):
    application: Literal["healthy"] = "healthy"
    comfyui: ComfyUIStatus
