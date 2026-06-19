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

from mcp_server.server import _get_client, mcp


@mcp.tool()
def list_style_presets() -> str:
    """List available style presets (creator/style recipes). Returns agent-friendly JSON with each preset's id, name, available profiles, and summary resource references. Use a preset id with compose_style_preset to build a generation payload."""
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
        return json.dumps(
            {
                "ok": False,
                "tool": "list_style_presets",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )


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
        return json.dumps(
            {
                "ok": False,
                "tool": "get_style_preset",
                "where": "backend",
                "preset_id": preset_id,
                "error": str(e),
            },
            ensure_ascii=False,
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
        return json.dumps(
            {
                "ok": False,
                "tool": "validate_style_presets",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )


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
        return json.dumps(
            {
                "ok": False,
                "tool": "compose_style_preset",
                "where": "backend",
                "preset_id": preset_id,
                "error": str(e),
            },
            ensure_ascii=False,
        )
