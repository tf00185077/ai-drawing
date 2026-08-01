from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.comfyui import ComfyUIError
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


def test_digest_reuses_cache_until_file_changes(tmp_path, monkeypatch) -> None:
    nvidia_worker._digest_cache.clear()
    model = tmp_path / "big.safetensors"
    model.write_bytes(b"seven!!")  # 7 bytes

    reads = {"n": 0}
    real = nvidia_worker._read_and_hash

    def counting(path):
        reads["n"] += 1
        return real(path)

    monkeypatch.setattr(nvidia_worker, "_read_and_hash", counting)

    first = nvidia_worker._digest(model)
    second = nvidia_worker._digest(model)
    assert first == second
    assert reads["n"] == 1, "unchanged file must not be re-hashed on every call"

    # Different size invalidates the cache.
    model.write_bytes(b"different-bytes")
    third = nvidia_worker._digest(model)
    assert third != first
    assert reads["n"] == 2

    # Same size but newer mtime invalidates the cache.
    model.write_bytes(b"same-length-xyz")  # same 15 bytes as previous write
    stat = model.stat()
    os.utime(model, (stat.st_atime, stat.st_mtime + 100))
    nvidia_worker._digest(model)
    assert reads["n"] == 3


def test_worker_submit_prompt_surfaces_node_errors(monkeypatch) -> None:
    client = nvidia_worker.NvidiaWorkerClient("http://worker", "tok", 5.0)
    monkeypatch.setattr(client, "_preflight", lambda prompt: None)
    monkeypatch.setattr(client, "_synchronize", lambda prompt: None)

    response = MagicMock()
    response.is_success = False
    response.status_code = 400
    response.text = ""
    response.json.return_value = {
        "error": "invalid prompt",
        "node_errors": {"6": "checkpoint not found"},
    }
    instance = MagicMock()
    instance.request.return_value = response
    fake = MagicMock()
    fake.__enter__.return_value = instance
    fake.__exit__.return_value = None
    monkeypatch.setattr(nvidia_worker.httpx, "Client", lambda *a, **k: fake)

    with pytest.raises(ComfyUIError) as exc:
        client.submit_prompt(
            {"6": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        )

    assert exc.value.args[0] == "invalid prompt"
    assert exc.value.node_errors == {"6": "checkpoint not found"}


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
