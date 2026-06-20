"""Style preset catalog MCP tools 單元測試"""
import json
from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.generate import generate_image
from mcp_server.tools.style_presets import (
    compose_style_preset,
    create_style_preset,
    get_style_preset,
    list_style_presets,
    reindex_style_presets,
    validate_style_presets,
)


def test_create_style_preset_forwards_and_reports() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"id": "cx", "created": True, "validation": {"valid": True, "missing": []}}
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = json.loads(create_style_preset("cx", "Name", checkpoint="m.safetensors"))
    assert result["ok"] is True and result["created"] is True
    body = mock_client.post.call_args[1]["json"]
    assert body["id"] == "cx" and body["name"] == "Name" and body["checkpoint"] == "m.safetensors"


def test_create_style_preset_duplicate_409() -> None:
    mock_client = MagicMock()
    resp = httpx.Response(409, request=httpx.Request("POST", "http://x/style-presets/"))
    mock_client.post.side_effect = httpx.HTTPStatusError("409", request=resp.request, response=resp)
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = json.loads(create_style_preset("dup", "Y"))
    assert result["ok"] is False and result["error"] == "already_exists"


def test_reindex_style_presets_rebuilds() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"presets": [{"id": "creator-a", "name": "x", "profiles": []}]}
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = json.loads(reindex_style_presets())
    assert result["ok"] is True
    assert result["count"] == 1
    mock_client.post.assert_called_once_with("style-presets/reindex")


def test_list_style_presets_returns_agent_friendly_json() -> None:
    """list_style_presets 回傳 agent 可解析 JSON，含 presets 與 next"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "items": [{"id": "creator-a", "name": "Creator A", "profiles": ["portrait"]}]
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = list_style_presets()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "list_style_presets"
    assert data["presets"][0]["id"] == "creator-a"
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
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "id": "creator-a",
        "name": "Creator A",
        "checkpoint": "model.safetensors",
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = get_style_preset("creator-a")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "get_style_preset"
    assert data["preset"]["checkpoint"] == "model.safetensors"
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
    assert data["where"] == "backend"
    assert data["preset_id"] == "nope"
    assert "not found" in data["error"]


def test_validate_style_presets_returns_repairable_diagnostics() -> None:
    """invalid preset 以資料形式回傳，不是 tool failure"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "items": [
            {
                "preset_id": "creator-a",
                "valid": False,
                "checked": {"checkpoint": "model.safetensors"},
                "missing": [{"resource_type": "checkpoint", "name": "model.safetensors"}],
            },
            {"preset_id": "anima-b", "valid": True, "checked": {}, "missing": []},
        ]
    }

    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = validate_style_presets()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "validate_style_presets"
    assert data["invalid_presets"] == ["creator-a"]
    assert data["results"][0]["missing"][0]["resource_type"] == "checkpoint"
    assert "creator-a" in data["next"]
    mock_client.get.assert_called_once_with("style-presets/validate")


def test_compose_style_preset_returns_next_action() -> None:
    """compose 成功時回傳 generation payload 與呼叫 generate_image 的 next 指示"""
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": "portrait",
        "generation": {
            "checkpoint": "model.safetensors",
            "lora": "creator-a.safetensors",
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
    assert data["where"] == "backend"
    assert data["preset_id"] == "creator-a"
    assert "unknown profile" in data["error"]


def test_generate_image_forwards_composed_diffusion_fields() -> None:
    """composed generation payload 的 diffusion 元件欄位可透過 generate_image 轉送"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image(
            prompt="anima_style, a girl",
            template="anima",
            diffusion_model="anima_unet.safetensors",
            text_encoder="anima_clip.safetensors",
            vae="anima_vae.safetensors",
        )

    data = json.loads(result)
    assert data["ok"] is True
    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["template"] == "anima"
    assert call_json["diffusion_model"] == "anima_unet.safetensors"
    assert call_json["text_encoder"] == "anima_clip.safetensors"
    assert call_json["vae"] == "anima_vae.safetensors"


def test_generate_image_omits_diffusion_fields_when_absent() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image(prompt="1girl")

    call_json = mock_client.post.call_args[1]["json"]
    for key in ("diffusion_model", "text_encoder", "vae"):
        assert key not in call_json
