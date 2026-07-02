from pathlib import Path

from app.core import resources


class Settings:
    lora_default_checkpoint = "fallback.safetensors"

    def __init__(self, checkpoints: str, loras: str = "") -> None:
        self.comfyui_checkpoints_dir = checkpoints
        self.comfyui_loras_dir = loras
        self.comfyui_diffusion_models_dir = ""
        self.comfyui_text_encoders_dir = ""
        self.comfyui_vae_dir = ""


def test_list_model_files_in_comma_separated_dirs_dedupes(tmp_path: Path) -> None:
    local = tmp_path / "local"
    external = tmp_path / "external"
    local.mkdir()
    external.mkdir()
    (local / "a.safetensors").write_text("local")
    (local / "same.safetensors").write_text("local")
    (external / "b.ckpt").write_text("external")
    (external / "same.safetensors").write_text("external")
    (external / "ignore.txt").write_text("nope")

    settings = Settings(f"{local},{external}")

    assert resources.list_checkpoints(settings) == [
        "a.safetensors",
        "b.ckpt",
        "same.safetensors",
    ]


def test_missing_paths_in_comma_separated_dirs_are_ignored(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "model.pth").write_text("model")

    settings = Settings(f"{tmp_path / 'missing'}, {existing}")

    assert resources.list_checkpoints(settings) == ["model.pth"]
