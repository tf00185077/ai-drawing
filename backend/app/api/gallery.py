"""
模組 2：圖庫 API
參數與圖片記錄、Gallery 瀏覽、一鍵重現、匯出
契約：docs/api-contract.md
"""
import csv
import io
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.queue import QueueFullError, submit, submit_custom
from app.db.database import get_db
from app.db.models import GeneratedImage
from app.schemas.gallery import GalleryItem, GalleryListResponse, ImageDetail, RerunRequest, RerunResponse

router = APIRouter(prefix="/api/gallery", tags=["圖庫"])


def _to_image_url(path: str) -> str:
    """將 image_path 轉為 /gallery/xxx 格式供前端顯示"""
    if not path:
        return ""
    gallery_dir = Path(get_settings().gallery_dir).resolve()
    try:
        p = Path(path)
        resolved = p.resolve()
        rel = resolved.relative_to(gallery_dir)
        return "/gallery/" + str(rel).replace("\\", "/")
    except (ValueError, OSError):
        pass
    if not (path.startswith("/") or (len(path) > 1 and path[1] == ":")):
        return "/gallery/" + path.replace("\\", "/")
    return ""


def _image_to_item(row: GeneratedImage) -> GalleryItem:
    """GeneratedImage 轉 GalleryItem"""
    return GalleryItem(
        id=row.id,
        image_path=row.image_path,
        image_url=_to_image_url(row.image_path) or None,
        checkpoint=row.checkpoint,
        lora=row.lora,
        template=row.template,
        diffusion_model=row.diffusion_model,
        text_encoder=row.text_encoder,
        vae=row.vae,
        seed=row.seed,
        steps=row.steps,
        cfg=row.cfg,
        prompt=row.prompt,
        negative_prompt=row.negative_prompt,
        created_at=row.created_at,
    )


@router.get("/", response_model=GalleryListResponse)
async def list_images(
    checkpoint: str | None = Query(None, description="篩選 checkpoint"),
    lora: str | None = Query(None, description="篩選 LoRA"),
    from_date: str | None = Query(None, description="ISO 日期起"),
    to_date: str | None = Query(None, description="ISO 日期迄"),
    image_id: int | None = Query(None, description="依圖片 ID 精確查詢"),
    image_name: str | None = Query(None, description="依圖片路徑/檔名關鍵字模糊查詢"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """圖庫列表，支援篩選"""
    q = db.query(GeneratedImage)

    if image_id is not None:
        q = q.filter(GeneratedImage.id == image_id)
    if image_name and image_name.strip():
        q = q.filter(GeneratedImage.image_path.ilike(f"%{image_name.strip()}%"))
    if checkpoint:
        q = q.filter(GeneratedImage.checkpoint.ilike(f"%{checkpoint}%"))
    if lora:
        q = q.filter(GeneratedImage.lora.ilike(f"%{lora}%"))
    if from_date:
        try:
            dt = datetime.fromisoformat(from_date.split("T")[0])
            q = q.filter(GeneratedImage.created_at >= dt)
        except ValueError:
            pass
    if to_date:
        try:
            dt = datetime.fromisoformat(to_date.split("T")[0])
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            q = q.filter(GeneratedImage.created_at <= dt)
        except ValueError:
            pass

    total = q.count()
    rows = q.order_by(GeneratedImage.created_at.desc()).offset(offset).limit(limit).all()

    items = [_image_to_item(r) for r in rows]
    return GalleryListResponse(items=items, total=total)


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image_detail(image_id: int, db: Session = Depends(get_db)):
    """取得單張圖片完整參數"""
    row = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not row:
        raise HTTPException(404, "找不到該圖片")
    return _image_to_item(row)


@router.post("/{image_id}/rerun", response_model=RerunResponse, status_code=202)
async def rerun_image(
    image_id: int,
    db: Session = Depends(get_db),
):
    """一鍵重現：載入參數再次生成。

    有存完整 workflow（workflow_json）者走 custom 路徑忠實重現：重新上傳 source_image/
    source_mask 並重注入，沿用 workflow 內 baked 的 seed（不重新隨機）。
    舊資料（無 workflow_json）退回原本依欄位重建、走 template 路徑。
    """
    row = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not row:
        raise HTTPException(404, "找不到該圖片")

    # 忠實重現路徑：有存完整 workflow
    if row.workflow_json:
        try:
            wf = json.loads(row.workflow_json)
        except (TypeError, ValueError):
            wf = None
        if wf:
            gallery_dir = Path(get_settings().gallery_dir).resolve()

            def _require_source(rel: str, label: str) -> None:
                # 來源圖被刪則無法重新上傳，明確報錯而非送出壞圖
                if not (gallery_dir / rel).resolve().is_file():
                    raise HTTPException(409, f"無法重現：{label} 來源檔已不存在（{rel}）")

            params: dict = {"workflow": wf, "prompt": row.prompt or ""}
            if row.source_image:
                _require_source(row.source_image, "image")
                params["image"] = row.source_image
            if row.source_mask:
                _require_source(row.source_mask, "mask")
                params["mask"] = row.source_mask
            # 不傳 seed：custom 路徑省略時保留 workflow 原值 → 忠實重現
            try:
                job_id = submit_custom(params)
                return RerunResponse(job_id=job_id, status="queued", message="已加入生圖佇列（忠實重現）")
            except QueueFullError as e:
                raise HTTPException(503, str(e))

    # Legacy 路徑：依欄位重建、走 template
    params = {
        "checkpoint": row.checkpoint,
        "lora": row.lora,
        "prompt": row.prompt or "",
        "negative_prompt": row.negative_prompt,
        "seed": row.seed,
        "steps": row.steps,
        "cfg": row.cfg,
    }
    # 帶回模板與 diffusion-model 元件，確保 Anima 等非傳統 checkpoint 也能重生
    if row.template:
        params["template"] = row.template
    if row.diffusion_model:
        params["diffusion_model"] = row.diffusion_model
    if row.text_encoder:
        params["text_encoder"] = row.text_encoder
    if row.vae:
        params["vae"] = row.vae
    try:
        job_id = submit(params)
        return RerunResponse(job_id=job_id, status="queued", message="已加入生圖佇列")
    except QueueFullError as e:
        raise HTTPException(503, str(e))


@router.get("/{image_id}/export")
async def export_params(
    image_id: int,
    format: str = Query("json", description="json 或 csv"),
    db: Session = Depends(get_db),
):
    """匯出參數（JSON / CSV）"""
    row = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not row:
        raise HTTPException(404, "找不到該圖片")

    fmt = format.lower().strip()
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "id", "image_path", "checkpoint", "lora", "template",
            "diffusion_model", "text_encoder", "vae", "seed", "steps", "cfg",
            "prompt", "negative_prompt", "created_at",
        ])
        created = row.created_at.isoformat() if row.created_at else ""
        writer.writerow([
            row.id, row.image_path or "", row.checkpoint or "", row.lora or "",
            row.template or "", row.diffusion_model or "", row.text_encoder or "",
            row.vae or "", row.seed or "", row.steps or "", row.cfg or "",
            row.prompt or "", row.negative_prompt or "", created,
        ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="gallery_{image_id}.csv"'},
        )

    item = _image_to_item(row)
    return item
