"""MCP Server 單元測試"""
import pytest

from mcp_server.server import mcp, mcp_ping


def test_mcp_instance_exists() -> None:
    """MCP 實例存在且為 FastMCP"""
    assert mcp is not None
    assert mcp.name == "AI Drawing"


def test_mcp_ping_returns_string() -> None:
    """mcp_ping 回傳字串（Backend 未啟動時會回傳 error）"""
    result = mcp_ping()
    assert isinstance(result, str)
    assert "ok" in result or "error" in result.lower()


def test_minimum_loop_tools_are_importable() -> None:
    """五個最小閉環 tools 可從各自模組成功 import（確認 server 載入無誤）"""
    from mcp_server.tools.comfyui import free_comfyui_memory
    from mcp_server.tools.gallery import get_gallery_image
    from mcp_server.tools.generate import (
        generate_image,
        get_generation_status,
        list_resources,
    )

    assert callable(list_resources)
    assert callable(generate_image)
    assert callable(get_generation_status)
    assert callable(get_gallery_image)
    assert callable(free_comfyui_memory)
