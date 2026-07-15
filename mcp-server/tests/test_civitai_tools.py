"""Civitai best-effort MCP tool contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.civitai import (
    civitai_generate_like,
    civitai_resource_acquire,
    civitai_resource_status,
    civitai_source_info,
)


def _http_error(status_code: int, detail: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://backend.test/api")
    response = httpx.Response(status_code, json={"detail": detail}, request=request)
    return httpx.HTTPStatusError(str(status_code), request=request, response=response)


def test_source_info_forwards_locator_and_returns_payload() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "prompt": "1girl, city night",
        "local_plan": {"checkpoint": "novaAnimeXL_ilV190.safetensors", "needs_download": []},
    }

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        result = civitai_source_info("https://civitai.com/images/123")

    assert result["ok"] is True
    assert result["tool"] == "civitai_source_info"
    assert result["prompt"] == "1girl, city night"
    mock_client.get.assert_called_once_with(
        "civitai/source-info", params={"locator": "https://civitai.com/images/123"}
    )


def test_generate_like_sends_only_provided_overrides() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"status": "queued", "job_id": "job-1", "substitutions": []}

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        result = civitai_generate_like("123", prompt="my subject", batch_size=4)

    assert result["ok"] is True
    assert result["job_id"] == "job-1"
    body = mock_client.post.call_args[1]["json"]
    assert body == {
        "locator": "123",
        "download_missing": True,
        "prompt": "my subject",
        "batch_size": 4,
    }


def test_generate_like_acquiring_state_passes_through() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "status": "acquiring_resources",
        "downloads": [{"status": "downloading", "resource": {"acquisition_id": 7}}],
        "next_step": "poll civitai_resource_status",
    }

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        result = civitai_generate_like("123", download_missing=True)

    assert result["ok"] is True
    assert result["status"] == "acquiring_resources"
    assert result["downloads"][0]["resource"]["acquisition_id"] == 7


def test_generate_like_backend_error_surfaces_code_and_hint() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = _http_error(
        422,
        {"code": "no_local_checkpoint", "message": "本地沒有任何 checkpoint 可用", "hint": "先下載"},
    )

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        result = civitai_generate_like("123")

    assert result["ok"] is False
    assert result["error"]["code"] == "no_local_checkpoint"
    assert result["error"]["hint"] == "先下載"


def test_resource_acquire_posts_locator() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "status": "downloading",
        "resource": {"acquisition_id": 3, "resource_name": "model.safetensors"},
    }

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        result = civitai_resource_acquire("https://civitai.com/models/376130?modelVersionId=2940478")

    assert result["ok"] is True
    assert result["resource"]["acquisition_id"] == 3
    mock_client.post.assert_called_once_with(
        "civitai/resources/acquire",
        json={"locator": "https://civitai.com/models/376130?modelVersionId=2940478"},
    )


def test_resource_status_with_and_without_id() -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = {"resources": [{"acquisition_id": 3, "status": "installed"}]}

    with patch("mcp_server.tools.civitai._get_client", return_value=mock_client):
        by_id = civitai_resource_status(acquisition_id=3)
        recent = civitai_resource_status()

    assert by_id["ok"] is True and recent["ok"] is True
    first_call, second_call = mock_client.get.call_args_list
    assert first_call[1]["params"] == {"limit": 10, "acquisition_id": 3}
    assert second_call[1]["params"] == {"limit": 10}
