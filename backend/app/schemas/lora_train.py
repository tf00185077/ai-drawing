"""
LoRA 訓練 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 4
"""
from pydantic import BaseModel, Field


class TrainStartRequest(BaseModel):
    """POST /api/lora-train/start 的 Request Body"""

    folder: str = Field(..., min_length=1)
    checkpoint: str | None = None
    epochs: int = Field(default=10, ge=1, le=500)


class TrainStartResponse(BaseModel):
    """POST /api/lora-train/start 的 Response"""

    job_id: str
    status: str = "queued"
    message: str | None = None


class TrainJobInfo(BaseModel):
    """訓練任務資訊"""

    job_id: str
    folder: str
    progress: float | None = None
    epoch: int | None = None
    total_epochs: int | None = None


class TrainStatusResponse(BaseModel):
    """GET /api/lora-train/status 的 Response"""

    status: str = "idle"  # idle | running | queued
    current_job: TrainJobInfo | None = None
    queue: list[TrainJobInfo] = Field(default_factory=list)


class TriggerCandidate(BaseModel):
    """符合自動觸發條件的資料夾"""

    folder: str
    image_count: int


class TriggerCheckResponse(BaseModel):
    """POST /api/lora-train/trigger-check 的 Response"""

    should_trigger: bool
    candidates: list[TriggerCandidate] = Field(default_factory=list)
