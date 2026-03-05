"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/generate", tags=["生圖"])


@router.post("/")
async def trigger_generate():
    """觸發圖片生成"""
    raise HTTPException(501, "TODO: ComfyUI API 串接")


@router.get("/queue")
async def get_queue_status():
    """取得生圖佇列狀態"""
    raise HTTPException(501, "TODO: 批次排程器")
