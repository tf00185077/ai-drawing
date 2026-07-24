"""Prompt Library MCP 工具：雙語軟性 warning 測試"""
from unittest.mock import MagicMock, patch

from mcp_server.tools.prompt_library import prompt_library_save


def _save(resource_type, payload, **kwargs):
    client = MagicMock()
    client.put.return_value = {"entry": {"id": kwargs.get("resource_id", "x")}, "entry_revision": 2}
    with patch("mcp_server.tools.prompt_library._get_client", return_value=client):
        result = prompt_library_save(resource_type=resource_type, payload=payload, **kwargs)
    return result, client


def test_entry_without_chinese_warns_but_saves():
    payload = {"name_zh": "masterpiece detail", "description_zh": "quality", "prompt": "masterpiece"}
    result, client = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert client.put.called
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"


def test_entry_echoing_prompt_warns_echoes():
    payload = {"name_zh": "Masterpiece", "description_zh": "quality", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_echoes_prompt"


def test_entry_with_meaningful_chinese_has_no_warnings():
    payload = {"name_zh": "傑作", "description_zh": "品質詞", "prompt": "masterpiece"}
    result, _ = _save("entry", payload, resource_id="masterpiece", polarity="positive", category_id="quality-details")
    assert result["ok"] is True
    assert "warnings" not in result


def test_category_without_chinese_warns_missing():
    payload = {"name_zh": "quality details", "description_zh": "quality"}
    result, _ = _save("category", payload, resource_id="quality-details", polarity="positive")
    assert result["ok"] is True
    assert result["warnings"][0]["code"] == "name_zh_missing_chinese"
