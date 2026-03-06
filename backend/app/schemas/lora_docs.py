"""
LoRA 文件 API 的 Request/Response 結構
對應 docs/api-contract.md 模組 3
"""
from pydantic import BaseModel, Field


class UploadItem(BaseModel):
    """上傳後的單一項目"""

    filename: str
    path: str
    caption_path: str


class UploadResponse(BaseModel):
    """POST /api/lora-docs/upload 的 Response"""

    uploaded: int
    items: list[UploadItem] = Field(default_factory=list)


class CaptionEditRequest(BaseModel):
    """PUT /api/lora-docs/caption/{image_id} 的 Request Body"""

    content: str = Field(..., min_length=0)


class CaptionEditResponse(BaseModel):
    """PUT /api/lora-docs/caption/{image_id} 的 Response"""

    path: str
    updated: bool = True


class BatchPrefixRequest(BaseModel):
    """POST /api/lora-docs/batch-prefix 的 Request Body"""

    images: list[str] = Field(..., min_length=1)
    prefix: str = Field(..., min_length=1)


class BatchPrefixResponse(BaseModel):
    """POST /api/lora-docs/batch-prefix 的 Response"""

    updated: int
    failed: list[str] = Field(default_factory=list)
