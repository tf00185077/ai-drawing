"""CIV-SA-K typed MCP source-alias rename lifecycle facade; offline only."""
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

    def post(self, path: str, json: dict[str, object]) -> object:
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _audited_rename_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "code": "source_alias_renamed",
        "immutable_record": {
            "source_identity": {"provider": "civitai", "image_id": 123},
            "acquisition_evidence_sha256": "a" * 64,
            "parent_recipe_sha256": "b" * 64,
        },
        "new_primary": {"original_alias": "Golden Hero", "normalized_key": "golden hero"},
        "preserved_old_alternate": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
        "alternate_aliases": [
            {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
            {"original_alias": "hero sunset", "normalized_key": "hero sunset"},
        ],
        "event": {
            "id": "rename-event-7",
            "registry_version": 8,
            "operation": "rename_primary_alias",
            "before_aliases": ["Sunset Hero", "hero sunset"],
            "after_aliases": ["Golden Hero", "Sunset Hero", "hero sunset"],
            "previous_event_sha256": "c" * 64,
            "event_sha256": "d" * 64,
            "created_at": "2026-07-13T00:00:00Z",
        },
    }


@pytest.mark.asyncio
async def test_mcp_source_alias_rename_schema_and_exact_forwarding(monkeypatch) -> None:
    """CIV-SA-K-AC1: exactly three typed caller intent fields make one transparent POST."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_rename"]
    assert len(registered) == 1
    schema = registered[0].inputSchema
    assert set(schema["properties"]) == {"current_primary_alias", "new_primary_alias", "expected_registry_version"}
    assert schema["required"] == ["current_primary_alias", "new_primary_alias", "expected_registry_version"]
    for name in ("current_primary_alias", "new_primary_alias"):
        assert {"type": "string", "minLength": 1, "maxLength": 512}.items() <= schema["properties"][name].items()
    assert {"type": "integer", "minimum": 1}.items() <= schema["properties"]["expected_registry_version"].items()
    assert not ({"target", "evidence", "history", "archive", "replacement", "generation"} & set(schema["properties"]))

    client = Client(_audited_rename_payload())
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_rename(
        current_primary_alias="  ＳＵＮＳＥＴ\u2003Hero  ",
        new_primary_alias="  Golden Hero  ",
        expected_registry_version=7,
    )

    assert result["ok"] is True
    assert client.calls == [(
        "post",
        "civitai-recipes/source-aliases/rename",
        {
            "current_primary_alias": "  ＳＵＮＳＥＴ\u2003Hero  ",
            "new_primary_alias": "  Golden Hero  ",
            "expected_registry_version": 7,
        },
    )]


def test_mcp_source_alias_rename_preserves_audited_success_payload(monkeypatch) -> None:
    """CIV-SA-K-AC2: success payload is returned as the audited backend data verbatim."""
    payload = _audited_rename_payload()
    client = Client(payload)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)

    result = civitai_recipes.civitai_source_alias_rename("Sunset Hero", "Golden Hero", 7)

    assert result == {
        "ok": True,
        "tool": "civitai_source_alias_rename",
        "data": payload,
        "next": "use the returned audited lifecycle evidence as-is; do not archive, repoint, build, or queue",
    }
    assert client.calls == [(
        "post",
        "civitai-recipes/source-aliases/rename",
        {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Golden Hero", "expected_registry_version": 7},
    )]


def test_mcp_source_alias_rename_failures_are_redacted_and_never_fallback(monkeypatch) -> None:
    """CIV-SA-K-AC3: domain/transport errors remain one redacted rename POST without fallback."""
    forbidden = (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_list", "civitai_source_alias_search",
        "civitai_recipe_build", "civitai_recipe_compatibility", "civitai_recipe_variant_generate",
        "civitai_recipe_variation_set_generate", "civitai_recipe_run",
    )
    for name in forbidden:
        monkeypatch.setattr(civitai_recipes, name, lambda *args, **kwargs: pytest.fail(f"forbidden fallback: {name}"))

    body = {"current_primary_alias": "Sunset Hero", "new_primary_alias": "Golden Hero", "expected_registry_version": 7}
    cases = [
        (422, "alias_invalid", {"code": "alias_invalid", "message": "Authorization: RENAME-SECRET", "nested": {"token": "RENAME-SECRET"}}),
        (404, "not_primary", {"code": "not_primary", "message": "Bearer RENAME-SECRET", "nested": {"cookie": "RENAME-SECRET"}}),
        (409, "stale_registry_version", {"code": "stale_registry_version", "message": "password=RENAME-SECRET", "nested": {"signed_url": "https://x/?signature=RENAME-SECRET"}}),
    ]
    for status, expected_code, detail in cases:
        request = httpx.Request("POST", "http://backend/api/civitai-recipes/source-aliases/rename")
        response = httpx.Response(status, request=request, json={"detail": detail})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response))
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)

        result = civitai_recipes.civitai_source_alias_rename(**body)

        assert result["ok"] is False
        assert result["tool"] == "civitai_source_alias_rename"
        assert result["status_code"] == status
        assert result["error"]["code"] == expected_code
        assert "RENAME-SECRET" not in json.dumps(result)
        assert client.calls == [("post", "civitai-recipes/source-aliases/rename", body)]

    transport = Client(httpx.ConnectError("Bearer RENAME-SECRET token=RENAME-SECRET"))
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    result = civitai_recipes.civitai_source_alias_rename(**body)
    assert result["ok"] is False
    assert result["tool"] == "civitai_source_alias_rename"
    assert result["error"]["code"] == "ConnectError"
    assert "RENAME-SECRET" not in json.dumps(result)
    assert transport.calls == [("post", "civitai-recipes/source-aliases/rename", body)]


@pytest.mark.asyncio
async def test_mcp_source_alias_rename_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-K-AC4: one registered dict tool has matching audited catalog and active docs."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_rename"]
    assert len(registered) == 1
    assert registered[0].outputSchema["type"] == "object"
    entries = [entry for entry in INTENDED_TOOLS if entry.name == "civitai_source_alias_rename"]
    assert len(entries) == 1
    assert entries[0].response_category == "dict"
    assert entries[0].backend_endpoints == ("POST /api/civitai-recipes/source-aliases/rename",)

    root = Path(__file__).resolve().parents[2]
    expected_row = "| `civitai_source_alias_rename` | `dict` | POST /api/civitai-recipes/source-aliases/rename |"
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count(expected_row) == 1
        assert "rename" in text.lower()
        for existing in (
            "| `civitai_recipe_import` | `dict` | POST /api/civitai-recipes/import |",
            "| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |",
            "| `civitai_source_alias_list` | `dict` | GET /api/civitai-recipes/source-aliases |",
            "| `civitai_source_alias_search` | `dict` | POST /api/civitai-recipes/source-aliases/search |",
        ):
            assert existing in active
