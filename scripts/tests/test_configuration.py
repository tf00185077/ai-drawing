import json
from pathlib import Path

import pytest

import launcher.configuration as configuration
from launcher.configuration import (
    ConfigurationError,
    atomic_write,
    load_state,
    parse_env,
    redact,
    render_compose_override,
    render_env,
    write_configuration,
)
from launcher.models import ComfyPaths, DeviceMode, LauncherState, LocalSettings


def state_for(root: Path) -> LauncherState:
    return LauncherState(
        schema_version=1,
        comfy_mode=LocalSettings.connected(ComfyPaths.from_root(root)).comfy_mode,
        comfyui_root=root,
        device=DeviceMode.CPU,
        comfyui_port=8188,
        managed_pid=None,
        managed_identity=None,
    )


def test_connected_env_uses_only_container_model_paths(tmp_path):
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))

    rendered = render_env(settings)

    assert "COMFYUI_BASE_URL=http://host.docker.internal:8188" in rendered
    assert "COMFYUI_CHECKPOINTS_DIR=/comfyui/models/checkpoints" in rendered
    assert "DATABASE_URL=sqlite:////data/database/auto_draw.db" in rendered
    assert str(tmp_path) not in rendered


def test_disabled_override_is_empty():
    assert render_compose_override(LocalSettings.disabled()) == "services: {}\n"


def test_override_json_quotes_windows_paths_with_spaces_and_non_ascii():
    root = Path("C:/AI 模型/Comfy UI")
    settings = LocalSettings.connected(ComfyPaths.from_root(root))

    rendered = render_compose_override(settings)

    assert f"source: {json.dumps(str(root / 'models' / 'checkpoints'))}" in rendered
    assert "target: /comfyui/models/checkpoints" in rendered
    assert "type: bind" in rendered


def test_failed_validation_keeps_previous_config(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OLD=1\n", encoding="utf-8")
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))
    state = state_for(tmp_path / "Comfy UI")

    with pytest.raises(ConfigurationError):
        write_configuration(tmp_path, settings, state, validate=lambda *_: False)

    assert env_path.read_text(encoding="utf-8") == "OLD=1\n"


def test_write_configuration_preserves_existing_civitai_authorization(tmp_path):
    (tmp_path / ".env").write_text(
        "CIVITAI_AUTHORIZATION=Bearer private-value\nUNRELATED=discard-me\n",
        encoding="utf-8",
    )
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))

    write_configuration(tmp_path, settings, state_for(tmp_path / "Comfy UI"), validate=lambda *_: True)

    rendered = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "CIVITAI_AUTHORIZATION=Bearer private-value" in rendered
    assert "UNRELATED=discard-me" not in rendered


def test_replacement_failure_restores_all_previous_files(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    override_path = tmp_path / ".ai-drawing" / "compose.local.yaml"
    state_path = tmp_path / "data" / "bootstrap" / "state.json"
    previous = {
        env_path: "OLD_ENV=1\n",
        override_path: "services: {old: true}\n",
        state_path: "{\"old\": true}\n",
    }
    for path, content in previous.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    original_replace = Path.replace
    failed = False

    def fail_override_once(path, target):
        nonlocal failed
        if Path(target) == override_path and not failed:
            failed = True
            raise OSError("injected replacement failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_override_once)
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))

    with pytest.raises(ConfigurationError, match="unable to write"):
        write_configuration(tmp_path, settings, state_for(tmp_path / "Comfy UI"), lambda *_: True)

    assert {path: path.read_text(encoding="utf-8") for path in previous} == previous
    assert not list(tmp_path.rglob("*.tmp"))


def test_replacement_failure_removes_files_that_were_initially_absent(tmp_path, monkeypatch):
    state_path = tmp_path / "data" / "bootstrap" / "state.json"
    original_replace = Path.replace
    failed = False

    def fail_state_once(path, target):
        nonlocal failed
        if Path(target) == state_path and not failed:
            failed = True
            raise OSError("injected replacement failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_state_once)
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))

    with pytest.raises(ConfigurationError, match="unable to write"):
        write_configuration(tmp_path, settings, state_for(tmp_path / "Comfy UI"), lambda *_: True)

    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".ai-drawing" / "compose.local.yaml").exists()
    assert not state_path.exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_staging_creation_failure_cleans_earlier_secret_bearing_temp(tmp_path, monkeypatch):
    original_temporary_path = configuration._temporary_path
    calls = 0

    def fail_second_staging(path, content):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected staging failure")
        return original_temporary_path(path, content)

    monkeypatch.setattr(configuration, "_temporary_path", fail_second_staging)
    (tmp_path / ".env").write_text(
        "CIVITAI_AUTHORIZATION=Bearer private-value\n", encoding="utf-8"
    )
    settings = LocalSettings.connected(ComfyPaths.from_root(tmp_path / "Comfy UI"))

    with pytest.raises(ConfigurationError, match="unable to write"):
        write_configuration(tmp_path, settings, state_for(tmp_path / "Comfy UI"), lambda *_: True)

    assert not list(tmp_path.rglob("*.tmp"))


def test_atomic_write_removes_temp_after_replace_failure(tmp_path, monkeypatch):
    destination = tmp_path / ".env"

    def fail_replace(path, target):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replacement failure"):
        atomic_write(destination, "CIVITAI_AUTHORIZATION=Bearer private-value\n")

    assert not list(tmp_path.glob("*.tmp"))


def test_load_state_rejects_unknown_schema(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="schema"):
        load_state(path)


def test_load_state_wraps_malformed_current_schema(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="invalid launcher state"):
        load_state(path)


def test_parse_env_ignores_comments_and_export_prefix():
    assert parse_env("# comment\nexport ONE=1\nTWO=two=2\n") == {
        "ONE": "1",
        "TWO": "two=2",
    }


def test_redact_recursively_hides_sensitive_values():
    value = {
        "authorization": "Bearer private",
        "nested": [{"api_token": "token-value"}],
        "secret_value": "secret-value",
        "password": "password-value",
        "safe": "visible",
    }

    assert redact(value) == {
        "authorization": "[REDACTED]",
        "nested": [{"api_token": "[REDACTED]"}],
        "secret_value": "[REDACTED]",
        "password": "[REDACTED]",
        "safe": "visible",
    }


def test_example_and_gitignore_use_safe_runtime_defaults(project_root):
    example = (project_root / ".env.example").read_text(encoding="utf-8")
    ignored = (project_root / ".gitignore").read_text(encoding="utf-8")

    assert "COMFYUI_MODE=disabled" in example
    assert "DATABASE_URL=sqlite:////data/database/auto_draw.db" in example
    assert "COMFYUI_CHECKPOINTS_DIR=/comfyui/models/checkpoints" in example
    assert "MCP_BACKEND_API_URL=http://127.0.0.1:8001" in example
    assert "BACKEND_PORT=8001" in example
    assert "FRONTEND_PORT=5173" in example
    assert "# CIVITAI_AUTHORIZATION=YOUR_CIVITAI_API_KEY" in example
    assert ".ai-drawing/" in ignored
    assert "data/" in ignored
