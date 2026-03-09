"""
slack_handler 單元測試
測試指令解析與 handle_message 核心邏輯
"""
import pytest

from app.services.slack_handler import _is_slack_command, _parse_legacy_command


def test_parse_command_generate_with_count() -> None:
    """!generate 初音 5 → (初音, 5)"""
    result = _parse_legacy_command("!generate 初音 5")
    assert result is not None
    assert result[0] == "初音"
    assert result[1] == 5


def test_parse_command_shengtu_without_count() -> None:
    """生圖 1girl, solo → (1girl, solo, 1)"""
    result = _parse_legacy_command("生圖 1girl, solo")
    assert result is not None
    assert result[0] == "1girl, solo"
    assert result[1] == 1


def test_parse_command_unknown_format_returns_none() -> None:
    """非指令格式回傳 None"""
    assert _parse_legacy_command("hello world") is None
    assert _parse_legacy_command("") is None
    assert _parse_legacy_command("   ") is None


def test_parse_command_batch_size_clamped() -> None:
    """張數超過 8 時 clamp 至 8"""
    result = _parse_legacy_command("!generate test 99")
    assert result is not None
    assert result[1] == 8


def test_parse_command_shengtu_with_zhang() -> None:
    """生圖 初音 5張 → (初音, 5)"""
    result = _parse_legacy_command("生圖 初音 5張")
    assert result is not None
    assert result[0] == "初音"
    assert result[1] == 5


def test_is_slack_command_new_commands() -> None:
    """新指令 !給我可用指令、!生圖片 等應被辨識"""
    assert _is_slack_command("!給我可用指令") is True
    assert _is_slack_command("!help") is True
    assert _is_slack_command('!生圖片 {"prompt":"test"}') is True
    assert _is_slack_command("!訓練lora {}") is True


def test_is_slack_command_legacy() -> None:
    """Legacy !generate、生圖 應被辨識"""
    assert _is_slack_command("!generate 初音 5") is True
    assert _is_slack_command("生圖 1girl") is True


def test_is_slack_command_unknown() -> None:
    """非指令不處理"""
    assert _is_slack_command("hello") is False
    assert _is_slack_command("") is False
