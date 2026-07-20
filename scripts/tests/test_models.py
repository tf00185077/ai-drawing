import json
from pathlib import Path

import pytest

from launcher.cli import main
from launcher.models import ComfyMode, DeviceMode, LauncherCommand, LauncherState
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
    state = LauncherState(
        schema_version=1,
        comfy_mode=ComfyMode.MANAGED,
        comfyui_root=tmp_path / "Comfy UI",
        device=DeviceMode.MPS,
        comfyui_port=8188,
        managed_pid=42,
        managed_identity="python main.py --port 8188",
    )

    assert LauncherState.from_json(state.to_json()) == state
    assert "authorization" not in state.to_json().lower()


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


def test_cli_accepts_each_stable_command():
    for command in LauncherCommand:
        assert main([command.value]) == 0


def test_subprocess_runner_uses_argument_list_without_shell(tmp_path):
    result = SubprocessRunner().run(
        ["python", "-c", "print('ready')"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ready"
    assert result.stderr == ""
    assert isinstance(result.args, tuple)
