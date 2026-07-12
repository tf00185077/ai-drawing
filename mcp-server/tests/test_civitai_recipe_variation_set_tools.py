"""CIV-V-G MCP variation-set wrapper contract."""
from __future__ import annotations

import pytest

from mcp_server.tools import civitai_recipes


@pytest.mark.asyncio
async def test_generate_wrapper_fastmcp_schema_is_strict_nested_and_bounded() -> None:
    """CIV-V-G-AC6: the client-visible schema itself rejects oversized/forged child input."""
    from mcp_server.server import mcp

    tool = {item.name: item for item in await mcp.list_tools()}["civitai_recipe_variation_set_generate"]
    children = tool.inputSchema["properties"]["children"]
    assert children["minItems"] == 1
    assert children["maxItems"] == 8
    child_schema = tool.inputSchema["$defs"][children["items"]["$ref"].split("/")[-1]]
    assert child_schema["additionalProperties"] is False
    assert child_schema["properties"]["client_child_key"]["maxLength"] == 128


def test_four_variation_set_wrappers_forward_exact_method_path(monkeypatch) -> None:
    calls = []
    class Client:
        def post(self, endpoint, json): calls.append(("POST", endpoint, json)); return {"variation_set_id": "set"}
        def get(self, endpoint): calls.append(("GET", endpoint, None)); return {"variation_set_id": "set"}
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    child = civitai_recipes.CivitaiVariationSetChild(client_child_key="child-1", directives=[])
    civitai_recipes.civitai_recipe_variation_set_generate(
        parent_recipe={"schema_version": "1.0", "source": {"provider": "civitai", "image_id": 1}},
        parent_recipe_sha256="a" * 64, children=[child], model_family="sdxl",
        runtime_capabilities={"engine": "comfyui", "engine_version": "1", "node_types": [], "sampler_names": [], "scheduler_names": [], "snapshot_sha256": "b" * 64},
        runtime_provenance={"engine": "comfyui", "engine_version": "1", "reference": "runtime:1"},
        input_bindings={},
    )
    civitai_recipes.civitai_recipe_variation_set_status("set")
    civitai_recipes.civitai_recipe_variation_set_cancel("set")
    civitai_recipes.civitai_recipe_variation_set_export("set")
    assert [(method, path) for method, path, _payload in calls] == [
        ("POST", "civitai-recipes/variation-sets"),
        ("GET", "civitai-recipes/variation-sets/set"),
        ("POST", "civitai-recipes/variation-sets/set/cancel"),
        ("GET", "civitai-recipes/variation-sets/set/export"),
    ]
    assert calls[0][2] == {
        "parent_recipe": {"schema_version": "1.0", "source": {"provider": "civitai", "image_id": 1}},
        "parent_recipe_sha256": "a" * 64,
        "children": [{"client_child_key": "child-1", "directives": []}],
        "model_family": "sdxl",
        "runtime_capabilities": {"engine": "comfyui", "engine_version": "1", "node_types": [], "sampler_names": [], "scheduler_names": [], "snapshot_sha256": "b" * 64},
        "runtime_provenance": {"engine": "comfyui", "engine_version": "1", "reference": "runtime:1"},
        "input_bindings": {},
    }


def test_catalog_has_four_variation_set_tools() -> None:
    from mcp_server.tool_catalog import INTENDED_TOOLS
    names = {item.name for item in INTENDED_TOOLS}
    assert {"civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status", "civitai_recipe_variation_set_cancel", "civitai_recipe_variation_set_export"} <= names


def test_mcp_variation_set_payload_redacts_controlled_facade_and_signed_url_sentinels() -> None:
    """CIV-V-G-AC2/AC7: MCP is a second redaction boundary for backend evidence."""
    payload = civitai_recipes._result("civitai_recipe_variation_set_generate", {
        "members": [{
            "outcome": "failed",
            "error": {
                "message": "Authorization: local-secret-sentinel; Cookie: cookie-sentinel; token=token-sentinel",
            },
        }],
        "gallery_export": {
            "signed_url": "https://cdn.example/file?X-Amz-Signature=signed-sentinel&token=token-sentinel",
        },
    }, "next")
    assert "sentinel" not in str(payload).lower()
