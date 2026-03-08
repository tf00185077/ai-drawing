"""MCP Tools 單元測試"""
from unittest.mock import MagicMock, patch

from mcp_server.tools.generate import (
    generate_image,
    generate_image_custom_workflow,
    generate_queue_status,
    get_workflow_template,
    list_workflow_templates,
)
from mcp_server.tools.gallery import gallery_detail, gallery_list, gallery_rerun
from mcp_server.tools.lora_train import lora_train_start, lora_train_status


def test_generate_image_returns_success_message() -> None:
    """generate_image 成功時回傳 job_id"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc-123", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image(prompt="1girl, solo")

    assert "abc-123" in result
    assert "error" not in result.lower()
    mock_client.post.assert_called_once_with("generate/", json={"prompt": "1girl, solo"})


def test_generate_image_with_optional_params() -> None:
    """generate_image 可傳入 checkpoint、lora 等參數"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "x", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image(
            prompt="test",
            checkpoint="model.safetensors",
            lora="style.safetensors",
            steps=25,
        )

    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["prompt"] == "test"
    assert call_json["checkpoint"] == "model.safetensors"
    assert call_json["lora"] == "style.safetensors"
    assert call_json["steps"] == 25


def test_generate_queue_status_formats_output() -> None:
    """generate_queue_status 正確格式化佇列資訊"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "queue_running": [{"job_id": "r1", "status": "running"}],
        "queue_pending": [{"job_id": "p1", "status": "queued"}],
    }

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_queue_status()

    assert "執行中" in result
    assert "等候中" in result
    assert "r1" in result
    assert "p1" in result


def test_generate_image_with_character_style_resolves_prompt() -> None:
    """generate_image 使用 character、style 時會解析為 prompt"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "x", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image(character="初音", style="動漫")

    call_json = mock_client.post.call_args[1]["json"]
    assert "prompt" in call_json
    # 應包含語意解析後的關鍵字
    assert "anime" in call_json["prompt"] or "miku" in call_json["prompt"]


def test_list_workflow_templates_returns_template_names() -> None:
    """list_workflow_templates 回傳模板名稱列表"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"templates": ["default", "default_lora"]}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = list_workflow_templates()

    assert "default" in result
    assert "default_lora" in result
    mock_client.get.assert_called_once_with("generate/workflow-templates")


def test_get_workflow_template_returns_json_string() -> None:
    """get_workflow_template 回傳 workflow 的 JSON 字串"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"4": {"class_type": "CheckpointLoaderSimple"}}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_workflow_template("default")

    assert "CheckpointLoaderSimple" in result
    assert "4" in result
    mock_client.get.assert_called_once_with("generate/workflow-templates/default")


def test_generate_image_custom_workflow_submits_workflow() -> None:
    """generate_image_custom_workflow 將 workflow JSON 提交至 custom 端點"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc", "status": "queued"}
    wf_json = '{"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"x.safetensors"}}}'

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image_custom_workflow(workflow=wf_json, prompt="1girl")

    assert "abc" in result
    assert "error" not in result.lower()
    mock_client.post.assert_called_once()
    call_json = mock_client.post.call_args[1]["json"]
    assert "workflow" in call_json
    assert call_json["workflow"]["4"]["class_type"] == "CheckpointLoaderSimple"
    assert call_json["prompt"] == "1girl"


def test_gallery_list_returns_summary() -> None:
    """gallery_list 回傳圖庫摘要"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "items": [{"id": 1, "prompt": "test prompt", "created_at": "2024-01-01"}],
        "total": 1,
    }

    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        result = gallery_list()

    assert "1" in result
    assert "test prompt" in result or "1 筆" in result
