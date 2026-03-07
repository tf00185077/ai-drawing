"""角色與風格語意對應單元測試"""
from mcp_server.character_style import (
    DefaultCharacterStyleResolver,
    ResolveResult,
    resolve_to_prompt,
)


def test_resolve_character_returns_prompt() -> None:
    """resolve_character 正確對應角色到 prompt"""
    r = DefaultCharacterStyleResolver()
    result = r.resolve_character("初音")
    assert result is not None
    assert isinstance(result, ResolveResult)
    assert "miku" in result.prompt_part or "初音" in result.prompt_part
    assert result.lora is None


def test_resolve_style_returns_prompt() -> None:
    """resolve_style 正確對應風格到 prompt"""
    r = DefaultCharacterStyleResolver()
    result = r.resolve_style("動漫")
    assert result is not None
    assert "anime" in result.prompt_part or "動漫" in result.prompt_part


def test_resolve_to_prompt_combines_character_and_style() -> None:
    """resolve_to_prompt 正確組合角色與風格"""
    prompt, lora = resolve_to_prompt(
        character="初音", style="動漫", base_prompt="1girl, solo"
    )
    assert "1girl" in prompt or "solo" in prompt
    assert "miku" in prompt or "anime" in prompt or "動漫" in prompt


def test_resolve_unknown_returns_as_is() -> None:
    """未知的角色／風格直接加入 prompt"""
    prompt, _ = resolve_to_prompt(
        character="未知角色", style="未知風格", base_prompt="1girl"
    )
    assert "未知角色" in prompt
    assert "未知風格" in prompt


def test_list_characters_and_styles() -> None:
    """list_characters、list_styles 回傳非空列表"""
    r = DefaultCharacterStyleResolver()
    chars = r.list_characters()
    styles = r.list_styles()
    assert len(chars) > 0
    assert len(styles) > 0
    assert "初音" in chars or "sks" in chars
    assert "動漫" in styles
