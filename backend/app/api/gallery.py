"""
模組 2：圖庫 API
參數與圖片記錄、Gallery 瀏覽、一鍵重現、匯出
契約：docs/api-contract.md
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.gallery import GalleryListResponse, ImageDetail, RerunResponse

router = APIRouter(prefix="/api/gallery", tags=["圖庫"])


@router.get("/", response_model=GalleryListResponse)
async def list_images(
    checkpoint: str | None = Query(None),
    lora: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """圖庫列表，支援篩選"""
    # TODO: 實作搜尋、篩選
    return GalleryListResponse(items=[], total=0)


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image_detail(image_id: int, db: Session = Depends(get_db)):
    """取得單張圖片完整參數"""
    raise HTTPException(501, "TODO: 實作")


@router.post("/{image_id}/rerun", response_model=RerunResponse)
async def rerun_image(image_id: int, db: Session = Depends(get_db)):
    """一鍵重現：載入參數再次生成"""
    raise HTTPException(501, "TODO: 實作")


@router.get("/{image_id}/export")
async def export_params(
    image_id: int,
    format: str = Query("json"),
    db: Session = Depends(get_db),
):
    """匯出參數（JSON / CSV）"""
    raise HTTPException(501, "TODO: 實作")
