"""MCP Server 單元測試"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
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


def test_mcp_ping_returns_structured_result() -> None:
    """Ping checks its health dependency without contacting a product service."""
    client = MagicMock()
    client.get.return_value = {"status": "ok"}
    with patch("mcp_server.server.HttpBackendClient", return_value=client):
        result = mcp_ping()
    client.get.assert_called_once_with("health")
    assert isinstance(result, dict)
    assert "ok" in result


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


@pytest.mark.asyncio
async def test_stdio_start_legacy_flat_field_gets_redacted_migration_error() -> None:
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
            catalog = await session.list_tools()
            result = await session.call_tool(
                "lora_train_start",
                {
                    "folder": "character/miku",
                    "checkpoint": "super-secret-value",
                },
            )

    start_tool = next(
        tool for tool in catalog.tools if tool.name == "lora_train_start"
    )
    assert {
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "output_name",
        "recipe",
    } <= set(start_tool.inputSchema["required"])
    assert result.isError is False
    assert result.structuredContent is not None
    payload = result.structuredContent.get("result", result.structuredContent)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "legacy_training_fields_removed"
    assert payload["error"]["details"]["fields"] == ["checkpoint"]
    assert "decision preflight" in payload["error"]["hint"]
    assert "super-secret-value" not in json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_protocol_start_missing_recipe_is_structured_and_redacted() -> None:
    result = await mcp.call_tool(
        "lora_train_start",
        {
            "folder": "character/miku",
            "expected_dataset_hash": "dataset-hash",
            "expected_profile_hash": "profile-hash",
            "output_name": "Protocol Test",
        },
    )
    payload = result[1]

    assert payload["ok"] is False
    assert payload["error"]["code"] == "request_validation_failed"
    assert {
        tuple(entry["loc"])
        for entry in payload["error"]["details"]["validation_errors"]
    } == {("recipe",)}


@pytest.mark.asyncio
async def test_stdio_envelope_success_and_non_lora_validation_before_http() -> None:
    """Formal stdio protocol with a test-only HTTP dependency below real tools."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    requests = []
    class Backend(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass

    backend = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    try:
        params = StdioServerParameters(command=sys.executable, args=['-m', 'mcp_server.server'], cwd=str(Path(__file__).resolve().parents[1]), env={'MCP_BACKEND_API_URL': f'http://127.0.0.1:{backend.server_port}'})
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool('mcp_ping', {})
                assert result.isError is False
                assert result.structuredContent == {'ok': True, 'data': {'backend_reachable': True}}
                assert json.loads(result.content[0].text) == result.structuredContent
                for name, args in [('job_status', {}), ('prompt_compose', {'save_as': None})]:
                    result = await session.call_tool(name, args)
                    assert result.isError is False
                    assert set(result.structuredContent) == {'ok', 'error'}
                    assert result.structuredContent['error']['code'] == 'request_validation_failed'
                    assert json.loads(result.content[0].text) == result.structuredContent
        assert requests == ['/health']
    finally:
        backend.shutdown()
        backend.server_close()
        thread.join(timeout=2)
