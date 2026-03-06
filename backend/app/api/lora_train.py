"""
模組 4：LoRA 訓練與產圖串接 API
訓練執行器、觸發邏輯、Pipeline 自動產圖、佇列管理
契約：docs/api-contract.md
"""
from fastapi import APIRouter, HTTPException

from app.schemas.lora_train import (
    TrainStartRequest,
    TrainStartResponse,
    TrainStatusResponse,
    TriggerCheckResponse,
)

router = APIRouter(prefix="/api/lora-train", tags=["LoRA 訓練"])


@router.post("/start", response_model=TrainStartResponse)
async def start_training(body: TrainStartRequest):
    """手動觸發 LoRA 訓練"""
    raise HTTPException(501, "TODO: LoRA 訓練執行器")


@router.get("/status", response_model=TrainStatusResponse)
async def get_training_status():
    """訓練進度與佇列狀態"""
    return TrainStatusResponse(status="idle", queue=[])


@router.post("/trigger-check", response_model=TriggerCheckResponse)
async def check_auto_trigger():
    """檢查是否符合自動觸發條件（圖片數 ≥ 門檻）"""
    return TriggerCheckResponse(should_trigger=False)
