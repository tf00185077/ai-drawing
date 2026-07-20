from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app import config as config_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DB_URL = f"sqlite:///{(PROJECT_ROOT / 'backend' / 'auto_draw.db').resolve()}"
EXPECTED_OUTPUT_DIR = str((PROJECT_ROOT / 'backend' / 'outputs').resolve())
EXPECTED_GALLERY_DIR = str((PROJECT_ROOT / 'backend' / 'outputs' / 'gallery').resolve())
EXPECTED_LORA_TRAIN_DIR = str((PROJECT_ROOT / 'backend' / 'lora_train').resolve())
EXPECTED_LORA_TRAIN_LOGS_DIR = str((PROJECT_ROOT / 'backend' / 'lora_train' / 'logs').resolve())
EXPECTED_SD_SCRIPTS_DIR = str((PROJECT_ROOT / 'sd-scripts').resolve())
EXPECTED_WATCH_DIRS = str((PROJECT_ROOT / 'backend' / 'lora_train').resolve())


def _load_settings_from_cwd(monkeypatch, cwd: Path):
    monkeypatch.chdir(cwd)
    config_module.get_settings.cache_clear()
    settings = config_module.Settings(_env_file=None)
    config_module.get_settings.cache_clear()
    return settings


def test_relative_defaults_are_project_root_based_from_any_cwd(monkeypatch):
    for env_name in [
        'DATABASE_URL',
        'OUTPUT_DIR',
        'GALLERY_DIR',
        'LORA_TRAIN_DIR',
        'LORA_TRAIN_LOGS_DIR',
        'SD_SCRIPTS_PATH',
        'WATCH_DIRS',
        'COMFYUI_LORA_DIR',
    ]:
        monkeypatch.delenv(env_name, raising=False)
        monkeypatch.delenv(env_name.lower(), raising=False)

    root_settings = _load_settings_from_cwd(monkeypatch, PROJECT_ROOT)
    backend_settings = _load_settings_from_cwd(monkeypatch, PROJECT_ROOT / 'backend')

    assert root_settings.database_url == EXPECTED_DB_URL
    assert backend_settings.database_url == EXPECTED_DB_URL
    assert root_settings.output_dir == EXPECTED_OUTPUT_DIR
    assert backend_settings.output_dir == EXPECTED_OUTPUT_DIR
    assert root_settings.gallery_dir == EXPECTED_GALLERY_DIR
    assert backend_settings.gallery_dir == EXPECTED_GALLERY_DIR
    assert root_settings.lora_train_dir == EXPECTED_LORA_TRAIN_DIR
    assert backend_settings.lora_train_dir == EXPECTED_LORA_TRAIN_DIR
    assert root_settings.lora_train_logs_dir == EXPECTED_LORA_TRAIN_LOGS_DIR
    assert backend_settings.lora_train_logs_dir == EXPECTED_LORA_TRAIN_LOGS_DIR
    assert root_settings.comfyui_lora_dir == root_settings.comfyui_loras_dir.split(',')[0]
    assert root_settings.sd_scripts_path == EXPECTED_SD_SCRIPTS_DIR
    assert backend_settings.sd_scripts_path == EXPECTED_SD_SCRIPTS_DIR
    assert root_settings.watch_dirs == EXPECTED_WATCH_DIRS
    assert backend_settings.watch_dirs == EXPECTED_WATCH_DIRS


def test_relative_env_overrides_are_normalized_from_project_root(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///./tmp/test.db')
    monkeypatch.setenv('OUTPUT_DIR', './var/outputs')
    monkeypatch.setenv('GALLERY_DIR', './var/gallery')
    monkeypatch.setenv('LORA_TRAIN_DIR', './var/lora_train')
    monkeypatch.setenv('LORA_TRAIN_LOGS_DIR', './var/lora_logs')
    monkeypatch.setenv('SD_SCRIPTS_PATH', './vendor/sd-scripts')
    monkeypatch.setenv('WATCH_DIRS', './watch/a, ./watch/b')
    monkeypatch.setenv('COMFYUI_LORA_DIR', './var/comfyui/loras')

    settings = _load_settings_from_cwd(monkeypatch, PROJECT_ROOT / 'backend')

    assert settings.database_url == f"sqlite:///{(PROJECT_ROOT / 'tmp' / 'test.db').resolve()}"
    assert settings.output_dir == str((PROJECT_ROOT / 'var' / 'outputs').resolve())
    assert settings.gallery_dir == str((PROJECT_ROOT / 'var' / 'gallery').resolve())
    assert settings.lora_train_dir == str((PROJECT_ROOT / 'var' / 'lora_train').resolve())
    assert settings.lora_train_logs_dir == str((PROJECT_ROOT / 'var' / 'lora_logs').resolve())
    assert settings.comfyui_lora_dir == str((PROJECT_ROOT / 'var' / 'comfyui' / 'loras').resolve())
    assert settings.sd_scripts_path == str((PROJECT_ROOT / 'vendor' / 'sd-scripts').resolve())
    assert settings.watch_dirs == ','.join(
        [
            str((PROJECT_ROOT / 'watch' / 'a').resolve()),
            str((PROJECT_ROOT / 'watch' / 'b').resolve()),
        ]
    )


def test_prompt_library_dir_is_project_root_relative(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_LIBRARY_DIR", "prompt_library-test")
    settings = config_module.Settings()
    assert Path(settings.prompt_library_dir).is_absolute()
    assert Path(settings.prompt_library_dir).name == "prompt_library-test"


@pytest.mark.parametrize("timeout", ["0", "-0.1"])
def test_prompt_library_lock_timeout_must_be_positive(monkeypatch, timeout: str) -> None:
    monkeypatch.setenv("PROMPT_LIBRARY_LOCK_TIMEOUT", timeout)
    with pytest.raises(ValidationError, match="greater than 0"):
        config_module.Settings()


def test_comfyui_mode_defaults_to_external_for_local_development(monkeypatch) -> None:
    monkeypatch.delenv("COMFYUI_MODE", raising=False)
    settings = config_module.Settings(_env_file=None)

    assert settings.comfyui_mode == "external"


@pytest.mark.parametrize("mode", ["disabled", "external", "managed"])
def test_comfyui_mode_accepts_supported_values(mode: str) -> None:
    settings = config_module.Settings(_env_file=None, comfyui_mode=mode)

    assert settings.comfyui_mode == mode


def test_comfyui_mode_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError, match="literal_error"):
        config_module.Settings(_env_file=None, comfyui_mode="automatic")
