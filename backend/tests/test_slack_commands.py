"""Slack 指令模組單元測試"""
from __future__ import annotations

import pytest

from app.services.slack_commands import (
    COMMAND_SPECS,
    build_help_message,
    parse_command,
    parse_json_safe,
    validate_params,
)


def test_parse_command_recognizes_commands() -> None:
    """parse_command 正確辨識各指令並解析 JSON"""
    # help
    assert parse_command("!給我可用指令") == ("help", "{}")
    assert parse_command("!help") == ("help", "{}")

    # generate
    assert parse_command("!生圖片 {}") == ("generate", "{}")
    assert parse_command('!生圖片 {"prompt":"test"}') == ("generate", '{"prompt":"test"}')

    # generate_pose
    assert parse_command("!用指定動作生圖片 {}") == ("generate_pose", "{}")

    # train_lora
    assert parse_command('!訓練lora {"folder":"x"}') == ("train_lora", '{"folder":"x"}')

    # query_gallery
    assert parse_command('!查詢圖片 {"limit":5}') == ("query_gallery", '{"limit":5}')

    # rerun
    assert parse_command('!重新生成圖片 {"image_id":123}') == ("rerun", '{"image_id":123}')

    # 無匹配
    assert parse_command("hello world") == (None, None)
    assert parse_command("") == (None, None)


def test_build_help_message_contains_all() -> None:
    """build_help_message 回傳包含 6 個指令的文案"""
    msg = build_help_message()
    assert "!生圖片" in msg
    assert "!用指定動作生圖片" in msg
    assert "!訓練lora" in msg
    assert "!查詢圖片" in msg
    assert "!重新生成圖片" in msg
    assert "!給我可用指令" in msg
    assert len(COMMAND_SPECS) == 6


def test_validate_params_generate() -> None:
    """validate_params 檢查 generate 必填 prompt"""
    assert validate_params("generate", {}) == "缺少必填參數：prompt"
    assert validate_params("generate", {"prompt": "x"}) is None


def test_validate_params_generate_pose() -> None:
    """validate_params 檢查 generate_pose 必填 prompt、image_pose"""
    assert validate_params("generate_pose", {}) == "缺少必填參數：prompt"
    assert validate_params("generate_pose", {"prompt": "x"}) == "缺少必填參數：image_pose"
    assert validate_params("generate_pose", {"prompt": "1girl", "image_pose": "2026-03-08/x.png"}) is None


def test_validate_params_rerun() -> None:
    """validate_params 檢查 rerun 的 image_id 為整數"""
    assert validate_params("rerun", {}) == "缺少必填參數：image_id"
    assert validate_params("rerun", {"image_id": 123}) is None
    assert "必須為整數" in (validate_params("rerun", {"image_id": "x"}) or "")


def test_parse_json_safe() -> None:
    """parse_json_safe 正確解析或回傳錯誤"""
    data, err = parse_json_safe('{"a":1}')
    assert data == {"a": 1} and err is None
    data, err = parse_json_safe("")
    assert data == {} and err is None
    data, err = parse_json_safe("invalid")
    assert data is None and err is not None
