"""
圖庫 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 2
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GalleryItem(BaseModel):
    """單張圖片記錄，對應 GeneratedImage"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    image_path: str
    checkpoint: str | None = None
    lora: str | None = None
    seed: int | None = None
    steps: int | None = None
    cfg: float | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    created_at: datetime


class GalleryListResponse(BaseModel):
    """GET /api/gallery/ 的 Response"""

    items: list[GalleryItem]
    total: int


class ImageDetail(GalleryItem):
    """GET /api/gallery/{id} 的 Response，與 GalleryItem 同構"""

    pass


class RerunResponse(BaseModel):
    """POST /api/gallery/{id}/rerun 的 Response"""

    job_id: str
    status: str = "queued"
    message: str | None = None
