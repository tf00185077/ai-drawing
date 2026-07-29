"""MCP tool catalog registration and documentation tests."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import re

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
async def test_prompt_library_restore_exposes_exact_locator_schema() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["prompt_library_restore"].inputSchema

    assert set(schema["required"]) == {
        "resource_type",
        "resource_id",
        "expected_revision",
        "expected_etag",
    }
    assert {"polarity", "category_id"} <= set(schema["properties"])


@pytest.mark.asyncio
async def test_lora_start_exposes_only_broad_recipe_transport() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["lora_train_start"].inputSchema

    assert set(schema["properties"]) == {
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe",
    }
    assert set(schema["required"]) == set(schema["properties"])
    recipe_schema = schema["properties"]["recipe"]
    accepted_types = {
        branch.get("type")
        for branch in recipe_schema.get("anyOf", [])
    }
    assert accepted_types == {"object", "string"}
    description = registered["lora_train_start"].description.lower()
    assert "json object string" in description
    assert "alias" in description


@pytest.mark.asyncio
async def test_lora_preflight_advertises_optional_broad_recipe_hints() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["lora_training_decision_preflight"].inputSchema

    assert "recipe" in schema["properties"]
    assert "recipe" not in schema.get("required", [])
    description = registered[
        "lora_training_decision_preflight"
    ].description.lower()
    assert "json object string" in description


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


def test_lora_recipe_docs_describe_broad_input_and_exact_start_handoff() -> None:
    text = (PROJECT_ROOT / "docs" / "mcp-setup.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"```json lora-recipe-contract\n(.*?)\n```",
        text,
        flags=re.S,
    )
    assert match, "docs must include a machine-readable LoRA recipe contract"
    contract = json.loads(match.group(1))

    assert contract["schema_version"] == "lora-training-recipe/v1"
    assert set(contract["start_required_top_level"]) == {
        "folder",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe",
    }
    assert set(contract["recipe_input_forms"]) == {
        "object",
        "JSON-object string",
    }
    assert {
        "schema_version",
        "expected_recipe_hash",
        "model",
        "scope",
        "dataset",
        "optimization",
        "caching",
        "execution",
    } == set(contract["canonical_recipe_fields"])

    envelope = contract["strict_error_envelope"]
    assert envelope["ok"] is False
    assert envelope["tool"] == "lora_train_start"
    assert set(envelope["error_fields"]) == {
        "code",
        "message",
        "hint",
        "details",
    }

    migration = contract["migration_error"]
    assert migration["code"] == "legacy_training_fields_removed"
    assert migration["invokes_start"] is False
    assert migration["returns_field_names_only"] is True

    handoff = contract["handoff"]
    assert handoff["source"] == "preflight.start_payload"
    assert handoff["submit_exact"] is True
    assert handoff["allow_rebuild_or_override"] is False


def test_saved_workflow_intents_are_in_the_audited_catalog() -> None:
    entries = {entry.name: entry for entry in INTENDED_TOOLS}
    assert entries[
        "save_successful_workflow_as_style_preset"
    ].backend_endpoints == (
        "POST /api/style-presets/{preset_id}/workflow/save",
    )
    assert entries["test_saved_style_preset_workflow"].backend_endpoints == (
        "POST /api/style-presets/{preset_id}/workflow/test",
    )
