"""MCP tool catalog registration and documentation tests."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DOCS = (
    PROJECT_ROOT / "mcp-server" / "README.md",
    PROJECT_ROOT / "docs" / "mcp-setup.md",
)


@pytest.mark.asyncio
async def test_intended_catalog_matches_fastmcp_registration() -> None:
    """Every intended external MCP tool is registered, and extras must be cataloged."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    expected = {entry.name for entry in INTENDED_TOOLS if entry.external}

    assert expected - set(registered) == set()
    assert set(registered) - expected == set()


def test_catalog_points_to_existing_tool_functions() -> None:
    """The catalog's module/function pointers stay aligned with implementation."""
    for entry in INTENDED_TOOLS:
        module = importlib.import_module(entry.module)
        function = getattr(module, entry.function)
        assert callable(function), entry.name


@pytest.mark.asyncio
async def test_generate_image_exposes_multi_lora_schema() -> None:
    """generate_image keeps ordered multi-LoRA fields visible to agents."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    properties = registered["generate_image"].inputSchema["properties"]
    for field in ("lora", "lora_strength", "loras"):
        assert field in properties


@pytest.mark.asyncio
async def test_civitai_generate_like_exposes_intent_level_schema() -> None:
    """The one-call Civitai tool keeps its forgiving, prompt-first schema."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    properties = registered["civitai_generate_like"].inputSchema["properties"]
    for field in ("source", "prompt", "batch_size", "download_missing", "checkpoint"):
        assert field in properties


@pytest.mark.asyncio
async def test_response_categories_match_fastmcp_output_schema() -> None:
    """Structured dict tools expose object output; transitional string tools expose result strings."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    for entry in INTENDED_TOOLS:
        schema = registered[entry.name].outputSchema
        if entry.response_category == "dict":
            assert schema.get("type") == "object", entry.name
            assert "result" not in schema.get("properties", {}), entry.name
        else:
            assert schema["properties"]["result"]["type"] == "string", entry.name


def test_catalog_docs_list_active_tools() -> None:
    """Docs must list the audited active catalog between the MCP-CATALOG markers."""
    expected_names = {entry.name for entry in INTENDED_TOOLS if entry.external and entry.docs_required}

    for path in CATALOG_DOCS:
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split(
            "<!-- MCP-CATALOG:END -->", 1
        )[0]

        for name in expected_names:
            assert f"`{name}`" in active, f"{name} missing from {path}"
