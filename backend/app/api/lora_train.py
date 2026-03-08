"""
模組 4：LoRA 訓練與產圖串接 API
訓練執行器、觸發邏輯、Pipeline 自動產圖、佇列管理
契約：docs/api-contract.md
"""
from fastapi import APIRouter, HTTPException

from app.schemas.lora_train import (
    FolderItem,
    TrainFoldersResponse,
    TrainJobInfo,
    TrainLastResult,
    TrainStartRequest,
    TrainStartResponse,
    TrainStatusResponse,
    TriggerCandidate,
    TriggerCheckResponse,
)
from app.config import get_settings
from app.services import lora_trainer

router = APIRouter(prefix="/api/lora-train", tags=["LoRA 訓練"])


@router.get("/config")
async def get_train_config():
    """取得訓練預設設定（供前端 checkbox 預設值）"""
    settings = get_settings()
    return {"sdxl": settings.lora_sdxl}


@router.get("/folders", response_model=TrainFoldersResponse)
async def list_training_folders():
    """列出可訓練的資料夾（含圖片數）"""
    items = lora_trainer.list_folders()
    return TrainFoldersResponse(
        folders=[FolderItem(folder=f["folder"], image_count=f["image_count"]) for f in items]
    )


@router.post("/start", response_model=TrainStartResponse, status_code=202)
async def start_training(body: TrainStartRequest):
    """手動觸發 LoRA 訓練。可附 generate_after：訓練完成後才自動生圖。"""
    try:
        gen_after = None
        if body.generate_after:
            gen_after = body.generate_after.model_dump()
        job_id = lora_trainer.enqueue(
            body.folder,
            checkpoint=body.checkpoint,
            sdxl=body.sdxl,
            epochs=body.epochs,
            resolution=body.resolution,
            batch_size=body.batch_size,
            learning_rate=body.learning_rate,
            class_tokens=body.class_tokens,
            keep_tokens=body.keep_tokens,
            num_repeats=body.num_repeats,
            mixed_precision=body.mixed_precision,
            network_dim=body.network_dim,
            network_alpha=body.network_alpha,
            generate_after=gen_after,
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


@router.post("/clear")
async def clear_training_queue():
    """清除訓練佇列，停止正在執行的任務"""
    count = lora_trainer.clear_queue()
    return {"cleared": count, "message": f"已清除 {count} 個任務"}


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
    last = st.get("last_result")
    last_result = TrainLastResult(**last) if last else None
    return TrainStatusResponse(
        status=st["status"],
        current_job=current_job,
        queue=queue_list,
        last_result=last_result,
    )


@router.post("/trigger-check", response_model=TriggerCheckResponse)
async def check_auto_trigger():
    """檢查是否符合自動觸發條件（圖片數 ≥ 門檻），符合者自動加入訓練佇列"""
    result = lora_trainer.trigger_check()
    candidates = [
        TriggerCandidate(folder=c["folder"], image_count=c["image_count"])
        for c in result["candidates"]
    ]
    return TriggerCheckResponse(
        should_trigger=result["should_trigger"],
        candidates=candidates,
    )
