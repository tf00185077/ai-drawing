"""
Workflow 模板能力目錄 MCP Tools

對應：GET /api/workflow-catalog/、GET /api/workflow-catalog/validate

讓 agent 先用能力標籤判斷「有沒有現成模板能解決需求」，命中就用模板名走 generate_image，
未命中再自組 workflow（見 search_nodes / get_node_schema）。標籤輕量、不含完整 workflow JSON。
"""
import json

from mcp_server.server import _get_client, mcp
from mcp_server.tools.responses import exception_error_json


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
        return exception_error_json("list_template_capabilities", e, where="backend")


@mcp.tool()
def match_workflow_template(
    modality: str,
    model_family: str = "",
    conditioning: list[str] | None = None,
    io: list[str] | None = None,
) -> str:
    """Deterministically decide whether an existing template can satisfy a need, by the binary set test `template capabilities ⊇ required capabilities`. Supply the capabilities you need: `modality` is REQUIRED (txt2img | img2img | inpaint | txt2video | img2video); `model_family` (e.g. sdxl, anima, wan) constrains family only if given; `conditioning` (e.g. ["controlnet_pose"]) and `io` (e.g. ["text","image_ref","mask","first_frame","last_frame","video_ref","audio_ref"]) are sets the template must cover. On a hit, apply a returned image template id via generate_image(template=...) or fetch/derive a video template and submit through generate_video_custom_workflow. On a miss (empty list), self-author a workflow with search_nodes/get_node_schema — matching is strict (a differing modality is a miss even if other tags overlap). Returns agent-friendly JSON."""
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
        request_modality = str(resp.get("request", {}).get("modality") or modality)
        if matched and request_modality in {"txt2video", "img2video"}:
            next_step = (
                f"reuse video base: call get_workflow_template({matched[0]!r}), inspect/derive with "
                "search_nodes/get_node_schema, then submit via generate_video_custom_workflow"
            )
        elif matched:
            next_step = f"reuse: call generate_image(template={matched[0]!r}, ...) (or pick among {matched})"
        else:
            next_step = "miss: no template covers this need; self-author a workflow via search_nodes/get_node_schema"
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
        return exception_error_json("match_workflow_template", e, where="backend")


@mcp.tool()
def save_workflow_template(
    job_id: str,
    modality: str,
    model_family: str,
    conditioning: list[str] | None = None,
    io: list[str] | None = None,
    description: str = "",
) -> str:
    """Promote a self-authored workflow that SUCCEEDED into the reusable template catalog, so future needs match it (the library self-extends). Call this only after a custom-workflow job has completed successfully (get_generation_status returns completed with an image or artifact). Pass that job's `job_id` plus the capability tags describing what the workflow does — `modality` (txt2img|img2img|inpaint|txt2video|img2video), `model_family` (e.g. sdxl, anima, wan), and optional `conditioning`/`io` sets — drawn from the controlled vocabulary. The backend gates on the DB success record (only a recorded success is promotable), reads the actual submitted workflow, strips one-off prompt/seed to store a reusable shape, dedupes on the capability tag-set (no duplicate if already covered), files it under its modality family, and versions rather than overwriting. Returns agent-friendly JSON: created (new template_id), reused (existing id covers it), or an error. Reserve this for genuinely new, reusable shapes — not one-off experiments."""
    try:
        client = _get_client()
        body = {
            "job_id": job_id,
            "modality": modality,
            "model_family": model_family,
            "conditioning": conditioning or [],
            "io": io or [],
            "description": description,
        }
        resp = client.post("workflow-catalog/backfill", json=body)
        if resp.get("created"):
            nxt = f"template '{resp.get('template_id')}' added; future matches can reuse it"
            if resp.get("deprecated"):
                nxt += f" (superseded broken template '{resp['deprecated']}')"
        else:
            nxt = f"not added; capability already covered by '{resp.get('reused')}'"
        return json.dumps(
            {"ok": True, "tool": "save_workflow_template", **resp, "next": nxt},
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("save_workflow_template", e, where="backend")


@mcp.tool()
def consolidate_workflow_templates() -> str:
    """Retire deprecated templates by deleting their files — periodic/manual housekeeping for the self-extending catalog. Deprecated templates (superseded by a newer version) are already excluded from reuse matching; this just removes the leftover files so the catalog stays tidy. Safe to run anytime. Returns the removed template ids."""
    try:
        client = _get_client()
        resp = client.post("workflow-catalog/consolidate")
        removed = resp.get("removed", [])
        return json.dumps(
            {
                "ok": True,
                "tool": "consolidate_workflow_templates",
                "removed": removed,
                "count": resp.get("count", len(removed)),
                "next": "catalog cleaned" if removed else "nothing to retire",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("consolidate_workflow_templates", e, where="backend")


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
        return exception_error_json("validate_template_capabilities", e, where="backend")
