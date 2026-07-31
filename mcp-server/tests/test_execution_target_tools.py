"""Execution target contract for every MCP product tool that queues ComfyUI work."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_server.server import mcp
from mcp_server.tools.civitai import civitai_generate_like
from mcp_server.tools.gallery import gallery_rerun
from mcp_server.tools.generate import (
    generate_image,
    generate_image_custom_workflow,
    generate_video_custom_workflow,
    generate_video_wan_keyframes,
)
from mcp_server.tools.lora_train import lora_train_smoke_test
from mcp_server.tools.style_presets import test_saved_style_preset_workflow as run_saved_workflow_test


COMFYUI_JOB_TOOLS = (
    "generate_image",
    "generate_image_custom_workflow",
    "generate_video_custom_workflow",
    "generate_video_wan_keyframes",
    "civitai_generate_like",
    "gallery_rerun",
    "test_saved_style_preset_workflow",
    "lora_train_smoke_test",
)


@pytest.mark.asyncio
async def test_all_comfyui_job_tools_expose_execution_target_enum_with_local_default() -> None:
    registered = {tool.name: tool for tool in await mcp.list_tools()}

    for tool_name in COMFYUI_JOB_TOOLS:
        execution_target = registered[tool_name].inputSchema["properties"]["execution_target"]
        assert execution_target["enum"] == ["local", "worker"], tool_name
        assert execution_target["default"] == "local", tool_name


def test_generate_entrypoints_forward_worker_exactly() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "job-1", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image(prompt="test", execution_target="worker")
        generate_image_custom_workflow(
            workflow='{"1": {"class_type": "SaveImage"}}',
            execution_target="worker",
        )
        generate_video_custom_workflow(
            workflow='{"1": {"class_type": "VHS_VideoCombine"}}',
            execution_target="worker",
        )
        generate_video_wan_keyframes(
            images=["frames/a.png", "frames/b.png"],
            prompt="move",
            execution_target="worker",
        )

    assert [call.kwargs["json"]["execution_target"] for call in mock_client.post.call_args_list] == [
        "worker",
        "worker",
        "worker",
        "worker",
    ]


def test_non_generate_module_entrypoints_forward_worker_exactly() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "job-2", "status": "queued"}

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        civitai_generate_like("123", execution_target="worker")
    assert mock_client.post.call_args.kwargs["json"]["execution_target"] == "worker"

    mock_client.reset_mock()
    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        gallery_rerun(42, execution_target="worker")
    mock_client.post.assert_called_once_with(
        "gallery/42/rerun",
        json={"execution_target": "worker"},
    )

    mock_client.reset_mock()
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        run_saved_workflow_test("creator-a", execution_target="worker")
    mock_client.post.assert_called_once_with(
        "style-presets/creator-a/workflow/test",
        json={"execution_target": "worker"},
    )

    mock_client.reset_mock()
    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        lora_train_smoke_test("train-1", execution_target="worker")
    mock_client.post.assert_called_once_with(
        "lora-train/jobs/train-1/smoke-test",
        json={"execution_target": "worker"},
    )


def test_all_comfyui_job_tools_forward_local_by_default() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "job-local", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image(prompt="test")
        generate_image_custom_workflow(workflow="{}")
        generate_video_custom_workflow(workflow="{}")
        generate_video_wan_keyframes(images=["a.png"], prompt="move")
    assert all(
        call.kwargs["json"]["execution_target"] == "local"
        for call in mock_client.post.call_args_list
    )

    mock_client.reset_mock()
    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        civitai_generate_like("123")
    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        gallery_rerun(42)
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        run_saved_workflow_test("creator-a")
    with patch("mcp_server.tools.lora_train._get_client", return_value=mock_client):
        lora_train_smoke_test("train-1")

    assert all(
        call.kwargs["json"]["execution_target"] == "local"
        for call in mock_client.post.call_args_list
    )
