from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import nvidia_worker


def _settings(root):
    empty = root / "empty"
    empty.mkdir(exist_ok=True)
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(root / "checkpoints"),
        comfyui_diffusion_models_dir=str(root / "diffusion_models"),
        comfyui_text_encoders_dir=str(root / "text_encoders"),
        comfyui_vae_dir=str(root / "vae"),
        comfyui_loras_dir=str(root / "loras"),
        comfyui_controlnet_dir=str(empty),
        comfyui_upscale_models_dir=str(empty),
    )


def test_workflow_resources_resolves_and_hashes_known_loaders(
    tmp_path, monkeypatch
) -> None:
    for folder in ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras"):
        (tmp_path / folder).mkdir()
    model = tmp_path / "diffusion_models" / "anima.safetensors"
    lora = tmp_path / "loras" / "style.safetensors"
    model.write_bytes(b"anima")
    lora.write_bytes(b"lora")
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: _settings(tmp_path))
    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": model.name}},
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"lora_name": lora.name},
        },
    }

    resources = nvidia_worker.workflow_resources(workflow)

    assert [(item.kind, item.name, item.size) for item in resources] == [
        ("diffusion_models", model.name, 5),
        ("loras", lora.name, 4),
    ]
    assert all(len(item.sha256) == 64 for item in resources)


def test_workflow_resources_rejects_traversal(tmp_path, monkeypatch) -> None:
    for folder in ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras"):
        (tmp_path / folder).mkdir()
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: _settings(tmp_path))

    with pytest.raises(nvidia_worker.WorkerConfigurationError, match="unsafe"):
        nvidia_worker.workflow_resources(
            {
                "1": {
                    "class_type": "UNETLoader",
                    "inputs": {"unet_name": "../escape.safetensors"},
                }
            }
        )
