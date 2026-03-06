"""ComfyUI API 串接單元測試"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.comfyui import (
    ComfyUIError,
    ComfyUIClient,
    get_comfy_client,
    get_output_images,
)


@patch("app.core.comfyui.httpx.Client")
def test_submit_prompt_returns_prompt_id(mock_client_class: MagicMock) -> None:
    """提交 workflow 成功時回傳 prompt_id"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"prompt_id": "abc-123", "number": 1}
    mock_response.raise_for_status = MagicMock()

    mock_instance = MagicMock()
    mock_instance.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_instance
    mock_client_class.return_value.__exit__.return_value = None

    client = ComfyUIClient(base_url="http://test:8188")
    prompt = {"3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}}}

    pid = client.submit_prompt(prompt)

    assert pid == "abc-123"
    mock_instance.post.assert_called_once()
    call_json = mock_instance.post.call_args[1]["json"]
    assert call_json["prompt"] == prompt


@patch("app.core.comfyui.httpx.Client")
def test_submit_prompt_raises_on_api_error(mock_client_class: MagicMock) -> None:
    """ComfyUI 回傳 error 時拋出 ComfyUIError"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "error": "Node 3 not found",
        "node_errors": {"3": "Checkpoint not found"},
    }
    mock_response.raise_for_status = MagicMock()

    mock_instance = MagicMock()
    mock_instance.post.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_instance
    mock_client_class.return_value.__exit__.return_value = None

    client = ComfyUIClient(base_url="http://test:8188")

    with pytest.raises(ComfyUIError) as exc_info:
        client.submit_prompt({"3": {}})

    assert exc_info.value.args[0] == "Node 3 not found"
    assert exc_info.value.node_errors == {"3": "Checkpoint not found"}


def test_get_output_images_extracts_from_history() -> None:
    """從 history 正確萃取出輸出圖片列表"""
    history = {
        "prompt-xyz": {
            "outputs": {
                "9": {
                    "images": [
                        {
                            "filename": "ComfyUI_00001_.png",
                            "subfolder": "2024-01",
                            "type": "output",
                        },
                    ],
                },
            },
            "status": {},
        },
    }

    images = get_output_images(history, "prompt-xyz")

    assert len(images) == 1
    assert images[0]["filename"] == "ComfyUI_00001_.png"
    assert images[0]["subfolder"] == "2024-01"
    assert images[0]["type"] == "output"


def test_get_output_images_empty_when_prompt_missing() -> None:
    """prompt_id 不存在時回傳空列表"""
    history = {"other-id": {"outputs": {}}}
    images = get_output_images(history, "missing-id")
    assert images == []


@patch("app.core.comfyui.get_settings")
def test_get_comfy_client_returns_client_with_base_url_from_settings(
    mock_get_settings: MagicMock,
) -> None:
    """get_comfy_client 使用 config 的 comfyui_base_url"""
    mock_settings = MagicMock()
    mock_settings.comfyui_base_url = "http://custom:9999"
    mock_get_settings.return_value = mock_settings

    client = get_comfy_client()

    assert isinstance(client, ComfyUIClient)
    assert client.base_url == "http://custom:9999"


def test_get_comfy_client_returns_comfy_client_instance() -> None:
    """get_comfy_client 回傳 ComfyUIClient 實例"""
    client = get_comfy_client()
    assert isinstance(client, ComfyUIClient)
    assert client.base_url.endswith("8188") or "127.0.0.1" in client.base_url
