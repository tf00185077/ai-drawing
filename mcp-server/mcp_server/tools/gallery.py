"""
Gallery MCP Tools

Corresponds to: GET /api/gallery/, GET /api/gallery/{id}, POST /api/gallery/{id}/rerun
"""
import json
import os

from mcp_server.config import get_mcp_settings
from mcp_server.server import _get_client, mcp


@mcp.tool()
def gallery_list(
    checkpoint: str | None = None,
    lora: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Get the gallery list with optional filtering by checkpoint, lora, and date range."""
    try:
        client = _get_client()
        params = {"limit": limit, "offset": offset}
        if checkpoint:
            params["checkpoint"] = checkpoint
        if lora:
            params["lora"] = lora
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        resp = client.get("gallery/", params=params)
        items = resp.get("items", [])
        total = resp.get("total", 0)
        if not items:
            return f"共 {total} 筆，無符合條件的圖片"
        lines = [f"共 {total} 筆，顯示 {len(items)} 筆:"]
        for it in items[:10]:  # 最多列 10 筆
            lines.append(
                f"  id={it.get('id')} | {it.get('prompt', '')[:50]}... | {it.get('created_at', '')}"
            )
        if len(items) > 10:
            lines.append("  ...")
        return "\n".join(lines)
    except Exception as e:
        return f"error: {e}"


@mcp.tool()
def get_gallery_image(image_id: int) -> str:
    """Get a single image and return agent-friendly JSON including image_url, local_path, and full metadata."""
    try:
        settings = get_mcp_settings()
        client = _get_client()
        resp = client.get(f"gallery/{image_id}")
        image_path = resp.get("image_path", "")
        # 優先使用 backend 回傳的 image_url；若無則由 backend base URL + image_path 組出
        image_url = resp.get("image_url") or f"{settings.backend_api_url}/gallery/{image_path}"
        local_path = os.path.join(settings.gallery_dir, image_path) if image_path else ""
        return json.dumps(
            {
                "ok": True,
                "tool": "get_gallery_image",
                "image_id": resp.get("id", image_id),
                "image_path": image_path,
                "image_url": image_url,
                "local_path": local_path,
                "metadata": {
                    "checkpoint": resp.get("checkpoint"),
                    "lora": resp.get("lora"),
                    "template": resp.get("template"),
                    "diffusion_model": resp.get("diffusion_model"),
                    "text_encoder": resp.get("text_encoder"),
                    "vae": resp.get("vae"),
                    "seed": resp.get("seed"),
                    "steps": resp.get("steps"),
                    "cfg": resp.get("cfg"),
                    "prompt": resp.get("prompt"),
                    "negative_prompt": resp.get("negative_prompt"),
                    "created_at": resp.get("created_at"),
                },
                "next": "deliver image to user, then call free_comfyui_memory if not already called",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "get_gallery_image",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )


@mcp.tool()
def get_gallery_artifact(artifact_id: int) -> str:
    """Get a recorded generated artifact, including video artifacts, and return stable JSON with local delivery metadata."""
    try:
        client = _get_client()
        resp = client.get(f"gallery/artifacts/{artifact_id}")
        return json.dumps(
            {
                "ok": True,
                "tool": "get_gallery_artifact",
                "artifact_id": resp.get("id", artifact_id),
                "artifact_type": resp.get("artifact_type"),
                "mime_type": resp.get("mime_type"),
                "gallery_path": resp.get("gallery_path"),
                "artifact_url": resp.get("artifact_url"),
                "local_path": resp.get("local_path"),
                "file_size": resp.get("file_size"),
                "job_id": resp.get("job_id"),
                "source_node_id": resp.get("source_node_id"),
                "source_node_type": resp.get("source_node_type"),
                "workflow_metadata": {
                    "workflow_json": resp.get("workflow_json"),
                    "prompt": resp.get("prompt"),
                    "negative_prompt": resp.get("negative_prompt"),
                    "metadata_json": resp.get("metadata_json"),
                    "fps": resp.get("fps"),
                    "frame_count": resp.get("frame_count"),
                    "duration": resp.get("duration"),
                    "width": resp.get("width"),
                    "height": resp.get("height"),
                    "created_at": resp.get("created_at"),
                },
                "next": "deliver artifact to user, then call free_comfyui_memory if not already called",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "get_gallery_artifact",
                "where": "backend",
                "artifact_id": artifact_id,
                "error": str(e),
            },
            ensure_ascii=False,
        )


@mcp.tool()
def gallery_rerun(image_id: int) -> str:
    """One-click re-run: reload the image parameters and generate again, returns job_id."""
    try:
        client = _get_client()
        resp = client.post(f"gallery/{image_id}/rerun")
        job_id = resp.get("job_id", "unknown")
        return f"已加入生圖佇列: job_id={job_id}"
    except Exception as e:
        return f"error: {e}"
