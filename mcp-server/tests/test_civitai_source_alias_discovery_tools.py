"""CIV-SA-G typed source-alias discovery MCP contracts; offline only."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS
from mcp_server.tools import civitai_recipes


class Client:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def get(self, path: str, params: dict[str, object]) -> object:
        self.calls.append(("get", path, params))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def post(self, path: str, json: dict[str, object]) -> object:
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _list_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "code": "source_aliases_listed",
        "total": 2,
        "paging": {"limit": 2, "offset": 0, "next_offset": None},
        "records": [
            {
                "primary_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
                "alternate_aliases": [{"original_alias": "hero sunset", "normalized_key": "hero sunset"}],
                "source_identity": {"provider": "civitai", "image_id": 123},
                "acquisition_evidence_sha256": "a" * 64,
                "parent_recipe_sha256": "b" * 64,
                "registry_version": 7,
                "created_at": "2026-07-13T00:00:00Z",
            }
        ],
    }


def _search_payload() -> dict[str, object]:
    return {
        "normalized_query": "sunset hero",
        "total": 2,
        "paging": {"limit": 2, "offset": 0, "next_offset": None},
        "candidates": [
            {
                "score": 1.0,
                "matched_fields": ["primary_alias"],
                "aliases": {"primary": "Sunset Hero", "alternates": ["hero sunset"]},
                "source_evidence": {
                    "source_identity": {"provider": "civitai", "image_id": 123},
                    "acquisition_evidence_sha256": "a" * 64,
                    "parent_recipe_sha256": "b" * 64,
                },
            },
            {
                "score": 0.5,
                "matched_fields": ["alternate_alias"],
                "aliases": {"primary": "Sunset Portrait", "alternates": ["hero"]},
                "source_evidence": {"source_identity": {"provider": "civitai", "image_id": 124}},
            },
        ],
    }


@pytest.mark.asyncio
async def test_mcp_source_alias_list_schema_and_exact_get_forwarding(monkeypatch) -> None:
    """CIV-SA-G-AC1: typed paging and one transparent audited-list GET."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["civitai_source_alias_list"].inputSchema
    assert set(schema["properties"]) == {"limit", "offset"}
    assert schema.get("required", []) == []
    assert {"default": 50, "maximum": 100, "minimum": 1, "type": "integer"}.items() <= schema["properties"]["limit"].items()
    assert {"default": 0, "minimum": 0, "type": "integer"}.items() <= schema["properties"]["offset"].items()

    payload = _list_payload()
    client = Client(payload)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_list(limit=2, offset=0)

    assert result["ok"] is True
    assert result["tool"] == "civitai_source_alias_list"
    assert result["data"] == payload
    assert client.calls == [("get", "civitai-recipes/source-aliases", {"limit": 2, "offset": 0})]


@pytest.mark.asyncio
async def test_mcp_source_alias_search_schema_and_candidate_only_forwarding(monkeypatch) -> None:
    """CIV-SA-G-AC2: required bounded query and one candidate-only search POST."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    schema = registered["civitai_source_alias_search"].inputSchema
    assert set(schema["properties"]) == {"query", "limit", "offset"}
    assert schema["required"] == ["query"]
    assert {"maxLength": 512, "minLength": 1, "type": "string"}.items() <= schema["properties"]["query"].items()
    assert {"default": 50, "maximum": 100, "minimum": 1, "type": "integer"}.items() <= schema["properties"]["limit"].items()
    assert {"default": 0, "minimum": 0, "type": "integer"}.items() <= schema["properties"]["offset"].items()

    payload = _search_payload()
    client = Client(payload)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    monkeypatch.setattr(civitai_recipes, "civitai_source_alias_resolve", lambda **_: pytest.fail("search must not exact-resolve"))

    result = civitai_recipes.civitai_source_alias_search(query="Sunset Hero", limit=2, offset=0)

    assert result["ok"] is True
    assert result["tool"] == "civitai_source_alias_search"
    assert result["data"] == payload
    assert "selected" not in result["data"]
    assert "resolved" not in result["data"]
    assert client.calls == [("post", "civitai-recipes/source-aliases/search", {"query": "Sunset Hero", "limit": 2, "offset": 0})]


@pytest.mark.parametrize(
    ("tool", "method", "call", "status", "detail", "expected_code"),
    [
        ("civitai_source_alias_list", "get", lambda: civitai_recipes.civitai_source_alias_list(), 422, {"code": "invalid_page", "message": "Bearer DISCOVERY-SECRET", "nested": {"token": "DISCOVERY-SECRET"}}, "invalid_page"),
        ("civitai_source_alias_search", "post", lambda: civitai_recipes.civitai_source_alias_search(query="hero"), 409, {"code": "corrupt_registry", "message": "cookie=DISCOVERY-SECRET", "nested": [{"password": "DISCOVERY-SECRET"}]}, "corrupt_registry"),
    ],
)
def test_mcp_source_alias_discovery_failures_are_redacted_and_never_fallback(monkeypatch, tool, method, call, status, detail, expected_code) -> None:
    """CIV-SA-G-AC3: failures stay redacted, fail closed, and make no fallback call."""
    request = httpx.Request(method.upper(), "http://backend/api/civitai-recipes/source-aliases")
    response = httpx.Response(status, request=request, json={"detail": detail})
    client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response))
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    monkeypatch.setattr(civitai_recipes, "civitai_source_alias_resolve", lambda **_: pytest.fail("no exact resolver fallback"))

    result = call()

    assert result["ok"] is False
    assert result["tool"] == tool
    assert result["status_code"] == status
    assert result["error"]["code"] == expected_code
    assert "DISCOVERY-SECRET" not in json.dumps(result)
    assert len(client.calls) == 1
    assert client.calls[0][0] == method

    transport = Client(httpx.ConnectError("signed query token=DISCOVERY-SECRET Bearer DISCOVERY-SECRET"))
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    transport_result = civitai_recipes.civitai_source_alias_search(query="offline")
    assert transport_result["ok"] is False
    assert transport_result["tool"] == "civitai_source_alias_search"
    assert "DISCOVERY-SECRET" not in json.dumps(transport_result)
    assert transport.calls == [("post", "civitai-recipes/source-aliases/search", {"query": "offline", "limit": 50, "offset": 0})]


@pytest.mark.asyncio
async def test_mcp_source_alias_discovery_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-G-AC4: only the two audited discovery tools join registration/catalog/docs."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    expected = {
        "civitai_source_alias_list": ("dict", ("GET /api/civitai-recipes/source-aliases",)),
        "civitai_source_alias_search": ("dict", ("POST /api/civitai-recipes/source-aliases/search",)),
    }
    entries = {entry.name: entry for entry in INTENDED_TOOLS}
    for name, (response_category, endpoints) in expected.items():
        assert entries[name].response_category == response_category
        assert entries[name].backend_endpoints == endpoints
        assert registered[name].outputSchema["type"] == "object"
    assert "civitai_recipe_import" in registered
    assert "civitai_source_alias_resolve" in registered

    root = Path(__file__).resolve().parents[2]
    expected_rows = {
        "| `civitai_source_alias_list` | `dict` | GET /api/civitai-recipes/source-aliases |",
        "| `civitai_source_alias_search` | `dict` | POST /api/civitai-recipes/source-aliases/search |",
    }
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert expected_rows <= set(active.splitlines())
        assert "`civitai_recipe_import`" in active
        assert "`civitai_source_alias_resolve`" in active
        assert "53 個 server-side registered tool" in text
