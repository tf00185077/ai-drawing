"""Workflow 模板能力目錄 MCP 工具測試"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.workflow_catalog import (
    list_template_capabilities,
    validate_template_capabilities,
)


def test_list_template_capabilities_returns_tags() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "items": [
            {"id": "anima", "modality": "txt2img", "conditioning": [], "io": ["text"],
             "model_family": "anima", "description": "...", "valid": True}
        ],
        "total": 1,
    }
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(list_template_capabilities())

    assert result["ok"] is True
    assert result["templates"][0]["id"] == "anima"
    mock_client.get.assert_called_once_with("workflow-catalog/")


def test_validate_template_capabilities_surfaces_invalid() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "items": [{"id": "bad", "valid": False, "problems": ["modality not in vocabulary: 'video'"]}],
        "invalid": ["bad"],
        "total": 1,
    }
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(validate_template_capabilities())

    assert result["ok"] is True
    assert result["invalid"] == ["bad"]
    assert "bad" in result["next"]
