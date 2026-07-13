"""CIV-SA-P typed MCP source-alias explicit-repoint facade; offline only."""
from __future__ import annotations

import builtins
import hashlib
import json
import os
import pathlib
from pathlib import Path

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS
from mcp_server.tools import civitai_recipes


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _replacement(image_id: int = 789) -> dict[str, object]:
    evidence = {"raw_api_payload": {"id": image_id}, "source": "Civitai"}
    return {
        "source_identity": {
            "provider": "civitai",
            "image_id": image_id,
            "url": f"https://civitai.com/images/{image_id}",
        },
        "acquisition_evidence_snapshot": evidence,
        "acquisition_evidence_sha256": _sha(evidence),
        "parent_recipe_sha256": "b" * 64,
        "thumbnail_url": "https://image.civitai.com/x.jpg",
        "thumbnail_path": "thumbs/x.png",
        "user_note": "approved replacement",
        "approved_tags": ["hero", "sunset"],
        "prompt_summary": "hero at sunset",
    }


def _audited_repoint_payload() -> dict[str, object]:
    replacement = _replacement()
    from_record = {
        "registry_version": 7,
        "source_identity": {"provider": "civitai", "image_id": 123},
        "acquisition_evidence_snapshot": {"raw_api_payload": {"id": 123}},
        "acquisition_evidence_sha256": "a" * 64,
        "parent_recipe_sha256": "c" * 64,
        "created_at": "2026-07-13T00:00:00Z",
    }
    to_record = {"registry_version": 8, **replacement, "created_at": "2026-07-13T00:00:01Z"}
    return {
        "status": "success",
        "code": "repointed",
        "from_record": from_record,
        "to_record": to_record,
        "event": {
            "id": "repoint-event-8",
            "from_registry_version": 7,
            "to_registry_version": 8,
            "aliases": {
                "primary": {"original_alias": "Sunset Hero", "normalized_key": "sunset hero"},
                "alternates": [{"original_alias": "hero sunset", "normalized_key": "hero sunset"}],
            },
            "from_record_sha256": "d" * 64,
            "to_record_sha256": "e" * 64,
            "source_history_tail_sha256": "f" * 64,
            "previous_repoint_event_sha256": "0" * 64,
            "event_sha256": "1" * 64,
            "created_at": "2026-07-13T00:00:01Z",
        },
    }


class Client:
    """One-shot repoint-only HTTP fake; every fallback request is a failure."""

    def __init__(self, result: object, *, expected_body: dict[str, object] | None = None) -> None:
        self.result = result
        self.expected_body = expected_body
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]) -> object:
        if self.calls:
            pytest.fail("repoint tool made a second HTTP request")
        if path != "civitai-recipes/source-aliases/repoint":
            pytest.fail(f"repoint tool used forbidden POST path: {path}")
        if set(json) != {"current_primary_alias", "expected_registry_version", "replacement"}:
            pytest.fail(f"repoint tool used forbidden request body: {json!r}")
        if self.expected_body is not None and json != self.expected_body:
            pytest.fail(f"repoint tool changed typed caller intent: {json!r}")
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def __getattr__(self, method: str) -> object:
        pytest.fail(f"repoint tool used forbidden HTTP method: {method}")


@pytest.mark.asyncio
async def test_mcp_source_alias_repoint_nested_schema_and_exact_forwarding(monkeypatch) -> None:
    """CIV-SA-P-AC1: strict nested replacement makes exactly one transparent POST."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_repoint"]
    assert len(registered) == 1
    schema = registered[0].inputSchema
    assert set(schema["properties"]) == {"current_primary_alias", "expected_registry_version", "replacement"}
    assert schema["required"] == ["current_primary_alias", "expected_registry_version", "replacement"]
    assert {"type": "string", "minLength": 1, "maxLength": 512}.items() <= schema["properties"]["current_primary_alias"].items()
    assert {"type": "integer", "minimum": 1}.items() <= schema["properties"]["expected_registry_version"].items()
    replacement_schema = schema["$defs"]["CivitaiSourceAliasRepointReplacement"]
    assert replacement_schema["additionalProperties"] is False
    assert replacement_schema["required"] == [
        "source_identity", "acquisition_evidence_snapshot", "acquisition_evidence_sha256", "parent_recipe_sha256",
    ]
    assert set(replacement_schema["properties"]) == {
        "source_identity", "acquisition_evidence_snapshot", "acquisition_evidence_sha256", "parent_recipe_sha256",
        "thumbnail_url", "thumbnail_path", "user_note", "approved_tags", "prompt_summary",
    }
    identity_schema = schema["$defs"]["CivitaiSourceAliasRepointIdentity"]
    assert identity_schema["additionalProperties"] is False
    assert identity_schema["properties"]["provider"]["const"] == "civitai"
    assert not ({"aliases", "history", "event", "from_record", "to_record", "archive", "resolve", "queue", "generation"} & set(schema["properties"]))

    body = {
        "current_primary_alias": "  ＳＵＮＳＥＴ\u2003Hero  ",
        "expected_registry_version": 7,
        "replacement": _replacement(),
    }
    client = Client(_audited_repoint_payload(), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_source_alias_repoint(**body)
    assert result["ok"] is True
    assert client.calls == [("post", "civitai-recipes/source-aliases/repoint", body)]

    with pytest.raises(Exception):
        civitai_recipes.CivitaiSourceAliasRepointReplacement.model_validate({
            **_replacement(), "aliases": ["forbidden"],
        })
    with pytest.raises(Exception):
        civitai_recipes.CivitaiSourceAliasRepointReplacement.model_validate({
            **_replacement(), "acquisition_evidence_sha256": "0" * 64,
        })
    with pytest.raises(Exception):
        civitai_recipes.CivitaiSourceAliasRepointReplacement.model_validate({
            **_replacement(), "source_identity": {"provider": "civitai", "url": "https://civitai.com/images/789"},
        })


def test_mcp_source_alias_repoint_preserves_audited_transition_payload(monkeypatch) -> None:
    """CIV-SA-P-AC2: full backend repoint transition evidence remains untouched."""
    payload = _audited_repoint_payload()
    body = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 7, "replacement": _replacement()}
    client = Client(payload, expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)

    result = civitai_recipes.civitai_source_alias_repoint(**body)

    assert result == {
        "ok": True,
        "tool": "civitai_source_alias_repoint",
        "data": payload,
        "next": "use the returned audited explicit-repoint evidence as-is; bare alias use still requires an explicit registry version and does not resolve, build, or queue automatically",
    }
    assert client.calls == [("post", "civitai-recipes/source-aliases/repoint", body)]


def test_mcp_source_alias_repoint_failures_are_redacted_and_never_fallback(monkeypatch) -> None:
    """CIV-SA-P-AC3: one redacted repoint POST covers domain and transport failures."""
    def bomb(surface: str):
        def _bomb(*args: object, **kwargs: object) -> object:
            pytest.fail(f"forbidden repoint fallback: {surface}")
        return _bomb

    forbidden = (
        "civitai_recipe_import", "civitai_source_alias_resolve", "civitai_source_alias_list", "civitai_source_alias_search",
        "civitai_source_alias_rename", "civitai_source_alias_archive", "civitai_recipe_build", "civitai_recipe_compatibility",
        "civitai_recipe_variant_generate", "civitai_recipe_variation_set_generate", "civitai_recipe_run", "civitai_recipe_export",
        "gallery_list", "get_gallery_image", "get_gallery_artifact", "gallery_rerun", "free_comfyui_memory", "search_nodes",
        "list_node_categories", "get_node_schema", "generate_image", "generate_image_custom_workflow", "generate_video_custom_workflow",
        "generate_video_wan_keyframes", "generate_queue_status", "get_generation_status", "cancel_job",
    )
    for name in forbidden:
        monkeypatch.setattr(civitai_recipes, name, bomb(name), raising=False)
    monkeypatch.setattr(builtins, "open", bomb("filesystem.open"))
    monkeypatch.setattr(os, "open", bomb("filesystem.os.open"))
    monkeypatch.setattr(pathlib.Path, "read_text", bomb("filesystem.Path.read_text"))
    monkeypatch.setattr(pathlib.Path, "write_text", bomb("filesystem.Path.write_text"))

    body = {"current_primary_alias": "Sunset Hero", "expected_registry_version": 7, "replacement": _replacement()}
    cases = [
        (422, "source_alias_repoint_invalid", {"code": "source_alias_repoint_invalid", "message": "Authorization: REPOINT-SECRET", "nested": {"token": "REPOINT-SECRET"}}),
        (422, "same_immutable_target", {"code": "same_immutable_target", "message": "Bearer REPOINT-SECRET", "nested": {"cookie": "REPOINT-SECRET"}}),
        (404, "current_alias_not_found", {"code": "current_alias_not_found", "message": "token=REPOINT-SECRET"}),
        (404, "current_alias_not_primary", {"code": "current_alias_not_primary", "message": "password=REPOINT-SECRET"}),
        (409, "stale_registry_version", {"code": "stale_registry_version", "message": "cookie=REPOINT-SECRET"}),
        (409, "target_archived", {"code": "target_archived", "message": "Bearer REPOINT-SECRET"}),
        (409, "repoint_conflict", {"code": "repoint_conflict", "message": "Authorization: REPOINT-SECRET"}),
        (409, "source_alias_registry_corrupt", {"code": "source_alias_registry_corrupt", "message": "signed=https://x/?signature=REPOINT-SECRET"}),
    ]
    for status, expected_code, detail in cases:
        request = httpx.Request("POST", "http://backend/api/civitai-recipes/source-aliases/repoint")
        response = httpx.Response(status, request=request, json={"detail": detail})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response), expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_source_alias_repoint(**body)
        assert result["ok"] is False
        assert result["tool"] == "civitai_source_alias_repoint"
        assert result["status_code"] == status
        assert result["error"]["code"] == expected_code
        assert "REPOINT-SECRET" not in json.dumps(result)
        assert client.calls == [("post", "civitai-recipes/source-aliases/repoint", body)]

    transport = Client(httpx.ConnectError("Bearer REPOINT-SECRET token=REPOINT-SECRET"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: transport)
    result = civitai_recipes.civitai_source_alias_repoint(**body)
    assert result["ok"] is False
    assert result["error"]["code"] == "ConnectError"
    assert "REPOINT-SECRET" not in json.dumps(result)
    assert transport.calls == [("post", "civitai-recipes/source-aliases/repoint", body)]


@pytest.mark.asyncio
async def test_mcp_source_alias_repoint_registration_catalog_and_docs_parity() -> None:
    """CIV-SA-P-AC4: one registered tool, catalog entry, active rows, and count all agree."""
    registered = [tool for tool in await mcp.list_tools() if tool.name == "civitai_source_alias_repoint"]
    assert len(registered) == 1
    assert registered[0].outputSchema["type"] == "object"
    entries = [entry for entry in INTENDED_TOOLS if entry.name == "civitai_source_alias_repoint"]
    assert len(entries) == 1
    assert entries[0].response_category == "dict"
    assert entries[0].backend_endpoints == ("POST /api/civitai-recipes/source-aliases/repoint",)

    root = Path(__file__).resolve().parents[2]
    expected_row = "| `civitai_source_alias_repoint` | `dict` | POST /api/civitai-recipes/source-aliases/repoint |"
    existing_rows = (
        "| `civitai_recipe_import` | `dict` | POST /api/civitai-recipes/import |",
        "| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |",
        "| `civitai_source_alias_list` | `dict` | GET /api/civitai-recipes/source-aliases |",
        "| `civitai_source_alias_search` | `dict` | POST /api/civitai-recipes/source-aliases/search |",
        "| `civitai_source_alias_rename` | `dict` | POST /api/civitai-recipes/source-aliases/rename |",
        "| `civitai_source_alias_archive` | `dict` | POST /api/civitai-recipes/source-aliases/archive |",
    )
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        text = path.read_text(encoding="utf-8")
        active = text.split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count(expected_row) == 1
        assert "54 個 server-side registered tool" in text
        assert "explicit repoint" in text.lower()
        assert "explicit registry version" in text.lower()
        for existing_row in existing_rows:
            assert existing_row in active
