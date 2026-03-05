"""
模組 3：LoRA 文件工具 API
資料夾監聽 .txt、Caption 編輯、打包下載
"""
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/lora-docs", tags=["LoRA 文件"])


@router.post("/upload")
async def upload_training_images(files: list[UploadFile] = File(...)):
    """上傳訓練圖片，自動產生 .txt"""
    # TODO: 整合 WD Tagger / BLIP2
    return {"uploaded": len(files)}


@router.put("/caption/{image_id}")
async def edit_caption(image_id: str, content: str):
    """編輯單張圖片 .txt 內容"""
    # TODO: 實作
    return {}


@router.post("/batch-prefix")
async def batch_add_trigger_prefix(images: list[str], prefix: str):
    """批次加入 trigger word 前綴"""
    # TODO: 實作
    return {}


@router.get("/download-zip")
async def download_training_pack(folder: str):
    """打包圖片 + .txt 成 ZIP 下載"""
    # TODO: 實作
    return StreamingResponse(iter([]), media_type="application/zip")
