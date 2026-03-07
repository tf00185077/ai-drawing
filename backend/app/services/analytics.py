"""
生成統計分析（Phase 5c）
參數分佈、checkpoint / LoRA 使用頻率、seed 統計
查詢邏輯集中於此，與 route 分離，便於未來抽出 GalleryRepository
"""
from datetime import datetime
from typing import TypedDict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import GeneratedImage


class UsageItem(TypedDict):
    """使用頻率單項"""

    name: str
    count: int


class NumericStats(TypedDict):
    """數值參數統計"""

    min: float | None
    max: float | None
    avg: float | None
    count: int


class SeedUsageItem(TypedDict):
    """seed 使用頻率單項"""

    seed: int
    count: int


class AnalyticsSummary(TypedDict):
    """統計摘要"""

    total_count: int
    checkpoint_usage: list[UsageItem]
    lora_usage: list[UsageItem]
    steps_stats: NumericStats
    cfg_stats: NumericStats
    top_seeds: list[SeedUsageItem]


def _parse_date(s: str) -> datetime:
    """
    解析 ISO 日期字串，支援 YYYY-MM-DD。
    Raises ValueError 若格式無效。
    """
    part = s.split("T")[0].strip()
    return datetime.fromisoformat(part)


def _numeric_stats(values: list[float | None]) -> NumericStats:
    """從數值串列計算 min/max/avg"""
    valid = [v for v in values if v is not None]
    if not valid:
        return {"min": None, "max": None, "avg": None, "count": 0}
    return {
        "min": min(valid),
        "max": max(valid),
        "avg": sum(valid) / len(valid),
        "count": len(valid),
    }


def get_stats(
    db: Session,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> AnalyticsSummary:
    """
    取得生成統計摘要。
    from_date / to_date: ISO 日期（YYYY-MM-DD），無效格式由呼叫端轉為 400。
    limit: checkpoint/lora/seed 各取前 N 筆。
    """
    base = db.query(GeneratedImage)
    if from_date:
        base = base.filter(GeneratedImage.created_at >= _parse_date(from_date))
    if to_date:
        dt = _parse_date(to_date).replace(hour=23, minute=59, second=59, microsecond=999999)
        base = base.filter(GeneratedImage.created_at <= dt)

    total = base.count()

    # checkpoint 使用頻率
    ckpt_rows = (
        base.filter(GeneratedImage.checkpoint.isnot(None), GeneratedImage.checkpoint != "")
        .with_entities(GeneratedImage.checkpoint, func.count(GeneratedImage.id).label("cnt"))
        .group_by(GeneratedImage.checkpoint)
        .order_by(func.count(GeneratedImage.id).desc())
        .limit(limit)
        .all()
    )
    checkpoint_usage: list[UsageItem] = [
        {"name": str(c or ""), "count": int(cnt)} for c, cnt in ckpt_rows
    ]

    # lora 使用頻率
    lora_rows = (
        base.filter(GeneratedImage.lora.isnot(None), GeneratedImage.lora != "")
        .with_entities(GeneratedImage.lora, func.count(GeneratedImage.id).label("cnt"))
        .group_by(GeneratedImage.lora)
        .order_by(func.count(GeneratedImage.id).desc())
        .limit(limit)
        .all()
    )
    lora_usage: list[UsageItem] = [
        {"name": str(l or ""), "count": int(cnt)} for l, cnt in lora_rows
    ]

    # steps / cfg 統計
    rows = base.with_entities(GeneratedImage.steps, GeneratedImage.cfg).all()
    steps_vals = [r[0] for r in rows]
    cfg_vals = [r[1] for r in rows]
    steps_stats = _numeric_stats([float(x) if x is not None else None for x in steps_vals])
    cfg_stats = _numeric_stats([float(x) if x is not None else None for x in cfg_vals])

    # 最常使用的 seed
    seed_rows = (
        base.filter(GeneratedImage.seed.isnot(None))
        .with_entities(GeneratedImage.seed, func.count(GeneratedImage.id).label("cnt"))
        .group_by(GeneratedImage.seed)
        .order_by(func.count(GeneratedImage.id).desc())
        .limit(limit)
        .all()
    )
    top_seeds: list[SeedUsageItem] = [{"seed": int(s), "count": int(cnt)} for s, cnt in seed_rows]

    return AnalyticsSummary(
        total_count=total,
        checkpoint_usage=checkpoint_usage,
        lora_usage=lora_usage,
        steps_stats=steps_stats,
        cfg_stats=cfg_stats,
        top_seeds=top_seeds,
    )
