"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.comfyui import ComfyUIClient, get_comfy_client

router = APIRouter(prefix="/api/generate", tags=["生圖"])


@router.post("/")
async def trigger_generate(comfy: ComfyUIClient = Depends(get_comfy_client)):
    """觸發圖片生成"""
    raise HTTPException(501, "TODO: ComfyUI API 串接")


@router.get("/queue")
async def get_queue_status(comfy: ComfyUIClient = Depends(get_comfy_client)):
    """取得生圖佇列狀態"""
    raise HTTPException(501, "TODO: 批次排程器")
