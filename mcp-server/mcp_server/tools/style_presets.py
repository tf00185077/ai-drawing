"""
Style Preset Catalog MCP Tools

Corresponds to: GET /api/style-presets/, GET /api/style-presets/{id},
GET /api/style-presets/validate, POST /api/style-presets/{id}/compose

These tools let an agent discover creator/style recipes ("presets"), inspect them,
validate that the referenced ComfyUI resources are installed, and compose a preset
with a user content prompt into a generation payload. Composition does NOT submit a
job: the agent then forwards the composed `generation` payload to generate_image
(compose first, generate second).
"""
import json

import httpx

from mcp_server.server import _get_client, mcp
from mcp_server.tools.responses import error_json, exception_error_json


@mcp.tool()
def create_style_preset(
    id: str,
    name: str,
    base_prompt: str = "",
    negative_prompt: str = "",
    template: str | None = None,
    checkpoint: str | None = None,
    lora: str | None = None,
    lora_strength: float | None = None,
    loras: list[dict] | None = None,
    diffusion_model: str | None = None,
    text_encoder: str | None = None,
    vae: str | None = None,
    default_params: dict | None = None,
    profiles: dict | None = None,
    overwrite: bool = False,
) -> str:
    """Create a new style preset from the fields the user describes, writing BOTH the machine recipe (style_presets/agent/presets/<id>.json) and a human note (style_presets/human/<id>.md, frontmatter preset_id matching id), then reindexing so it's listable. `id` (kebab-ish slug) and `name` are required; fill the recipe fields you know (template/checkpoint/lora/lora_strength, base_prompt/negative_prompt, default_params, and `profiles` as {name: {prompt_prefix, prompt_suffix, negative_prompt, params}}). For multiple LoRAs use `loras` = [{name, strength_model, strength_clip?}] (ordered to the template's LoraLoader nodes; takes precedence over single lora). Refuses to overwrite an existing preset unless `overwrite=true`. Missing referenced resources are reported in the result (validation) but do NOT block creation. Returns agent-friendly JSON with the created id and validation."""
    try:
        client = _get_client()
        body = {
            "id": id,
            "name": name,
            "base_prompt": base_prompt,
            "negative_prompt": negative_prompt,
            "template": template,
            "checkpoint": checkpoint,
            "lora": lora,
            "lora_strength": lora_strength,
            "loras": loras or [],
            "diffusion_model": diffusion_model,
            "text_encoder": text_encoder,
            "vae": vae,
            "default_params": default_params or {},
            "profiles": profiles or {},
            "overwrite": overwrite,
        }
        resp = client.post("style-presets/", json=body)
        val = resp.get("validation", {})
        missing = val.get("missing", [])
        if missing:
            nxt = f"created; but missing resources {[m['name'] for m in missing]} — install them or edit the preset"
        else:
            nxt = "created and valid; use compose_style_preset to generate with it"
        return json.dumps(
            {"ok": True, "tool": "create_style_preset", **resp, "next": nxt},
            ensure_ascii=False,
        )
    except httpx.HTTPStatusError as e:
        code = e.response.status_code if e.response is not None else None
        if code == 409:
            err, nxt = "already_exists", "set overwrite=true to replace, or choose a different id"
        elif code == 422:
            err, nxt = "invalid_request", "id must be a slug (letters/digits/_/-) and name is required"
        else:
            err, nxt = str(e), "check backend"
        return error_json(
            "create_style_preset",
            err,
            err,
            details={"where": "backend", "status_code": code},
            next=nxt,
        )
    except Exception as e:
        return exception_error_json("create_style_preset", e, where="backend")


@mcp.tool()
def reindex_style_presets() -> str:
    """Rebuild the style-preset lightweight index from the per-preset detail files. Call after manually adding/editing presets so list_style_presets reflects them. Returns the rebuilt index entries."""
    try:
        client = _get_client()
        resp = client.post("style-presets/reindex")
        presets = resp.get("presets", [])
        return json.dumps(
            {
                "ok": True,
                "tool": "reindex_style_presets",
                "presets": presets,
                "count": len(presets),
                "next": "index rebuilt; list_style_presets now reflects current presets",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("reindex_style_presets", e, where="backend")


@mcp.tool()
def list_style_presets() -> str:
    """List available style presets (creator/style recipes) from the lightweight index — does not load full preset bodies. Returns agent-friendly JSON with each preset's id, name, available profiles, and summary resource references. Use a preset id with compose_style_preset to build a generation payload."""
    try:
        client = _get_client()
        resp = client.get("style-presets/")
        items = resp.get("items", [])
        next_step = (
            "call get_style_preset or compose_style_preset with a preset id"
            if items
            else "no presets defined; ask the user to add a recipe or use generate_image directly"
        )
        return json.dumps(
            {
                "ok": True,
                "tool": "list_style_presets",
                "presets": items,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("list_style_presets", e, where="backend")


@mcp.tool()
def get_style_preset(preset_id: str) -> str:
    """Get the full recipe for a style preset by id: resource references, base/negative prompt, default params, profiles, and note metadata. Returns agent-friendly JSON."""
    try:
        client = _get_client()
        resp = client.get(f"style-presets/{preset_id}")
        return json.dumps(
            {
                "ok": True,
                "tool": "get_style_preset",
                "preset": resp,
                "next": "call compose_style_preset with this preset_id and a content_prompt",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json(
            "get_style_preset",
            e,
            where="backend",
            preset_id=preset_id,
        )


@mcp.tool()
def validate_style_presets() -> str:
    """Validate that every style preset's referenced resources (checkpoint, LoRA, diffusion model, text encoder, VAE, workflow template) are installed. Returns agent-friendly JSON with per-preset validity and missing-resource diagnostics. Invalid presets are returned as data, not as a tool failure."""
    try:
        client = _get_client()
        resp = client.get("style-presets/validate")
        items = resp.get("items", [])
        invalid = [v["preset_id"] for v in items if not v.get("valid", False)]
        next_step = (
            f"presets with missing resources: {invalid}; fix the catalog or install the resources"
            if invalid
            else "all presets valid; safe to compose and generate"
        )
        return json.dumps(
            {
                "ok": True,
                "tool": "validate_style_presets",
                "results": items,
                "invalid_presets": invalid,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json("validate_style_presets", e, where="backend")


@mcp.tool()
def compose_style_preset(
    preset_id: str,
    content_prompt: str,
    profile: str | None = None,
    overrides: dict | None = None,
) -> str:
    """
    Compose a style preset with a user content_prompt into a generate_image-compatible payload.

    content_prompt is "what the user wants in this image" (not the full final prompt); the final
    prompt is assembled as preset base_prompt + profile prefix + content_prompt + profile suffix.
    profile selects a named variant (e.g. "portrait"). overrides is an optional dict of generation
    params (e.g. {"seed": 123, "steps": 40}) that take highest priority.

    This does NOT submit a job. On success the returned JSON includes the composed `generation`
    payload and a `next` instruction to call generate_image with that payload.
    """
    try:
        client = _get_client()
        body: dict[str, object] = {"content_prompt": content_prompt}
        if profile is not None:
            body["profile"] = profile
        if overrides:
            body["overrides"] = overrides
        resp = client.post(f"style-presets/{preset_id}/compose", json=body)
        return json.dumps(
            {
                "ok": True,
                "tool": "compose_style_preset",
                "preset_id": resp.get("preset_id", preset_id),
                "profile": resp.get("profile"),
                "generation": resp.get("generation", {}),
                "next": "call generate_image with the fields in `generation` (prompt, checkpoint, lora, diffusion_model, etc.)",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return exception_error_json(
            "compose_style_preset",
            e,
            where="backend",
            preset_id=preset_id,
        )
