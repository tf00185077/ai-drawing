"""
AI Drawing MCP Server

Uses FastMCP, communicates with Cursor and other MCP clients via stdio.
Tools are defined in the mcp_server.tools module.
"""
from mcp.server.fastmcp import FastMCP

from mcp_server.client import HttpBackendClient
from mcp_server.config import get_mcp_settings

mcp = FastMCP(
    "AI Drawing",
    json_response=True,
)


def _get_client() -> HttpBackendClient:
    """Get the Backend API Client (injectable for testing)"""
    settings = get_mcp_settings()
    return HttpBackendClient(base_url=f"{settings.backend_api_url}/api")


@mcp.tool()
def mcp_ping() -> str:
    """Check MCP Server and Backend connection status. Returns an error if the Backend is not running."""
    try:
        # Use the /health endpoint, independent of DB or gallery
        settings = get_mcp_settings()
        client = HttpBackendClient(base_url=settings.backend_api_url, timeout=5.0)
        client.get("health")
        return "ok: Backend 連線正常"
    except Exception as e:
        return f"error: {e}"


# Register tools modules (importing triggers @mcp.tool() decorators)
from mcp_server.tools import (  # noqa: E402, F401
    character_style_tools,
    comfyui,
    gallery,
    generate,
    lora_train,
)


def main() -> None:
    """Entry point: start with stdio transport (for Cursor and other MCP clients)"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
