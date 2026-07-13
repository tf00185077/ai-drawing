"""CIV-SA-AA typed MCP audited Gallery source-alias backfill facade; offline only."""
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


_TOOL = "civitai_source_alias_backfill_gallery"
_PATH = "civitai-recipes/source-aliases/backfill-gallery"


class Client:
    """One-shot backfill-only HTTP fake; every fallback surface fails the test."""

    def __init__(self, result: object, *, expected_body: dict[str, object] | None = None) -> None:
        self.result = result
        self.expected_body = expected_body
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]) -> object:
        if self.calls:
            pytest.fail("gallery backfill made a second HTTP request")
        if path != _PATH:
            pytest.fail(f"gallery backfill used forbidden POST path: {path}")
        if set(json) != {"gallery_image_id", "primary_alias"}:
            pytest.fail(f"gallery backfill used forbidden request body: {json!r}")
        if self.expected_body is not None and json != self.expected_body:
            pytest.fail(f"gallery backfill changed caller intent: {json!r}")
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def __getattr__(self, method: str) -> object:
        pytest.fail(f"gallery backfill used forbidden HTTP method: {method}")


def _payload(status: str) -> dict[str, object]:
    if status == "named":
        return {
            "status": "named",
            "record": {"primary_alias": "Hero Parent", "registry_version": 7, "created_at": "2026-07-14T00:00:00Z"},
            "source_identity": {"provider": "civitai", "image_id": 123},
            "acquisition_evidence_snapshot": {"raw_api_payload": {"id": 123}},
            "acquisition_evidence_sha256": "a" * 64,
            "parent_recipe_sha256": "b" * 64,
        }
    candidate = {
        "suggested_alias": "Hero Parent",
        "target": {"gallery_image_id": 7, "source_identity": {"provider": "civitai", "image_id": 123}},
        "thumbnail_path": "thumbs/hero.png",
        "created_at": "2026-07-14T00:00:00Z",
    }
    return {"status": status, "candidate": candidate}


@pytest.mark.asyncio
async def test_gallery_backfill_tool_schema_is_strict_and_forwards_once(monkeypatch) -> None:
    """CIV-SA-AA-AC1: formal strict validation rejects invalid input before one untouched POST."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == _TOOL]
    assert len(registered) == 1
    schema = registered[0].inputSchema
    assert set(schema["properties"]) == {"gallery_image_id", "primary_alias"}
    assert schema["required"] == ["gallery_image_id"]
    assert schema["additionalProperties"] is False
    assert {"type": "integer", "minimum": 1}.items() <= schema["properties"]["gallery_image_id"].items()
    primary_alias = schema["properties"]["primary_alias"]
    assert primary_alias["anyOf"][0]["type"] == "string"
    assert {"minLength": 1, "maxLength": 512, "pattern": ".*\\S.*"}.items() <= primary_alias["anyOf"][0].items()
    assert any(item.get("type") == "null" for item in primary_alias["anyOf"])

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: pytest.fail("formal validation reached backend"))
    invalid = (
        {}, {"gallery_image_id": "7"}, {"gallery_image_id": True}, {"gallery_image_id": 7.0},
        {"gallery_image_id": 0}, {"gallery_image_id": -1}, {"gallery_image_id": 7, "primary_alias": " \t\n"},
        {"gallery_image_id": 7, "primary_alias": "x" * 513}, {"gallery_image_id": 7, "extra": "forbidden"},
    )
    for arguments in invalid:
        with pytest.raises(Exception):
            await mcp.call_tool(_TOOL, arguments)

    body = {"gallery_image_id": 7, "primary_alias": "  Ｈｅｒｏ Parent  "}
    client = Client(_payload("named"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_backfill_gallery(**body)
    assert result["ok"] is True
    assert client.calls == [("post", _PATH, body)]


def test_gallery_backfill_tool_preserves_named_pending_and_idempotent_payloads(monkeypatch) -> None:
    """CIV-SA-AA-AC2: all backend success shapes pass through redaction without selection or work."""
    body = {"gallery_image_id": 7, "primary_alias": None}
    for status in ("named", "pending_name", "already_backfilled"):
        payload = _payload(status)
        client = Client(payload, expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_source_alias_backfill_gallery(**body)
        assert result["ok"] is True
        assert result["tool"] == _TOOL
        assert result["data"] == payload
        assert not ({"selected", "resolved", "build", "job", "lineage"} & set(result["data"]))
        assert "exact resolve" in result["next"]
        assert client.calls == [("post", _PATH, body)]


def test_gallery_backfill_tool_failures_are_redacted_without_fallback(monkeypatch) -> None:
    """CIV-SA-AA-AC3: failures remain redacted, one-shot, and never touch other surfaces."""
    def bomb(surface: str):
        def _bomb(*args: object, **kwargs: object) -> object:
            pytest.fail(f"forbidden gallery-backfill fallback: {surface}")
        return _bomb

    forbidden = (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_resolve_explicit_version",
        "civitai_source_alias_list", "civitai_source_alias_search", "civitai_source_alias_rename", "civitai_source_alias_archive",
        "civitai_source_alias_repoint", "civitai_recipe_build", "civitai_recipe_compatibility", "civitai_recipe_resolve",
        "civitai_recipe_resolve_local", "civitai_recipe_variant_generate", "civitai_recipe_variation_set_generate",
        "civitai_recipe_run", "civitai_recipe_export", "gallery_list", "get_gallery_image", "get_gallery_artifact",
        "gallery_rerun", "generate_image", "generate_image_custom_workflow", "generate_video_custom_workflow",
        "generate_video_wan_keyframes", "generate_queue_status", "get_generation_status", "cancel_job",
    )
    for name in forbidden:
        monkeypatch.setattr(civitai_recipes, name, bomb(name), raising=False)
    monkeypatch.setattr(builtins, "open", bomb("filesystem.open"))
    monkeypatch.setattr(os, "open", bomb("filesystem.os.open"))
    monkeypatch.setattr(pathlib.Path, "read_text", bomb("filesystem.Path.read_text"))
    monkeypatch.setattr(pathlib.Path, "write_text", bomb("filesystem.Path.write_text"))

    body = {"gallery_image_id": 7, "primary_alias": None}
    cases = (
        (422, "source_alias_gallery_backfill_invalid"), (404, "gallery_not_found"), (422, "gallery_ineligible"),
        (409, "backfill_conflict"), (409, "source_alias_gallery_backfill_corrupt"),
    )
    for status, code in cases:
        detail = {"code": code, "message": "Bearer BACKFILL-SECRET", "nested": {"token": "BACKFILL-SECRET", "signature": "BACKFILL-SECRET"}}
        request = httpx.Request("POST", f"http://backend/api/{_PATH}")
        response = httpx.Response(status, request=request, json={"detail": detail})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response), expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_source_alias_backfill_gallery(**body)
        assert result["ok"] is False
        assert result["tool"] == _TOOL
        assert result["status_code"] == status
        assert result["error"]["code"] == code
        assert "BACKFILL-SECRET" not in json.dumps(result)
        assert client.calls == [("post", _PATH, body)]

    transport = Client(httpx.ConnectError("Bearer BACKFILL-SECRET token=BACKFILL-SECRET"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    result = civitai_recipes.civitai_source_alias_backfill_gallery(**body)
    assert result["ok"] is False
    assert result["error"]["code"] == "ConnectError"
    assert "BACKFILL-SECRET" not in json.dumps(result)
    assert transport.calls == [("post", _PATH, body)]


@pytest.mark.asyncio
async def test_gallery_backfill_tool_registration_catalog_docs_and_existing_alias_contracts() -> None:
    """CIV-SA-AA-AC4: registration/catalog/docs count agree without changing established alias tools."""
    live_tools = await mcp.list_tools()
    assert len(live_tools) == len(INTENDED_TOOLS) == 75
    assert sum(tool.name == _TOOL for tool in live_tools) == 1
    registered = {tool.name: tool for tool in live_tools}
    assert registered[_TOOL].outputSchema["type"] == "object"
    entries = [entry for entry in INTENDED_TOOLS if entry.name == _TOOL]
    assert len(entries) == 1
    assert entries[0].response_category == "dict"
    assert entries[0].backend_endpoints == ("POST /api/civitai-recipes/source-aliases/backfill-gallery",)
    for name in (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_resolve_explicit_version",
        "civitai_source_alias_list", "civitai_source_alias_search", "civitai_source_alias_rename", "civitai_source_alias_archive",
        "civitai_source_alias_repoint", "civitai_recipe_variant_generate", "civitai_recipe_variation_set_generate",
    ):
        assert name in registered

    root = Path(__file__).resolve().parents[2]
    row = "| `civitai_source_alias_backfill_gallery` | `dict` | POST /api/civitai-recipes/source-aliases/backfill-gallery |"
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count(row) == 1
        assert "75 個 server-side registered tool" in text
        assert "74 個 server-side registered tool" in text
        assert "新增 `civitai_source_alias_backfill_gallery` 後以本頁的 75 為準" in text
        assert "pending_name" in text
        assert "不自動 remember、resolve、build 或 queue" in text
