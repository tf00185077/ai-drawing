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
