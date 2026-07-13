"""CIV-SA-S typed MCP explicit-version source-alias resolution facade; offline only."""
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


_TOOL = "civitai_source_alias_resolve_explicit_version"
_PATH = "civitai-recipes/source-aliases/resolve-explicit-version"


class Client:
    """One-shot explicit-version-only HTTP fake; every fallback request is a failure."""

    def __init__(self, result: object, *, expected_body: dict[str, object] | None = None) -> None:
        self.result = result
        self.expected_body = expected_body
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]) -> object:
        if self.calls:
            pytest.fail("explicit-version resolver made a second HTTP request")
        if path != _PATH:
            pytest.fail(f"explicit-version resolver used forbidden POST path: {path}")
        if set(json) != {"alias", "registry_version"}:
            pytest.fail(f"explicit-version resolver used forbidden request body: {json!r}")
        if self.expected_body is not None and json != self.expected_body:
            pytest.fail(f"explicit-version resolver changed caller intent: {json!r}")
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def __getattr__(self, method: str) -> object:
        pytest.fail(f"explicit-version resolver used forbidden HTTP method: {method}")


def _audited_binding(*, version: int, image_id: int, label: str) -> dict[str, object]:
    return {
        "matched_alias": {"original_alias": f"  {label}  ", "normalized_key": label.casefold(), "kind": "primary"},
        "registry_version": version,
        "source_identity": {"provider": "civitai", "image_id": image_id, "url": f"https://civitai.com/images/{image_id}"},
        "acquisition_evidence_snapshot": {"raw_api_payload": {"id": image_id, "version": version}},
        "acquisition_evidence_sha256": ("a" if version == 7 else "c") * 64,
        "parent_recipe_sha256": ("b" if version == 7 else "d") * 64,
        "thumbnail_url": f"https://image.civitai.com/{image_id}.png",
        "thumbnail_path": f"thumbs/{image_id}.png",
        "user_note": f"{label} note",
        "approved_tags": [label, "approved"],
        "prompt_summary": f"{label} prompt",
        "created_at": "2026-07-14T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_mcp_explicit_version_resolve_schema_and_exact_forwarding(monkeypatch) -> None:
    """CIV-SA-S-AC1: strict two-field schema forwards one untouched explicit-version intent."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == _TOOL]
    assert len(registered) == 1
    schema = registered[0].inputSchema
    assert set(schema["properties"]) == {"alias", "registry_version"}
    assert schema["required"] == ["alias", "registry_version"]
    assert {"type": "string", "minLength": 1, "maxLength": 512}.items() <= schema["properties"]["alias"].items()
    assert {"type": "integer", "minimum": 1}.items() <= schema["properties"]["registry_version"].items()
    assert not ({"record", "identity", "evidence", "matched_alias", "alias_kind", "archive_override", "fallback", "candidate", "build", "queue", "generation"} & set(schema["properties"]))

    def backend_bomb() -> object:
        pytest.fail("MCP formal validation reached the backend")

    monkeypatch.setattr(civitai_recipes, "_get_client", backend_bomb)
    invalid = (
        {}, {"alias": "x"}, {"registry_version": 1}, {"alias": "x", "registry_version": 1, "extra": "forbidden"},
        {"alias": " \t\n", "registry_version": 1}, {"alias": "x" * 513, "registry_version": 1},
        {"alias": "x", "registry_version": True}, {"alias": "x", "registry_version": "1"},
        {"alias": "x", "registry_version": 1.0}, {"alias": "x", "registry_version": 0}, {"alias": "x", "registry_version": -1},
    )
    for arguments in invalid:
        with pytest.raises(Exception):
            await mcp.call_tool(_TOOL, arguments)

    body = {"alias": "  ＳＵＮＳＥＴ\u2003Hero  ", "registry_version": 7}
    client = Client(_audited_binding(version=7, image_id=123, label="Sunset Hero"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_resolve_explicit_version(**body)
    assert result["ok"] is True
    assert client.calls == [("post", _PATH, body)]


def test_mcp_explicit_version_resolve_preserves_current_and_historical_audited_binding(monkeypatch) -> None:
    """CIV-SA-S-AC2: current and superseded requested versions pass through byte-for-field payloads."""
    current = _audited_binding(version=7, image_id=123, label="Current Alias")
    historical = _audited_binding(version=3, image_id=456, label="Historical Alias")
    for body, payload in (
        ({"alias": "Current Alias", "registry_version": 7}, current),
        ({"alias": "Historical Alias", "registry_version": 3}, historical),
    ):
        client = Client(payload, expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_source_alias_resolve_explicit_version(**body)
        assert result == {
            "ok": True,
            "tool": _TOOL,
            "data": payload,
            "next": "use the caller-selected immutable audited registry binding as-is; do not search, build, queue, or generate",
        }
        assert result["data"]["registry_version"] == body["registry_version"]
        assert client.calls == [("post", _PATH, body)]


def test_mcp_explicit_version_resolve_failures_are_redacted_and_never_fallback_or_generate(monkeypatch) -> None:
    """CIV-SA-S-AC3: exactly one explicit-version POST covers all failures without side effects."""
    def bomb(surface: str):
        def _bomb(*args: object, **kwargs: object) -> object:
            pytest.fail(f"forbidden explicit-version fallback: {surface}")
        return _bomb

    forbidden = (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_list", "civitai_source_alias_search",
        "civitai_source_alias_rename", "civitai_source_alias_archive", "civitai_source_alias_repoint", "civitai_recipe_build",
        "civitai_recipe_compatibility", "civitai_recipe_variant_generate", "civitai_recipe_variation_set_generate",
        "civitai_recipe_run", "civitai_recipe_export", "gallery_list", "get_gallery_image", "get_gallery_artifact",
        "gallery_rerun", "free_comfyui_memory", "search_nodes", "list_node_categories", "get_node_schema",
        "generate_image", "generate_image_custom_workflow", "generate_video_custom_workflow", "generate_video_wan_keyframes",
        "generate_queue_status", "get_generation_status", "cancel_job",
    )
    for name in forbidden:
        monkeypatch.setattr(civitai_recipes, name, bomb(name), raising=False)
    monkeypatch.setattr(builtins, "open", bomb("filesystem.open"))
    monkeypatch.setattr(os, "open", bomb("filesystem.os.open"))
    monkeypatch.setattr(pathlib.Path, "read_text", bomb("filesystem.Path.read_text"))
    monkeypatch.setattr(pathlib.Path, "write_text", bomb("filesystem.Path.write_text"))

    body = {"alias": "Sunset Hero", "registry_version": 7}
    cases = (
        (422, "source_alias_explicit_version_resolve_invalid", {"code": "source_alias_explicit_version_resolve_invalid", "message": "Authorization: VERSION-SECRET", "nested": {"token": "VERSION-SECRET"}}),
        (404, "registry_version_not_found", {"code": "registry_version_not_found", "message": "Bearer VERSION-SECRET"}),
        (404, "alias_not_bound_to_registry_version", {"code": "alias_not_bound_to_registry_version", "message": "cookie=VERSION-SECRET"}),
        (409, "target_archived", {"code": "target_archived", "message": "password=VERSION-SECRET"}),
        (409, "source_alias_registry_corrupt", {"code": "source_alias_registry_corrupt", "message": "signed=https://x/?signature=VERSION-SECRET"}),
    )
    for status, expected_code, detail in cases:
        request = httpx.Request("POST", f"http://backend/api/{_PATH}")
        response = httpx.Response(status, request=request, json={"detail": detail})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response), expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_source_alias_resolve_explicit_version(**body)
        assert result["ok"] is False
        assert result["tool"] == _TOOL
        assert result["status_code"] == status
        assert result["error"]["code"] == expected_code
        assert "VERSION-SECRET" not in json.dumps(result)
        assert "matched_alias" not in result and "candidate" not in result
        assert client.calls == [("post", _PATH, body)]

    transport = Client(httpx.ConnectError("Bearer VERSION-SECRET token=VERSION-SECRET"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    result = civitai_recipes.civitai_source_alias_resolve_explicit_version(**body)
    assert result["ok"] is False
    assert result["error"]["code"] == "ConnectError"
    assert "VERSION-SECRET" not in json.dumps(result)
    assert "matched_alias" not in result and "candidate" not in result
    assert transport.calls == [("post", _PATH, body)]


@pytest.mark.asyncio
async def test_mcp_explicit_version_resolve_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-S-AC4: one registered tool, catalog/docs parity, and adjacent aliases remain intact."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == _TOOL]
    assert len(registered) == 1
    assert registered[0].outputSchema["type"] == "object"
    entries = [entry for entry in INTENDED_TOOLS if entry.name == _TOOL]
    assert len(entries) == 1
    assert entries[0].response_category == "dict"
    assert entries[0].backend_endpoints == ("POST /api/civitai-recipes/source-aliases/resolve-explicit-version",)

    root = Path(__file__).resolve().parents[2]
    expected_row = "| `civitai_source_alias_resolve_explicit_version` | `dict` | POST /api/civitai-recipes/source-aliases/resolve-explicit-version |"
    existing_rows = (
        "| `civitai_recipe_import` | `dict` | POST /api/civitai-recipes/import |",
        "| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |",
        "| `civitai_source_alias_list` | `dict` | GET /api/civitai-recipes/source-aliases |",
        "| `civitai_source_alias_search` | `dict` | POST /api/civitai-recipes/source-aliases/search |",
        "| `civitai_source_alias_rename` | `dict` | POST /api/civitai-recipes/source-aliases/rename |",
        "| `civitai_source_alias_archive` | `dict` | POST /api/civitai-recipes/source-aliases/archive |",
        "| `civitai_source_alias_repoint` | `dict` | POST /api/civitai-recipes/source-aliases/repoint |",
    )
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count(expected_row) == 1
        assert "55 個 server-side registered tool" in text
        assert "explicit registry version" in text.lower()
        assert "歷史" in text
        assert "不自動 build/queue" in text
        for existing_row in existing_rows:
            assert existing_row in active
