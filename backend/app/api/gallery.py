"""
模組 2：圖庫 API
參數與圖片記錄、Gallery 瀏覽、一鍵重現、匯出
契約：docs/api-contract.md
"""
import csv
import io
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.queue import QueueFullError, submit
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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """圖庫列表，支援篩選"""
    q = db.query(GeneratedImage)

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
    body: RerunRequest | None = Body(None),
    db: Session = Depends(get_db),
):
    """一鍵重現：載入參數再次生成。body 可帶 slack_channel_id、slack_thread_ts 供 Slack 生圖完成後回傳"""
    row = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not row:
        raise HTTPException(404, "找不到該圖片")
    params: dict = {
        "checkpoint": row.checkpoint,
        "lora": row.lora,
        "prompt": row.prompt or "",
        "negative_prompt": row.negative_prompt,
        "seed": row.seed,
        "steps": row.steps,
        "cfg": row.cfg,
    }
    if body:
        if body.slack_channel_id:
            params["slack_channel_id"] = body.slack_channel_id
        if body.slack_thread_ts:
            params["slack_thread_ts"] = body.slack_thread_ts
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
            "id", "image_path", "checkpoint", "lora", "seed", "steps", "cfg",
            "prompt", "negative_prompt", "created_at",
        ])
        created = row.created_at.isoformat() if row.created_at else ""
        writer.writerow([
            row.id, row.image_path or "", row.checkpoint or "", row.lora or "",
            row.seed or "", row.steps or "", row.cfg or "",
            row.prompt or "", row.negative_prompt or "", created,
        ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="gallery_{image_id}.csv"'},
        )

    item = _image_to_item(row)
    return item
