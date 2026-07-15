"""Style preset catalog MCP tools 單元測試"""
import json
from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.style_presets import (
    compose_style_preset,
    get_style_preset,
    list_style_presets,
)


def test_list_style_presets_returns_agent_friendly_json() -> None:
    """list_style_presets 回傳 agent 可解析 JSON，含 presets 與 next"""
    mock_client = MagicMock()
    loras = [{"name": "line.safetensors", "strength_model": 0.8}]
    mock_client.get.return_value = {
        "items": [{"id": "creator-a", "name": "Creator A", "profiles": ["portrait"], "loras": loras}]
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = list_style_presets()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "list_style_presets"
    assert data["presets"][0]["id"] == "creator-a"
    assert data["presets"][0]["loras"] == loras
    assert "compose_style_preset" in data["next"]
    mock_client.get.assert_called_once_with("style-presets/")


def test_list_style_presets_empty_tells_agent_alternative() -> None:
    """無 preset 時 next 引導使用者新增或改用 generate_image"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"items": []}

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = list_style_presets()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["presets"] == []
    assert "generate_image" in data["next"]


def test_get_style_preset_returns_full_recipe() -> None:
    loras = [
        {"name": "line.safetensors", "strength_model": 0.8},
        {"name": "color.safetensors", "strength_model": 0.5, "strength_clip": 0.4},
    ]
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "id": "creator-a",
        "name": "Creator A",
        "checkpoint": "model.safetensors",
        "loras": loras,
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = get_style_preset("creator-a")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "get_style_preset"
    assert data["preset"]["checkpoint"] == "model.safetensors"
    assert data["preset"]["loras"] == loras
    assert "compose_style_preset" in data["next"]
    mock_client.get.assert_called_once_with("style-presets/creator-a")


def test_get_style_preset_backend_error_returns_structured_json() -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("not found")

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = get_style_preset("nope")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "get_style_preset"
    assert data["preset_id"] == "nope"
    assert data["error"]["code"] == "RuntimeError"
    assert data["error"]["message"] == "not found"
    assert data["error"]["details"]["where"] == "backend"


def test_compose_style_preset_returns_next_action() -> None:
    """compose 成功時回傳 generation payload 與呼叫 generate_image 的 next 指示"""
    mock_client = MagicMock()
    loras = [{"name": "ordered.safetensors", "strength_model": 0.8}]
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": "portrait",
        "generation": {
            "checkpoint": "model.safetensors",
            "loras": loras,
            "prompt": "creator_a_style, upper body, a girl in a raincoat",
            "steps": 32,
        },
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = compose_style_preset(
            "creator-a", content_prompt="a girl in a raincoat", profile="portrait"
        )

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "compose_style_preset"
    assert data["preset_id"] == "creator-a"
    assert data["profile"] == "portrait"
    assert data["generation"]["prompt"].startswith("creator_a_style")
    assert data["generation"]["loras"] == loras
    assert "generate_image" in data["next"]
    mock_client.post.assert_called_once_with(
        "style-presets/creator-a/compose",
        json={"content_prompt": "a girl in a raincoat", "profile": "portrait"},
    )


def test_compose_style_preset_forwards_overrides() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": None,
        "generation": {"prompt": "x", "seed": 123},
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        compose_style_preset(
            "creator-a", content_prompt="a girl", overrides={"seed": 123}
        )

    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["overrides"] == {"seed": 123}
    assert "profile" not in call_json


def test_compose_style_preset_backend_error_returns_structured_json() -> None:
    mock_client = MagicMock()
    mock_client.post.side_effect = RuntimeError("unknown profile")

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = compose_style_preset("creator-a", content_prompt="a girl", profile="bad")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "compose_style_preset"
    assert data["preset_id"] == "creator-a"
    assert data["error"]["code"] == "RuntimeError"
    assert data["error"]["message"] == "unknown profile"
    assert data["error"]["details"]["where"] == "backend"
