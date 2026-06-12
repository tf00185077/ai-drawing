"""批次生圖排程器單元測試"""
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

    def submit_prompt(self, prompt):
        self.submitted_prompt = prompt
        return "prompt-123"


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
