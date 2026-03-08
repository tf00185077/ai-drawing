"""
生圖 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 1
"""
from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """POST /api/generate/ 的 Request Body"""

    checkpoint: str | None = None
    lora: str | None = None
    prompt: str = Field(..., min_length=1)
    negative_prompt: str | None = None
    seed: int | None = None
    steps: int = Field(default=20, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=1.0, le=30.0)
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)
    batch_size: int | None = Field(default=None, ge=1, le=8)
    sampler_name: str | None = None  # e.g. euler, dpmpp_2m, ddim
    scheduler: str | None = None  # e.g. normal, karras, exponential


class GenerateResponse(BaseModel):
    """POST /api/generate/ 的 Response"""

    job_id: str
    status: str = "queued"
    message: str | None = None


class QueueItem(BaseModel):
    """佇列單一項目"""

    job_id: str
    status: str
    submitted_at: str | None = None
    prompt_id: str | None = None


class QueueStatusResponse(BaseModel):
    """GET /api/generate/queue 的 Response"""

    queue_running: list[QueueItem] = Field(default_factory=list)
    queue_pending: list[QueueItem] = Field(default_factory=list)


class GenerateCustomRequest(BaseModel):
    """
    POST /api/generate/custom 的 Request Body
    可傳入自訂 ComfyUI workflow JSON，由 AI 根據使用者描述動態產生。
    """

    workflow: dict[str, Any] = Field(
        ...,
        description="ComfyUI API 格式的 workflow 物件，含 class_type、inputs 等節點",
    )
    prompt: str = Field(default="1girl, solo", min_length=1)
    checkpoint: str | None = None
    lora: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    steps: int = Field(default=20, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=1.0, le=30.0)
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)
    batch_size: int | None = Field(default=None, ge=1, le=8)
    sampler_name: str | None = None
    scheduler: str | None = None
    image_pose: str | None = Field(
        default=None,
        description="姿態參考圖路徑，相對於 gallery_dir（如 2026-03-08/ComfyUI_xxx.png）。會先上傳至 ComfyUI 再替換 LoadImage",
    )
