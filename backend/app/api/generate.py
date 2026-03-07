"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
契約：docs/api-contract.md
"""
from fastapi import APIRouter, HTTPException

from app.core.queue import QueueFullError, get_status, submit
from app.schemas.generate import GenerateRequest, GenerateResponse, QueueStatusResponse

router = APIRouter(prefix="/api/generate", tags=["生圖"])


@router.post("/", response_model=GenerateResponse, status_code=201)
async def trigger_generate(body: GenerateRequest):
    """觸發圖片生成"""
    try:
        job_id = submit({
            "checkpoint": body.checkpoint,
            "lora": body.lora,
            "prompt": body.prompt,
            "negative_prompt": body.negative_prompt,
            "seed": body.seed,
            "steps": body.steps,
            "cfg": body.cfg,
        })
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入生圖佇列",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue_status():
    """取得生圖佇列狀態"""
    status = get_status()
    return QueueStatusResponse(
        queue_running=status["queue_running"],
        queue_pending=status["queue_pending"],
    )
