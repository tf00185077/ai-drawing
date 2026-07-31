from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.civitai_easy import GenerateLikeRequest
from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
from app.schemas.gallery import RerunRequest
from app.schemas.generate import GenerateWanKeyframesVideoRequest
from app.schemas.lora_train import LoraSmokeTestRequest
from app.schemas.style_preset_workflows import TestStylePresetWorkflowRequest
from app.services import nvidia_worker


@pytest.mark.parametrize(
    "model, payload",
    [
        (GenerateLikeRequest, {"locator": 1}),
        (RerunRequest, {}),
        (TestStylePresetWorkflowRequest, {}),
        (LoraSmokeTestRequest, {}),
        (GenerateWanKeyframesVideoRequest, {"images": ["a.png", "b.png"], "prompt": "x"}),
    ],
)
def test_product_generation_contracts_default_local_and_accept_worker(model, payload) -> None:
    assert model.model_validate(payload).execution_target == "local"
    assert model.model_validate({**payload, "execution_target": "worker"}).execution_target == "worker"
    with pytest.raises(Exception):
        model.model_validate({**payload, "execution_target": "auto"})


def test_strict_civitai_generation_contracts_expose_execution_target() -> None:
    assert "execution_target" in CivitaiRecipeVariantGenerateRequest.model_fields
    assert "execution_target" in CivitaiRecipeVariationSetCreateRequest.model_fields


def _resource_settings(root: Path):
    for name in ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras", "controlnet", "upscale_models", "clip_vision", "audio", "models"):
        (root / name).mkdir(exist_ok=True)
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(root / "checkpoints"),
        comfyui_diffusion_models_dir=str(root / "diffusion_models"),
        comfyui_text_encoders_dir=str(root / "text_encoders"),
        comfyui_vae_dir=str(root / "vae"),
        comfyui_loras_dir=str(root / "loras"),
        comfyui_controlnet_dir=str(root / "controlnet"),
        comfyui_upscale_models_dir=str(root / "upscale_models"),
        comfyui_clip_vision_dir=str(root / "clip_vision"),
        comfyui_audio_models_dir=str(root / "audio"),
        comfyui_models_dir=str(root / "models"),
    )


def test_resource_manifest_covers_dualclip_clipvision_and_gguf(tmp_path, monkeypatch) -> None:
    settings = _resource_settings(tmp_path)
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)
    files = {
        "text_encoders": ["clip_l.safetensors", "t5xxl.safetensors"],
        "clip_vision": ["clip_vision_h.safetensors"],
        "diffusion_models": ["wan.gguf", "qwen.gguf"],
    }
    for kind, names in files.items():
        for name in names:
            (tmp_path / kind / name).write_bytes(name.encode())
    workflow = {
        "1": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": files["text_encoders"][0], "clip_name2": files["text_encoders"][1]}},
        "2": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": files["clip_vision"][0]}},
        "3": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": files["diffusion_models"][0]}},
        "4": {"class_type": "GGUFLoaderKJ", "inputs": {"model_name": files["diffusion_models"][1], "extra_model_name": "none"}},
    }
    assert {(item.kind, item.name) for item in nvidia_worker.workflow_resources(workflow)} == {
        (kind, name) for kind, names in files.items() for name in names
    }


def test_worker_manifest_is_pinned_and_distribution_matches_source() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    manifest = json.loads((source / "worker-manifest.json").read_text())
    assert manifest["cache_gb"] == 100
    assert manifest["minimum_free_gb"] == 20
    assert manifest["custom_nodes"]
    assert all(item.get("repository") and item.get("revision") for item in manifest["custom_nodes"])
    dist = repo / "dist" / "AI-Drawing-NVIDIA-Worker"
    for name in ("worker.py", "worker-manifest.json", "Install-Worker.ps1", "Start-Worker.ps1", "requirements.txt", "README.md"):
        assert (dist / name).read_bytes() == (source / name).read_bytes()
