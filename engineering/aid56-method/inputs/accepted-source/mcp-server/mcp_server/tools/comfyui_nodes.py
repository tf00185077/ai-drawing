"""
ComfyUI-Manager node resolve/install MCP tools.

Resolves a missing ComfyUI node class name (from a validation error) to
the ComfyUI-Manager package that provides it, and installs that package —
without restarting ComfyUI. Calls ComfyUI-Manager's REST API directly
(it runs on the same ComfyUI server free_comfyui_memory already talks
to), bypassing the ai-drawing backend, same as free_comfyui_memory.
"""
import json
import time

from mcp_server.client import HttpBackendClient
from mcp_server.config import get_mcp_settings
from mcp_server.server import mcp
from mcp_server.tools.responses import exception_error_json

_INSTALL_POLL_TIMEOUT_SECONDS = 60.0
_INSTALL_POLL_INTERVAL_SECONDS = 2.0


def _get_comfyui_client() -> HttpBackendClient:
    settings = get_mcp_settings()
    return HttpBackendClient(base_url=settings.comfyui_api_url, timeout=30.0)


def _looks_like_cnr_id(key: str) -> bool:
    """map_to_unified_keys leaves non-registry packages as a raw repo URL."""
    return "://" not in key


@mcp.tool()
def comfyui_node_provision(node_class_names: list[str]) -> str:
    """Resolve one or more missing ComfyUI node class names (as they appear in a ComfyUI
    validation error) to the ComfyUI-Manager package that provides them, and install that
    package if it is in ComfyUI-Manager's curated registry. Never installs from an
    arbitrary/uncurated git URL. Installing does NOT restart ComfyUI — the response's
    needs_restart flag means a restart is required before the node loads. Drawing Shasha
    must never call comfyui_restart without CTY's explicit approval in the current turn.
    Returns agent-friendly JSON."""
    client = _get_comfyui_client()

    try:
        mappings = client.get("/customnode/getmappings", params={"mode": "local"})
    except Exception as e:
        return exception_error_json(
            "comfyui_node_provision", e, where="comfyui_manager_getmappings"
        )

    resolved_key = None
    resolved_node_type = None
    unresolved: list[str] = []
    for name in node_class_names:
        match = None
        for pack_key, entry in mappings.items():
            node_list = entry[0] if isinstance(entry, list) and len(entry) > 0 else []
            if name in node_list:
                match = pack_key
                break
        if match and _looks_like_cnr_id(match) and resolved_key is None:
            resolved_key = match
            resolved_node_type = name
        elif not match or not _looks_like_cnr_id(match):
            unresolved.append(name)

    if resolved_key is None:
        return json.dumps(
            {
                "ok": True,
                "tool": "comfyui_node_provision",
                "resolved": False,
                "unresolved_node_types": unresolved,
                "next": (
                    "No installable curated package found for these node types. Fall back "
                    "to manual author/community research (new-architecture-bootstrap.md Phase A)."
                ),
            },
            ensure_ascii=False,
        )

    try:
        client.post(
            "/manager/queue/install",
            json={
                "id": resolved_key,
                "version": "latest",
                "selected_version": "latest",
                "channel": "default",
                "mode": "cache",
                "ui_id": resolved_key,
            },
        )
        client.post("/manager/queue/start", json={})
    except Exception as e:
        return exception_error_json(
            "comfyui_node_provision",
            e,
            where="comfyui_manager_install",
            details={"cnr_id": resolved_key},
        )

    status: dict = {}
    deadline = time.monotonic() + _INSTALL_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status = client.get("/manager/queue/status")
        if not status.get("is_processing") and status.get("in_progress_count", 0) == 0:
            break
        time.sleep(_INSTALL_POLL_INTERVAL_SECONDS)

    return json.dumps(
        {
            "ok": True,
            "tool": "comfyui_node_provision",
            "resolved": True,
            "node_type": resolved_node_type,
            "cnr_id": resolved_key,
            "unresolved_node_types": unresolved,
            "install_status": status,
            "needs_restart": True,
            "next": (
                "Package installed but ComfyUI must be restarted to load it. Ask CTY for "
                "explicit approval before calling comfyui_restart."
            ),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def comfyui_restart() -> str:
    """Restart ComfyUI so a newly-installed custom node package takes effect. Drawing Shasha
    must NEVER call this tool without CTY's explicit approval in the current turn — restarting
    interrupts any other job currently running on this ComfyUI instance. This is the only MCP
    path to an action CTY otherwise performs by hand. Returns agent-friendly JSON."""
    client = _get_comfyui_client()
    try:
        client.post("/manager/reboot", json={})
    except Exception as e:
        return exception_error_json(
            "comfyui_restart", e, where="comfyui_manager_reboot"
        )
    return json.dumps(
        {
            "ok": True,
            "tool": "comfyui_restart",
            "next": "ComfyUI is restarting. Poll mcp_ping until it responds before resubmitting any job.",
        },
        ensure_ascii=False,
    )
