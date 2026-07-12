"""CIV-F MCP forwarding, error, and schema contracts without backend network calls."""
from __future__ import annotations

import base64

import httpx
import pytest

from mcp_server.server import mcp
from mcp_server.tools import civitai_recipes


class Client:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def post(self, path, json):
        self.calls.append(("post", path, json))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def get(self, path, params=None):
        self.calls.append(("get", path, params))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    ("function", "kwargs", "path"),
    [
        (civitai_recipes.civitai_recipe_import, {"locator": 123, "embedded_image": b"png"}, "civitai-recipes/import"),
        (civitai_recipes.civitai_recipe_inspect, {"recipe": {"schema_version": "1.0"}}, "civitai-recipes/inspect"),
        (civitai_recipes.civitai_recipe_resolve, {"recipe": {"schema_version": "1.0"}, "ledger": [], "strict": False}, "civitai-recipes/resolve"),
        (civitai_recipes.civitai_recipe_build, {"recipe": {"schema_version": "1.0"}, "resource_report": {}, "model_family": "sdxl", "input_bindings": {}}, "civitai-recipes/build"),
        (civitai_recipes.civitai_recipe_run, {"build": {"workflow": {}}, "runtime_provenance": {}}, "civitai-recipes/run"),
    ],
)
def test_recipe_tools_forward_all_frozen_inputs_and_return_structured_success(monkeypatch, function, kwargs, path) -> None:
    client = Client({"ok": True, "data": {"accepted": True}})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = function(**kwargs)
    assert result["ok"] is True
    assert result["tool"].startswith("civitai_recipe_")
    assert result["data"]["data"]["accepted"] is True
    assert result["next"]
    assert client.calls[0][1] == path


def test_recipe_import_decodes_formal_stdio_base64_without_changing_http_contract(monkeypatch) -> None:
    client = Client({"ok": True})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    raw = b"\x89PNG\r\n\x1a\nembedded"
    encoded = base64.b64encode(raw).decode("ascii")

    result = civitai_recipes.civitai_recipe_import(locator=123, embedded_image=encoded)

    assert result["ok"] is True
    assert client.calls == [
        ("post", "civitai-recipes/import", {
            "locator": 123,
            "embedded_image_base64": encoded,
        })
    ]


def test_recipe_export_wraps_existing_gallery_recipe_export(monkeypatch) -> None:
    client = Client({"schema_version": "1.0", "recipe": {}, "workflow": {}, "input_hashes": [], "resource_locks": [], "runtime_provenance": {}, "reproduction_level": "not_reproducible"})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: client)
    result = civitai_recipes.civitai_recipe_export(7)
    assert result["ok"] is True
    assert result["data"] == client.result
    assert client.calls == [("get", "gallery/7/export", {"format": "recipe"})]


def test_recipe_tools_preserve_backend_structured_diagnostic(monkeypatch) -> None:
    request = httpx.Request("POST", "http://backend/api/civitai-recipes/resolve")
    response = httpx.Response(409, request=request, json={"detail": {"code": "resource_resolution_failed", "message": "missing", "report": {"entries": [{"status": "missing"}]}}})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client(httpx.HTTPStatusError("conflict", request=request, response=response)))
    result = civitai_recipes.civitai_recipe_resolve(recipe={"schema_version": "1.0"}, ledger=[], strict=True)
    assert result == {"ok": False, "tool": "civitai_recipe_resolve", "status_code": 409, "error": {"code": "resource_resolution_failed", "message": "missing", "details": {"report": {"entries": [{"status": "missing"}]}}}}


@pytest.mark.parametrize(
    ("status_code", "detail", "expected_code", "expected_details"),
    [
        (422, [{"loc": ["body", "recipe"], "msg": "Field required", "type": "missing"}], "http_422", {"detail": [{"loc": ["body", "recipe"], "msg": "Field required", "type": "missing"}]}),
        (500, {"code": "compiler_failed", "message": "diagnostic", "node_errors": {"17": ["missing model"]}}, "compiler_failed", {"node_errors": {"17": ["missing model"]}}),
    ],
)
def test_recipe_tools_preserve_non_success_backend_diagnostics(monkeypatch, status_code, detail, expected_code, expected_details) -> None:
    request = httpx.Request("POST", "http://backend/api/civitai-recipes/inspect")
    response = httpx.Response(status_code, request=request, json={"detail": detail})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client(httpx.HTTPStatusError("backend failure", request=request, response=response)))

    result = civitai_recipes.civitai_recipe_inspect(recipe={"schema_version": "1.0"})

    assert result["ok"] is False
    assert result["tool"] == "civitai_recipe_inspect"
    assert result["status_code"] == status_code
    assert result["error"]["code"] == expected_code
    assert result["error"]["details"] == expected_details


def test_recipe_tools_return_structured_transport_failure(monkeypatch) -> None:
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client(httpx.ConnectError("offline")))

    result = civitai_recipes.civitai_recipe_export(7)

    assert result == {"ok": False, "tool": "civitai_recipe_export", "error": {"code": "ConnectError", "message": "offline", "details": {"where": "backend"}}}


@pytest.mark.asyncio
async def test_all_civ_f_tools_are_registered_with_their_frozen_inputs() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    expected = {
        "civitai_recipe_import": {"locator", "embedded_image"},
        "civitai_recipe_inspect": {"recipe"},
        "civitai_recipe_resolve": {"recipe", "ledger", "strict"},
        "civitai_recipe_build": {"recipe", "resource_report", "model_family", "input_bindings"},
        "civitai_recipe_run": {"build", "runtime_provenance"},
        "civitai_recipe_export": {"image_id"},
    }
    for name, fields in expected.items():
        assert fields <= set(registered[name].inputSchema["properties"])
