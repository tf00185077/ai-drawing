"""CIV-SA-D typed MCP source-alias forwarding contracts; offline only."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS
from mcp_server.tools import civitai_recipes


class Client:
    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]):
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _audited_binding() -> dict[str, object]:
    return {
        "matched_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero", "kind": "primary"},
        "registry_version": 7,
        "source_identity": {"provider": "civitai", "image_id": 123},
        "acquisition_evidence_snapshot": {"raw_api_payload": {"id": 123}},
        "acquisition_evidence_sha256": "a" * 64,
        "parent_recipe_sha256": "b" * 64,
        "thumbnail_url": "https://image.civitai.com/thumb.png",
        "thumbnail_path": "2026-07/hero.png",
        "user_note": "approved source",
        "approved_tags": ["hero"],
        "prompt_summary": "hero at sunset",
        "created_at": "2026-07-13T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_mcp_import_remember_alias_schema_and_exact_forwarding(monkeypatch) -> None:
    """CIV-SA-D-AC1: expose and transparently forward optional remember_alias once."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["civitai_recipe_import"].inputSchema
    assert set(schema["properties"]) == {"locator", "embedded_image", "remember_alias"}
    assert "remember_alias" not in schema.get("required", [])

    client = Client({"source_alias_result": {"persisted": True, "registry_version": 7}})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    raw = b"\x89PNG\r\n\x1a\nfixture"
    encoded = base64.b64encode(raw).decode("ascii")

    without_alias = civitai_recipes.civitai_recipe_import(locator=123)
    with_alias = civitai_recipes.civitai_recipe_import(locator=123, embedded_image=encoded, remember_alias="  Sunset Hero  ")

    assert without_alias["data"]["source_alias_result"] == {"persisted": True, "registry_version": 7}
    assert with_alias["data"]["source_alias_result"] == {"persisted": True, "registry_version": 7}
    assert client.calls == [
        ("post", "civitai-recipes/import", {"locator": 123}),
        ("post", "civitai-recipes/import", {"locator": 123, "embedded_image_base64": encoded, "remember_alias": "  Sunset Hero  "}),
    ]


@pytest.mark.asyncio
async def test_mcp_exact_alias_resolve_forwards_one_alias_and_preserves_audited_binding(monkeypatch) -> None:
    """CIV-SA-D-AC2: resolver is a single-alias exact route facade."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["civitai_source_alias_resolve"].inputSchema
    assert set(schema["properties"]) == {"alias"}
    assert schema["required"] == ["alias"]

    binding = _audited_binding()
    client = Client(binding)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)

    result = civitai_recipes.civitai_source_alias_resolve(alias="  ＳＵＮＳＥＴ\u2003Hero  ")

    assert result == {
        "ok": True,
        "tool": "civitai_source_alias_resolve",
        "data": binding,
        "next": "use the immutable audited source binding as-is; do not search or rebuild it",
    }
    assert client.calls == [("post", "civitai-recipes/source-aliases/resolve", {"alias": "  ＳＵＮＳＥＴ\u2003Hero  "})]


@pytest.mark.parametrize(
    ("tool", "call", "status", "detail", "expected_code"),
    [
        (
            "civitai_recipe_import",
            lambda: civitai_recipes.civitai_recipe_import(locator=123, remember_alias="hero"),
            422,
            {"code": "alias_invalid", "message": "Bearer ALIAS-SECRET", "details": {"token": "ALIAS-SECRET"}},
            "alias_invalid",
        ),
        (
            "civitai_source_alias_resolve",
            lambda: civitai_recipes.civitai_source_alias_resolve(alias="hero"),
            404,
            {"code": "not_found", "message": "token=ALIAS-SECRET", "details": {"secret": "ALIAS-SECRET"}},
            "not_found",
        ),
        (
            "civitai_source_alias_resolve",
            lambda: civitai_recipes.civitai_source_alias_resolve(alias="duplicate"),
            409,
            {"code": "corrupt_registry", "message": "cookie=ALIAS-SECRET", "details": {"password": "ALIAS-SECRET"}},
            "corrupt_registry",
        ),
    ],
)
def test_mcp_alias_failures_are_redacted_fail_closed_and_do_not_fallback(monkeypatch, tool, call, status, detail, expected_code) -> None:
    """CIV-SA-D-AC3: every failure is one redacted request with no fallback paths."""
    request = httpx.Request("POST", "http://backend/api/civitai-recipes/source-aliases/resolve")
    response = httpx.Response(status, request=request, json={"detail": detail})
    client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response))
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)

    result = call()

    assert result["ok"] is False
    assert result["tool"] == tool
    assert result["status_code"] == status
    assert result["error"]["code"] == expected_code
    assert "ALIAS-SECRET" not in json.dumps(result)
    assert len(client.calls) == 1
    assert client.calls[0][0] == "post"
    assert client.calls[0][1] in {"civitai-recipes/import", "civitai-recipes/source-aliases/resolve"}

    transport_client = Client(httpx.ConnectError("Bearer ALIAS-SECRET"))
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport_client)
    transport_result = civitai_recipes.civitai_source_alias_resolve(alias="offline")
    assert transport_result == {
        "ok": False,
        "tool": "civitai_source_alias_resolve",
        "error": {"code": "ConnectError", "message": "Bearer [REDACTED]", "details": {"where": "backend"}},
    }
    assert transport_client.calls == [("post", "civitai-recipes/source-aliases/resolve", {"alias": "offline"})]


@pytest.mark.asyncio
async def test_mcp_alias_tools_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-D-AC4: registration, audited catalog, and active-doc rows agree."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    entry = next(item for item in INTENDED_TOOLS if item.name == "civitai_source_alias_resolve")
    assert entry.response_category == "dict"
    assert entry.backend_endpoints == ("POST /api/civitai-recipes/source-aliases/resolve",)
    assert registered[entry.name].outputSchema["type"] == "object"
    assert set(registered["civitai_recipe_import"].inputSchema["properties"]) == {"locator", "embedded_image", "remember_alias"}

    root = Path(__file__).resolve().parents[2]
    expected_row = "| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |"
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        active = path.read_text(encoding="utf-8").split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert expected_row in active
        assert "`civitai_recipe_import`" in active
