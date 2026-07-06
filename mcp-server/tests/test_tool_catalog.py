"""MCP tool catalog registration and documentation tests."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS, INTENTIONAL_OMISSIONS


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
async def test_video_custom_workflow_is_registered_with_lora_schema() -> None:
    """Regression for Hermes missing video tool and LoRA fields in its schema."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    tool = registered["generate_video_custom_workflow"]
    properties = tool.inputSchema["properties"]

    assert "generate_video_custom_workflow" in registered
    for name in (
        "workflow",
        "image",
        "first_frame",
        "last_frame",
        "video_ref",
        "checkpoint",
        "lora",
        "lora_strength",
        "loras",
    ):
        assert name in properties


@pytest.mark.asyncio
async def test_supported_lora_tools_expose_loras_input_schema() -> None:
    """Supported generation and preset-authoring tools expose ordered multi-LoRA fields to agents."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    expected_fields = {
        "generate_image": ("lora", "lora_strength", "loras"),
        "generate_image_custom_workflow": ("lora", "lora_strength", "loras"),
        "generate_video_custom_workflow": ("lora", "lora_strength", "loras"),
        "create_style_preset": ("lora", "lora_strength", "loras"),
    }

    for tool_name, fields in expected_fields.items():
        properties = registered[tool_name].inputSchema["properties"]
        for field in fields:
            assert field in properties, f"{tool_name} missing {field}"


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


def test_catalog_docs_list_active_tools_and_intentional_omissions() -> None:
    """Docs must list the audited active catalog and keep stale names out of active tables."""
    expected_names = {entry.name for entry in INTENDED_TOOLS if entry.external}
    omitted_names = {entry.name for entry in INTENTIONAL_OMISSIONS}

    for path in CATALOG_DOCS:
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split(
            "<!-- MCP-CATALOG:END -->", 1
        )[0]
        omissions = text.split("<!-- MCP-OMISSIONS:START -->", 1)[1].split(
            "<!-- MCP-OMISSIONS:END -->", 1
        )[0]

        for name in expected_names:
            assert f"`{name}`" in active, f"{name} missing from {path}"
        for name in omitted_names:
            assert f"`{name}`" not in active, f"{name} listed as active in {path}"
            assert f"`{name}`" in omissions, f"{name} omission missing from {path}"
