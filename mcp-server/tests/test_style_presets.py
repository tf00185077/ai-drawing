"""Style preset catalog MCP tools 單元測試"""
import json
from unittest.mock import MagicMock, patch

import httpx

from mcp_server.tools.style_presets import (
    compose_style_preset,
    create_style_preset,
    get_style_preset,
    list_style_presets,
    save_successful_workflow_as_style_preset,
    test_saved_style_preset_workflow as queue_saved_style_preset_workflow,
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


def test_create_style_preset_forwards_and_reports() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"id": "cx", "created": True, "validation": {"valid": True, "missing": []}}
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = json.loads(create_style_preset("cx", "Name", checkpoint="m.safetensors"))
    assert result["ok"] is True and result["created"] is True
    body = mock_client.post.call_args[1]["json"]
    assert body["id"] == "cx" and body["name"] == "Name" and body["checkpoint"] == "m.safetensors"


def test_create_style_preset_forwards_loras() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {"id": "mlx", "created": True, "validation": {"valid": True, "missing": []}}
    loras = [{"name": "a.safetensors", "strength_model": 0.8}, {"name": "b.safetensors", "strength_model": 0.5}]
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        create_style_preset("mlx", "ML", template="multi", loras=loras)
    assert mock_client.post.call_args[1]["json"]["loras"] == loras


def test_create_style_preset_duplicate_409() -> None:
    mock_client = MagicMock()
    resp = httpx.Response(409, request=httpx.Request("POST", "http://x/style-presets/"))
    mock_client.post.side_effect = httpx.HTTPStatusError("409", request=resp.request, response=resp)
    with patch("mcp_server.tools.style_presets._get_client", return_value=mock_client):
        result = json.loads(create_style_preset("dup", "Y"))
    assert result["ok"] is False
    assert result["error"]["code"] == "already_exists"


def test_save_successful_workflow_forwards_loose_inputs_without_graph() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": "portrait",
        "source": {"type": "artifact", "id": "44"},
        "workflow_path": (
            "style_presets/agent/workflows/creator-a/portrait.api.json"
        ),
        "prompt_keywords": ["ink wash", "soft light"],
        "negative_prompt_keywords": ["watermark"],
        "retest_required": True,
    }

    with patch(
        "mcp_server.tools.style_presets._get_client",
        return_value=mock_client,
    ):
        result = save_successful_workflow_as_style_preset(
            source="artifact:44",
            preset_id="creator-a",
            profile="portrait",
            prompt_keywords="ink wash,\nsoft light",
            negative_prompt_keywords=["watermark", ""],
        )

    data = json.loads(result)
    assert data == {
        "ok": True,
        "tool": "save_successful_workflow_as_style_preset",
        "preset_id": "creator-a",
        "profile": "portrait",
        "source": {"type": "artifact", "id": "44"},
        "workflow_path": (
            "style_presets/agent/workflows/creator-a/portrait.api.json"
        ),
        "prompt_keywords": ["ink wash", "soft light"],
        "negative_prompt_keywords": ["watermark"],
        "retest_required": True,
        "next": (
            "call test_saved_style_preset_workflow for this preset/profile"
        ),
    }
    mock_client.post.assert_called_once_with(
        "style-presets/creator-a/workflow/save",
        json={
            "source": "artifact:44",
            "profile": "portrait",
            "prompt_keywords": "ink wash,\nsoft light",
            "negative_prompt_keywords": ["watermark", ""],
        },
    )
    assert "workflow_json" not in result
    assert "full prompt" not in result


def test_save_successful_workflow_forwards_numeric_source_and_omits_profile() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": None,
        "source": {"type": "image", "id": "7"},
        "workflow_path": (
            "style_presets/agent/workflows/creator-a/__base__.api.json"
        ),
        "prompt_keywords": ["line art"],
        "negative_prompt_keywords": [],
        "retest_required": True,
    }

    with patch(
        "mcp_server.tools.style_presets._get_client",
        return_value=mock_client,
    ):
        save_successful_workflow_as_style_preset(
            source=7,
            preset_id="creator-a",
            prompt_keywords=["line art"],
            negative_prompt_keywords="",
        )

    assert mock_client.post.call_args.kwargs["json"] == {
        "source": 7,
        "prompt_keywords": ["line art"],
        "negative_prompt_keywords": "",
    }


def test_save_successful_workflow_returns_backend_repair_hint() -> None:
    mock_client = MagicMock()
    request = httpx.Request(
        "POST",
        "http://x/style-presets/creator-a/workflow/save",
    )
    response = httpx.Response(
        404,
        request=request,
        json={
            "detail": {
                "code": "source_not_found",
                "message": "Gallery image 404 was not found.",
                "hint": "Use an id returned by get_gallery_image.",
            }
        },
    )
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "404", request=request, response=response
    )

    with patch(
        "mcp_server.tools.style_presets._get_client",
        return_value=mock_client,
    ):
        result = save_successful_workflow_as_style_preset(
            source=404,
            preset_id="creator-a",
            prompt_keywords="line art",
            negative_prompt_keywords="",
        )

    data = json.loads(result)
    assert data == {
        "ok": False,
        "tool": "save_successful_workflow_as_style_preset",
        "error": {
            "code": "source_not_found",
            "message": "Gallery image 404 was not found.",
            "hint": "Use an id returned by get_gallery_image.",
        },
    }


def test_saved_workflow_retest_returns_job_and_polling_instruction() -> None:
    mock_client = MagicMock()
    mock_client.post.return_value = {
        "preset_id": "creator-a",
        "profile": "portrait",
        "job_id": "job-saved-1",
        "status": "queued",
    }

    with patch(
        "mcp_server.tools.style_presets._get_client",
        return_value=mock_client,
    ):
        result = queue_saved_style_preset_workflow(
            "creator-a", profile="portrait"
        )

    data = json.loads(result)
    assert data == {
        "ok": True,
        "tool": "test_saved_style_preset_workflow",
        "preset_id": "creator-a",
        "profile": "portrait",
        "job_id": "job-saved-1",
        "status": "queued",
        "next": "poll get_generation_status with job_id job-saved-1",
    }
    mock_client.post.assert_called_once_with(
        "style-presets/creator-a/workflow/test",
        json={"profile": "portrait"},
    )


def test_saved_workflow_retest_error_is_stable() -> None:
    mock_client = MagicMock()
    request = httpx.Request(
        "POST",
        "http://x/style-presets/creator-a/workflow/test",
    )
    response = httpx.Response(
        404,
        request=request,
        json={
            "detail": {
                "code": "saved_workflow_not_found",
                "message": "No saved workflow exists.",
                "hint": "Explicitly save a successful workflow first.",
            }
        },
    )
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "404", request=request, response=response
    )

    with patch(
        "mcp_server.tools.style_presets._get_client",
        return_value=mock_client,
    ):
        result = queue_saved_style_preset_workflow("creator-a")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "test_saved_style_preset_workflow"
    assert data["error"] == {
        "code": "saved_workflow_not_found",
        "message": "No saved workflow exists.",
        "hint": "Explicitly save a successful workflow first.",
    }
