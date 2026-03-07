"""
模組 5：生成統計分析 API
參數分佈、checkpoint / LoRA 使用頻率、seed 統計
契約：docs/api-contract.md 模組 5（Analytics）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    NumericStats,
    SeedUsageItem,
    UsageItem,
)
from app.services.analytics import get_stats

router = APIRouter(prefix="/api/analytics", tags=["統計分析"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    from_date: str | None = Query(None, description="ISO 日期起，如 2024-01-01"),
    to_date: str | None = Query(None, description="ISO 日期迄"),
    limit: int = Query(20, ge=1, le=100, description="各類別取前 N 筆"),
    db: Session = Depends(get_db),
):
    """
    取得生成統計摘要。
    無效的 from_date / to_date 回傳 400。
    """
    try:
        result = get_stats(db, from_date=from_date, to_date=to_date, limit=limit)
    except ValueError as e:
        raise HTTPException(400, f"無效的日期格式: {e}") from e

    return AnalyticsSummaryResponse(
        total_count=result["total_count"],
        checkpoint_usage=[UsageItem(**u) for u in result["checkpoint_usage"]],
        lora_usage=[UsageItem(**u) for u in result["lora_usage"]],
        steps_stats=NumericStats(**result["steps_stats"]),
        cfg_stats=NumericStats(**result["cfg_stats"]),
        top_seeds=[SeedUsageItem(**s) for s in result["top_seeds"]],
    )
