"""Workflow 模板能力目錄 MCP 工具測試"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.workflow_catalog import (
    list_template_capabilities,
    match_workflow_template,
    validate_template_capabilities,
)


def test_match_hit_tells_agent_to_reuse() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "request": {"modality": "img2img"},
        "matched": ["img2img_lora_pose", "controlnet_pose"],
        "total": 2,
    }
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(
            match_workflow_template("img2img", conditioning=["controlnet_pose"], io=["image_ref"])
        )

    assert result["ok"] is True
    assert "img2img_lora_pose" in result["matched"]
    assert "generate_image" in result["next"]
    mock_client.get.assert_called_once_with(
        "workflow-catalog/match",
        params={
            "modality": "img2img",
            "model_family": "",
            "conditioning": "controlnet_pose",
            "io": "image_ref",
        },
    )


def test_match_miss_tells_agent_to_self_author() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {"request": {"modality": "txt2img"}, "matched": [], "total": 0}
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(match_workflow_template("txt2img", model_family="sd15"))

    assert result["ok"] is True
    assert result["matched"] == []
    assert "self-author" in result["next"]


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
