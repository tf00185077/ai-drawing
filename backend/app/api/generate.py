"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
契約：docs/api-contract.md
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.core.queue import QueueFullError, get_status, submit, submit_custom
from app.schemas.generate import (
    GenerateCustomRequest,
    GenerateRequest,
    GenerateResponse,
    QueueStatusResponse,
)

router = APIRouter(prefix="/api/generate", tags=["生圖"])


@router.post("/", response_model=GenerateResponse, status_code=201)
async def trigger_generate(body: GenerateRequest):
    """觸發圖片生成"""
    try:
        params = {
            "checkpoint": body.checkpoint,
            "lora": body.lora,
            "prompt": body.prompt,
            "negative_prompt": body.negative_prompt,
            "seed": body.seed,
            "steps": body.steps,
            "cfg": body.cfg,
        }
        if body.width is not None:
            params["width"] = body.width
        if body.height is not None:
            params["height"] = body.height
        if body.batch_size is not None:
            params["batch_size"] = body.batch_size
        if body.sampler_name is not None:
            params["sampler_name"] = body.sampler_name
        if body.scheduler is not None:
            params["scheduler"] = body.scheduler
        if body.slack_channel_id:
            params["slack_channel_id"] = body.slack_channel_id
        if body.slack_thread_ts:
            params["slack_thread_ts"] = body.slack_thread_ts
        job_id = submit(params)
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入生圖佇列",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))


@router.post("/custom", response_model=GenerateResponse, status_code=201)
async def trigger_generate_custom(body: GenerateCustomRequest):
    """
    使用自訂 workflow 觸發圖片生成。
    workflow 為 ComfyUI API 格式，可由 AI 根據使用者描述動態產生。
    """
    try:
        params = {
            "workflow": body.workflow,
            "checkpoint": body.checkpoint,
            "lora": body.lora,
            "prompt": body.prompt,
            "negative_prompt": body.negative_prompt,
            "seed": body.seed,
            "steps": body.steps,
            "cfg": body.cfg,
        }
        if body.width is not None:
            params["width"] = body.width
        if body.height is not None:
            params["height"] = body.height
        if body.batch_size is not None:
            params["batch_size"] = body.batch_size
        if body.sampler_name is not None:
            params["sampler_name"] = body.sampler_name
        if body.scheduler is not None:
            params["scheduler"] = body.scheduler
        if body.image is not None:
            params["image"] = body.image
        if body.image_pose is not None:
            params["image_pose"] = body.image_pose
        if body.slack_channel_id:
            params["slack_channel_id"] = body.slack_channel_id
        if body.slack_thread_ts:
            params["slack_thread_ts"] = body.slack_thread_ts
        job_id = submit_custom(params)
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入生圖佇列（自訂 workflow）",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))


def _list_model_files(dir_path: Path, exts: tuple[str, ...] = (".safetensors", ".ckpt", ".pth")) -> list[str]:
    """列出目錄下模型檔名（純檔名）"""
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    names = []
    for p in dir_path.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            names.append(p.name)
    return sorted(names)


@router.get("/available-resources")
async def get_available_resources():
    """
    列出可用的 checkpoint、lora、workflow 模板。
    供 Slack !查可用資源 指令使用。
    """
    settings = get_settings()
    checkpoints_dir = Path(settings.comfyui_checkpoints_dir)
    loras_dir = Path(settings.comfyui_loras_dir)

    checkpoints = _list_model_files(checkpoints_dir)
    loras = _list_model_files(loras_dir)

    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    templates = []
    if workflows_dir.exists():
        templates = sorted(p.stem for p in workflows_dir.glob("*.json"))

    return {
        "checkpoints": checkpoints,
        "loras": loras,
        "workflows": templates,
    }


@router.get("/workflow-templates")
async def list_workflow_templates():
    """列出可用的 workflow 模板名稱，供 AI 根據描述選擇或組合"""
    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    if not workflows_dir.exists():
        return {"templates": []}
    names = [
        p.stem for p in workflows_dir.glob("*.json")
    ]
    return {"templates": sorted(names)}


@router.get("/workflow-templates/{name}")
async def get_workflow_template(name: str):
    """取得指定模板的 workflow JSON，供 AI 修改或直接使用"""
    import json
    from pathlib import Path


    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    path = (workflows_dir / name).with_suffix(".json")
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, f"Workflow template not found: {name}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@router.get("/queue", response_model=QueueStatusResponse)
async def get_queue_status():
    """取得生圖佇列狀態"""
    status = get_status()
    return QueueStatusResponse(
        queue_running=status["queue_running"],
        queue_pending=status["queue_pending"],
    )
