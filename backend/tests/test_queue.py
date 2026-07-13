"""批次生圖排程器單元測試"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.queue import (
    QueueFullError,
    _process_pending,
    _reset_for_test,
    get_job_status,
    get_status,
    submit,
    submit_custom,
)
from app.core.style_presets import _parse_preset, compose_preset


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def setup_function() -> None:
    """每個測試前清空佇列"""
    _reset_for_test()


def test_submit_returns_job_id() -> None:
    """submit 回傳有效的 job_id"""
    job_id = submit({"prompt": "1girl"})
    assert isinstance(job_id, str)
    assert len(job_id) == 36


def test_submit_raises_when_full() -> None:
    """佇列已滿時 submit 拋出 QueueFullError"""
    with patch("app.core.queue.MAX_PENDING", 2):
        submit({"prompt": "a"})
        submit({"prompt": "b"})
        with pytest.raises(QueueFullError):
            submit({"prompt": "c"})


def test_get_status_empty_initially() -> None:
    """初始狀態下 get_status 回傳空佇列"""
    status = get_status()
    assert status["queue_running"] == []
    assert status["queue_pending"] == []


def test_get_status_after_submit() -> None:
    """submit 後 get_status 包含 pending 項目"""
    job_id = submit({"prompt": "test"})
    status = get_status()
    assert len(status["queue_pending"]) == 1
    assert status["queue_pending"][0]["job_id"] == job_id
    assert status["queue_pending"][0]["status"] == "queued"
    assert "submitted_at" in status["queue_pending"][0]


def test_get_job_status_returns_none_for_unknown() -> None:
    """未知 job_id 時 get_job_status 回傳 None"""
    assert get_job_status("nonexistent-id") is None


def test_get_job_status_returns_pending_job() -> None:
    """get_job_status 可取得 pending 任務狀態"""
    job_id = submit({"prompt": "x"})
    job = get_job_status(job_id)
    assert job is not None
    assert job["job_id"] == job_id
    assert job["status"] == "queued"


def test_submit_custom_requires_workflow() -> None:
    """submit_custom 缺少 workflow 時拋出 ValueError"""
    with pytest.raises(ValueError, match="workflow"):
        submit_custom({"prompt": "test"})


def test_submit_custom_returns_job_id() -> None:
    """submit_custom 含 workflow 時回傳 job_id 並加入 pending"""
    min_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {"class_type": "KSampler", "inputs": {"positive": ["6", 0], "negative": ["7", 0]}},
    }
    job_id = submit_custom({"workflow": min_wf, "prompt": "1girl"})
    assert isinstance(job_id, str)
    assert len(job_id) == 36
    status = get_status()
    assert any(p["job_id"] == job_id for p in status["queue_pending"])


class _FakeComfy:
    def __init__(self) -> None:
        self.submitted_prompt = None
        self.uploaded_paths: list = []

    def submit_prompt(self, prompt):
        self.submitted_prompt = prompt
        return "prompt-123"

    def upload_image(self, path):
        self.uploaded_paths.append(path)
        return {"name": path.name, "subfolder": ""}


def _settings_for_checkpoint_dir(tmp_path):
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path),
        lora_default_checkpoint="",
        lora_sdxl=False,
        gallery_dir=str(tmp_path),
        controlnet_default_pose_image="",
    )


def test_process_pending_uses_first_available_resource_checkpoint_when_unspecified(tmp_path) -> None:
    """未指定 checkpoint 時，queue 使用 available-resources 同源掃描到的第一個 checkpoint。"""
    (tmp_path / "b_model.safetensors").write_text("", encoding="utf-8")
    (tmp_path / "a_model.safetensors").write_text("", encoding="utf-8")
    fake_comfy = _FakeComfy()
    submit({"prompt": "1girl"})

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["4"]["inputs"]["ckpt_name"] == "a_model.safetensors"


def test_process_pending_keeps_explicit_checkpoint_over_available_resources(tmp_path) -> None:
    """明確傳入 checkpoint 時，不被 available-resources 預設值覆蓋。"""
    (tmp_path / "a_model.safetensors").write_text("", encoding="utf-8")
    fake_comfy = _FakeComfy()
    submit({"prompt": "1girl", "checkpoint": "manual.safetensors"})

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["4"]["inputs"]["ckpt_name"] == "manual.safetensors"


def test_process_pending_template_path_defaults_steps_cfg_and_random_seed_when_omitted(tmp_path) -> None:
    """template 路徑省略 steps/cfg/seed 時，仍補上 20/7.0 並產生隨機 seed（回歸測試）"""
    (tmp_path / "a_model.safetensors").write_text("", encoding="utf-8")
    fake_comfy = _FakeComfy()
    job_id = submit({"prompt": "1girl"})

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["3"]["inputs"]["steps"] == 20
    assert fake_comfy.submitted_prompt["3"]["inputs"]["cfg"] == 7.0
    seed = fake_comfy.submitted_prompt["3"]["inputs"]["seed"]
    assert isinstance(seed, int)
    assert 0 <= seed <= 2**32 - 1
    job = get_job_status(job_id)
    assert job is not None
    assert job["status"] == "running"


def test_process_pending_custom_path_preserves_workflow_json_steps_cfg_when_omitted(tmp_path) -> None:
    """custom 路徑省略 steps/cfg 時，保留提交 workflow JSON 中的原值"""
    custom_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"steps": 30, "cfg": 5.5, "seed": 999, "positive": ["6", 0], "negative": ["7", 0]},
        },
    }
    fake_comfy = _FakeComfy()
    submit_custom({"workflow": custom_wf, "prompt": "1girl", "checkpoint": "x.safetensors"})

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["3"]["inputs"]["steps"] == 30
    assert fake_comfy.submitted_prompt["3"]["inputs"]["cfg"] == 5.5
    assert fake_comfy.submitted_prompt["3"]["inputs"]["seed"] == 999


def test_process_pending_custom_path_two_ksamplers_keep_independent_values(tmp_path) -> None:
    """custom 路徑下，兩個 KSampler（hires-fix）省略 steps/cfg 時各自保留原值"""
    custom_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"steps": 30, "cfg": 5.5, "seed": 1, "positive": ["6", 0], "negative": ["7", 0]},
        },
        "20": {
            "class_type": "KSampler",
            "inputs": {"steps": 12, "cfg": 9.0, "seed": 2, "positive": ["6", 0], "negative": ["7", 0]},
        },
    }
    fake_comfy = _FakeComfy()
    submit_custom({"workflow": custom_wf, "prompt": "1girl", "checkpoint": "x.safetensors"})

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["3"]["inputs"]["steps"] == 30
    assert fake_comfy.submitted_prompt["3"]["inputs"]["cfg"] == 5.5
    assert fake_comfy.submitted_prompt["20"]["inputs"]["steps"] == 12
    assert fake_comfy.submitted_prompt["20"]["inputs"]["cfg"] == 9.0


def test_process_pending_smoke_composed_multi_lora_preset_keeps_distinct_nodes(tmp_path) -> None:
    """compose preset payload -> queue processing keeps distinct LoRA nodes in submitted workflow."""
    preset_path = (
        PROJECT_ROOT
        / "style_presets"
        / "agent"
        / "presets"
        / "high-contrast-color-anima.json"
    )
    preset = _parse_preset(json.loads(preset_path.read_text(encoding="utf-8")))
    generation = compose_preset(
        preset,
        "Honoka Kousaka standing in a bright school courtyard",
        profile="anime-2d-default",
    ).generation
    fake_comfy = _FakeComfy()

    submit(generation)

    with patch("app.core.queue.get_settings", return_value=_settings_for_checkpoint_dir(tmp_path)):
        _process_pending(fake_comfy)

    prompt = fake_comfy.submitted_prompt
    assert prompt is not None
    expected_loras = generation["loras"]
    submitted_loras = [
        (
            node["inputs"]["lora_name"],
            node["inputs"]["strength_model"],
        )
        for node in prompt.values()
        if isinstance(node, dict)
        and node.get("class_type") in ("LoraLoader", "LoraLoaderModelOnly")
    ]
    assert submitted_loras == [
        (expected_loras[0]["name"], expected_loras[0]["strength_model"]),
        (expected_loras[1]["name"], expected_loras[1]["strength_model"]),
        (expected_loras[2]["name"], expected_loras[2]["strength_model"]),
    ]
    assert len({name for name, _strength in submitted_loras}) == 3


def test_process_pending_uploads_subject_image_and_mask(tmp_path) -> None:
    """queue 上傳 image 與 mask 至 ComfyUI，並將上傳後檔名注入對應節點"""
    gallery = tmp_path / "gallery"
    gallery.mkdir()
    (gallery / "subject.png").write_bytes(b"fake")
    (gallery / "mask.png").write_bytes(b"fake")
    custom_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 1, "positive": ["6", 0], "negative": ["7", 0]},
        },
        "10": {"class_type": "LoadImage", "inputs": {"image": "orig_subject.png"}},
        "11": {"class_type": "LoadImageMask", "inputs": {"image": "orig_mask.png"}},
    }
    fake_comfy = _FakeComfy()
    submit_custom({
        "workflow": custom_wf,
        "prompt": "1girl",
        "checkpoint": "x.safetensors",
        "image": "subject.png",
        "mask": "mask.png",
    })

    settings = SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path),
        lora_default_checkpoint="",
        lora_sdxl=False,
        gallery_dir=str(gallery),
        controlnet_default_pose_image="",
    )
    with patch("app.core.queue.get_settings", return_value=settings):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["10"]["inputs"]["image"] == "subject.png"
    assert fake_comfy.submitted_prompt["11"]["inputs"]["image"] == "mask.png"


def test_process_pending_rejects_gallery_escaping_mask_path(tmp_path) -> None:
    """mask 路徑逃出 gallery_dir 時被視為不存在，不注入 workflow"""
    gallery = tmp_path / "gallery"
    gallery.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"fake")
    custom_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 1, "positive": ["6", 0], "negative": ["7", 0]},
        },
        "11": {"class_type": "LoadImageMask", "inputs": {"image": "orig_mask.png"}},
    }
    fake_comfy = _FakeComfy()
    submit_custom({
        "workflow": custom_wf,
        "prompt": "1girl",
        "checkpoint": "x.safetensors",
        "mask": "../outside.png",
    })

    settings = SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path),
        lora_default_checkpoint="",
        lora_sdxl=False,
        gallery_dir=str(gallery),
        controlnet_default_pose_image="",
    )
    with patch("app.core.queue.get_settings", return_value=settings):
        _process_pending(fake_comfy)

    assert fake_comfy.submitted_prompt["11"]["inputs"]["image"] == "orig_mask.png"
    assert fake_comfy.uploaded_paths == []


def test_process_pending_rejects_gallery_escaping_video_ref_path(tmp_path) -> None:
    """video_ref 路徑逃出 gallery_dir 時任務失敗，且不提交至 ComfyUI。"""
    gallery = tmp_path / "gallery"
    gallery.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"fake")
    custom_wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": ""}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 1, "positive": ["6", 0], "negative": ["7", 0]},
        },
        "20": {"class_type": "LoadVideo", "inputs": {"video": "orig.mp4"}},
    }
    fake_comfy = _FakeComfy()
    job_id = submit_custom({
        "workflow": custom_wf,
        "prompt": "slow pan",
        "checkpoint": "x.safetensors",
        "video_ref": "../outside.mp4",
    })

    settings = SimpleNamespace(
        comfyui_checkpoints_dir=str(tmp_path),
        lora_default_checkpoint="",
        lora_sdxl=False,
        gallery_dir=str(gallery),
        controlnet_default_pose_image="",
    )
    with patch("app.core.queue.get_settings", return_value=settings):
        _process_pending(fake_comfy)

    status = get_job_status(job_id)
    assert status["status"] == "failed"
    assert "Unsafe gallery path" in status["error"]
    assert fake_comfy.submitted_prompt is None
