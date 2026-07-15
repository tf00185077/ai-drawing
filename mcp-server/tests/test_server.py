"""MCP Server 單元測試"""
from pathlib import Path
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_server.server import mcp, mcp_ping
from mcp_server.tool_catalog import INTENDED_TOOLS


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
    """最小閉環 tools 可從各自模組成功 import（確認 server 載入無誤）"""
    from mcp_server.tools.civitai import civitai_generate_like
    from mcp_server.tools.gallery import get_gallery_image
    from mcp_server.tools.generate import (
        generate_image,
        get_generation_status,
        list_available_resources,
    )

    assert callable(list_available_resources)
    assert callable(generate_image)
    assert callable(get_generation_status)
    assert callable(get_gallery_image)
    assert callable(civitai_generate_like)


@pytest.mark.asyncio
async def test_module_entrypoint_exposes_complete_formal_stdio_catalog() -> None:
    """``python -m mcp_server.server`` must register tools on the served instance."""
    project_dir = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(project_dir),
        env={},
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()

    assert {tool.name for tool in response.tools} == {
        entry.name for entry in INTENDED_TOOLS
    }
