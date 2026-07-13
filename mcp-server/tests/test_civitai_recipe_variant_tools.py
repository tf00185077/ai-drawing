from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from mcp_server.tools import civitai_recipes


def test_variant_tool_forwards_only_frozen_request_and_accepts_queued(monkeypatch) -> None:
    captured = {}

    class Client:
        def post(self, endpoint, json):
            captured["endpoint"], captured["json"] = endpoint, json
            return {"variant_id": "v", "job_id": "j", "status": "queued"}

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    result = civitai_recipes.civitai_recipe_variant_generate(
        parent_recipe={"schema_version": "1.0"}, parent_recipe_sha256="a" * 64,
        directives=[], model_family="sdxl", runtime_capabilities={}, runtime_provenance={}, input_bindings={},
    )
    assert result["ok"] is True
    assert captured["endpoint"] == "civitai-recipes/variants/generate-one"
    assert set(captured["json"]) == {"parent_recipe", "parent_recipe_sha256", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}


async def _variant_schema() -> dict:
    from mcp_server.server import mcp
    return {tool.name: tool for tool in await mcp.list_tools()}["civitai_recipe_variant_generate"].inputSchema


def test_variant_tool_uses_strict_nested_input_models() -> None:
    """Formal FastMCP schema must not collapse frozen inputs into free-form dicts."""
    import asyncio

    schema = asyncio.run(_variant_schema())
    properties = schema["properties"]
    definitions = schema["$defs"]
    parent = definitions[properties["parent_recipe"]["$ref"].rsplit("/", 1)[-1]]
    runtime = definitions[properties["runtime_capabilities"]["$ref"].rsplit("/", 1)[-1]]
    provenance = definitions[properties["runtime_provenance"]["$ref"].rsplit("/", 1)[-1]]
    directive = definitions[properties["directives"]["items"]["$ref"].rsplit("/", 1)[-1]]
    assert set(schema["required"]) == {"parent_recipe", "parent_recipe_sha256", "directives", "model_family", "runtime_capabilities", "runtime_provenance", "input_bindings"}
    assert properties["model_family"]["enum"] == ["sdxl", "illustrious"]
    assert parent["additionalProperties"] is False
    assert runtime["additionalProperties"] is False
    assert provenance["additionalProperties"] is False
    assert directive["additionalProperties"] is False


def test_variant_tool_schema_exposes_typed_recipe_and_runtime_children() -> None:
    """AC3: Parent/runtime objects must not degrade to free-form JSON placeholders."""
    import asyncio

    schema = asyncio.run(_variant_schema())
    definitions = schema["$defs"]

    def definition(ref: str) -> dict:
        return definitions[ref.rsplit("/", 1)[-1]]

    parent = definition(schema["properties"]["parent_recipe"]["$ref"])
    provenance = definition(schema["properties"]["runtime_provenance"]["$ref"])
    for name in ("source", "resources", "sampling", "passes", "inputs", "controls", "detailers", "postprocess", "workflow", "runtime", "evidence_manifest"):
        value = parent["properties"][name]
        assert "$ref" in value or "$ref" in value.get("items", {}) or "$ref" in value.get("additionalProperties", {}) or any("$ref" in branch for branch in value.get("anyOf", []))
    # RuntimeProvenance canonically keeps settings/snapshot as arbitrary
    # evidence maps; resource locks remain a strict typed child model.
    locks = provenance["properties"]["resource_locks"]
    assert "$ref" in locks.get("items", {})
    for name in ("runtime_settings", "inspection_snapshot"):
        value = provenance["properties"][name]
        assert "$ref" in value or value.get("type") == "object" or value.get("additionalProperties") is True


def test_variant_tool_accepts_backend_canonical_evidence_contract_without_translation() -> None:
    """AC3: MCP client types are the canonical backend Recipe/Runtime shapes."""
    from mcp_server.tools.civitai_recipes import CivitaiVariantParentRecipe

    recipe = {
        "schema_version": "1.0",
        "source": {"provider": "civitai", "image_id": 1},
        "resources": [{"kind": "checkpoint", "name": "base.safetensors", "sha256": "a" * 64}],
        "confirmed": [{"canonical_field": "base_prompt", "source": "importer", "reference": "import:1", "snapshot_sha256": "b" * 64, "note": "verified"}],
        "inferred": [{"canonical_field": "sampling.seed", "source": "embedded_metadata", "reference": "image:1"}],
        "evidence_manifest": [{
            "identity": "import:1", "reference": "import:1", "payload": {"prompt": "test"},
            "sha256": "c" * 64, "assertions": [],
        }],
    }
    forwarded = CivitaiVariantParentRecipe.model_validate(recipe).model_dump(mode="json", exclude_none=True)
    for field in ("source", "resources", "confirmed", "inferred", "evidence_manifest"):
        assert forwarded[field] == recipe[field]


def test_variant_tool_forwards_generic_compiler_input_reference_with_hash(monkeypatch) -> None:
    captured = {}

    class Client:
        def post(self, endpoint, json):
            captured["endpoint"], captured["json"] = endpoint, json
            return {"variant_id": "v", "job_id": "j", "status": "queued"}

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    result = civitai_recipes.civitai_recipe_variant_generate(
        parent_recipe={"schema_version": "1.0", "source": {"provider": "civitai", "image_id": 1}},
        parent_recipe_sha256="a" * 64, directives=[], model_family="sdxl",
        runtime_capabilities={"engine": "comfyui", "engine_version": "1", "node_types": [], "sampler_names": [], "scheduler_names": [], "snapshot_sha256": "b" * 64},
        runtime_provenance={"engine": "comfyui", "engine_version": "1", "reference": "runtime:1"},
        input_bindings={"control_ref": {"filename": "pose.png", "sha256": "c" * 64, "local_path": "inputs/pose.png"}},
    )
    assert result["ok"] is True
    assert captured["json"]["input_bindings"] == {"control_ref": {"filename": "pose.png", "sha256": "c" * 64, "local_path": "inputs/pose.png"}}


def test_variant_schema_recursively_keeps_every_nested_model_strict_and_only_seven_inputs() -> None:
    schema = asyncio.run(_variant_schema())
    assert set(schema["properties"]) == {
        "parent_recipe", "parent_recipe_sha256", "directives", "model_family",
        "runtime_capabilities", "runtime_provenance", "input_bindings",
    }
    assert set(schema["required"]) == set(schema["properties"])

    reachable: set[str] = set()

    def visit(value):
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
    assert {
        "CivitaiVariantParentRecipe", "CivitaiVariantRuntimeCapabilities",
        "CivitaiVariantRuntimeProvenance", "CivitaiVariantInputBinding",
        "CivitaiVariantResource", "CivitaiVariantPass", "CivitaiVariantRuntimeLock",
    }.issubset(reachable)


def test_variant_wrapper_preserves_structured_backend_failure_and_redacts_all_sentinels(monkeypatch) -> None:
    class Client:
        def post(self, endpoint, json):
            request = httpx.Request("POST", f"http://backend/{endpoint}")
            response = httpx.Response(
                422,
                request=request,
                json={"detail": {
                    "phase": "provenance_validation",
                    "code": "canonicalization_failed",
                    "message": "Bearer bearer-sentinel https://x.invalid/?token=token-query-sentinel",
                    "authorization": "authorization-sentinel",
                    "password": "password-sentinel",
                    "secret": "secret-sentinel",
                }},
            )
            raise httpx.HTTPStatusError("backend rejected", request=request, response=response)

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    result = civitai_recipes.civitai_recipe_variant_generate(
        parent_recipe={"schema_version": "1.0"}, parent_recipe_sha256="a" * 64,
        directives=[], model_family="sdxl", runtime_capabilities={}, runtime_provenance={}, input_bindings={},
    )
    encoded = json.dumps(result).lower()
    assert result["ok"] is False
    assert result["error"]["code"] == "canonicalization_failed"
    assert result["error"]["details"]["phase"] == "provenance_validation"
    for sentinel in (
        "authorization-sentinel", "bearer-sentinel", "token-query-sentinel",
        "password-sentinel", "secret-sentinel",
    ):
        assert sentinel not in encoded


def test_variant_wrapper_redacts_backend_success_payload_without_changing_queued_semantics(monkeypatch) -> None:
    class Client:
        def post(self, _endpoint, json):
            return {
                "variant_id": "variant-one", "job_id": "job-one", "status": "queued",
                "diagnostic": {
                    "authorization": "authorization-sentinel",
                    "message": "Bearer bearer-sentinel https://x.invalid/?token=token-query-sentinel",
                    "password": "password-sentinel", "secret": "secret-sentinel",
                },
            }

    monkeypatch.setattr(civitai_recipes, "_get_client", lambda: Client())
    result = civitai_recipes.civitai_recipe_variant_generate(
        parent_recipe={"schema_version": "1.0"}, parent_recipe_sha256="a" * 64,
        directives=[], model_family="sdxl", runtime_capabilities={}, runtime_provenance={}, input_bindings={},
    )
    assert result["ok"] is True and result["data"]["status"] == "queued"
    encoded = json.dumps(result).lower()
    for sentinel in (
        "authorization-sentinel", "bearer-sentinel", "token-query-sentinel",
        "password-sentinel", "secret-sentinel",
    ):
        assert sentinel not in encoded


def test_variant_catalog_and_public_docs_have_exact_name_endpoint_parity() -> None:
    from mcp_server.tool_catalog import INTENDED_TOOLS

    entry = next(item for item in INTENDED_TOOLS if item.name == "civitai_recipe_variant_generate")
    assert entry.function == "civitai_recipe_variant_generate"
    assert entry.backend_endpoints == ("POST /api/civitai-recipes/variants/generate-one",)
    root = Path(__file__).resolve().parents[2]
    for path in (root / "mcp-server" / "README.md", root / "docs" / "mcp-setup.md"):
        active = path.read_text(encoding="utf-8").split("<!-- MCP-CATALOG:START -->", 1)[1].split("<!-- MCP-CATALOG:END -->", 1)[0]
        assert active.count("`civitai_recipe_variant_generate`") == 1
        assert "POST /api/civitai-recipes/variants/generate-one" in active
