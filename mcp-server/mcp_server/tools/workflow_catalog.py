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
def match_workflow_template(
    modality: str,
    model_family: str = "",
    conditioning: list[str] | None = None,
    io: list[str] | None = None,
) -> str:
    """Deterministically decide whether an existing template can satisfy a need, by the binary set test `template capabilities ⊇ required capabilities`. Supply the capabilities you need: `modality` is REQUIRED (txt2img | img2img | inpaint); `model_family` (e.g. sdxl, anima) constrains family only if given; `conditioning` (e.g. ["controlnet_pose"]) and `io` (e.g. ["text","image_ref","mask"]) are sets the template must cover. On a hit, apply a returned template id via generate_image(template=...). On a miss (empty list), self-author a workflow with search_nodes/get_node_schema — matching is strict (a differing modality is a miss even if other tags overlap). Returns agent-friendly JSON."""
    try:
        client = _get_client()
        params = {
            "modality": modality,
            "model_family": model_family,
            "conditioning": ",".join(conditioning or []),
            "io": ",".join(io or []),
        }
        resp = client.get("workflow-catalog/match", params=params)
        matched = resp.get("matched", [])
        next_step = (
            f"reuse: call generate_image(template={matched[0]!r}, ...) (or pick among {matched})"
            if matched
            else "miss: no template covers this need; self-author a workflow via search_nodes/get_node_schema"
        )
        return json.dumps(
            {
                "ok": True,
                "tool": "match_workflow_template",
                "request": resp.get("request", params),
                "matched": matched,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "match_workflow_template",
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
