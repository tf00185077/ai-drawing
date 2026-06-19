"""
ComfyUI Direct-Connection MCP Tools

Calls the ComfyUI API directly (bypassing the ai-drawing backend) to free memory,
and queries the live ComfyUI node catalog (via the backend proxy) so an agent can
ground self-authored workflows in the nodes this instance actually has.
"""
import json

import httpx

from mcp_server.config import get_mcp_settings
from mcp_server.server import _get_client, mcp


@mcp.tool()
def free_comfyui_memory(
    unload_models: bool = True,
    free_memory: bool = True,
) -> str:
    """Free ComfyUI VRAM. Must be called after image generation completes or fails. Returns agent-friendly JSON."""
    settings = get_mcp_settings()
    comfyui_url = settings.comfyui_api_url.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{comfyui_url}/free",
                json={"unload_models": unload_models, "free_memory": free_memory},
            )
            resp.raise_for_status()
        return json.dumps(
            {
                "ok": True,
                "tool": "free_comfyui_memory",
                "comfyui_base_url": comfyui_url,
                "unload_models": unload_models,
                "free_memory": free_memory,
                "next": "generation cycle is complete",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "free_comfyui_memory",
                "where": "comfyui",
                "error": str(e),
            },
            ensure_ascii=False,
        )


@mcp.tool()
def search_nodes(query: str = "", category: str = "", limit: int = 50, offset: int = 0) -> str:
    """Search the live ComfyUI node catalog by name and/or category, returning matching node types as {name, category} (not full schemas). Use when self-authoring a workflow to discover which nodes this instance actually has, then call get_node_schema for the ones you need. You MUST supply at least one of `query` or `category` (calling with neither is rejected to avoid dumping the whole catalog) — call list_node_categories first to browse categories, then narrow. `query` matches the node name (e.g. "ksampler"); `category` matches the functional category (e.g. "loaders", "conditioning") — both are case-insensitive substring filters combined with AND. Results are paged: each call returns at most `limit` (default 50) entries to protect context. `total` is the real match count; when `truncated=true`, prefer narrowing `query`/`category`, but you can reach the rest by calling again with `offset=next_offset`. Returns agent-friendly JSON."""
    if not query.strip() and not category.strip():
        return json.dumps(
            {
                "ok": False,
                "tool": "search_nodes",
                "error": "missing_filter",
                "next": "supply query or category; call list_node_categories to browse available categories first",
            },
            ensure_ascii=False,
        )
    try:
        client = _get_client()
        params = {"query": query, "category": category, "limit": limit, "offset": offset}
        resp = client.get("comfyui/nodes", params=params)
        nodes = resp.get("nodes", [])
        truncated = resp.get("truncated", False)
        next_offset = resp.get("next_offset")
        if truncated:
            next_step = (
                f"showing {resp.get('returned', len(nodes))} of {resp.get('total')} matches; "
                f"prefer narrowing query/category, or page the rest with offset={next_offset}"
            )
        elif nodes:
            next_step = "call get_node_schema for the node types you plan to use"
        else:
            next_step = "no node types match; broaden query/category, call list_node_categories, or check ComfyUI is running"
        return json.dumps(
            {
                "ok": True,
                "tool": "search_nodes",
                "query": query,
                "category": category,
                "nodes": nodes,
                "total": resp.get("total", len(nodes)),
                "offset": resp.get("offset", offset),
                "returned": resp.get("returned", len(nodes)),
                "truncated": truncated,
                "next_offset": next_offset,
                "next": next_step,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"ok": False, "tool": "search_nodes", "where": "backend", "error": str(e)},
            ensure_ascii=False,
        )


@mcp.tool()
def list_node_categories() -> str:
    """List all ComfyUI node categories on the live instance with each category's node count. Use this to browse available functional groupings (e.g. loaders, conditioning, sampling, image/mask) before narrowing a search with search_nodes(category=...), instead of guessing node names. Returns agent-friendly JSON."""
    try:
        client = _get_client()
        resp = client.get("comfyui/node-categories")
        categories = resp.get("categories", [])
        return json.dumps(
            {
                "ok": True,
                "tool": "list_node_categories",
                "categories": categories,
                "total": resp.get("total", len(categories)),
                "next": "call search_nodes(category=...) to list nodes in a category",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "list_node_categories",
                "where": "backend",
                "error": str(e),
            },
            ensure_ascii=False,
        )


@mcp.tool()
def get_node_schema(node_type: str) -> str:
    """Get one ComfyUI node type's input/output schema (required/optional input names with types, and output types) from the live instance, so you can wire it correctly when self-authoring a workflow. Returns agent-friendly JSON; a node type absent from this instance returns ok=false with a not-found indication."""
    try:
        client = _get_client()
        schema = client.get(f"comfyui/nodes/{node_type}")
        return json.dumps(
            {
                "ok": True,
                "tool": "get_node_schema",
                "node_type": node_type,
                "schema": schema,
                "next": "use these input/output names and types to build the workflow node",
            },
            ensure_ascii=False,
        )
    except httpx.HTTPStatusError as e:
        not_found = e.response is not None and e.response.status_code == 404
        return json.dumps(
            {
                "ok": False,
                "tool": "get_node_schema",
                "where": "backend",
                "node_type": node_type,
                "error": "not_found" if not_found else str(e),
                "next": (
                    "call search_nodes to find the correct node type name"
                    if not_found
                    else "check backend/ComfyUI status"
                ),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "tool": "get_node_schema",
                "where": "backend",
                "node_type": node_type,
                "error": str(e),
            },
            ensure_ascii=False,
        )
