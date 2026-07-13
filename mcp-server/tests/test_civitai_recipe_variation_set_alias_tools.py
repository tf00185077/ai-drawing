"""CIV-SA-X typed Variation Set source-alias facade; offline only."""
from __future__ import annotations

import asyncio
import builtins
import json
import os
import pathlib

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tool_catalog import INTENDED_TOOLS
from mcp_server.tools import civitai_recipes


_TOOL = "civitai_recipe_variation_set_generate"
_PATH = "civitai-recipes/variation-sets"


class Client:
    """One-shot Variation Set transport; any other request is a failure."""

    def __init__(self, result: object, *, expected_body: dict[str, object] | None = None) -> None:
        self.result = result
        self.expected_body = expected_body
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, path: str, json: dict[str, object]) -> object:
        if self.calls:
            pytest.fail("Variation Set facade made a second HTTP request")
        if path != _PATH:
            pytest.fail(f"Variation Set facade used forbidden POST path: {path}")
        if self.expected_body is not None and json != self.expected_body:
            pytest.fail(f"Variation Set facade changed caller intent: {json!r}")
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def __getattr__(self, method: str) -> object:
        pytest.fail(f"Variation Set facade used forbidden HTTP method: {method}")


def _inputs() -> dict[str, object]:
    return {
        "children": [
            {
                "client_child_key": "first-child",
                "directives": [
                    {"field": "base_prompt", "policy": "preserve"},
                    {"field": "sampling.seed", "policy": "randomize"},
                ],
            },
            {
                "client_child_key": "second-child",
                "directives": [{"field": "sampling.cfg", "policy": "replace", "value": 7.5}],
            },
        ],
        "model_family": "sdxl",
        "runtime_capabilities": {
            "engine": "comfyui", "engine_version": "1", "node_types": [],
            "sampler_names": [], "scheduler_names": [], "snapshot_sha256": "a" * 64,
        },
        "runtime_provenance": {
            "engine": "comfyui", "engine_version": "1", "reference": "runtime:1",
            "runtime_lock_sha256": "b" * 64, "node_versions": {},
            "inspection_snapshot": {
                "snapshot_sha256": "c" * 64, "engine": "comfyui", "engine_version": "1", "node_types": [],
            },
        },
        "input_bindings": {},
    }


def _direct_source() -> dict[str, object]:
    return {
        "parent_recipe": {"schema_version": "1.0", "source": {"provider": "civitai", "image_id": 123}},
        "parent_recipe_sha256": "d" * 64,
    }


async def _schema() -> dict[str, object]:
    return {tool.name: tool for tool in await mcp.list_tools()}[_TOOL].inputSchema


@pytest.mark.asyncio
async def test_variation_set_alias_tool_schema_is_strict_exactly_one_parent_source(monkeypatch) -> None:
    """CIV-SA-X-AC1: formal schema exposes only direct-pair XOR typed selector."""
    schema = await _schema()
    properties = schema["properties"]
    assert schema["additionalProperties"] is False
    assert set(properties) == {
        "parent_recipe", "parent_recipe_sha256", "source_alias", "children", "model_family",
        "runtime_capabilities", "runtime_provenance", "input_bindings",
    }
    assert set(schema["required"]) == {"children", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}
    assert len(schema["oneOf"]) == 2
    assert {tuple(branch.get("required", [])) for branch in schema["oneOf"]} == {
        ("parent_recipe", "parent_recipe_sha256"), ("source_alias",),
    }
    alias = schema["$defs"][properties["source_alias"]["anyOf"][0]["$ref"].rsplit("/", 1)[-1]]
    assert alias["additionalProperties"] is False
    assert set(alias["properties"]) == {"alias", "registry_version"}
    assert alias["required"] == ["alias"]
    assert {"type": "string", "minLength": 1, "maxLength": 512}.items() <= alias["properties"]["alias"].items()
    registry_version = alias["properties"]["registry_version"]
    version_branch = next(branch for branch in registry_version["anyOf"] if branch.get("type") == "integer")
    assert version_branch["minimum"] == 1

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: pytest.fail("formal validation reached transport"))
    common = _inputs()
    invalid = (
        common,
        common | _direct_source() | {"source_alias": {"alias": "x"}},
        common | {"parent_recipe": _direct_source()["parent_recipe"]},
        common | {"parent_recipe_sha256": "d" * 64},
        common | {"source_alias": {"alias": " \t\n"}},
        common | {"source_alias": {"alias": "x" * 513}},
        *tuple(common | {"source_alias": {"alias": "x", "registry_version": value}} for value in (True, "1", 1.0, 0, -1)),
        common | {"source_alias": {"alias": "x", "extra": "forbidden"}},
        common | {"source_alias": {"alias": "x"}, "extra": "forbidden"},
    )
    for arguments in invalid:
        with pytest.raises(Exception):
            await mcp.call_tool(_TOOL, arguments)


def test_variation_set_alias_tool_forwards_bare_and_explicit_selector_once(monkeypatch) -> None:
    """CIV-SA-X-AC2: alias selectors are opaque, ordered, one-shot pass-through bodies."""
    for source_alias in (
        {"alias": "  ＳＵＮＳＥＴ\u2003Hero  "},
        {"alias": "  ＳＵＮＳＥＴ\u2003Hero  ", "registry_version": 7},
    ):
        body = _inputs() | {"source_alias": source_alias}
        client = Client({"variation_set_id": "set", "status": "queued"}, expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_recipe_variation_set_generate(**body)
        assert result["ok"] is True
        assert result["data"]["status"] == "queued"
        assert client.calls == [("post", _PATH, body)]
        forwarded = client.calls[0][2]
        assert "parent_recipe" not in forwarded
        assert "parent_recipe_sha256" not in forwarded
        assert forwarded["children"] == body["children"]
        assert "value" not in forwarded["children"][0]["directives"][0]


def test_variation_set_alias_tool_fail_closed_errors_are_redacted_without_fallback(monkeypatch) -> None:
    """CIV-SA-X-AC3: alias materialization failures retain safe status/phase/code once."""
    def bomb(surface: str):
        def _bomb(*args: object, **kwargs: object) -> object:
            pytest.fail(f"forbidden alias facade fallback: {surface}")
        return _bomb

    for name in (
        "civitai_source_alias_resolve", "civitai_source_alias_resolve_explicit_version", "civitai_source_alias_list",
        "civitai_source_alias_search", "civitai_recipe_import", "civitai_source_alias_repoint", "civitai_recipe_build",
        "civitai_recipe_run", "civitai_recipe_variant_generate", "civitai_recipe_variation_set_status",
        "civitai_recipe_variation_set_cancel", "civitai_recipe_variation_set_export", "civitai_recipe_export",
        "generate_image", "generate_image_custom_workflow", "get_generation_status", "gallery_rerun",
    ):
        monkeypatch.setattr(civitai_recipes, name, bomb(name), raising=False)
    monkeypatch.setattr(builtins, "open", bomb("filesystem.open"))
    monkeypatch.setattr(os, "open", bomb("filesystem.os.open"))
    monkeypatch.setattr(pathlib.Path, "read_text", bomb("filesystem.Path.read_text"))
    monkeypatch.setattr(pathlib.Path, "write_text", bomb("filesystem.Path.write_text"))

    body = _inputs() | {"source_alias": {"alias": "Sunset Hero"}}
    failure_cases = (
        (404, "source_alias_missing"),
        (409, "source_alias_ambiguous"),
        (410, "source_alias_archived"),
        (422, "source_alias_materialization_invalid"),
        (409, "source_alias_repoint_requires_explicit_version"),
        (404, "source_alias_registry_version_missing"),
        (409, "source_alias_registry_version_mismatch"),
    )
    for status, code in failure_cases:
        request = httpx.Request("POST", f"http://backend/api/{_PATH}")
        response = httpx.Response(status, request=request, json={"detail": {
            "phase": "source_alias_materialization", "code": code,
            "message": "Bearer ALIAS-SECRET https://x.invalid/?token=ALIAS-SECRET",
            "nested": {"authorization": "ALIAS-SECRET", "cookie": "ALIAS-SECRET", "password": "ALIAS-SECRET", "secret": "ALIAS-SECRET"},
        }})
        client = Client(httpx.HTTPStatusError("backend failure", request=request, response=response), expected_body=body)
        monkeypatch.setattr(civitai_recipes, "_get_client", lambda client=client: client)
        result = civitai_recipes.civitai_recipe_variation_set_generate(**body)
        assert result["ok"] is False
        assert result["status_code"] == status
        assert result["error"]["code"] == code
        assert result["error"]["details"]["phase"] == "source_alias_materialization"
        assert "ALIAS-SECRET" not in json.dumps(result)
        assert client.calls == [("post", _PATH, body)]

    client = Client(httpx.ConnectError("Bearer ALIAS-SECRET token=ALIAS-SECRET"), expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_recipe_variation_set_generate(**body)
    assert result["ok"] is False and result["error"]["code"] == "ConnectError"
    assert "ALIAS-SECRET" not in json.dumps(result)
    assert client.calls == [("post", _PATH, body)]


def test_variation_set_alias_tool_preserves_direct_parent_children_and_catalog_contract(monkeypatch) -> None:
    """CIV-SA-X-AC4: direct Parent remains opaque, strict, one-shot, and catalog-compatible."""
    body = _inputs() | _direct_source()
    client = Client({"variation_set_id": "set", "status": "queued"}, expected_body=body)
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_recipe_variation_set_generate(**body)
    assert result["ok"] is True and result["data"]["status"] == "queued"
    assert client.calls == [("post", _PATH, body)]
    assert "source_alias" not in client.calls[0][2]
    assert "value" not in client.calls[0][2]["children"][0]["directives"][0]

    schema = asyncio.run(_schema())
    assert schema["additionalProperties"] is False
    reachable: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/$defs/"):
                name = reference.rsplit("/", 1)[-1]
                if name not in reachable:
                    reachable.add(name)
                    visit(schema["$defs"][name])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit({"properties": schema["properties"]})
    for name in reachable:
        definition = schema["$defs"][name]
        if definition.get("type") == "object" and "properties" in definition:
            assert definition.get("additionalProperties") is False, name

    entries = [item for item in INTENDED_TOOLS if item.name.startswith("civitai_recipe_variation_set_")]
    assert {item.name for item in entries} == {
        "civitai_recipe_variation_set_generate", "civitai_recipe_variation_set_status",
        "civitai_recipe_variation_set_cancel", "civitai_recipe_variation_set_export",
    }
    generate_entry = next(item for item in entries if item.name == _TOOL)
    assert generate_entry.response_category == "dict"
    assert generate_entry.backend_endpoints == ("POST /api/civitai-recipes/variation-sets",)
