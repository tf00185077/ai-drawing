from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
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


@pytest.mark.skipif(os.name != "nt", reason="Windows Worker launcher requires Windows process semantics")
def test_installed_worker_launcher_redirects_comfyui_output_to_rotated_logs(tmp_path) -> None:
    """Catch a regression to an attached ComfyUI console whose output can block Python."""
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    root = tmp_path / "AI-Drawing-Worker"
    (root / "config").mkdir(parents=True)
    comfy_root = root / "runtime" / "ComfyUI"
    comfy_root.mkdir(parents=True)
    logs = root / "runtime" / "logs"
    logs.mkdir()

    for name in ("Start-Worker.ps1", "Start-Worker.cmd"):
        shutil.copy2(source / name, root / name)
    start_script = root / "Start-Worker.ps1"
    start_script.write_text(
        start_script.read_text(encoding="utf-8").replace(
            '$Root = "C:\\AI-Drawing-Worker"',
            f'$Root = "{root}"',
        ),
        encoding="utf-8",
    )
    (root / "config" / "python-path.txt").write_text(sys.executable, encoding="utf-8")
    (logs / "comfyui.stdout.log").write_text("old stdout\n", encoding="utf-8")
    (logs / "comfyui.stderr.log").write_text("old stderr\n", encoding="utf-8")
    (comfy_root / "main.py").write_text(
        """import os
import sys
import threading
import time
from pathlib import Path

Path(__file__).with_name(\"fixture.pid\").write_text(str(os.getpid()))
def write_output():
    while True:
        print(\"comfy stdout fixture\", flush=True)
        print(\"comfy stderr fixture\", file=sys.stderr, flush=True)
        time.sleep(0.1)
threading.Thread(target=write_output, daemon=True).start()
while True:
    time.sleep(1)
""",
        encoding="utf-8",
    )

    launcher = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(start_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    fixture_pid_path = comfy_root / "fixture.pid"
    stdout_log = logs / "comfyui.stdout.log"
    stderr_log = logs / "comfyui.stderr.log"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not fixture_pid_path.exists():
            time.sleep(0.1)
        assert fixture_pid_path.exists(), "ComfyUI fixture was not launched"

        while time.monotonic() < deadline:
            if (
                (logs / "comfyui.stdout.previous.log").exists()
                and (logs / "comfyui.stderr.previous.log").exists()
                and "comfy stdout fixture" in stdout_log.read_bytes().decode("utf-8", errors="replace")
                and "comfy stderr fixture" in stderr_log.read_bytes().decode("utf-8", errors="replace")
            ):
                break
            time.sleep(0.1)

        assert (logs / "comfyui.stdout.previous.log").read_text(encoding="utf-8") == "old stdout\n"
        assert (logs / "comfyui.stderr.previous.log").read_text(encoding="utf-8") == "old stderr\n"
        assert "comfy stdout fixture" in stdout_log.read_bytes().decode("utf-8", errors="replace")
        assert "comfy stderr fixture" in stderr_log.read_bytes().decode("utf-8", errors="replace")
    finally:
        launcher.terminate()
        try:
            launcher.wait(timeout=5)
        except subprocess.TimeoutExpired:
            launcher.kill()
            launcher.wait(timeout=5)
        if fixture_pid_path.exists():
            subprocess.run(
                ["taskkill.exe", "/PID", fixture_pid_path.read_text(encoding="utf-8").strip(), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
