"""
模組 1：生圖 API
ComfyUI API 串接、Workflow 模板、批次排程
契約：docs/api-contract.md
"""
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.resources import (
    default_checkpoint,
    list_checkpoints,
    list_diffusion_models,
    list_loras,
    list_text_encoders,
    list_vaes,
)
from app.core.queue import QueueFullError, GenerateParams, cancel as queue_cancel, get_job_status as queue_get_job_status, get_status, submit, submit_custom
from app.core.wan_keyframes import build_wan_keyframe_workflow
from app.db.database import get_db
from app.db.models import GeneratedArtifact, GeneratedImage
from app.schemas.generate import (
    GenerateCustomRequest,
    GenerateRequest,
    GenerateResponse,
    GenerateVideoCustomRequest,
    GenerateWanKeyframesVideoRequest,
    QueueStatusResponse,
)

router = APIRouter(prefix="/api/generate", tags=["生圖"])


def _custom_request_params(body: GenerateCustomRequest) -> dict:
    params = {
        "workflow": body.workflow,
        "checkpoint": body.checkpoint,
        "lora": body.lora,
        "prompt": body.prompt,
        "negative_prompt": body.negative_prompt,
        "seed": body.seed,
    }
    if body.steps is not None:
        params["steps"] = body.steps
    if body.cfg is not None:
        params["cfg"] = body.cfg
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
    if body.mask is not None:
        params["mask"] = body.mask
    if body.diffusion_model is not None:
        params["diffusion_model"] = body.diffusion_model
    if body.text_encoder is not None:
        params["text_encoder"] = body.text_encoder
    if body.vae is not None:
        params["vae"] = body.vae
    if body.lora_strength is not None:
        params["lora_strength"] = body.lora_strength
    if body.loras is not None:
        params["loras"] = [lo.model_dump(exclude_none=True) for lo in body.loras]
    if body.denoise is not None:
        params["denoise"] = body.denoise
    return params


@router.post("/", response_model=GenerateResponse, status_code=201)
async def trigger_generate(body: GenerateRequest):
    """觸發圖片生成"""
    try:
        params = {"prompt": body.prompt, "negative_prompt": body.negative_prompt}
        for key in ("checkpoint", "lora", "seed", "steps", "cfg"):
            value = getattr(body, key)
            if value is not None:
                params[key] = value
        if body.use_workflow_defaults:
            params["use_workflow_defaults"] = True
        if body.seed_mode is not None:
            params["seed_mode"] = body.seed_mode
        if body.template is not None:
            params["template"] = body.template
        if body.diffusion_model is not None:
            params["diffusion_model"] = body.diffusion_model
        if body.text_encoder is not None:
            params["text_encoder"] = body.text_encoder
        if body.vae is not None:
            params["vae"] = body.vae
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
        if body.loras is not None:
            params["loras"] = [lo.model_dump(exclude_none=True) for lo in body.loras]
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
        params = _custom_request_params(body)
        job_id = submit_custom(params)
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入生圖佇列（自訂 workflow）",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))


@router.post("/video/custom", response_model=GenerateResponse, status_code=201)
async def trigger_generate_video_custom(body: GenerateVideoCustomRequest):
    """
    使用自訂 workflow 觸發影片生成。
    MVP 不從自然語言合成影片 graph；呼叫端需提供完整 ComfyUI workflow JSON。
    """
    try:
        params = _custom_request_params(body)
        if body.first_frame is not None:
            params["first_frame"] = body.first_frame
        if body.last_frame is not None:
            params["last_frame"] = body.last_frame
        if body.video_ref is not None:
            params["video_ref"] = body.video_ref
        job_id = submit_custom(params)
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入影片生成佇列（自訂 workflow）",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))


@router.post("/video/wan-keyframes", response_model=GenerateResponse, status_code=201)
async def trigger_generate_video_wan_keyframes(body: GenerateWanKeyframesVideoRequest):
    """用 WanDancer 單一 workflow 將多張 gallery keyframes 生成一支影片。"""
    try:
        settings = get_settings()
        workflow = build_wan_keyframe_workflow(
            settings=settings,
            image_paths=body.images,
            prompt=body.prompt,
            negative_prompt=body.negative_prompt,
            width=body.width,
            height=body.height,
            length=body.length,
            fps=body.fps,
            steps=body.steps,
            cfg=body.cfg,
            seed=body.seed,
            filename_prefix=body.filename_prefix,
        )
        params = {
            "workflow": workflow,
            "prompt": body.prompt,
            "negative_prompt": body.negative_prompt,
            "width": body.width,
            "height": body.height,
            "steps": body.steps,
            "cfg": body.cfg,
            "seed": body.seed,
            "template": "gen_img2video_wan_5keyframe_single_workflow",
        }
        job_id = submit_custom(cast(GenerateParams, params))
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            message="已加入影片生成佇列（Wan 多 keyframe 單 workflow）",
        )
    except QueueFullError as e:
        raise HTTPException(503, str(e))
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, {"error": "wan_keyframes_invalid_request", "detail": str(e)})


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
    diffusion_models = list_diffusion_models(settings)
    text_encoders = list_text_encoders(settings)
    vaes = list_vaes(settings)

    workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
    templates = []
    if workflows_dir.exists():
        templates = sorted(p.stem for p in workflows_dir.glob("*.json"))

    return {
        "checkpoints": checkpoints,
        "loras": loras,
        "diffusion_models": diffusion_models,
        "text_encoders": text_encoders,
        "vaes": vaes,
        "video_models": [],
        "video_loras": [],
        "video_inputs": [],
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
    # 1. 先查 in-memory queue（queued / running / failed）
    queue_status = queue_get_job_status(job_id)
    if queue_status:
        resp = {
            "status": queue_status["status"],
            "job_id": job_id,
            "prompt_id": queue_status.get("prompt_id"),
            "submitted_at": queue_status.get("submitted_at"),
        }
        if queue_status["status"] == "failed":
            # 自訂 workflow 被 ComfyUI 拒絕時，回傳結構化 node_errors 供 agent 修正重送
            resp["error"] = queue_status.get("error")
            resp["node_errors"] = queue_status.get("node_errors", [])
            resp["recording_error"] = queue_status.get("recording_error")
        return resp

    # 2. 查 DB（completed）
    artifacts = (
        db.query(GeneratedArtifact)
        .filter(GeneratedArtifact.job_id == job_id)
        .order_by(GeneratedArtifact.id.asc())
        .all()
    )
    image_record = db.query(GeneratedImage).filter_by(job_id=job_id).first()
    if artifacts or image_record:
        artifact_items = [
            {
                "id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "mime_type": artifact.mime_type,
                "gallery_path": artifact.gallery_path,
                "file_size": artifact.file_size,
                "job_id": artifact.job_id,
                "source_node_id": artifact.source_node_id,
                "source_node_type": artifact.source_node_type,
            }
            for artifact in artifacts
        ]
        resp = {
            "status": "completed",
            "job_id": job_id,
            "artifacts": artifact_items,
        }
        if image_record:
            resp["image_id"] = image_record.id
            resp["image_path"] = image_record.image_path
        return resp

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
