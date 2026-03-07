"""
模組 3：LoRA 文件工具 API
資料夾監聽 .txt、Caption 編輯、打包下載
契約：docs/api-contract.md
"""
import re
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

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


def _resolve_image_and_caption(path: str, base_dir: Path) -> tuple[Path, Path, str]:
    """
    驗證 image_path，回傳 (image_full_path, caption_full_path, caption_rel_path)。
    image_path 如 my_lora/img1.png 或 my_lora/img1 → caption 為 my_lora/img1.txt
    """
    cleaned = path.strip().replace("\\", "/").strip("/")
    if ".." in cleaned or cleaned.startswith("/"):
        raise HTTPException(400, "無效的 image 路徑")
    if not re.match(r"^[\w\-/.]*$", cleaned):
        raise HTTPException(400, "無效的 image 路徑")
    base_resolved = base_dir.resolve()
    full = (base_dir / cleaned).resolve()
    if not str(full).startswith(str(base_resolved)):
        raise HTTPException(400, "無效的 image 路徑")
    p = Path(cleaned)
    if p.suffix.lower() in IMAGE_EXTENSIONS:
        stem = p.stem
        parent = str(p.parent) if p.parent != Path(".") else ""
        caption_rel = f"{parent}/{stem}.txt".strip("/") if parent else f"{stem}.txt"
    else:
        caption_rel = f"{cleaned}.txt" if not cleaned.endswith(".txt") else cleaned
    caption_full = (base_dir / caption_rel).resolve()
    return full, caption_full, caption_rel


@router.get("/files")
async def list_folder_files(folder: str = Query(..., min_length=1)):
    """列出資料夾內圖片與對應 caption 路徑（供 Caption 編輯器使用）"""
    rel_folder = _sanitize_folder(folder)
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    target_dir = base_dir / rel_folder
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(404, "資料夾不存在")
    items: list[dict] = []
    for f in sorted(target_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel = str(f.relative_to(base_dir)).replace("\\", "/")
        p = Path(rel)
        caption_rel = f"{p.parent}/{p.stem}.txt" if p.parent != Path(".") else f"{p.stem}.txt"
        items.append({"path": rel, "caption_path": caption_rel})
    return {"items": items}


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


@router.get("/caption/{image_path:path}")
async def get_caption(image_path: str):
    """取得單張圖片的 .txt 內容（供編輯器載入）"""
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    try:
        img_full, caption_full, caption_rel = _resolve_image_and_caption(
            image_path, base_dir
        )
    except HTTPException:
        raise
    if not img_full.exists():
        raise HTTPException(404, "找不到該圖片")
    if not caption_full.exists():
        return {"path": caption_rel, "content": ""}
    return {"path": caption_rel, "content": caption_full.read_text(encoding="utf-8")}


@router.put("/caption/{image_path:path}", response_model=CaptionEditResponse)
async def edit_caption(image_path: str, body: CaptionEditRequest):
    """編輯單張圖片 .txt 內容。image_path 為相對路徑，如 my_lora/img1.png"""
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    try:
        img_full, caption_full, caption_rel = _resolve_image_and_caption(
            image_path, base_dir
        )
    except HTTPException:
        raise
    if not img_full.exists():
        raise HTTPException(404, "找不到該圖片或 .txt")
    caption_full.parent.mkdir(parents=True, exist_ok=True)
    caption_full.write_text(body.content, encoding="utf-8")
    return CaptionEditResponse(path=caption_rel, updated=True)


@router.post("/batch-prefix", response_model=BatchPrefixResponse)
async def batch_add_trigger_prefix(body: BatchPrefixRequest):
    """批次加入 trigger word 前綴"""
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    updated = 0
    failed: list[str] = []
    for path_str in body.images:
        try:
            _, caption_full, _ = _resolve_image_and_caption(path_str.strip(), base_dir)
        except HTTPException:
            failed.append(path_str)
            continue
        if not caption_full.exists():
            failed.append(path_str)
            continue
        content = caption_full.read_text(encoding="utf-8")
        if content.startswith(body.prefix):
            updated += 1  # 已含前綴，仍算成功
            continue
        new_content = body.prefix + content
        caption_full.write_text(new_content, encoding="utf-8")
        updated += 1
    return BatchPrefixResponse(updated=updated, failed=failed)


@router.get("/download-zip")
async def download_training_pack(folder: str = Query(..., min_length=1)):
    """打包圖片 + .txt 成 ZIP 下載"""
    rel_folder = _sanitize_folder(folder)
    settings = get_settings()
    base_dir = Path(settings.lora_train_dir).resolve()
    target_dir = base_dir / rel_folder

    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(404, "資料夾不存在")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in target_dir.rglob("*"):
            if f.is_file():
                arcname = f.relative_to(target_dir)
                zf.write(f, arcname)

    buffer.seek(0)
    zip_name = f"{Path(rel_folder).name or 'lora_data'}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )
