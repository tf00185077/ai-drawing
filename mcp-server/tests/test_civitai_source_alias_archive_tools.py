"""CIV-SA-M typed MCP source-alias archive lifecycle facade; offline only."""
from __future__ import annotations

import builtins
import json
import os
import pathlib
from pathlib import Path

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS
from mcp_server.tools import civitai_recipes


class Client:
    """One-shot archive-only HTTP fake; every fallback request fails immediately."""

    def __init__(self, result: object, *, expected_body: dict[str, object] | None = None) -> None:
        self.result = result
        self.expected_body = expected_body
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]) -> object:
        if self.calls:
            pytest.fail("archive tool made a second HTTP request")
        if path != "civitai-recipes/source-aliases/archive":
            pytest.fail(f"archive tool used forbidden POST path: {path}")
        if set(json) != {"current_primary_alias", "expected_registry_version"}:
            pytest.fail(f"archive tool used forbidden request body: {json!r}")
        if self.expected_body is not None and json != self.expected_body:
            pytest.fail(f"archive tool changed caller intent: {json!r}")
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def __getattr__(self, method: str) -> object:
        pytest.fail(f"archive tool used forbidden HTTP method: {method}")


def _terminal_archive_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "code": "source_alias_archived",
        "immutable_record": {
            "source_identity": {"provider": "civitai", "image_id": 123},
            "acquisition_evidence_sha256": "a" * 64,
            "parent_recipe_sha256": "b" * 64,
            "primary_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
        },
        "archived_record": {
            "source_identity": {"provider": "civitai", "image_id": 123},
            "acquisition_evidence_sha256": "a" * 64,
            "parent_recipe_sha256": "b" * 64,
            "primary_alias": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
            "archived_at": "2026-07-13T00:00:00Z",
        },
        "archived_at": "2026-07-13T00:00:00Z",
        "event": {
            "id": "archive-event-8",
            "registry_version": 8,
            "operation": "archive",
            "before_aliases": ["Sunset Hero", "hero sunset"],
            "after_aliases": ["Sunset Hero", "hero sunset"],
            "previous_event_sha256": "c" * 64,
            "event_sha256": "d" * 64,
            "created_at": "2026-07-13T00:00:00Z",
        },
    }


@pytest.mark.asyncio
async def test_mcp_source_alias_archive_schema_and_exact_forwarding(monkeypatch) -> None:
    """CIV-SA-M-AC1: two bounded intent fields produce one exact archive POST."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_archive"]
    assert len(registered) == 1
    schema = registered[0].inputSchema
    assert set(schema["properties"]) == {"current_primary_alias", "expected_registry_version"}
    assert schema["required"] == ["current_primary_alias", "expected_registry_version"]
    assert {"type": "string", "minLength": 1, "maxLength": 512}.items() <= schema["properties"]["current_primary_alias"].items()
    assert {"type": "integer", "minimum": 1}.items() <= schema["properties"]["expected_registry_version"].items()
    assert not ({"target", "evidence", "history", "replacement", "unarchive", "generation"} & set(schema["properties"]))

    client = Client(_terminal_archive_payload())
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_archive(
        current_primary_alias="  ＳＵＮＳＥＴ\u2003Hero  ", expected_registry_version=7
    )

    assert result["ok"] is True
    assert client.calls == [(
        "post",
        "civitai-recipes/source-aliases/archive",
        {"current_primary_alias": "  ＳＵＮＳＥＴ\u2003Hero  ", "expected_registry_version": 7},
    )]


def test_mcp_source_alias_archive_preserves_terminal_audited_payload(monkeypatch) -> None:
    """CIV-SA-M-AC2: terminal archive evidence is returned in backend field order unchanged."""
    payload = _terminal_archive_payload()
    client = Client(payload)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)

    result = civitai_recipes.civitai_source_alias_archive("Sunset Hero", 7)

    assert result == {
        "ok": True,
        "tool": "civitai_source_alias_archive",
        "data": payload,
        "next": "use the returned terminal audited archive evidence as-is; do not unarchive, repoint, build, or queue",
    }
    assert client.calls == [(
        "post",
        "civitai-recipes/source-aliases/archive",
        {"current_primary_alias": "Sunset Hero", "expected_registry_version": 7},
    )]


def test_mcp_source_alias_archive_failures_are_redacted_and_never_fallback(monkeypatch) -> None:
    """CIV-SA-M-AC3: domain/transport errors stay one redacted archive POST with no fallback."""
    def bomb(surface: str):
        def _bomb(*args: object, **kwargs: object) -> object:
            pytest.fail(f"forbidden archive fallback: {surface}")

        return _bomb

    # These MCP tool surfaces cover imports, exact resolution/discovery, compiler,
    # queue, variant, Gallery, ComfyUI, and generation.  The archive facade must
    # never reach any of them, including while formatting an error response.
    forbidden = (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_list", "civitai_source_alias_search",
        "civitai_source_alias_rename", "civitai_recipe_build", "civitai_recipe_compatibility", "civitai_recipe_variant_generate",
        "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_cancel", "civitai_recipe_variation_set_export",
        "civitai_recipe_run", "civitai_recipe_export", "gallery_list", "get_gallery_image", "get_gallery_artifact",
        "gallery_rerun", "free_comfyui_memory", "search_nodes", "list_node_categories", "get_node_schema",
        "generate_image", "generate_image_custom_workflow", "generate_video_custom_workflow", "generate_video_wan_keyframes",
        "generate_queue_status", "get_generation_status", "cancel_job",
    )
    for name in forbidden:
        monkeypatch.setattr(civitai_recipes, name, bomb(name), raising=False)

    # Fail closed if an archive call starts touching local state.  The function
    # under test performs no filesystem work, so these are safe narrow bombs.
    monkeypatch.setattr(builtins, "open", bomb("filesystem.open"))
    monkeypatch.setattr(os, "open", bomb("filesystem.os.open"))
    monkeypatch.setattr(pathlib.Path, "read_text", bomb("filesystem.Path.read_text"))
    monkeypatch.setattr(pathlib.Path, "write_text", bomb("filesystem.Path.write_text"))

    body = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 7}
    cases = [
        (422, "alias_invalid", {"code": "alias_invalid", "message": "Authorization: ARCHIVE-SECRET", "nested": {"token": "ARCHIVE-SECRET"}}),
        (404, "not_primary", {"code": "not_primary", "message": "Bearer ARCHIVE-SECRET", "nested": {"cookie": "ARCHIVE-SECRET"}}),
        (409, "stale_registry_version", {"code": "stale_registry_version", "message": "password=ARCHIVE-SECRET", "nested": {"signed_url": "https://x/?signature=ARCHIVE-SECRET"}}),
    ]
    for status, expected_code, detail in cases:
        request = httpx.Request("POST", "http://backend/api/civitai-recipes/source-aliases/archive")
        response = httpx.Response(status, request=request, json={"detail": detail})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response), expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)

        result = civitai_recipes.civitai_source_alias_archive(**body)

        assert result["ok"] is False
        assert result["tool"] == "civitai_source_alias_archive"
        assert result["status_code"] == status
        assert result["error"]["code"] == expected_code
        assert "ARCHIVE-SECRET" not in json.dumps(result)
        assert client.calls == [("post", "civitai-recipes/source-aliases/archive", body)]

    transport = Client(httpx.ConnectError("Bearer ARCHIVE-SECRET token=ARCHIVE-SECRET"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    result = civitai_recipes.civitai_source_alias_archive(**body)
    assert result["ok"] is False
    assert result["tool"] == "civitai_source_alias_archive"
    assert result["error"]["code"] == "ConnectError"
    assert "ARCHIVE-SECRET" not in json.dumps(result)
    assert transport.calls == [("post", "civitai-recipes/source-aliases/archive", body)]


@pytest.mark.asyncio
async def test_mcp_source_alias_archive_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-M-AC4: one registered dict tool has matching catalog and terminal archive docs."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_archive"]
    assert len(registered) == 1
    assert registered[0].outputSchema["type"] == "object"
    entries = [entry for entry in INTENDED_TOOLS if entry.name == "civitai_source_alias_archive"]
    assert len(entries) == 1
    assert entries[0].response_category == "dict"
    assert entries[0].backend_endpoints == ("POST /api/civitai-recipes/source-aliases/archive",)

    root = Path(__file__).resolve().parents[2]
    expected_row = "| `civitai_source_alias_archive` | `dict` | POST /api/civitai-recipes/source-aliases/archive |"
    existing_rows = (
        "| `civitai_recipe_import` | `dict` | POST /api/civitai-recipes/import |",
        "| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |",
        "| `civitai_source_alias_list` | `dict` | GET /api/civitai-recipes/source-aliases |",
        "| `civitai_source_alias_search` | `dict` | POST /api/civitai-recipes/source-aliases/search |",
        "| `civitai_source_alias_rename` | `dict` | POST /api/civitai-recipes/source-aliases/rename |",
    )
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count(expected_row) == 1
        assert "terminal audited archive" in text
        for existing_row in existing_rows:
            assert existing_row in active
