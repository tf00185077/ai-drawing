"""描述解析器單元測試"""
from mcp_server.description_parser import parse_description


def test_parse_character_and_style() -> None:
    """解析出角色與風格"""
    r = parse_description("初音，動漫風格")
    assert r.character == "初音"
    assert r.style == "動漫"
    assert r.template == "default"


def test_parse_resolution_1024() -> None:
    """解析 1024 解析度"""
    r = parse_description("初音 1024")
    assert r.width == 1024
    assert r.height == 1024


def test_parse_extra_prompt() -> None:
    """解析額外描述並對應關鍵字"""
    r = parse_description("穿和服的初音")
    assert r.character == "初音"
    assert "kimono" in r.extra_prompt


def test_parse_lora_hint() -> None:
    """含 lora 關鍵字時選 default_lora"""
    r = parse_description("用 lora 產生初音")
    assert r.template == "default_lora"
