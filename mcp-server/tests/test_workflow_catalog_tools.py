"""Workflow 模板能力目錄 MCP 工具測試"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.workflow_catalog import (
    consolidate_workflow_templates,
    list_template_capabilities,
    match_workflow_template,
    save_workflow_template,
    validate_template_capabilities,
)


def test_consolidate_reports_removed() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"removed": ["old_v1"], "count": 1}
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(consolidate_workflow_templates())

    assert result["ok"] is True
    assert result["removed"] == ["old_v1"]
    mock_client.post.assert_called_once_with("workflow-catalog/consolidate")


def test_save_workflow_template_created() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"ok": True, "created": True, "template_id": "gen_img2img_sdxl", "deprecated": None}
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(save_workflow_template("job1", "img2img", "sdxl", conditioning=["controlnet_pose"], io=["text", "image_ref"]))

    assert result["ok"] is True and result["created"] is True
    assert result["template_id"] == "gen_img2img_sdxl"
    assert "reuse" in result["next"]
    mock_client.post.assert_called_once_with(
        "workflow-catalog/backfill",
        json={"job_id": "job1", "modality": "img2img", "model_family": "sdxl",
              "conditioning": ["controlnet_pose"], "io": ["text", "image_ref"], "description": ""},
    )


def test_save_workflow_template_reused() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"ok": True, "created": False, "reused": "default"}
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(save_workflow_template("job1", "txt2img", "sdxl"))

    assert result["created"] is False
    assert "default" in result["next"]


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


def test_match_video_hit_tells_agent_to_derive_custom_workflow() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "request": {"modality": "img2video"},
        "matched": ["wan_i2v_base"],
        "total": 1,
    }
    with patch("mcp_server.tools.workflow_catalog._get_client", return_value=mock_client):
        result = json.loads(match_workflow_template("img2video", model_family="wan", io=["first_frame"]))

    assert result["ok"] is True
    assert result["matched"] == ["wan_i2v_base"]
    assert "get_workflow_template" in result["next"]
    assert "generate_video_custom_workflow" in result["next"]
    mock_client.get.assert_called_once_with(
        "workflow-catalog/match",
        params={
            "modality": "img2video",
            "model_family": "wan",
            "conditioning": "",
            "io": "first_frame",
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
