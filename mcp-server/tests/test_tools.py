"""MCP Tools 單元測試"""
import json
from unittest.mock import MagicMock, patch

from mcp_server.tools.comfyui import free_comfyui_memory
from mcp_server.tools.generate import (
    generate_image,
    generate_image_custom_workflow,
    generate_image_from_description,
    generate_queue_status,
    get_generation_status,
    get_workflow_template,
    list_available_resources,
    list_workflow_templates,
    suggest_workflow_from_description,
)
from mcp_server.tools.gallery import gallery_list, gallery_rerun, get_gallery_image
from mcp_server.tools.lora_train import lora_train_start, lora_train_status


def test_list_resources_returns_agent_friendly_json() -> None:
    """list_resources 回傳 agent 可解析的 JSON 資源清單"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "checkpoints": ["novaAnimeXL_ilV190.safetensors", "v1-5-pruned-emaonly.ckpt"],
        "loras": [],
        "workflows": ["default", "default_lora"],
    }

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = list_available_resources()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "list_available_resources"
    assert data["backend_base_url"] == "http://127.0.0.1:8001"
    assert data["checkpoints"] == ["novaAnimeXL_ilV190.safetensors", "v1-5-pruned-emaonly.ckpt"]
    assert data["loras"] == []
    assert data["workflows"] == ["default", "default_lora"]
    assert "generate_image" in data["next"]
    mock_client.get.assert_called_once_with("generate/available-resources")


def test_list_resources_empty_checkpoints_tells_agent_not_to_submit() -> None:
    """list_resources 在 checkpoints 空時仍可解析，但 next 必須提醒不可提交生圖"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"checkpoints": [], "loras": [], "workflows": ["default"]}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = list_available_resources()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["checkpoints"] == []
    assert "no checkpoints" in data["next"].lower()
    assert "do not call generate_image" in data["next"].lower()


def test_list_resources_backend_error_returns_structured_error() -> None:
    """list_resources backend 失敗時回傳 ok=false 的穩定 JSON"""
    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("backend down")

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = list_available_resources()

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "list_available_resources"
    assert data["where"] == "backend"
    assert "backend down" in data["error"]


def test_generate_image_returns_agent_friendly_json() -> None:
    """generate_image 成功時回傳 agent 可解析的 JSON job 結果"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc-123", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image(prompt="1girl, solo")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "generate_image"
    assert data["job_id"] == "abc-123"
    assert data["status"] == "queued"
    assert data["submitted"]["prompt"] == "1girl, solo"
    assert data["submitted"]["batch_size"] == 1
    assert "get_generation_status" in data["next"]
    mock_client.post.assert_called_once_with(
        "generate/",
        json={"prompt": "1girl, solo", "batch_size": 1},
    )


def test_generate_image_with_optional_params_returns_submitted_payload() -> None:
    """generate_image 可傳入完整參數並在 submitted 中回傳"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "x", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image(
            prompt="test",
            checkpoint="model.safetensors",
            lora="style.safetensors",
            negative_prompt="bad",
            steps=25,
            cfg=6.5,
            width=512,
            height=768,
            batch_size=1,
            sampler_name="euler",
            scheduler="normal",
        )

    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["prompt"] == "test"
    assert call_json["checkpoint"] == "model.safetensors"
    assert call_json["lora"] == "style.safetensors"
    assert call_json["negative_prompt"] == "bad"
    assert call_json["steps"] == 25
    assert call_json["cfg"] == 6.5
    assert call_json["width"] == 512
    assert call_json["height"] == 768
    assert call_json["batch_size"] == 1
    assert call_json["sampler_name"] == "euler"
    assert call_json["scheduler"] == "normal"

    data = json.loads(result)
    assert data["ok"] is True
    assert data["submitted"] == call_json


def test_generate_image_backend_error_returns_structured_json() -> None:
    """generate_image backend 失敗時回傳 ok=false 的穩定 JSON"""
    mock_client = MagicMock()
    mock_client.post.side_effect = RuntimeError("queue full")

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image(prompt="test")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "generate_image"
    assert data["where"] == "backend"
    assert "queue full" in data["error"]


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


def test_generate_image_from_description_parses_and_submits() -> None:
    """generate_image_from_description 解析描述後取模板提交"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"4": {"class_type": "CheckpointLoaderSimple"}}
    mock_client.post.return_value = {"job_id": "xyz", "status": "queued"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image_from_description("初音 動漫 1024")

    assert "xyz" in result
    assert "初音" in result
    mock_client.get.assert_called_once_with("generate/workflow-templates/default")
    assert mock_client.post.call_count == 1
    assert mock_client.post.call_args[0][0] == "generate/custom"


def test_suggest_workflow_from_description_returns_parse_result() -> None:
    """suggest_workflow_from_description 僅回傳解析結果"""
    result = suggest_workflow_from_description("初音 動漫")
    assert "初音" in result
    assert "動漫" in result
    assert "template" in result


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


def test_generate_image_custom_workflow_with_image_pose() -> None:
    """generate_image_custom_workflow 傳入 image_pose 時會帶入 body"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "xyz", "status": "queued"}
    wf_json = '{"5":{"class_type":"LoadImage","inputs":{"image":"pose.png"}}}'

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image_custom_workflow(
            workflow=wf_json,
            prompt="1girl",
            image_pose="2026-03-08/ComfyUI_01305__318631e3_0.png",
        )

    assert "xyz" in result
    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["image_pose"] == "2026-03-08/ComfyUI_01305__318631e3_0.png"


def test_generate_image_custom_workflow_forwards_new_params_when_provided() -> None:
    """generate_image_custom_workflow 傳入 image/mask/batch_size/diffusion_model/text_encoder/vae 時會帶入 body"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc", "status": "queued"}
    wf_json = '{"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"x.safetensors"}}}'

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = generate_image_custom_workflow(
            workflow=wf_json,
            prompt="1girl",
            image="2026-03-08/subject.png",
            mask="2026-03-08/mask.png",
            batch_size=4,
            diffusion_model="anima_unet.safetensors",
            text_encoder="anima_clip.safetensors",
            vae="anima_vae.safetensors",
        )

    assert "abc" in result
    call_json = mock_client.post.call_args[1]["json"]
    assert call_json["image"] == "2026-03-08/subject.png"
    assert call_json["mask"] == "2026-03-08/mask.png"
    assert call_json["batch_size"] == 4
    assert call_json["diffusion_model"] == "anima_unet.safetensors"
    assert call_json["text_encoder"] == "anima_clip.safetensors"
    assert call_json["vae"] == "anima_vae.safetensors"


def test_generate_image_custom_workflow_omits_new_params_when_not_provided() -> None:
    """generate_image_custom_workflow 未提供 image/mask/batch_size/diffusion_model/text_encoder/vae 時不放入 body"""
    mock_client = MagicMock()
    mock_client.post.return_value = {"job_id": "abc", "status": "queued"}
    wf_json = '{"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"x.safetensors"}}}'

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        generate_image_custom_workflow(workflow=wf_json, prompt="1girl")

    call_json = mock_client.post.call_args[1]["json"]
    for key in ("image", "mask", "batch_size", "diffusion_model", "text_encoder", "vae"):
        assert key not in call_json


def test_get_generation_status_queued_returns_agent_friendly_json() -> None:
    """get_generation_status queued 時回傳含 next 的穩定 JSON"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"status": "queued", "job_id": "job-q1", "prompt_id": None}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_generation_status("job-q1")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "get_generation_status"
    assert data["job_id"] == "job-q1"
    assert data["status"] == "queued"
    assert "again" in data["next"]
    mock_client.get.assert_called_once_with("generate/job/job-q1")


def test_get_generation_status_running_includes_prompt_id() -> None:
    """get_generation_status running 時包含 prompt_id"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "status": "running",
        "job_id": "job-r1",
        "prompt_id": "comfy-abc",
    }

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_generation_status("job-r1")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["status"] == "running"
    assert data["prompt_id"] == "comfy-abc"


def test_get_generation_status_completed_includes_image_info() -> None:
    """get_generation_status completed 時包含 image_id 與 image_path"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "status": "completed",
        "job_id": "job-c1",
        "image_id": 7,
        "image_path": "2026-06-11/ComfyUI_00007__job_0.png",
    }

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_generation_status("job-c1")

    data = json.loads(result)
    assert data["ok"] is True
    assert data["status"] == "completed"
    assert data["image_id"] == 7
    assert data["image_path"] == "2026-06-11/ComfyUI_00007__job_0.png"
    assert "get_gallery_image" in data["next"]
    assert "free_comfyui_memory" in data["next"]


def test_get_generation_status_not_found_returns_ok_false() -> None:
    """get_generation_status job 不存在時回傳 ok=false"""
    mock_client = MagicMock()
    mock_client.get.return_value = {"status": "not_found"}

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_generation_status("job-missing")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "get_generation_status"
    assert data["where"] == "backend"
    assert data["job_id"] == "job-missing"
    assert "not_found" in data["error"]


def test_get_generation_status_backend_error_returns_structured_json() -> None:
    """get_generation_status backend 失敗時回傳 ok=false 的穩定 JSON"""
    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("connection refused")

    with patch("mcp_server.tools.generate._get_client", return_value=mock_client):
        result = get_generation_status("job-err2")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "get_generation_status"
    assert data["where"] == "backend"
    assert data["job_id"] == "job-err2"
    assert "connection refused" in data["error"]


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


def test_get_gallery_image_returns_agent_friendly_json() -> None:
    """get_gallery_image 成功時回傳含 image_url、local_path 與 metadata 的 JSON"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "id": 1,
        "image_path": "2026-06-11/ComfyUI_00007__27920202_0.png",
        "image_url": "http://127.0.0.1:8001/gallery/2026-06-11/ComfyUI_00007__27920202_0.png",
        "checkpoint": "novaAnimeXL_ilV190.safetensors",
        "lora": None,
        "seed": 338566325,
        "steps": 8,
        "cfg": 6.0,
        "prompt": "1girl, solo",
        "negative_prompt": "lowres",
        "created_at": "2026-06-11T10:00:00",
    }

    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        result = get_gallery_image(1)

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "get_gallery_image"
    assert data["image_id"] == 1
    assert data["image_path"] == "2026-06-11/ComfyUI_00007__27920202_0.png"
    assert data["image_url"] == "http://127.0.0.1:8001/gallery/2026-06-11/ComfyUI_00007__27920202_0.png"
    assert "local_path" in data
    assert data["metadata"]["checkpoint"] == "novaAnimeXL_ilV190.safetensors"
    assert data["metadata"]["seed"] == 338566325
    assert data["metadata"]["prompt"] == "1girl, solo"
    assert "free_comfyui_memory" in data["next"]
    mock_client.get.assert_called_once_with("gallery/1")


def test_get_gallery_image_constructs_url_when_backend_omits_it() -> None:
    """get_gallery_image 在 backend 未回傳 image_url 時，應自行組出 URL"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "id": 2,
        "image_path": "2026-06-12/ComfyUI_00010__abc_0.png",
        "checkpoint": "model.safetensors",
    }

    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        result = get_gallery_image(2)

    data = json.loads(result)
    assert data["ok"] is True
    assert "2026-06-12/ComfyUI_00010__abc_0.png" in data["image_url"]
    assert data["image_url"].startswith("http://")


def test_get_gallery_image_local_path_uses_gallery_dir() -> None:
    """get_gallery_image local_path 應以 MCP_GALLERY_DIR 為根目錄拼接"""
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "id": 3,
        "image_path": "2026-06-12/ComfyUI_00011__xyz_0.png",
    }

    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        result = get_gallery_image(3)

    data = json.loads(result)
    assert data["ok"] is True
    assert "2026-06-12/ComfyUI_00011__xyz_0.png" in data["local_path"]
    # local_path 應包含 gallery_dir 的根目錄
    assert data["local_path"] != data["image_path"]


def test_get_gallery_image_backend_error_returns_structured_json() -> None:
    """get_gallery_image backend 失敗時回傳 ok=false 的穩定 JSON"""
    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("not found")

    with patch("mcp_server.tools.gallery._get_client", return_value=mock_client):
        result = get_gallery_image(999)

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "get_gallery_image"
    assert data["where"] == "backend"
    assert "not found" in data["error"]


def test_free_comfyui_memory_success_returns_agent_friendly_json() -> None:
    """free_comfyui_memory 成功時回傳含 ok/comfyui_base_url/next 的 JSON"""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("mcp_server.tools.comfyui.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        result = free_comfyui_memory()

    data = json.loads(result)
    assert data["ok"] is True
    assert data["tool"] == "free_comfyui_memory"
    assert "comfyui_base_url" in data
    assert data["unload_models"] is True
    assert data["free_memory"] is True
    assert "complete" in data["next"]
    mock_client_cls.return_value.__enter__.return_value.post.assert_called_once()
    call_args = mock_client_cls.return_value.__enter__.return_value.post.call_args
    assert call_args[1]["json"] == {"unload_models": True, "free_memory": True}
    assert "/free" in call_args[0][0]


def test_free_comfyui_memory_empty_response_body_treated_as_success() -> None:
    """free_comfyui_memory ComfyUI 回應空 body 時仍視為成功"""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b""

    with patch("mcp_server.tools.comfyui.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        result = free_comfyui_memory()

    data = json.loads(result)
    assert data["ok"] is True


def test_free_comfyui_memory_connection_error_returns_structured_json() -> None:
    """free_comfyui_memory 連線失敗時回傳 ok=false 的穩定 JSON"""
    with patch("mcp_server.tools.comfyui.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = (
            Exception("connection refused")
        )
        result = free_comfyui_memory()

    data = json.loads(result)
    assert data["ok"] is False
    assert data["tool"] == "free_comfyui_memory"
    assert data["where"] == "comfyui"
    assert "connection refused" in data["error"]
