"""
模組 3：LoRA 文件工具 API
資料夾監聽 .txt、Caption 編輯、打包下載
契約：docs/api-contract.md
"""
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.schemas.lora_docs import (
    BatchPrefixRequest,
    BatchPrefixResponse,
    CaptionEditRequest,
    CaptionEditResponse,
    UploadItem,
    UploadResponse,
)
from app.services.wd_tagger import run_wd_tagger

router = APIRouter(prefix="/api/lora-docs", tags=["LoRA 文件"])

# 支援的圖片副檔名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _sanitize_folder(folder: str | None) -> str:
    """清理 folder 參數，防止 path traversal，回傳相對路徑（可含子目錄）"""
    if not folder or not folder.strip():
        return ""
    # 移除開頭/結尾斜線，替換反斜線，排除 ..
    cleaned = folder.strip().replace("\\", "/").strip("/")
    if ".." in cleaned or cleaned.startswith("/"):
        raise HTTPException(400, "無效的 folder 路徑")
    # 僅允許英數字、底線、橫線、斜線
    if not re.match(r"^[\w\-/]*$", cleaned):
        raise HTTPException(400, "無效的 folder 路徑")
    return cleaned


@router.post("/upload", response_model=UploadResponse)
async def upload_training_images(
    files: list[UploadFile] = File(...),
    folder: str | None = Form(None),
):
    """上傳訓練圖片，自動產生 .txt caption"""
    if not files:
        raise HTTPException(400, "請至少上傳一張圖片")

    rel_folder = _sanitize_folder(folder)
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    target_dir = (base_dir / rel_folder) if rel_folder else base_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    items: list[UploadItem] = []
    for uf in files:
        if not uf.filename:
            continue
        ext = Path(uf.filename).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        safe_name = Path(uf.filename).name
        dest_path = target_dir / safe_name
        content = await uf.read()
        dest_path.write_bytes(content)
        rel_path = f"{rel_folder}/{safe_name}" if rel_folder else safe_name
        caption_name = f"{Path(safe_name).stem}.txt"
        caption_path = f"{rel_folder}/{caption_name}" if rel_folder else caption_name
        items.append(
            UploadItem(
                filename=safe_name,
                path=rel_path,
                caption_path=caption_path,
            )
        )

    if items:
        run_wd_tagger(target_dir)

    return UploadResponse(uploaded=len(items), items=items)


@router.put("/caption/{image_path:path}", response_model=CaptionEditResponse)
async def edit_caption(image_path: str, body: CaptionEditRequest):
    """編輯單張圖片 .txt 內容。image_path 為相對路徑，如 my_lora/img1.png"""
    raise HTTPException(501, "TODO: 實作")


@router.post("/batch-prefix", response_model=BatchPrefixResponse)
async def batch_add_trigger_prefix(body: BatchPrefixRequest):
    """批次加入 trigger word 前綴"""
    raise HTTPException(501, "TODO: 實作")


@router.get("/download-zip")
async def download_training_pack(folder: str):
    """打包圖片 + .txt 成 ZIP 下載"""
    raise HTTPException(501, "TODO: 實作")
