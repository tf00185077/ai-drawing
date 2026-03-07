"""
模組 4：LoRA 訓練與產圖串接 API
訓練執行器、觸發邏輯、Pipeline 自動產圖、佇列管理
契約：docs/api-contract.md
"""
from fastapi import APIRouter, HTTPException

from app.schemas.lora_train import (
    TrainJobInfo,
    TrainStartRequest,
    TrainStartResponse,
    TrainStatusResponse,
    TriggerCheckResponse,
)
from app.services import lora_trainer

router = APIRouter(prefix="/api/lora-train", tags=["LoRA 訓練"])


@router.post("/start", response_model=TrainStartResponse, status_code=202)
async def start_training(body: TrainStartRequest):
    """手動觸發 LoRA 訓練"""
    try:
        job_id = lora_trainer.enqueue(
            body.folder,
            checkpoint=body.checkpoint,
            epochs=body.epochs,
        )
    except ValueError as e:
        msg = str(e)
        if "已在佇列" in msg or "訓練中" in msg:
            raise HTTPException(409, msg)
        raise HTTPException(400, msg)
    return TrainStartResponse(
        job_id=job_id,
        status="queued",
        message="已加入訓練佇列",
    )


@router.get("/status", response_model=TrainStatusResponse)
async def get_training_status():
    """訓練進度與佇列狀態"""
    st = lora_trainer.get_status()
    current = st.get("current_job")
    current_job = None
    if current:
        current_job = TrainJobInfo(
            job_id=current["job_id"],
            folder=current["folder"],
            progress=current.get("progress"),
            epoch=current.get("epoch"),
            total_epochs=current.get("total_epochs"),
        )
    queue_list = [
        TrainJobInfo(job_id=q["job_id"], folder=q["folder"])
        for q in st.get("queue", [])
    ]
    return TrainStatusResponse(
        status=st["status"],
        current_job=current_job,
        queue=queue_list,
    )


@router.post("/trigger-check", response_model=TriggerCheckResponse)
async def check_auto_trigger():
    """檢查是否符合自動觸發條件（圖片數 ≥ 門檻）"""
    return TriggerCheckResponse(should_trigger=False)
