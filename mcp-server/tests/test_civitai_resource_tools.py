"""CIV-V-D formal MCP resource wrapper tests."""
from __future__ import annotations
import pytest
from mcp_server.server import mcp
from mcp_server.tools import civitai_recipes

class Client:
    def __init__(self): self.calls=[]
    def post(self, path, json): self.calls.append((path,json)); return {"status":"completed"}

def test_resource_wrappers_forward_only_frozen_bodies(monkeypatch):
    client=Client(); monkeypatch.setattr(civitai_recipes,"_get_client",lambda:client)
    civitai_recipes.civitai_resource_inspect("https://civitai.com/models/1")
    civitai_recipes.civitai_resource_select({"candidates":[]},{"civitai_file_id":1})
    civitai_recipes.civitai_resource_install({"civitai_file_id":1},"loras")
    assert client.calls == [
      ("civitai-recipes/resource-inspect", {"locator":"https://civitai.com/models/1"}),
      ("civitai-recipes/resource-select", {"inspect":{"candidates":[]},"selectors":{"civitai_file_id":1}}),
      ("civitai-recipes/resource-install", {"selected":{"civitai_file_id":1},"storage_root":"loras","overwrite":False}),
    ]

@pytest.mark.asyncio
async def test_resource_tools_have_strict_nested_frozen_schemas():
    """CIV-V-D-AC7: FastMCP exposes contracts, not unbounded dict inputs."""
    tools={tool.name:tool for tool in await mcp.list_tools()}
    inspect_schema = tools["civitai_resource_inspect"].inputSchema
    select_schema = tools["civitai_resource_select"].inputSchema
    install_schema = tools["civitai_resource_install"].inputSchema
    assert set(inspect_schema["properties"]) == {"locator"}
    assert set(select_schema["properties"]) == {"inspect","selectors"}
    assert set(install_schema["properties"]) == {"selected","storage_root","overwrite"}
    defs = {**select_schema.get("$defs", {}), **install_schema.get("$defs", {})}
    selectors = defs["ResourceSelectors"]
    descriptor = defs["CivitaiResourceSelectedDescriptor"]
    assert selectors["additionalProperties"] is False
    assert set(selectors["properties"]) == {"civitai_model_id", "civitai_model_version_id", "civitai_file_id", "sha256", "resource_kind"}
    assert descriptor["additionalProperties"] is False
    assert set(descriptor["required"]) == {
        "civitai_model_id", "civitai_model_version_id", "civitai_file_id", "resource_kind", "name",
        "download_url_identity", "sha256", "byte_size", "availability", "scan_status", "license",
        "usage_restrictions", "air", "model_family",
    }
    assert descriptor["properties"]["civitai_file_id"]["type"] == "integer"
    assert descriptor["properties"]["byte_size"]["type"] == "integer"
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        civitai_recipes.ResourceSelectors.model_validate({})
    with pytest.raises(ValidationError):
        civitai_recipes.ResourceSelectors.model_validate({"sha256": "not-a-full-sha"})


def test_resource_wrapper_preserves_redacted_backend_diagnostic(monkeypatch):
    import httpx
    request = httpx.Request("POST", "http://backend/api/civitai-recipes/resource-select")
    response = httpx.Response(409, request=request, json={"detail": {
        "code": "unsafe_metadata", "message": "blocked", "url": "https://civitai.com/a?token=[REDACTED]",
        "license": {"name": "test-license"},
    }})
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: type("Client", (), {
        "post": lambda self, path, json: (_ for _ in ()).throw(httpx.HTTPStatusError("blocked", request=request, response=response)),
    })())

    result = civitai_recipes.civitai_resource_select({"status": "completed", "source": {"provider": "civitai", "civitai_model_id": 1}, "model_family": "SDXL", "candidates": []}, {"civitai_file_id": 1})

    assert result["error"]["code"] == "unsafe_metadata"
    assert "TOKEN_SENTINEL" not in str(result)
    assert result["error"]["details"]["license"] == {"name": "test-license"}


def test_catalog_readme_and_setup_docs_have_resource_tool_parity():
    from pathlib import Path
    from mcp_server.tool_catalog import INTENDED_TOOLS

    root = Path(__file__).resolve().parents[2]
    names = {"civitai_resource_inspect", "civitai_resource_select", "civitai_resource_install"}
    assert names <= {item.name for item in INTENDED_TOOLS}
    readme = (root / "mcp-server" / "README.md").read_text()
    setup = (root / "docs" / "mcp-setup.md").read_text()
    for name in names:
        assert name in readme
        assert name in setup


def test_resource_wrapper_redacts_authorization_and_token_query_in_success_and_error_payloads(monkeypatch):
    """CIV-V-D-AC8: wrappers preserve canonical shape while redacting backend surprises."""
    import httpx

    secret = "AUTHORIZATION_SENTINEL"
    request = httpx.Request("POST", "http://backend/api/civitai-recipes/resource-install")
    response = httpx.Response(409, request=request, json={"detail": {
        "code": "unsafe_metadata", "message": f"Bearer {secret}",
        "authorization": f"Bearer {secret}",
        "source": f"https://civitai.com/api/download/models/11?token={secret}",
    }})

    class Client:
        def post(self, path, json):
            if path.endswith("resource-install"):
                return {
                    "status": "completed", "authorization": f"Bearer {secret}",
                    "source": f"https://civitai.com/api/download/models/11?token={secret}",
                }
            raise httpx.HTTPStatusError("backend failure", request=request, response=response)

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    success = civitai_recipes.civitai_resource_install({"civitai_file_id": 1}, "loras")
    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: type("ErrorClient", (), {
        "post": lambda self, path, json: (_ for _ in ()).throw(httpx.HTTPStatusError("backend failure", request=request, response=response)),
    })())
    error = civitai_recipes.civitai_resource_install({"civitai_file_id": 1}, "loras")

    assert success["ok"] is True
    assert error["ok"] is False
    assert secret not in str(success)
    assert secret not in str(error)
