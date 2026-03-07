"""
AI 自動化出圖系統 MCP Server

使用 FastMCP，透過 stdio 與 Cursor 等 MCP 用戶端通訊。
Tools 定義於 mcp_server.tools 模組（F2 實作）。
"""
from mcp.server.fastmcp import FastMCP

from mcp_server.client import HttpBackendClient
from mcp_server.config import get_mcp_settings

mcp = FastMCP(
    "AI Drawing",
    json_response=True,
)


def _get_client() -> HttpBackendClient:
    """取得 Backend API Client（可注入，便於測試）"""
    settings = get_mcp_settings()
    return HttpBackendClient(base_url=f"{settings.backend_api_url}/api")


@mcp.tool()
def mcp_ping() -> str:
    """檢查 MCP Server 與 Backend 連線狀態。若 Backend 未啟動會回傳錯誤。"""
    try:
        client = _get_client()
        # 呼叫一個輕量 endpoint 驗證連線
        client.get("gallery/", params={"limit": 1})
        return "ok: Backend 連線正常"
    except Exception as e:
        return f"error: {e}"


def main() -> None:
    """Entry point：以 stdio transport 啟動（供 Cursor 等 MCP 用戶端使用）"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
