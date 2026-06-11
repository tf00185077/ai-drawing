"""MCP settings tests."""

from mcp_server.config import McpSettings


def test_mcp_settings_defaults_match_local_ai_drawing_runtime() -> None:
    """Defaults should target the verified local ai-drawing backend, ComfyUI, and gallery."""
    settings = McpSettings()

    assert settings.backend_api_url == "http://127.0.0.1:8001"
    assert settings.comfyui_api_url == "http://127.0.0.1:8188"
    assert (
        settings.gallery_dir
        == "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"
    )


def test_mcp_settings_allow_env_overrides(monkeypatch) -> None:
    """MCP_* environment variables should override backend, ComfyUI, and gallery settings."""
    monkeypatch.setenv("MCP_BACKEND_API_URL", "http://127.0.0.1:9001")
    monkeypatch.setenv("MCP_COMFYUI_API_URL", "http://127.0.0.1:9188")
    monkeypatch.setenv("MCP_GALLERY_DIR", "/tmp/ai-drawing-gallery")

    settings = McpSettings()

    assert settings.backend_api_url == "http://127.0.0.1:9001"
    assert settings.comfyui_api_url == "http://127.0.0.1:9188"
    assert settings.gallery_dir == "/tmp/ai-drawing-gallery"
