"""CIV-V-E MCP compatibility preflight forwarding contract."""
from __future__ import annotations

import pytest

from mcp_server.server import mcp
from mcp_server.tools import civitai_recipes


class Client:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, json: dict) -> dict:
        self.calls.append((path, json))
        return self.payload


def test_compatibility_forwards_exact_frozen_body_and_keeps_incompatible_ok(monkeypatch) -> None:
    client = Client({"status": "incompatible", "compatible": False, "diagnostics": [{"code": "unknown_model_family"}]})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    body = {"recipe": {"schema_version": "1.0"}, "resource_report": {"strict": True}, "model_family": "sdxl", "runtime_capabilities": {"engine": "comfyui"}}
    result = civitai_recipes.civitai_recipe_compatibility(**body)
    assert result["ok"] is True
    assert result["data"]["compatible"] is False
    assert client.calls == [("civitai-recipes/compatibility", body)]


@pytest.mark.asyncio
async def test_compatibility_schema_exposes_only_frozen_inputs() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert set(tools["civitai_recipe_compatibility"].inputSchema["properties"]) == {"recipe", "resource_report", "model_family", "runtime_capabilities"}
