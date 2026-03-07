"""
生成統計分析 API 的 Response 結構
對應 docs/api-contract.md 模組 5（Analytics）
"""
from pydantic import BaseModel


class UsageItem(BaseModel):
    """使用頻率單項"""

    name: str
    count: int


class NumericStats(BaseModel):
    """數值參數統計"""

    min: float | None
    max: float | None
    avg: float | None
    count: int


class SeedUsageItem(BaseModel):
    """seed 使用頻率單項"""

    seed: int
    count: int


class AnalyticsSummaryResponse(BaseModel):
    """GET /api/analytics/summary 的 Response"""

    total_count: int
    checkpoint_usage: list[UsageItem]
    lora_usage: list[UsageItem]
    steps_stats: NumericStats
    cfg_stats: NumericStats
    top_seeds: list[SeedUsageItem]
