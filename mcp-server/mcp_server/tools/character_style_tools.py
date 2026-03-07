"""
角色與風格語意對應 MCP Tools

供 AI 查詢可用的角色／風格別名，或直接解析為 prompt。
"""
from mcp_server.character_style import get_resolver, resolve_to_prompt
from mcp_server.server import mcp


@mcp.tool()
def list_character_styles() -> str:
    """列出所有可用的角色與風格別名，供 generate_image 的 character、style 參數使用。"""
    resolver = get_resolver()
    chars = resolver.list_characters()
    styles = resolver.list_styles()
    lines = [
        "可用角色（character 參數）: " + ", ".join(chars) if chars else "無",
        "可用風格（style 參數）: " + ", ".join(styles) if styles else "無",
    ]
    return "\n".join(lines)


@mcp.tool()
def resolve_character_style_prompt(
    character: str | None = None,
    style: str | None = None,
    base_prompt: str = "1girl, solo",
) -> str:
    """將角色、風格解析為完整 prompt（不觸發生圖）。可先預覽再呼叫 generate_image。"""
    prompt, lora = resolve_to_prompt(
        character=character, style=style, base_prompt=base_prompt
    )
    if lora:
        return f"prompt: {prompt}\nlora: {lora}"
    return f"prompt: {prompt}"
