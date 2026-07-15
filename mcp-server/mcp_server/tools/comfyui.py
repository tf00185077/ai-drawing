"""
ComfyUI Direct-Connection MCP Tools

Calls the ComfyUI API directly (bypassing the ai-drawing backend) to free
VRAM after heavy jobs. Long video/high-resolution generations can leave
models resident; freeing keeps the next job from OOMing.
"""
import json

import httpx

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp
from mcp_server.tools.responses import exception_error_json


@mcp.tool()
def free_comfyui_memory(
    unload_models: bool = True,
    free_memory: bool = True,
) -> str:
    """Free ComfyUI VRAM. Call after a heavy generation (video, large batch, hires) completes or fails. Returns agent-friendly JSON."""
    settings = get_mcp_settings()
    comfyui_url = settings.comfyui_api_url.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{comfyui_url}/free",
                json={"unload_models": unload_models, "free_memory": free_memory},
            )
            resp.raise_for_status()
        return json.dumps(
            {
                "ok": True,
                "tool": "free_comfyui_memory",
                "comfyui_base_url": comfyui_url,
                "unload_models": unload_models,
                "free_memory": free_memory,
                "next": "generation cycle is complete",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("free_comfyui_memory", e, where="comfyui")
