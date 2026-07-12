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
    image_url: str | None = None  # 前端顯示用，/gallery/ 開頭
    checkpoint: str | None = None
    lora: str | None = None
    template: str | None = None
    diffusion_model: str | None = None
    text_encoder: str | None = None
    vae: str | None = None
    seed: int | None = None
    steps: int | None = None
    cfg: float | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    recipe_provenance_available: bool = False
    recipe_reproduction_level: str | None = None
    created_at: datetime


class GalleryListResponse(BaseModel):
    """GET /api/gallery/ 的 Response"""

    items: list[GalleryItem]
    total: int


class ImageDetail(GalleryItem):
    """GET /api/gallery/{id} 的 Response，與 GalleryItem 同構"""

    pass


class RerunRequest(BaseModel):
    """POST /api/gallery/{id}/rerun 的 Request Body（可選參數）"""

    pass


class RerunResponse(BaseModel):
    """POST /api/gallery/{id}/rerun 的 Response"""

    job_id: str
    status: str = "queued"
    message: str | None = None


class ArtifactSummary(BaseModel):
    """GeneratedArtifact summary for job status responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str | None = None
    artifact_type: str
    mime_type: str | None = None
    gallery_path: str
    artifact_url: str | None = None
    file_size: int | None = None
    source_node_id: str | None = None
    source_node_type: str | None = None
    created_at: datetime


class ArtifactDetail(ArtifactSummary):
    """GET /api/gallery/artifacts/{id} 的 Response."""

    local_path: str | None = None
    workflow_json: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    metadata_json: str | None = None
    fps: float | None = None
    frame_count: int | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
