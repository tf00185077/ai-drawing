"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
契約：docs/api-contract.md
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.resources import default_checkpoint, list_checkpoints, list_loras
from app.core.queue import QueueFullError, cancel as queue_cancel, get_job_status as queue_get_job_status, get_status, submit, submit_custom
from app.db.database import get_db
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
        if body.template is not None:
            params["template"] = body.template
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
        if body.lora_strength is not None:
            params["lora_strength"] = body.lora_strength
        if body.denoise is not None:
            params["denoise"] = body.denoise
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
        if body.lora_strength is not None:
            params["lora_strength"] = body.lora_strength
        if body.denoise is not None:
            params["denoise"] = body.denoise
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
    """列出可用的 checkpoint、lora、workflow 模板"""
    settings = get_settings()
    checkpoints = list_checkpoints(settings)
    loras = list_loras(settings)

    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    templates = []
    if workflows_dir.exists():
        templates = sorted(p.stem for p in workflows_dir.glob("*.json"))

    return {
        "checkpoints": checkpoints,
        "loras": loras,
        "workflows": templates,
        "default_checkpoint": default_checkpoint(settings),
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


@router.get("/job/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """查詢單一 job 狀態（queued / running / completed）"""
    from app.db.models import GeneratedImage

    # 1. 先查 in-memory queue（queued / running）
    queue_status = queue_get_job_status(job_id)
    if queue_status:
        return {
            "status": queue_status["status"],
            "job_id": job_id,
            "prompt_id": queue_status.get("prompt_id"),
            "submitted_at": queue_status.get("submitted_at"),
        }

    # 2. 查 DB（completed）
    image_record = db.query(GeneratedImage).filter_by(job_id=job_id).first()
    if image_record:
        return {
            "status": "completed",
            "job_id": job_id,
            "image_id": image_record.id,
            "image_path": image_record.image_path,
        }

    # 3. 找不到
    raise HTTPException(404, f"Job not found: {job_id}")


@router.delete("/queue/{job_id}", status_code=200)
async def cancel_job(job_id: str):
    """取消 pending 中的生圖 job"""
    try:
        found = queue_cancel(job_id)
    except ValueError:
        raise HTTPException(409, "job 正在執行中，無法取消")
    if not found:
        raise HTTPException(404, f"找不到該 job: {job_id}")
    return {"message": "已取消", "job_id": job_id}
