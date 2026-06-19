"""
Workflow 模板能力目錄 MCP Tools

對應：GET /api/workflow-catalog/、GET /api/workflow-catalog/validate

讓 agent 先用能力標籤判斷「有沒有現成模板能解決需求」，命中就用模板名走 generate_image，
未命中再自組 workflow（見 search_nodes / get_node_schema）。標籤輕量、不含完整 workflow JSON。
"""
import json

from mcp_server.server import _get_client, mcp


@mcp.tool()
def list_template_capabilities() -> str:
    """List workflow templates with their machine-readable capability tags (modality, conditioning, io, model_family) and a human description — without the full workflow JSON. Use this FIRST when deciding how to generate: check whether an existing template's capabilities cover what you need (a deterministic match), apply it by name via generate_image if so, and only self-author a workflow (search_nodes / get_node_schema) when nothing matches. `description` is for humans and must not drive the decision; match on the tags. Returns agent-friendly JSON."""
    try:
        client = _get_client()
        resp = client.get("workflow-catalog/")
        items = resp.get("items", [])
        return json.dumps(
            {
                "ok": True,
                "tool": "list_template_capabilities",
                "templates": items,
                "total": resp.get("total", len(items)),
                "next": "if a template's tags cover your need, call generate_image with its id as template; else self-author via search_nodes/get_node_schema",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "list_template_capabilities",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )


@mcp.tool()
def validate_template_capabilities() -> str:
    """Validate every workflow template's capability manifest: tags drawn from the controlled vocabulary, manifest id matching the template filename, and the referenced workflow file existing. Invalid templates are returned as data (with per-template problems), not as a tool failure. Returns agent-friendly JSON."""
    try:
        client = _get_client()
        resp = client.get("workflow-catalog/validate")
        items = resp.get("items", [])
        invalid = resp.get("invalid", [])
        next_step = (
            f"templates with manifest problems: {invalid}; fix tags/vocabulary or filenames"
            if invalid
            else "all template manifests valid"
        )
        return json.dumps(
            {
                "ok": True,
                "tool": "validate_template_capabilities",
                "results": items,
                "invalid": invalid,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "validate_template_capabilities",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )
