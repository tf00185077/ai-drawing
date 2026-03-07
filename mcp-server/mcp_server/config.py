"""
MCP Server 設定

Backend API URL 從環境變數讀取，避免硬編碼。
"""
from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class McpSettings(BaseSettings):
    """MCP Server 專用設定"""

    model_config = ConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Backend API Base URL（MCP 呼叫 ai-drawing 後端用）
    backend_api_url: str = "http://127.0.0.1:8000"


@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()
