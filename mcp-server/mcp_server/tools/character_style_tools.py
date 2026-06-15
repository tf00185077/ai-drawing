"""
Character and Style Semantic Mapping MCP Tools

Allows AI to query available character/style aliases or resolve them directly to prompts.
"""
from mcp_server.character_style import get_resolver, resolve_to_prompt
from mcp_server.server import mcp


@mcp.tool()
def list_character_styles() -> str:
    """List all available character and style aliases for use as character and style parameters in generate_image."""
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
    """Resolve a character and style into a full prompt (without triggering image generation). Use to preview before calling generate_image."""
    prompt, lora = resolve_to_prompt(
        character=character, style=style, base_prompt=base_prompt
    )
    if lora:
        return f"prompt: {prompt}\nlora: {lora}"
    return f"prompt: {prompt}"
