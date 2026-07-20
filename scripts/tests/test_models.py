import json

import pytest

from launcher.cli import build_parser
from launcher.models import (
    ComfyMode,
    DeviceMode,
    LauncherCommand,
    LauncherState,
    ProcessIdentity,
)
from launcher.runner import SubprocessRunner


def test_commands_are_stable():
    assert {item.value for item in LauncherCommand} == {
        "setup",
        "start",
        "stop",
        "status",
        "reconfigure",
        "logs",
        "update-comfyui",
    }


def test_state_round_trip(tmp_path):
    identity = ProcessIdentity(
        executable=str(tmp_path / "Comfy UI/.venv/bin/python"),
        started_at="123456",
        command_line="python main.py --port 8188",
    )
    state = LauncherState(
        schema_version=1,
        comfy_mode=ComfyMode.MANAGED,
        comfyui_root=tmp_path / "Comfy UI",
        device=DeviceMode.MPS,
        comfyui_port=8188,
        managed_pid=42,
        managed_identity=identity,
        launcher_installed=True,
        installed_root=tmp_path / "Comfy UI",
        installed_commit="v0.28.0",
    )

    assert LauncherState.from_json(state.to_json()) == state
    assert "authorization" not in state.to_json().lower()
    assert LauncherState.from_json(state.to_json()).launcher_installed is True


def test_legacy_state_defaults_to_user_owned_installation():
    legacy = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": "C:/User/ComfyUI",
        "device": "cpu",
        "comfyui_port": 8188,
        "managed_pid": None,
        "managed_identity": None,
    }

    loaded = LauncherState.from_json(json.dumps(legacy))

    assert loaded.launcher_installed is False
    assert loaded.installed_root is None
    assert loaded.installed_commit is None


def test_forged_install_provenance_with_mismatched_root_is_degraded(tmp_path):
    payload = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": str(tmp_path / "user-owned"),
        "device": "cpu",
        "comfyui_port": 8188,
        "managed_pid": None,
        "managed_identity": None,
        "launcher_installed": True,
        "installed_root": str(tmp_path / "launcher-owned"),
        "installed_commit": "v0.28.0",
    }

    loaded = LauncherState.from_json(json.dumps(payload))
    assert loaded.launcher_installed is False
    assert loaded.installed_root is None
    assert loaded.installed_commit is None


def test_managed_state_without_root_degrades_to_safe_disabled_state():
    payload = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": None,
        "device": "cpu",
        "comfyui_port": 8188,
        "managed_pid": 42,
        "managed_identity": {
            "executable": "python",
            "started_at": "123",
            "command_line": "python main.py --port 8188",
        },
        "launcher_installed": True,
        "installed_root": "C:/forged/ComfyUI",
        "installed_commit": "v0.28.0",
    }

    loaded = LauncherState.from_json(json.dumps(payload))
    assert loaded.comfy_mode is ComfyMode.DISABLED
    assert loaded.comfyui_root is None
    assert loaded.device is None
    assert loaded.managed_pid is None
    assert loaded.managed_identity is None
    assert loaded.launcher_installed is False


def test_legacy_command_line_only_identity_loads_as_unowned():
    state = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": "C:/Comfy UI",
        "device": "cpu",
        "comfyui_port": 8188,
        "managed_pid": 42,
        "managed_identity": "python main.py --port 8188",
    }

    loaded = LauncherState.from_json(json.dumps(state))

    assert loaded.managed_pid == 42
    assert loaded.managed_identity is None


def test_incomplete_structured_identity_loads_as_unowned():
    state = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": "C:/Comfy UI",
        "device": "cpu",
        "comfyui_port": 8188,
        "managed_pid": 42,
        "managed_identity": {
            "executable": "python",
            "command_line": "python main.py",
        },
    }

    assert LauncherState.from_json(json.dumps(state)).managed_identity is None


def test_state_rejects_unknown_schema_version():
    with pytest.raises(ValueError, match="schema"):
        LauncherState.from_json(json.dumps({"schema_version": 999}))


@pytest.mark.parametrize("managed_pid", [True, "42; Remove-Item C:\\", 0, -1])
def test_state_rejects_invalid_managed_pid(managed_pid):
    state = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": "C:/Comfy UI",
        "device": "nvidia",
        "comfyui_port": 8188,
        "managed_pid": managed_pid,
        "managed_identity": "python main.py --port 8188",
    }

    with pytest.raises(ValueError, match="managed_pid"):
        LauncherState.from_json(json.dumps(state))


@pytest.mark.parametrize("comfyui_port", [True, "8188", 0, -1, 65536])
def test_state_rejects_invalid_comfyui_port(comfyui_port):
    state = {
        "schema_version": 1,
        "comfy_mode": "managed",
        "comfyui_root": "C:/Comfy UI",
        "device": "nvidia",
        "comfyui_port": comfyui_port,
        "managed_pid": None,
        "managed_identity": None,
    }

    with pytest.raises(ValueError, match="comfyui_port"):
        LauncherState.from_json(json.dumps(state))


def test_cli_accepts_each_stable_command():
    for command in LauncherCommand:
        assert build_parser().parse_args([command.value]).command == command.value


def test_subprocess_runner_uses_argument_list_without_shell(tmp_path):
    result = SubprocessRunner().run(
        ["python", "-c", "print('ready')"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ready"
    assert result.stderr == ""
    assert isinstance(result.args, tuple)
