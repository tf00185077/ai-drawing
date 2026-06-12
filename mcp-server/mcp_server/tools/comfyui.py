"""
ComfyUI 直連 MCP Tools

直接呼叫 ComfyUI API（不走 ai-drawing backend），目前用於釋放記憶體。
"""
import json

import httpx

from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp


@mcp.tool()
def free_comfyui_memory(
    unload_models: bool = True,
    free_memory: bool = True,
) -> str:
    """釋放 ComfyUI 顯示記憶體，生圖完成或失敗後必須呼叫。回傳 agent-friendly JSON。"""
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
        return json.dumps(
            {
                "ok": False,
                "tool": "free_comfyui_memory",
                "where": "comfyui",
                "error": str(e),
            },
            ensure_ascii=False,
        )
