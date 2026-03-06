"""
模組 3：LoRA 文件工具 API
資料夾監聽 .txt、Caption 編輯、打包下載
契約：docs/api-contract.md
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.lora_docs import (
    BatchPrefixRequest,
    BatchPrefixResponse,
    CaptionEditRequest,
    CaptionEditResponse,
    UploadResponse,
)

router = APIRouter(prefix="/api/lora-docs", tags=["LoRA 文件"])


@router.post("/upload", response_model=UploadResponse)
async def upload_training_images(
    files: list[UploadFile] = File(...),
    folder: str | None = None,
):
    """上傳訓練圖片，自動產生 .txt"""
    # TODO: 整合 WD Tagger / BLIP2
    return UploadResponse(uploaded=len(files))


@router.put("/caption/{image_id}", response_model=CaptionEditResponse)
async def edit_caption(image_id: str, body: CaptionEditRequest):
    """編輯單張圖片 .txt 內容。image_id 為相對路徑，如 my_lora/img1.png"""
    raise HTTPException(501, "TODO: 實作")


@router.post("/batch-prefix", response_model=BatchPrefixResponse)
async def batch_add_trigger_prefix(body: BatchPrefixRequest):
    """批次加入 trigger word 前綴"""
    raise HTTPException(501, "TODO: 實作")


@router.get("/download-zip")
async def download_training_pack(folder: str):
    """打包圖片 + .txt 成 ZIP 下載"""
    raise HTTPException(501, "TODO: 實作")
