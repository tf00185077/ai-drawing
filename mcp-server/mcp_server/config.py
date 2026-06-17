"""
MCP Server 設定

Backend API URL 從環境變數讀取，避免硬編碼。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    """MCP Server 專用設定"""

    # 只從 MCP_ 開頭的真實環境變數讀取。
    # 不掛 env_file：避免誤吃啟動者 CWD（如 ~/.hermes/.env）的無關設定。
    # extra="ignore"：即使來源混入非預期欄位也直接忽略，不 raise。
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        extra="ignore",
    )

    # Backend API Base URL（MCP 呼叫 ai-drawing 後端用）
    # 本機已驗證 ai-drawing backend 使用 8001；8000 通常是其他本地 LLM/MLX 服務。
    backend_api_url: str = "http://127.0.0.1:8001"

    # ComfyUI API Base URL（用於 MCP 層釋放 ComfyUI 記憶體等操作）
    comfyui_api_url: str = "http://127.0.0.1:8188"

    # Backend gallery 實體檔案根目錄（用於 agent 交付本機圖片檔案）
    gallery_dir: str = "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"


@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()