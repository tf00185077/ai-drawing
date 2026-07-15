"""
Image Generation MCP Tools

Corresponds to: POST /api/generate/, GET /api/generate/job/{job_id}
Supports character and style semantic mapping (character_style).
"""
import json
from urllib.parse import quote

from mcp_server.character_style import resolve_to_prompt
from mcp_server.config import get_mcp_settings
from mcp_server.server import _get_client, mcp
from mcp_server.tools.responses import error_json, exception_error_json


def _resource_list(resp: dict, key: str) -> list:
    value = resp.get(key)
    return value if isinstance(value, list) else []


@mcp.tool()
def generate_image(
    prompt: str = "1girl, solo",
    character: str | None = None,
    style: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    template: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
    batch_size: int | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    lora_strength: float | None = None,
    loras: list[dict] | None = None,
    denoise: float | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
) -> str:
    """Trigger image generation. Accepts character and style in natural language or a direct prompt. Supports full parameter control: sampler_name, scheduler, lora_strength, denoise, width/height, etc. batch_size allows generating multiple images at once (1-8). template selects the workflow template (e.g. "anima" for the Anima diffusion-model family); omit it to auto-pick default / default_lora based on lora. diffusion_model / text_encoder / vae are components for diffusion-model families (e.g. Anima). loras is an ordered list of {name, strength_model, strength_clip?} for multi-LoRA workflows, taking precedence over the single lora. Returns job_id or an error message. To generate based on a Civitai image, use civitai_generate_like instead."""
    try:
        client = _get_client()
        final_prompt = prompt
        resolved_lora = lora

        if character or style:
            base = prompt if prompt else "1girl, solo"
            final_prompt, style_lora = resolve_to_prompt(
                character=character, style=style, base_prompt=base
            )
            if style_lora and not resolved_lora:
                resolved_lora = style_lora

        body: dict[str, object] = {"prompt": final_prompt}
        if checkpoint:
            body["checkpoint"] = checkpoint
        if template:
            body["template"] = template
        if resolved_lora:
            body["lora"] = resolved_lora
        if negative_prompt is not None:
            body["negative_prompt"] = negative_prompt
        if seed is not None:
            body["seed"] = seed
        if steps is not None:
            body["steps"] = steps
        if cfg is not None:
            body["cfg"] = cfg
        if batch_size is not None:
            if 1 <= batch_size <= 8:
                body["batch_size"] = batch_size
        else:
            body["batch_size"] = 1
        if width is not None:
            body["width"] = width
        if height is not None:
            body["height"] = height
        if sampler_name is not None:
            body["sampler_name"] = sampler_name
        if scheduler is not None:
            body["scheduler"] = scheduler
        if lora_strength is not None:
            body["lora_strength"] = lora_strength
        if loras is not None:
            body["loras"] = loras
        if denoise is not None:
            body["denoise"] = denoise
        if diffusion_model is not None:
            body["diffusion_model"] = diffusion_model
        if text_encoder is not None:
            body["text_encoder"] = text_encoder
        if vae is not None:
            body["vae"] = vae
        resp = client.post("generate/", json=body)
        job_id = resp.get("job_id", "unknown")
        status = resp.get("status", "queued")
        return json.dumps(
            {
                "ok": True,
                "tool": "generate_image",
                "job_id": job_id,
                "status": status,
                "submitted": body,
                "next": "call get_generation_status with this job_id",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("generate_image", e, where="backend")


@mcp.tool()
def generate_video_wan_keyframes(
    images: list[str],
    prompt: str,
    negative_prompt: str | None = None,
    width: int = 320,
    height: int = 480,
    length: int = 161,
    fps: float = 16.1,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
    filename_prefix: str = "video/wan_keyframes",
) -> str:
    """Generate one Wan video from multiple gallery-relative keyframe images using a single WanDancer workflow. This is not pairwise segment concatenation: the backend batches all keyframes into WanDancerPadKeyframes and submits one workflow. Poll get_generation_status(job_id), then fetch completed video artifacts via get_gallery_artifact."""
    try:
        client = _get_client()
        body: dict[str, object] = {
            "images": images,
            "prompt": prompt,
            "width": width,
            "height": height,
            "length": length,
            "fps": fps,
            "steps": steps,
            "cfg": cfg,
            "filename_prefix": filename_prefix,
        }
        optional_values = {
            "negative_prompt": negative_prompt,
            "seed": seed,
        }
        for key, value in optional_values.items():
            if value is not None:
                body[key] = value
        resp = client.post("generate/video/wan-keyframes", json=body)
        job_id = resp.get("job_id", "unknown")
        status = resp.get("status", "queued")
        return json.dumps(
            {
                "ok": True,
                "tool": "generate_video_wan_keyframes",
                "job_id": job_id,
                "status": status,
                "keyframe_count": len(images),
                "workflow_family": "wan_dancer_multi_keyframe",
                "next": "poll get_generation_status(job_id); on completion use artifacts[] with get_gallery_artifact",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("generate_video_wan_keyframes", e, where="backend")


@mcp.tool()
def get_generation_status(job_id: str) -> str:
    """Query generation job status, returns agent-friendly JSON. Completed jobs include artifacts[]; image jobs keep image_id/image_path. Failed jobs return a structured error."""
    try:
        client = _get_client()
        resp = client.get(f"generate/job/{job_id}")
        status = resp.get("status", "unknown")
        if status == "completed":
            artifacts = resp.get("artifacts", [])
            has_non_image_artifact = any(
                artifact.get("artifact_type") != "image"
                for artifact in artifacts
                if isinstance(artifact, dict)
            )
            next_step = (
                "call get_gallery_artifact with an artifact id from artifacts[]"
                if has_non_image_artifact
                else "call get_gallery_image with image_id to deliver the result"
            )
            return json.dumps(
                {
                    "ok": True,
                    "tool": "get_generation_status",
                    "job_id": job_id,
                    "status": "completed",
                    "image_id": resp.get("image_id"),
                    "image_path": resp.get("image_path", ""),
                    "artifacts": artifacts,
                    "next": next_step,
                },
                ensure_ascii=False,
            )
        elif status == "failed":
            node_errors = resp.get("node_errors", [])
            return json.dumps(
                {
                    "ok": False,
                    "tool": "get_generation_status",
                    "job_id": job_id,
                    "status": "failed",
                    "error": {
                        "code": "generation_failed",
                        "message": str(resp.get("error") or "generation failed"),
                        "details": {"where": "comfyui"},
                    },
                    "node_errors": node_errors,
                    "recording_error": resp.get("recording_error"),
                    "next": "generation failed; inspect the error, adjust parameters, and resubmit",
                },
                ensure_ascii=False,
            )
        elif status in ("queued", "running"):
            return json.dumps(
                {
                    "ok": True,
                    "tool": "get_generation_status",
                    "job_id": job_id,
                    "status": status,
                    "prompt_id": resp.get("prompt_id"),
                    "next": "wait, then call get_generation_status again",
                },
                ensure_ascii=False,
            )
        else:
            return error_json(
                "get_generation_status",
                "job_not_found",
                f"Job not found or unexpected status: {status}",
                details={"where": "backend"},
                job_id=job_id,
            )
    except Exception as e:
        return exception_error_json("get_generation_status", e, where="backend", job_id=job_id)


@mcp.tool()
def cancel_job(job_id: str) -> str:
    """Cancel an image generation job that has not yet started (pending status). Running jobs cannot be cancelled."""
    try:
        client = _get_client()
        resp = client.delete(f"generate/queue/{quote(job_id, safe='')}")
        return json.dumps(
            {
                "ok": True,
                "tool": "cancel_job",
                "job_id": resp.get("job_id", job_id),
                "status": "cancelled",
                "message": resp.get("message", "已取消"),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("cancel_job", e, where="backend", job_id=job_id)


@mcp.tool()
def list_available_resources() -> str:
    """List available checkpoints, LoRAs, diffusion models, text encoders, VAEs, and workflow templates, returns agent-friendly JSON. To add a new model from Civitai, use civitai_resource_acquire."""
    try:
        client = _get_client()
        resp = client.get("generate/available-resources")
        checkpoints = _resource_list(resp, "checkpoints")
        loras = _resource_list(resp, "loras")
        diffusion_models = _resource_list(resp, "diffusion_models")
        text_encoders = _resource_list(resp, "text_encoders")
        vaes = _resource_list(resp, "vaes")
        video_models = _resource_list(resp, "video_models")
        video_loras = _resource_list(resp, "video_loras")
        video_inputs = _resource_list(resp, "video_inputs")
        workflows = _resource_list(resp, "workflows")
        default_checkpoint = resp.get("default_checkpoint")
        next_step = (
            "choose a checkpoint, then call generate_image"
            if checkpoints
            else "no checkpoints available; download one with civitai_resource_acquire or check that the model disk is mounted"
        )
        return json.dumps(
            {
                "ok": True,
                "tool": "list_available_resources",
                "backend_base_url": get_mcp_settings().backend_api_url,
                "checkpoints": checkpoints,
                "loras": loras,
                "diffusion_models": diffusion_models,
                "text_encoders": text_encoders,
                "vaes": vaes,
                "video_models": video_models,
                "video_loras": video_loras,
                "video_inputs": video_inputs,
                "workflows": workflows,
                "default_checkpoint": default_checkpoint,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("list_available_resources", e, where="backend")
