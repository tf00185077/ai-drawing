from __future__ import annotations

from pathlib import Path
from typing import Protocol


MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pth")


class ResourceSettings(Protocol):
    comfyui_checkpoints_dir: str
    comfyui_loras_dir: str
    lora_default_checkpoint: str


def list_model_files(
    dir_path: Path,
    exts: tuple[str, ...] = MODEL_EXTENSIONS,
) -> list[str]:
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    return sorted(
        p.name
        for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )


def list_checkpoints(settings: ResourceSettings) -> list[str]:
    return list_model_files(Path(settings.comfyui_checkpoints_dir))


def list_loras(settings: ResourceSettings) -> list[str]:
    return list_model_files(Path(settings.comfyui_loras_dir))


def first_available_checkpoint(settings: ResourceSettings) -> str | None:
    checkpoints = list_checkpoints(settings)
    return checkpoints[0] if checkpoints else None


def default_checkpoint(settings: ResourceSettings) -> str | None:
    return first_available_checkpoint(settings) or settings.lora_default_checkpoint or None
