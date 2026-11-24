"""MCP tool catalog registration and documentation tests."""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DOCS = (
    PROJECT_ROOT / "docs" / "mcp.md",
)

# Independent policy expectations, not values read from the production catalog.
# Source: docs/decisions/mcp.md (tool map, retained intents and staged delivery),
# cleared at 496cee2f842dc9386d336afb237075bf952271ce; p1-02 D2.
# p1-03 adds wait=read under the cleared decision at a88b84a; all prior labels remain.
# p1-04 replaces ping and adds health/list_workers=read under the cleared
# configured-worker decision at b075f36. Preflight/compose POSTs are read intents; caption,
# acquisition, training/smoke submission and cancellation mutate persistent state.
APPROVED_INTENT_RISKS = {
    "health": "read",
    "list_workers": "read",
    "list_resources": "read",
    "generate": "mutate",
    "job_status": "read",
    "wait_for_job": "read",
    "cancel_job": "mutate",
    "gallery_search": "read",
    "gallery_get": "read",
    "gallery_rerun": "mutate",
    "prompt_search": "read",
    "prompt_compose": "read",
    "prompt_write": "mutate",
    "style_preset_get": "read",
    "style_preset_compose": "read",
    "style_preset_save": "mutate",
    "style_preset_test": "mutate",
    "comfyui_admin": "admin",
    "deliver_to_discord": "mutate",
    "civitai_source_info": "read",
    "civitai_resource_acquire": "mutate",
    "civitai_resource_status": "read",
    "lora_dataset_list": "read",
    "lora_dataset_inspect": "read",
    "caption_image": "mutate",
    "lora_training_decision_preflight": "read",
    "lora_train_start": "mutate",
    "lora_train_job_status": "read",
    "lora_train_logs": "read",
    "lora_train_cancel": "mutate",
    "lora_train_smoke_test": "mutate",
}


def test_catalog_risks_match_approved_intent_policy() -> None:
    """A false label (e.g. ComfyUI restart as read) must fail independently."""
    assert len(INTENDED_TOOLS) == len(APPROVED_INTENT_RISKS) == 31
    assert {entry.name: entry.risk for entry in INTENDED_TOOLS} == APPROVED_INTENT_RISKS
    assert all(entry.external for entry in INTENDED_TOOLS)


@pytest.mark.asyncio
async def test_discovered_risks_match_approved_intent_policy() -> None:
    """Actual MCP discovery must expose exactly one approved label per intent."""
    tools = await mcp.list_tools()
    assert len(tools) == len(APPROVED_INTENT_RISKS)
    assert {tool.name for tool in tools} == set(APPROVED_INTENT_RISKS)
    for tool in tools:
        expected = APPROVED_INTENT_RISKS[tool.name]
        assert tool.description.count("Risk:") == 1, tool.name
        assert re.findall(r"\bRisk:\s*(\w+)\.", tool.description) == [expected], tool.name
        assert tool.description.startswith(f"Risk: {expected}."), tool.name


def test_package_readme_routes_to_current_tool_and_acceptance_authorities() -> None:
    text = (PROJECT_ROOT / "mcp-server" / "README.md").read_text(encoding="utf-8")
    assert "../docs/mcp.md" in text
    assert "MCP-CATALOG:START" not in text



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
    properties = registered["generate"].inputSchema["properties"]
    assert properties["execution_target"]["enum"] == ["local", "worker"]
    for field in ("lora", "lora_strength", "loras"):
        assert field in properties


@pytest.mark.asyncio
async def test_removed_tools_and_staged_tools_are_not_registered() -> None:
    registered = {tool.name for tool in await mcp.list_tools()}
    assert len(registered) == 31
    assert not registered & {
        "generate_image", "generate_image_custom_workflow", "get_generation_status",
        "generate_video_wan_keyframes", "generate_video_custom_workflow", "civitai_generate_like",
        "mcp_ping", "prompt_library_restore",
    }


@pytest.mark.asyncio
async def test_prompt_write_exposes_locator_and_concurrency_schema() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["prompt_write"].inputSchema
    assert set(schema["required"]) == {"action", "resource_type", "resource_id"}
    assert {"polarity", "category_id", "payload", "expected_revision", "expected_etag"} <= set(schema["properties"])
    assert schema["properties"]["action"]["enum"] == ["save", "archive", "restore"]
    assert "save_as" not in registered["prompt_compose"].inputSchema["properties"]


@pytest.mark.asyncio
async def test_lora_start_exposes_only_broad_recipe_transport() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["lora_train_start"].inputSchema

    assert set(schema["properties"]) == {
        "folder",
        "output_name",
        "expected_output_config_hash",
        "expected_dataset_hash",
        "expected_profile_hash",
        "recipe",
    }
    assert set(schema["required"]) == set(schema["properties"]) - {"expected_output_config_hash"}
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
async def test_envelope_schema_and_one_truthful_risk_per_tool() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    for entry in INTENDED_TOOLS:
        schema = registered[entry.name].outputSchema
        assert entry.response_category == "envelope"
        assert schema.get("type") == "object", entry.name
        assert "result" not in schema.get("properties", {}), entry.name
        assert entry.risk in {"read", "mutate", "admin"}
        assert registered[entry.name].description.count("Risk:") == 1
        assert registered[entry.name].description.startswith(f"Risk: {entry.risk}.")
    assert {entry.name: entry.risk for entry in INTENDED_TOOLS}["caption_image"] == "mutate"



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


def test_mcp_docs_do_not_advertise_removed_workflow_tools() -> None:
    text = (PROJECT_ROOT / "docs" / "mcp.md").read_text(encoding="utf-8")
    for name in (
        "search_nodes", "get_node_schema", "list_workflow_templates", "get_workflow_template",
    ):
        assert f"`{name}`" not in text


def test_saved_workflow_intents_are_in_the_audited_catalog() -> None:
    entries = {entry.name: entry for entry in INTENDED_TOOLS}
    assert entries[
        "style_preset_save"
    ].backend_endpoints == (
        "POST /api/style-presets/",
        "POST /api/style-presets/{preset_id}/workflow/save",
    )
    assert entries["style_preset_test"].backend_endpoints == (
        "POST /api/style-presets/{preset_id}/workflow/test",
    )
