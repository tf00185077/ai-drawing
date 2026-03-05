"""
模組 4：LoRA 訓練與產圖串接 API
訓練執行器、觸發邏輯、Pipeline 自動產圖、佇列管理
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/lora-train", tags=["LoRA 訓練"])


@router.post("/start")
async def start_training(folder: str, checkpoint: str | None = None, epochs: int = 10):
    """手動觸發 LoRA 訓練"""
    # TODO: 整合 Kohya sd-scripts
    raise HTTPException(501, "TODO: LoRA 訓練執行器")


@router.get("/status")
async def get_training_status():
    """訓練進度與佇列狀態"""
    return {"status": "idle", "queue": []}


@router.post("/trigger-check")
async def check_auto_trigger():
    """檢查是否符合自動觸發條件（圖片數 ≥ 門檻）"""
    # TODO: 實作
    return {"should_trigger": False}
