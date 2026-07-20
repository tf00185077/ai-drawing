from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import launcher.cli as cli
from launcher.cli import DefaultServices, main
from launcher.comfyui import ComfyInstallError, ComfyValidation
from launcher.models import (
    ComfyMode,
    DeviceMode,
    HostInfo,
    LauncherState,
    ProcessIdentity,
)


def state(
    mode=ComfyMode.DISABLED,
    *,
    root=None,
    device=None,
    pid=None,
    identity=None,
    port=8188,
):
    return LauncherState(1, mode, root, device, port, pid, identity)


class Harness:
    def __init__(self, tmp_path):
        self.project_root = tmp_path
        self.answers = []
        self.choices = []
        self.loaded_state = None
        self.saved_state = None
        self.saved_settings = None
        self.events = []
        self.output = []
        self.discovered = ()
        self.external_running = False
        self.install_error = None
        self.detected_device = DeviceMode.CPU
        self.compose_was_running = False
        self.backend_ready = True
        self.frontend_ready = True
        self.config_snapshot = {"old": True}

    def emit(self, message):
        self.output.append(message)

    def preflight(self):
        self.events.append("preflight")

    def load_state(self):
        self.events.append("load_state")
        return self.loaded_state

    def ask(self, _message, default=False):
        self.events.append("ask")
        if not self.answers:
            return default
        return self.answers.pop(0)

    def choose(self, _message, options, default=None):
        self.events.append("choose")
        if self.choices:
            return self.choices.pop(0)
        return default or options[0]

    def detect_device(self):
        self.events.append("detect_device")
        return self.detected_device

    def discover_comfyui(self, _candidates):
        self.events.append("discover")
        return self.discovered

    def probe_external(self, _port):
        self.events.append("probe_external")
        return self.external_running

    def default_comfyui_root(self):
        return self.project_root / "ComfyUI"

    def install_comfyui(self, root, device):
        self.events.append(("install", device))
        if self.install_error:
            error = self.install_error
            self.install_error = None
            raise error
        python = Path(root) / ".venv/bin/python"
        return ComfyValidation(Path(root), True, python, ())

    def start_comfyui(self, planned):
        self.events.append("start_comfyui")
        return replace(planned, managed_pid=4242)

    def stop_comfyui(self, current):
        self.events.append("stop_comfyui")
        return replace(current, managed_pid=None, managed_identity=None)

    def select_ports(self, backend_port, frontend_port):
        self.events.append("ports")
        return backend_port, frontend_port

    def mount_probes(self, settings):
        self.events.append("mount_probes")

    def snapshot_configuration(self):
        self.events.append("snapshot_config")
        return self.config_snapshot

    def restore_configuration(self, snapshot):
        assert snapshot is self.config_snapshot
        self.events.append("restore_config")

    def write_configuration(self, settings, new_state):
        self.events.append("write_config")
        self.saved_settings = settings
        self.saved_state = new_state

    def validate_current_compose(self):
        self.events.append("validate_compose")

    def compose_running(self):
        return self.compose_was_running

    def compose_up(self):
        self.events.append("compose_up")

    def compose_down(self):
        self.events.append("compose_down")

    def wait_backend(self, _port):
        self.events.append("wait_backend")
        return self.backend_ready

    def wait_frontend(self, _port):
        self.events.append("wait_frontend")
        return self.frontend_ready

    def save_state(self, new_state):
        self.events.append("save_state")
        self.saved_state = new_state

    def status(self, current):
        self.events.append("status")
        return {"application": "running", "comfy_mode": current.comfy_mode.value if current else "missing"}

    def compose_logs(self):
        self.events.append("logs")

    def update_comfyui(self, current):
        self.events.append("update_comfyui")


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def test_first_run_can_decline_comfyui(harness):
    harness.answers = [False]
    assert main(["setup"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED
    assert "compose_up" in harness.events


def test_selected_alternate_ports_are_written_to_staged_settings(harness):
    harness.select_ports = lambda _backend, _frontend: (8101, 5273)
    assert main(["setup", "--comfyui-mode", "disabled"], services=harness) == 0
    assert harness.saved_settings.backend_port == 8101
    assert harness.saved_settings.frontend_port == 5273


def test_discovered_controllable_instance_can_be_managed(harness):
    root = harness.project_root / "Existing ComfyUI"
    harness.discovered = (ComfyValidation(root, True, root / ".venv/bin/python", ()),)
    harness.answers = [True, True]
    assert main(["setup"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.MANAGED
    assert harness.saved_state.comfyui_root == root
    assert "start_comfyui" in harness.events


def test_external_running_instance_is_never_claimed_or_stopped(harness):
    harness.external_running = True
    harness.answers = [True]
    assert main(["setup"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.EXTERNAL
    assert "start_comfyui" not in harness.events
    assert "stop_comfyui" not in harness.events


def test_explicit_external_must_be_reachable_before_configuration(harness):
    assert main(["setup", "--comfyui-mode", "external"], services=harness) == 1
    assert "COMFYUI_UNREACHABLE" in "\n".join(harness.output)
    assert "write_config" not in harness.events


def test_install_failure_can_explicitly_fallback_to_cpu(harness):
    harness.detected_device = DeviceMode.NVIDIA
    harness.install_error = ComfyInstallError("cuda smoke failed: TOPSECRET")
    harness.answers = [True, True]
    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert ("install", DeviceMode.NVIDIA) in harness.events
    assert ("install", DeviceMode.CPU) in harness.events
    assert "TOPSECRET" not in "\n".join(harness.output)


def test_install_failure_can_continue_disabled(harness):
    harness.install_error = ComfyInstallError("failed")
    harness.answers = [True]
    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED


def test_noninteractive_setup_requires_explicit_comfyui_decision(harness):
    assert main(["setup", "--non-interactive"], services=harness) == 2
    rendered = "\n".join(harness.output)
    assert "MISSING_DECISION" in rendered
    assert "--comfyui-mode" in rendered
    assert "ask" not in harness.events


def test_noninteractive_managed_requires_path_or_install_target(harness):
    assert (
        main(
            ["setup", "--non-interactive", "--comfyui-mode", "managed"],
            services=harness,
        )
        == 2
    )
    assert "MISSING_COMFYUI_PATH" in "\n".join(harness.output)


def test_valid_state_makes_default_command_start(harness):
    harness.loaded_state = state()
    assert main([], services=harness) == 0
    assert "compose_up" in harness.events
    assert "write_config" not in harness.events


def test_setup_rolls_back_compose_config_and_new_managed_process(harness):
    harness.answers = [True]
    harness.frontend_ready = False
    assert (
        main(
            [
                "setup",
                "--comfyui-mode",
                "managed",
                "--comfyui-path",
                str(harness.project_root / "ComfyUI"),
            ],
            services=harness,
        )
        == 1
    )
    assert harness.events[-3:] == ["compose_down", "restore_config", "stop_comfyui"]


def test_failed_reconfigure_restores_previously_running_compose(harness):
    harness.loaded_state = state()
    harness.compose_was_running = True
    harness.backend_ready = False
    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 1
    rollback = harness.events[harness.events.index("compose_down") :]
    assert rollback == ["compose_down", "restore_config", "compose_up"]


def test_failed_start_restores_state_after_starting_new_managed_process(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    harness.frontend_ready = False
    assert main(["start"], services=harness) == 1
    assert "save_state" in harness.events
    assert harness.events[-3:] == ["compose_down", "restore_config", "stop_comfyui"]


def test_rollback_continues_cleanup_when_config_restore_fails(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    harness.frontend_ready = False

    def failed_restore(_snapshot):
        harness.events.append("restore_config_failed")
        raise OSError("restore failed")

    harness.restore_configuration = failed_restore
    assert main(["start"], services=harness) == 1
    assert "stop_comfyui" in harness.events


@pytest.mark.parametrize(
    ("command", "event"),
    [
        ("status", "status"),
        ("logs", "logs"),
        ("update-comfyui", "update_comfyui"),
    ],
)
def test_information_and_update_commands(harness, command, event):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    assert main([command], services=harness) == 0
    assert event in harness.events


def test_stop_only_stops_managed_process(harness):
    harness.loaded_state = state(ComfyMode.EXTERNAL)
    assert main(["stop"], services=harness) == 0
    assert "compose_down" in harness.events
    assert "stop_comfyui" not in harness.events


def test_dry_run_does_not_write_start_or_stop(harness):
    assert main(["dry-run", "--comfyui-mode", "disabled"], services=harness) == 0
    assert not {"write_config", "compose_up", "compose_down", "start_comfyui"}.intersection(
        harness.events
    )


def test_error_output_is_structured_and_does_not_leak_exception(harness):
    def explode():
        raise RuntimeError("PASSWORD=hunter2")

    harness.preflight = explode
    assert main(["status"], services=harness) == 1
    rendered = "\n".join(harness.output)
    assert "UNEXPECTED_ERROR" in rendered
    assert "PASSWORD" not in rendered
    assert "hunter2" not in rendered


def test_invalid_port_is_a_structured_cli_error(harness):
    assert main(["setup", "--comfyui-mode", "disabled", "--backend-port", "70000"], services=harness) == 2
    assert "CLI_ARGUMENT_INVALID" in "\n".join(harness.output)


def test_stale_managed_pid_with_external_api_is_not_claimed(tmp_path, monkeypatch):
    class Runner:
        def run(self, *_args, **_kwargs):
            raise AssertionError("start must not run commands for an external API")

    service = DefaultServices(tmp_path, runner=Runner(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.probe_external = lambda _port: True
    recorded = ProcessIdentity("/old/python", "1", "python main.py")
    unrelated = ProcessIdentity("/other/python", "2", "other server")
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: unrelated)

    result = service.start_comfyui(
        state(
            ComfyMode.MANAGED,
            root=tmp_path / "ComfyUI",
            device=DeviceMode.CPU,
            pid=4242,
            identity=recorded,
        )
    )

    assert result.comfy_mode is ComfyMode.EXTERNAL
    assert result.managed_pid is None
    assert result.managed_identity is None


def test_known_managed_process_not_ready_is_not_started_twice(tmp_path, monkeypatch):
    class Runner:
        def run(self, *_args, **_kwargs):
            raise AssertionError("a known live managed process must not be duplicated")

    service = DefaultServices(tmp_path, runner=Runner(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.probe_external = lambda _port: False
    recorded = ProcessIdentity("/managed/python", "1", "python main.py")
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: recorded)

    with pytest.raises(cli.LauncherError) as raised:
        service.start_comfyui(
            state(
                ComfyMode.MANAGED,
                root=tmp_path / "ComfyUI",
                device=DeviceMode.CPU,
                pid=4242,
                identity=recorded,
            )
        )

    assert raised.value.code == "COMFYUI_MANAGED_NOT_READY"
