"""
模組 2：圖庫 API
參數與圖片記錄、Gallery 瀏覽、一鍵重現、匯出
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter(prefix="/api/gallery", tags=["圖庫"])


@router.get("/")
async def list_images(
    checkpoint: str | None = Query(None),
    lora: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """圖庫列表，支援篩選"""
    # TODO: 實作搜尋、篩選
    return {"items": []}


@router.get("/{image_id}")
async def get_image_detail(image_id: int, db: Session = Depends(get_db)):
    """取得單張圖片完整參數"""
    # TODO: 實作
    return {}


@router.post("/{image_id}/rerun")
async def rerun_image(image_id: int, db: Session = Depends(get_db)):
    """一鍵重現：載入參數再次生成"""
    # TODO: 實作
    return {}


@router.get("/{image_id}/export")
async def export_params(image_id: int, format: str = Query("json")):
    """匯出參數（JSON / CSV）"""
    # TODO: 實作
    return {}
