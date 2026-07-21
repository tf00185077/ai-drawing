from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import launcher.cli as cli
import launcher.comfyui as comfyui_module
from launcher.cli import DefaultServices, main
from launcher.comfyui import (
    ComfyInstallError,
    ComfyProbe,
    ComfyValidation,
    UnsupportedComfyArchitecture,
)
from launcher.models import (
    ComfyMode,
    DeviceMode,
    HostInfo,
    LauncherState,
    ProcessIdentity,
)
from launcher.processes import ProcessStartResult, ProcessStopResult
from launcher.relay import RelayStartResult, RelayState, RelayStopResult
from launcher.runner import CommandResult


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
        self.discovery_batches = []
        self.candidate_batches = []
        self.path_answers = []
        self.path_prompts = []
        self.external_running = False
        self.install_error = None
        self.installed_roots = []
        self.detected_device = DeviceMode.CPU
        self.compose_was_running = False
        self.compose_services = frozenset()
        self.backend_ready = True
        self.frontend_ready = True
        self.config_snapshot = {"old": True}
        self.relay_state = None
        self.relay_activation = None
        self.managed_verified = False
        self.preflight_error = None
        self.bootstrap_log_error = None

    def emit(self, message):
        self.output.append(message)

    def log_bootstrap(self, message):
        self.events.append(("bootstrap_log", message))
        if self.bootstrap_log_error is not None:
            raise self.bootstrap_log_error

    def preflight(self):
        self.events.append("preflight")
        if self.preflight_error is not None:
            raise self.preflight_error

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

    def discover_comfyui(self, candidates):
        self.events.append("discover")
        self.candidate_batches.append(tuple(candidates))
        if self.discovery_batches:
            return self.discovery_batches.pop(0)
        return self.discovered

    def candidate_roots(self, explicit=None, previous=None):
        values = (explicit, previous, self.default_comfyui_root())
        return tuple(dict.fromkeys(path.resolve() for path in values if path))

    def ask_path(self, message):
        self.events.append("ask_path")
        self.path_prompts.append(message)
        return self.path_answers.pop(0) if self.path_answers else None

    def probe_external(self, _port):
        self.events.append("probe_external")
        return self.external_running

    def managed_state_is_verified(self, _state):
        self.events.append("verify_managed")
        return self.managed_verified

    def default_comfyui_root(self):
        return self.project_root / "ComfyUI"

    def validate_install_target(self, _root):
        return Path(_root).resolve()

    def install_comfyui(self, root, device):
        self.events.append(("install", device))
        self.installed_roots.append(Path(root).resolve())
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
        cleared = replace(current, managed_pid=None, managed_identity=None)
        return ProcessStopResult(True, "stopped", cleared)

    def select_ports(self, backend_port, frontend_port):
        self.events.append("ports")
        return backend_port, frontend_port

    def select_ports_for_running(self, desired, _configured, _running_services):
        self.events.append("running_ports")
        return desired

    def load_ports(self):
        self.events.append("load_ports")
        return 8000, 5173

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

    def compose_running_services(self):
        return self.compose_services

    def compose_up_services(self, services):
        self.events.append(("compose_up_services", frozenset(services)))

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

    def ensure_relay(self, settings):
        self.events.append("ensure_relay")
        if self.relay_activation is not None:
            return self.relay_activation
        return RelayStartResult(
            self.relay_state is not None,
            "ready" if self.relay_state is not None else "not_required",
            self.relay_state,
        )

    def stop_relay(self, relay_state=None):
        self.events.append(("stop_relay", relay_state))
        return RelayStopResult(True, "stopped", None)

    def current_relay_state(self):
        self.events.append("current_relay_state")
        return self.relay_state

    def restore_relay(self, relay_state):
        self.events.append(("restore_relay", relay_state))

    def status(self, current, *, docker_available=True):
        self.events.append("status")
        return {
            "docker": "available" if docker_available else "unavailable",
            "services": {"backend": "running", "frontend": "running"},
            "backend": "reachable",
            "frontend": "reachable",
            "comfy": {
                "state": "connected" if current else "not_configured",
                "ownership": current.comfy_mode.value if current else "none",
                "model_count": 0,
                "device": current.device.value if current and current.device else None,
                "hint": "Add a model" if current else "Run reconfigure",
            },
            "relay": "not_required",
        }

    def compose_logs(self):
        self.events.append("logs")

    def update_comfyui(self, current):
        self.events.append("update_comfyui")


def test_default_services_passes_project_root_to_install_boundary(
    tmp_path,
    monkeypatch,
):
    project = tmp_path / "repository"
    project.mkdir()
    captured = {}

    def fake_install(target, device, runner, host, **kwargs):
        captured.update(kwargs)
        return ComfyValidation(Path(target), True, Path(target) / "python", ())

    monkeypatch.setattr(cli, "install_comfyui", fake_install)
    fake_uv = (tmp_path / "cache/uv.exe").resolve()
    monkeypatch.setattr(cli, "resolve_uv_binary", lambda: fake_uv)
    services = DefaultServices(project, runner=object(), output_fn=lambda _message: None)

    services.install_comfyui(tmp_path / "sibling", DeviceMode.CPU)

    assert captured["project_root"] == project.resolve()
    assert captured["uv_bin"] == fake_uv


def test_default_update_rejects_verified_live_managed_process_before_mutation(
    tmp_path,
    monkeypatch,
):
    root = (tmp_path / "ComfyUI").resolve()
    identity = ProcessIdentity(str(root / ".venv/bin/python"), "1", "python main.py")
    current = LauncherState(
        1,
        ComfyMode.MANAGED,
        root,
        DeviceMode.CPU,
        8188,
        4242,
        identity,
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.probe_external = lambda _port: True
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: identity)
    monkeypatch.setattr(
        cli,
        "resolve_uv_binary",
        lambda: (_ for _ in ()).throw(AssertionError("uv must not be resolved")),
    )
    monkeypatch.setattr(
        cli,
        "update_comfyui",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("update boundary must not run")
        ),
    )

    with pytest.raises(cli.LauncherError) as raised:
        service.update_comfyui(current)

    assert raised.value.code == "COMFYUI_UPDATE_REQUIRES_STOP"
    assert "stop" in raised.value.hint
    assert not (tmp_path / "data").exists()


def test_default_update_rejects_stale_or_mismatched_ownership_conservatively(
    tmp_path,
    monkeypatch,
):
    root = (tmp_path / "ComfyUI").resolve()
    recorded = ProcessIdentity("old-python", "1", "python main.py")
    unrelated = ProcessIdentity("other-python", "2", "other")
    current = LauncherState(
        1,
        ComfyMode.MANAGED,
        root,
        DeviceMode.CPU,
        8188,
        4242,
        recorded,
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: unrelated)
    monkeypatch.setattr(
        cli,
        "resolve_uv_binary",
        lambda: (_ for _ in ()).throw(AssertionError("uv must not be resolved")),
    )

    with pytest.raises(cli.LauncherError) as raised:
        service.update_comfyui(current)

    assert raised.value.code == "COMFYUI_UPDATE_OWNERSHIP_UNVERIFIED"
    assert "stop" in raised.value.hint
    assert not (tmp_path / "data").exists()


def test_default_stopped_update_saves_coherent_install_provenance(
    tmp_path,
    monkeypatch,
):
    root = (tmp_path / "ComfyUI").resolve()
    current = LauncherState(
        1,
        ComfyMode.MANAGED,
        root,
        DeviceMode.CPU,
        8188,
        None,
        None,
        launcher_installed=True,
        installed_root=root,
        installed_commit="old-pin",
    )
    fake_uv = (tmp_path / "uv").resolve()
    captured = {}
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    monkeypatch.setattr(cli, "resolve_uv_binary", lambda: fake_uv)

    def fake_update(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return "v0.28.0"

    monkeypatch.setattr(cli, "update_comfyui", fake_update)

    service.update_comfyui(current)

    saved = service.load_state()
    assert captured["kwargs"]["owned_root"] == root
    assert saved is not None
    assert saved.installed_commit == "v0.28.0"
    assert saved.launcher_installed is True
    assert saved.managed_pid is None


def test_default_services_filters_repository_comfyui_candidates(tmp_path):
    project = tmp_path / "repository"
    inside = project / "ComfyUI"
    outside = tmp_path / "external-ComfyUI"
    for root in (inside, outside):
        root.mkdir(parents=True)
        (root / "main.py").touch()
        (root / "models").mkdir()
    services = DefaultServices(project, runner=object(), output_fn=lambda _message: None)
    services.host = HostInfo("Linux", "x86_64", tmp_path)

    candidates = services.candidate_roots(inside, outside)
    found = services.discover_comfyui((inside, outside))

    assert inside.resolve() not in candidates
    assert outside.resolve() in candidates
    assert tuple(item.root for item in found) == (outside.resolve(),)


def test_default_services_rejects_repository_auto_destination(tmp_path):
    project = tmp_path / "repository"
    project.mkdir()
    services = DefaultServices(project, runner=object(), output_fn=lambda _message: None)

    with pytest.raises(cli.LauncherError) as caught:
        services.validate_install_target(project / "data/ComfyUI")

    assert caught.value.code == "COMFYUI_TARGET_IN_PROJECT"
    assert "repository" in caught.value.hint


def test_explicit_device_still_rejects_rosetta_install(harness):
    target = harness.project_root.parent / "managed-ComfyUI"
    harness.install_error = UnsupportedComfyArchitecture(
        "native arm64 architecture is required; Rosetta is unsupported"
    )

    result = main(
        [
            "setup",
            "--non-interactive",
            "--comfyui-mode",
            "managed",
            "--comfyui-path",
            str(target),
            "--device",
            "cpu",
        ],
        services=harness,
    )

    assert result == 2
    assert any(
        "UNSUPPORTED_NATIVE_ARCHITECTURE" in line for line in harness.output
    ), (harness.output, harness.events)
    assert "compose_up" not in harness.events


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
    harness.answers = [True]
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
    harness.choices = ["cpu"]
    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert ("install", DeviceMode.NVIDIA) in harness.events
    assert ("install", DeviceMode.CPU) in harness.events
    assert "TOPSECRET" not in "\n".join(harness.output)


def test_install_failure_can_continue_disabled(harness):
    harness.install_error = ComfyInstallError("failed")
    harness.choices = ["disabled"]
    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED


@pytest.mark.parametrize(
    ("operation", "uv_case", "expected_code"),
    [
        ("install", "invalid", "UV_BINARY_INVALID"),
        ("install", "missing", "UV_BINARY_MISSING"),
        ("update", "invalid", "UV_BINARY_INVALID"),
        ("update", "missing", "UV_BINARY_MISSING"),
    ],
)
def test_cli_surfaces_typed_uv_error_without_recovery_or_mutation(
    tmp_path,
    monkeypatch,
    operation,
    uv_case,
    expected_code,
):
    project = tmp_path / "repository"
    project.mkdir()
    (project / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    target = tmp_path / "managed-ComfyUI"
    output = []
    prompts = []

    class NoSideEffectRunner:
        def __init__(self):
            self.commands = []

        def run(self, args, **_kwargs):
            command = tuple(str(item) for item in args)
            self.commands.append(command)
            return CommandResult(command, 1, "", "runner must remain unused")

    runner = NoSideEffectRunner()
    if uv_case == "invalid":
        monkeypatch.setenv(
            "AI_DRAWING_UV_BIN",
            str((tmp_path / "missing-tools/uv.exe").resolve()),
        )
    else:
        monkeypatch.delenv("AI_DRAWING_UV_BIN", raising=False)
        monkeypatch.setattr(comfyui_module.shutil, "which", lambda _name: None)

    service = DefaultServices(
        project,
        runner=runner,
        input_fn=lambda message: prompts.append(message) or "",
        output_fn=output.append,
    )
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.preflight = lambda: None
    service.probe_external = lambda _port: False

    if operation == "install":
        argv = [
            "setup",
            "--non-interactive",
            "--comfyui-mode",
            "managed",
            "--comfyui-path",
            str(target),
            "--device",
            "cpu",
        ]
        before = None
    else:
        make_root = target
        make_root.mkdir()
        (make_root / "main.py").write_text("# ComfyUI\n", encoding="utf-8")
        (make_root / "models").mkdir()
        marker = make_root / "user-marker.txt"
        marker.write_text("keep", encoding="utf-8")
        current = replace(
            state(ComfyMode.MANAGED, root=target, device=DeviceMode.CPU),
            launcher_installed=True,
            installed_root=target,
            installed_commit="v0.28.0",
        )
        state_path = project / "data/bootstrap/state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(current.to_json(), encoding="utf-8")
        before = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        argv = ["update-comfyui"]

    assert main(argv, services=service) != 0

    rendered = "\n".join(output)
    assert f"ERROR [{expected_code}]" in rendered
    assert "COMFYUI_INSTALL_FAILED" not in rendered
    assert "COMFYUI_UPDATE_FAILED" not in rendered
    assert prompts == []
    assert runner.commands == []
    assert not (project / ".env").exists()
    assert not (project / ".ai-drawing").exists()
    assert not list(target.parent.glob(f".{target.name}.staging-*"))
    if operation == "install":
        assert not target.exists()
    else:
        after = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        assert after == before
    log = project / "data/logs/bootstrap.log"
    assert log.is_file()
    log_text = log.read_text(encoding="utf-8")
    assert expected_code in log_text
    assert "missing-tools" not in log_text


def test_noninteractive_install_failure_obeys_explicit_cpu_recovery(harness):
    target = harness.project_root / "ComfyUI"
    harness.detected_device = DeviceMode.NVIDIA
    harness.install_error = ComfyInstallError("cuda failed")
    assert (
        main(
            [
                "setup",
                "--non-interactive",
                "--comfyui-mode",
                "managed",
                "--comfyui-path",
                str(target),
                "--on-comfy-failure",
                "cpu",
            ],
            services=harness,
        )
        == 0
    )
    assert ("install", DeviceMode.NVIDIA) in harness.events
    assert ("install", DeviceMode.CPU) in harness.events


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


def test_automatic_install_prompts_for_custom_destination(harness):
    custom = (harness.project_root / "custom-install" / "ComfyUI").resolve()
    harness.path_answers = [None, custom]

    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.events.count("ask_path") == 2
    assert harness.installed_roots == [custom]


def test_automatic_install_blank_destination_uses_platform_default(harness):
    harness.path_answers = [None, None]

    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.events.count("ask_path") == 2
    assert harness.installed_roots == [harness.default_comfyui_root().resolve()]
    assert str(harness.default_comfyui_root().resolve()) in harness.path_prompts[-1]


def test_explicit_install_path_wins_without_destination_prompt(harness):
    explicit = (harness.project_root / "explicit" / "ComfyUI").resolve()
    harness.path_answers = [harness.project_root / "ignored"]

    assert main(
        ["setup", "--comfyui-mode", "managed", "--comfyui-path", str(explicit)],
        services=harness,
    ) == 0
    assert "ask_path" not in harness.events
    assert harness.installed_roots == [explicit]


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
    events = [event for event in harness.events if not (
        isinstance(event, tuple) and event[0] == "bootstrap_log"
    )]
    assert events[-3:] == ["compose_down", "restore_config", "stop_comfyui"]


def test_failed_reconfigure_restores_previously_running_compose(harness):
    harness.loaded_state = state()
    harness.compose_services = frozenset({"backend"})
    harness.backend_ready = False
    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 1
    rollback = [
        event
        for event in harness.events[harness.events.index("compose_down") :]
        if not (isinstance(event, tuple) and event[0] == "bootstrap_log")
    ]
    assert rollback == [
        "compose_down",
        "restore_config",
        ("compose_up_services", frozenset({"backend"})),
    ]


def test_failed_start_restores_state_after_starting_new_managed_process(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    harness.frontend_ready = False
    assert main(["start"], services=harness) == 1
    assert "save_state" in harness.events
    events = [event for event in harness.events if not (
        isinstance(event, tuple) and event[0] == "bootstrap_log"
    )]
    assert events[-3:] == ["compose_down", "restore_config", "stop_comfyui"]


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
    if command == "update-comfyui":
        harness.loaded_state = replace(
            harness.loaded_state,
            launcher_installed=True,
            installed_root=harness.loaded_state.comfyui_root,
            installed_commit="v0.28.0",
        )
    assert main([command], services=harness) == 0
    assert event in harness.events


def test_stop_only_stops_managed_process(harness):
    harness.loaded_state = state(ComfyMode.EXTERNAL)
    assert main(["stop"], services=harness) == 0
    assert "compose_down" in harness.events
    assert "stop_comfyui" not in harness.events
    assert any(isinstance(event, tuple) and event[0] == "stop_relay" for event in harness.events)


def test_connected_linux_flow_starts_relay_before_compose_and_rolls_it_back(harness):
    identity = ProcessIdentity("python", "1", "relay")
    harness.relay_state = RelayState("172.17.0.1", 8188, 8188, 5151, identity)
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
    assert harness.events.index("ensure_relay") < harness.events.index("compose_up")
    assert any(isinstance(event, tuple) and event[0] == "stop_relay" for event in harness.events)


def test_relay_stop_failure_is_truthful_nonzero(harness):
    harness.loaded_state = state(ComfyMode.EXTERNAL)
    harness.stop_relay = lambda _state=None: RelayStopResult(
        False, "termination_failed", harness.relay_state
    )
    assert main(["stop"], services=harness) == 1
    assert "RELAY_STOP_FAILED" in "\n".join(harness.output)


def test_relay_replacement_rollback_restores_exact_prior_relay(harness):
    identity = ProcessIdentity("python", "1", "relay")
    prior = RelayState("172.17.0.1", 8188, 8188, 5001, identity)
    replacement = RelayState("172.17.0.1", 8288, 8288, 5002, identity)
    harness.relay_state = prior
    harness.relay_activation = RelayStartResult(True, "ready", replacement)
    harness.frontend_ready = False

    assert (
        main(
            [
                "setup",
                "--comfyui-mode",
                "managed",
                "--comfyui-path",
                str(harness.project_root / "ComfyUI"),
                "--comfyui-port",
                "8288",
            ],
            services=harness,
        )
        == 1
    )
    assert ("stop_relay", replacement) in harness.events
    assert ("restore_relay", prior) in harness.events


def test_default_relay_snapshot_excludes_unverified_ownership(tmp_path, monkeypatch):
    identity = ProcessIdentity("python", "1", "relay")
    stale = RelayState("172.17.0.1", 8188, 8188, 5001, identity)
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    monkeypatch.setattr(cli, "load_relay_state", lambda *_args: stale)
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: None)
    assert service.current_relay_state() is None


def test_successful_disabled_transition_stops_prior_relay_after_readiness(harness):
    identity = ProcessIdentity("python", "1", "relay")
    prior = RelayState("172.17.0.1", 8188, 8188, 5001, identity)
    harness.relay_state = prior
    harness.loaded_state = state(ComfyMode.EXTERNAL)

    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 0
    stop_index = harness.events.index(("stop_relay", prior))
    assert stop_index > harness.events.index("wait_frontend")


def test_disabled_transition_preserves_owned_install_provenance_across_reload(harness):
    root = (harness.project_root / "ComfyUI").resolve()
    harness.loaded_state = LauncherState(
        1,
        ComfyMode.MANAGED,
        root,
        DeviceMode.CPU,
        8188,
        None,
        None,
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )

    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 0
    saved = harness.saved_state
    reloaded = LauncherState.from_json(saved.to_json())
    assert reloaded.comfy_mode is ComfyMode.DISABLED
    assert reloaded.comfyui_root == root
    assert reloaded.device is DeviceMode.CPU
    assert reloaded.launcher_installed is True
    assert reloaded.installed_root == root
    assert harness.saved_settings.comfy_paths is None
    harness.loaded_state = reloaded
    harness.events.clear()
    assert main(["update-comfyui"], services=harness) == 0
    assert "update_comfyui" in harness.events


def test_starting_disabled_owned_state_never_probes_starts_or_stops_comfyui(harness):
    root = (harness.project_root / "ComfyUI").resolve()
    harness.loaded_state = LauncherState(
        1,
        ComfyMode.DISABLED,
        root,
        DeviceMode.CPU,
        8188,
        None,
        None,
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )

    assert main(["start"], services=harness) == 0
    assert "probe_external" not in harness.events
    assert "start_comfyui" not in harness.events
    assert "stop_comfyui" not in harness.events


def test_stop_attempts_relay_and_comfy_when_compose_down_fails(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )

    def fail_down():
        harness.events.append("compose_down")
        raise cli.docker.DockerError("COMPOSE_DOWN_FAILED", "failed", "hint")

    harness.compose_down = fail_down
    assert main(["stop"], services=harness) == 1
    assert any(isinstance(event, tuple) and event[0] == "stop_relay" for event in harness.events)
    assert "stop_comfyui" in harness.events


def test_docker_unavailable_does_not_block_native_stop_cleanup(harness):
    harness.preflight_error = cli.docker.DockerError(
        "DOCKER_DAEMON_UNAVAILABLE", "down", "start docker"
    )
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    harness.compose_down = lambda: (_ for _ in ()).throw(
        cli.docker.DockerError("COMPOSE_DOWN_FAILED", "down", "start docker")
    )
    assert main(["stop"], services=harness) == 1
    assert "preflight" not in harness.events
    assert "stop_comfyui" in harness.events
    assert any(isinstance(event, tuple) and event[0] == "stop_relay" for event in harness.events)


def test_status_reports_docker_unavailable_and_native_truth(harness):
    harness.preflight_error = cli.docker.DockerError(
        "DOCKER_DAEMON_UNAVAILABLE", "down", "start docker"
    )
    harness.loaded_state = state(ComfyMode.EXTERNAL, device=DeviceMode.CPU)
    assert main(["status"], services=harness) == 0
    assert "Docker: unavailable" in "\n".join(harness.output)
    assert "ComfyUI device: cpu" in "\n".join(harness.output)
    assert "status" in harness.events


def test_logs_and_update_do_not_require_docker_preflight(harness):
    harness.preflight_error = cli.docker.DockerError(
        "DOCKER_DAEMON_UNAVAILABLE", "down", "start docker"
    )
    assert main(["logs"], services=harness) == 0
    assert "logs" in harness.events
    assert "preflight" not in harness.events

    root = harness.project_root / "ComfyUI"
    harness.loaded_state = replace(
        state(ComfyMode.MANAGED, root=root, device=DeviceMode.CPU),
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )
    assert main(["update-comfyui"], services=harness) == 0
    assert "update_comfyui" in harness.events


def test_dry_run_reports_preflight_failure_without_mutation(harness):
    harness.preflight_error = cli.docker.DockerError(
        "DOCKER_DAEMON_UNAVAILABLE", "down", "start docker"
    )
    assert main(["dry-run", "--comfyui-mode", "disabled"], services=harness) == 0
    assert "Docker preflight: unavailable" in "\n".join(harness.output)
    assert "write_config" not in harness.events


def test_discovered_user_owned_root_cannot_be_updated(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "User ComfyUI",
        device=DeviceMode.CPU,
    )
    assert main(["update-comfyui"], services=harness) == 1
    assert "COMFYUI_UPDATE_NOT_OWNED" in "\n".join(harness.output)
    assert "update_comfyui" not in harness.events


def test_auto_install_persists_launcher_provenance(harness):
    assert main(["setup", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.saved_state.launcher_installed is True
    assert harness.saved_state.installed_root == harness.saved_state.comfyui_root
    assert harness.saved_state.installed_commit == "v0.28.0"


def test_default_start_merges_install_provenance_into_task5_state(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    root.mkdir()
    python = root / "python"
    python.touch()
    class SmokeRunner:
        def run(self, args, **_kwargs):
            command = tuple(str(item) for item in args)
            return CommandResult(command, 0, "", "")

    service = DefaultServices(tmp_path, runner=SmokeRunner(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    planned = replace(
        state(ComfyMode.MANAGED, root=root, device=DeviceMode.CPU),
        launcher_installed=True,
        installed_root=root,
        installed_commit="v0.28.0",
    )
    task5_state = replace(planned, managed_pid=4242, launcher_installed=False, installed_root=None, installed_commit=None)
    monkeypatch.setattr(
        cli,
        "validate_comfyui_root",
        lambda *_args: ComfyValidation(root, True, python, ()),
    )
    monkeypatch.setattr(
        cli,
        "start_comfyui",
        lambda **_kwargs: ProcessStartResult(True, "ready", task5_state, 4242),
    )

    result = service.start_comfyui(planned)

    assert result.launcher_installed is True
    assert result.installed_root == root
    assert result.installed_commit == "v0.28.0"


def test_same_ready_managed_root_preserves_ownership_on_reconfigure(harness):
    root = harness.project_root / "ComfyUI"
    old = state(
        ComfyMode.MANAGED,
        root=root,
        device=DeviceMode.CPU,
        pid=4242,
        identity=ProcessIdentity("python", "1", "python main.py"),
    )
    harness.loaded_state = old
    harness.discovered = (ComfyValidation(root, True, root / ".venv/bin/python", ()),)
    harness.start_comfyui = lambda planned: harness.events.append("start_comfyui") or planned

    assert (
        main(
            ["reconfigure", "--comfyui-mode", "managed", "--comfyui-path", str(root)],
            services=harness,
        )
        == 0
    )
    assert harness.saved_state.managed_pid == 4242
    assert "stop_comfyui" not in harness.events


def test_ready_api_preserves_verified_previous_managed_before_external_classification(harness):
    root = harness.project_root / "Real Existing ComfyUI"
    identity = ProcessIdentity("python", "1", "python main.py")
    previous = state(
        ComfyMode.MANAGED,
        root=root,
        device=DeviceMode.CPU,
        pid=4242,
        identity=identity,
    )
    harness.loaded_state = previous
    harness.external_running = True
    harness.managed_verified = True

    assert main(["reconfigure", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.saved_state == previous
    assert "verify_managed" in harness.events
    assert "stop_comfyui" not in harness.events


def test_live_verified_managed_reconfigure_requires_explicit_stop(harness):
    old_root = (harness.project_root / "Old ComfyUI").resolve()
    new_root = (harness.project_root / "New ComfyUI").resolve()
    previous = state(
        ComfyMode.MANAGED,
        root=old_root,
        device=DeviceMode.NVIDIA,
        pid=4242,
        identity=ProcessIdentity("python", "1", "python main.py"),
    )
    harness.loaded_state = previous
    harness.external_running = True
    harness.managed_verified = True

    assert main(
        [
            "reconfigure",
            "--comfyui-mode",
            "managed",
            "--comfyui-path",
            str(new_root),
            "--device",
            "cpu",
        ],
        services=harness,
    ) == 1

    rendered = "\n".join(harness.output)
    assert "COMFYUI_RECONFIGURE_REQUIRES_STOP" in rendered
    assert "snapshot_config" not in harness.events
    assert "write_config" not in harness.events
    assert "stop_comfyui" not in harness.events
    assert not any(
        isinstance(event, tuple) and event[0] == "bootstrap_log"
        for event in harness.events
    )


@pytest.mark.parametrize(
    "change_args",
    [
        ("--comfyui-mode", "managed", "--comfyui-path", "NEW_ROOT"),
        ("--comfyui-mode", "managed", "--device", "cpu"),
        ("--comfyui-mode", "managed", "--comfyui-port", "8288"),
        ("--comfyui-mode", "external"),
    ],
)
def test_rejected_live_reconfigure_is_bootstrap_audit_write_free(
    tmp_path,
    monkeypatch,
    change_args,
):
    identity = ProcessIdentity("python", "1", "python main.py --port 8188")
    old_root = (tmp_path / "Old ComfyUI").resolve()
    previous = state(
        ComfyMode.MANAGED,
        root=old_root,
        device=DeviceMode.NVIDIA,
        pid=4242,
        identity=identity,
    )
    state_path = tmp_path / "data/bootstrap/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(previous.to_json(), encoding="utf-8")
    base = tmp_path / "docker-compose.yml"
    base.write_text("services: {}\n", encoding="utf-8")
    before_state = state_path.read_bytes()
    before_base = base.read_bytes()
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.preflight = lambda: None
    service.probe_external = lambda _port: True
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: identity)
    args = [
        str((tmp_path / "New ComfyUI").resolve()) if item == "NEW_ROOT" else item
        for item in change_args
    ]

    assert main(["reconfigure", *args], services=service) == 1

    assert state_path.read_bytes() == before_state
    assert base.read_bytes() == before_base
    assert not (tmp_path / "data/logs").exists()
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".ai-drawing").exists()


def test_production_verifier_rejects_live_managed_tuple_change_without_mutation(
    tmp_path,
    monkeypatch,
):
    identity = ProcessIdentity("python", "1", "python main.py --port 8188")
    old_root = (tmp_path / "Old ComfyUI").resolve()
    previous = state(
        ComfyMode.MANAGED,
        root=old_root,
        device=DeviceMode.NVIDIA,
        pid=4242,
        identity=identity,
    )
    state_path = tmp_path / "data/bootstrap/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(previous.to_json(), encoding="utf-8")
    before = state_path.read_bytes()
    probes = []
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.probe_external = lambda port: probes.append(port) or True
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: identity)
    args = cli.build_parser().parse_args(
        [
            "reconfigure",
            "--comfyui-mode",
            "managed",
            "--comfyui-path",
            str(tmp_path / "New ComfyUI"),
            "--device",
            "cpu",
        ]
    )

    with pytest.raises(cli.LauncherError) as raised:
        cli._plan_comfyui(args, service, previous)

    assert raised.value.code == "COMFYUI_RECONFIGURE_REQUIRES_STOP"
    assert probes == [8188]
    assert state_path.read_bytes() == before
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".ai-drawing/compose.local.yaml").exists()


def test_ready_api_with_identity_mismatch_becomes_external_unowned(harness):
    root = harness.project_root / "Old ComfyUI"
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=root,
        device=DeviceMode.CPU,
        pid=4242,
        identity=ProcessIdentity("python", "1", "python main.py"),
    )
    harness.external_running = True
    harness.managed_verified = False
    harness.discovered = (
        ComfyValidation(root.resolve(), True, root / ".venv/bin/python", ()),
    )

    assert main(["reconfigure", "--comfyui-mode", "managed"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.EXTERNAL
    assert harness.saved_state.managed_pid is None
    assert harness.saved_state.managed_identity is None
    assert harness.saved_state.comfyui_root == root.resolve()


def test_running_external_retains_valid_discovered_root_and_mounts(harness):
    root = (harness.project_root / "Existing ComfyUI").resolve()
    harness.external_running = True
    harness.discovered = (
        ComfyValidation(root, True, root / ".venv/bin/python", ()),
    )

    assert main(
        ["setup", "--comfyui-mode", "external", "--comfyui-path", str(root)],
        services=harness,
    ) == 0

    assert harness.saved_state.comfy_mode is ComfyMode.EXTERNAL
    assert harness.saved_state.comfyui_root == root
    assert harness.saved_settings.comfy_paths.root == root


def test_running_external_without_known_root_stays_pathless(harness):
    harness.external_running = True

    assert main(["setup", "--comfyui-mode", "external"], services=harness) == 0

    assert harness.saved_state.comfy_mode is ComfyMode.EXTERNAL
    assert harness.saved_state.comfyui_root is None
    assert harness.saved_settings.comfy_paths is None


def test_same_root_different_device_never_relabels_existing_process(tmp_path):
    root = tmp_path / "ComfyUI"
    old = state(
        ComfyMode.MANAGED,
        root=root,
        device=DeviceMode.NVIDIA,
        pid=4242,
        identity=ProcessIdentity("python", "1", "python main.py"),
    )
    planned = cli._base_state(
        ComfyMode.MANAGED,
        root=root,
        device=DeviceMode.CPU,
        port=8188,
        previous=old,
    )
    assert planned.managed_pid is None
    assert planned.managed_identity is None


def test_failed_managed_stop_is_nonzero_and_does_not_save_cleared_state(harness):
    current = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
        pid=4242,
        identity=ProcessIdentity("python", "1", "python main.py"),
    )
    harness.loaded_state = current
    harness.stop_comfyui = lambda _state: ProcessStopResult(
        False, "termination_failed", current
    )

    assert main(["stop"], services=harness) == 1
    assert "COMFYUI_STOP_FAILED" in "\n".join(harness.output)
    assert "save_state" not in harness.events


def test_dry_run_does_not_write_start_or_stop(harness):
    assert main(["dry-run", "--comfyui-mode", "disabled"], services=harness) == 0
    assert not {"write_config", "compose_up", "compose_down", "start_comfyui"}.intersection(
        harness.events
    )


def test_dry_run_managed_install_is_plan_only_with_no_mutating_boundary(harness):
    assert main(["dry-run", "--comfyui-mode", "managed"], services=harness) == 0
    forbidden = {
        "start_comfyui",
        "stop_comfyui",
        "ensure_relay",
        "stop_relay",
        "mount_probes",
        "snapshot_config",
        "restore_config",
        "write_config",
        "compose_up",
        "compose_down",
        "save_state",
    }
    assert not forbidden.intersection(harness.events)
    assert not any(isinstance(event, tuple) and event[0] == "install" for event in harness.events)
    assert "would install" in "\n".join(harness.output).lower()


def test_noninteractive_dry_run_can_plan_default_install_target(harness):
    assert (
        main(
            ["dry-run", "--non-interactive", "--comfyui-mode", "managed"],
            services=harness,
        )
        == 0
    )
    assert "would install" in "\n".join(harness.output).lower()


def test_interactive_alternate_ports_require_confirmation(harness):
    harness.select_ports = lambda _backend, _frontend: (8101, 5273)
    harness.answers = [False]
    assert main(["setup", "--comfyui-mode", "disabled"], services=harness) == 2
    assert "ALTERNATE_PORTS_REJECTED" in "\n".join(harness.output)
    assert "write_config" not in harness.events


def test_noninteractive_alternate_ports_require_acceptance_flag(harness):
    harness.select_ports = lambda _backend, _frontend: (8101, 5273)
    assert (
        main(
            ["setup", "--non-interactive", "--comfyui-mode", "disabled"],
            services=harness,
        )
        == 2
    )
    assert "ALTERNATE_PORTS_NOT_ACCEPTED" in "\n".join(harness.output)

    harness.output.clear()
    assert (
        main(
            [
                "setup",
                "--non-interactive",
                "--accept-alternate-ports",
                "--comfyui-mode",
                "disabled",
            ],
            services=harness,
        )
        == 0
    )


@pytest.mark.parametrize("ports", [(True, 5173), (8001, False), (0, 5173), (8001, 70000)])
def test_loaded_ports_require_builtin_bounded_ints(harness, ports):
    harness.loaded_state = state()
    harness.load_ports = lambda: ports
    assert main(["start"], services=harness) == 1
    assert "CONFIG_PORT_INVALID" in "\n".join(harness.output)


def test_default_services_rejects_out_of_range_loaded_env_port(tmp_path):
    (tmp_path / ".env").write_text(
        "BACKEND_PORT=70000\nFRONTEND_PORT=5173\n", encoding="utf-8"
    )
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    with pytest.raises(cli.LauncherError) as raised:
        service.load_ports()
    assert raised.value.code == "CONFIG_PORT_INVALID"


def test_fresh_clone_skips_compose_status_until_generated_files_exist(tmp_path):
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  backend:\n    image: example.invalid/backend\n",
        encoding="utf-8",
    )

    class StaticComposeRunner:
        def __init__(self):
            self.commands = []

        def run(self, args, cwd=None, **_kwargs):
            command = tuple(str(item) for item in args)
            self.commands.append(command)
            if command[:2] == ("docker", "version"):
                return CommandResult(command, 0, "26.1.0\n", "")
            if command[:3] == ("docker", "compose", "version"):
                return CommandResult(command, 0, "2.24.0\n", "")
            if "ps" in command:
                raise AssertionError("fresh clone must not query Compose with missing files")
            if "config" in command:
                env = Path(command[command.index("--env-file") + 1])
                override = Path(command[command.index("-f", 5) + 1])
                assert env.is_file()
                assert override.is_file()
            return CommandResult(command, 0, "", "")

    runner = StaticComposeRunner()
    service = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)
    service.host = HostInfo("Windows", "AMD64", tmp_path)
    service.wait_backend = lambda _port: True
    service.wait_frontend = lambda _port: True

    assert main(
        ["setup", "--non-interactive", "--comfyui-mode", "disabled"],
        services=service,
    ) == 0

    assert (tmp_path / ".env").is_file()
    assert (tmp_path / ".ai-drawing/compose.local.yaml").is_file()
    assert not any("ps" in command for command in runner.commands)
    assert any("config" in command for command in runner.commands)


def test_missing_base_compose_is_not_treated_as_fresh_clone(tmp_path):
    class StaticRunner:
        def run(self, args, **_kwargs):
            command = tuple(str(item) for item in args)
            return CommandResult(command, 1, "", "base compose missing")

    service = DefaultServices(tmp_path, runner=StaticRunner(), output_fn=lambda _message: None)
    with pytest.raises(cli.docker.DockerError) as raised:
        service.compose_running_services()
    assert raised.value.code == "COMPOSE_STATUS_FAILED"


def test_configured_project_queries_compose_with_exact_generated_files(tmp_path):
    base = tmp_path / "docker-compose.yml"
    env = tmp_path / ".env"
    override = tmp_path / ".ai-drawing/compose.local.yaml"
    override.parent.mkdir()
    base.write_text("services: {}\n", encoding="utf-8")
    env.write_text("COMFYUI_MODE=disabled\n", encoding="utf-8")
    override.write_text("services: {}\n", encoding="utf-8")

    class StaticRunner:
        def __init__(self):
            self.command = None

        def run(self, args, **_kwargs):
            self.command = tuple(str(item) for item in args)
            return CommandResult(
                self.command,
                0,
                '[{"Service":"backend","State":"running"}]',
                "",
            )

    runner = StaticRunner()
    service = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)

    assert service.compose_running_services() == frozenset({"backend"})
    assert runner.command == tuple(
        cli.docker.compose_command(tmp_path, "ps", "--all", "--format", "json")
    )


def test_managed_start_failure_can_explicitly_fallback_to_cpu(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.NVIDIA,
    )
    attempts = []

    def start(planned):
        attempts.append(planned.device)
        if len(attempts) == 1:
            raise cli.LauncherError("START_FAILED", "failed", "hint")
        return replace(planned, managed_pid=4242)

    harness.start_comfyui = start
    harness.choices = ["cpu"]
    assert main(["start"], services=harness) == 0
    assert attempts == [DeviceMode.NVIDIA, DeviceMode.CPU]
    assert harness.saved_state.device is DeviceMode.CPU
    assert "write_config" in harness.events


def test_managed_start_failure_can_continue_disabled_consistently(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.NVIDIA,
    )
    harness.start_comfyui = lambda _planned: (_ for _ in ()).throw(
        cli.LauncherError("START_FAILED", "failed", "hint")
    )
    harness.choices = ["disabled"]
    assert main(["start"], services=harness) == 0
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED
    assert harness.saved_settings.comfy_paths is None
    assert "ensure_relay" in harness.events


def test_mount_failure_can_continue_disabled_without_comfy_mounts(harness):
    calls = []

    def mount(settings):
        calls.append(settings.comfy_mode)
        if len(calls) == 1:
            raise cli.docker.DockerError("MOUNT_PROBE_FAILED", "failed", "hint")
        harness.events.append("mount_probes")

    harness.mount_probes = mount
    harness.choices = ["disabled"]
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
        == 0
    )
    assert calls == [ComfyMode.MANAGED, ComfyMode.DISABLED]
    assert harness.saved_state.comfy_mode is ComfyMode.DISABLED


def test_noninteractive_recovery_requires_explicit_flag(harness):
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.NVIDIA,
    )
    harness.start_comfyui = lambda _planned: (_ for _ in ()).throw(
        cli.LauncherError("START_FAILED", "failed", "hint")
    )
    assert main(["start", "--non-interactive"], services=harness) == 2
    assert "MISSING_RECOVERY_DECISION" in "\n".join(harness.output)


def test_status_reports_each_dependency_and_no_models_hint(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    (root / "models/checkpoints").mkdir(parents=True)
    (root / "models/diffusion_models").mkdir(parents=True)
    (tmp_path / ".ai-drawing").mkdir()
    for path in (
        tmp_path / "docker-compose.yml",
        tmp_path / ".env",
        tmp_path / ".ai-drawing/compose.local.yaml",
    ):
        path.touch()
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Windows", "AMD64", tmp_path)
    monkeypatch.setattr(
        cli.docker,
        "compose_service_states",
        lambda *_args: {"backend": "running", "frontend": "exited"},
    )
    service.wait_backend = lambda _port, **_kwargs: True
    service.wait_frontend = lambda _port, **_kwargs: False
    monkeypatch.setattr(
        cli,
        "probe_comfyui",
        lambda *_args, **_kwargs: ComfyProbe(
            "http://127.0.0.1:8188", True, ComfyMode.EXTERNAL
        ),
    )

    report = service.status(
        state(ComfyMode.EXTERNAL, root=root, device=DeviceMode.CPU)
    )

    assert report["docker"] == "available"
    assert report["services"] == {"backend": "running", "frontend": "exited"}
    assert report["backend"] == "reachable"
    assert report["frontend"] == "unreachable"
    assert report["comfy"]["state"] == "no_models"
    assert report["comfy"]["model_count"] == 0
    assert report["comfy"]["device"] == "cpu"
    assert report["comfy"]["hint"]


def test_status_before_setup_is_truthful_without_compose_files(tmp_path):
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.wait_backend = lambda _port, **_kwargs: False
    service.wait_frontend = lambda _port, **_kwargs: False
    report = service.status(None)
    assert report["services"] == {}
    assert report["comfy"]["state"] == "not_configured"


def test_status_invalid_relay_state_is_non_mutating_and_reports_stale(tmp_path):
    relay_path = tmp_path / "data/bootstrap/relay-state.json"
    relay_path.parent.mkdir(parents=True)
    relay_path.write_bytes(b"not-json")
    before = relay_path.stat().st_mtime_ns
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    service.wait_backend = lambda _port, **_kwargs: False
    service.wait_frontend = lambda _port, **_kwargs: False

    report = service.status(None, docker_available=False)

    assert report["relay"] == "stale"
    assert relay_path.read_bytes() == b"not-json"
    assert relay_path.stat().st_mtime_ns == before
    assert not (tmp_path / "data/bootstrap/relay-state.invalid.json").exists()
    assert not (tmp_path / "data/bootstrap/relay-state.lock").exists()


def test_status_verifies_managed_identity_and_counts_models(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    models = root / "models/checkpoints"
    models.mkdir(parents=True)
    (models / "one.safetensors").touch()
    identity = ProcessIdentity("python", "1", "python main.py")
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    monkeypatch.setattr(cli.docker, "compose_service_states", lambda *_args: {})
    service.wait_backend = lambda _port, **_kwargs: False
    service.wait_frontend = lambda _port, **_kwargs: False
    monkeypatch.setattr(
        cli,
        "probe_comfyui",
        lambda *_args, **_kwargs: ComfyProbe("http://127.0.0.1:8188", True, ComfyMode.EXTERNAL),
    )
    monkeypatch.setattr(cli, "read_process_identity", lambda *_args: identity)
    monkeypatch.setattr(cli, "load_relay_state", lambda *_args: None)

    report = service.status(
        state(
            ComfyMode.MANAGED,
            root=root,
            device=DeviceMode.CPU,
            pid=4242,
            identity=identity,
        )
    )

    assert report["comfy"]["state"] == "connected"
    assert report["comfy"]["ownership"] == "managed_verified"
    assert report["comfy"]["model_count"] == 1
    assert report["relay"] == "not_running"


def test_logs_include_all_sources_redact_secrets_and_tolerate_missing(tmp_path):
    (tmp_path / "data/logs").mkdir(parents=True)
    (tmp_path / "data/logs/bootstrap.log").write_text(
        "ready\nTOKEN=private-token\nAuthorization: Bearer private-bearer\n"
        'CIVITAI_AUTHORIZATION="Bearer civitai-private"\n'
        '{"my_token": "json-private"}\n'
        "MY_API_KEY=dict-private\n"
        "prefix_password: password-private\n"
        "secret_value=secret-private\n",
        encoding="utf-8",
    )
    (tmp_path / "data/logs/comfyui.log").write_text("comfy ready\n", encoding="utf-8")

    class Runner:
        def run(self, args, **_kwargs):
            return CommandResult(tuple(args), 0, "backend ready\nPASSWORD=hunter2\n", "")

    output = []
    service = DefaultServices(tmp_path, runner=Runner(), output_fn=output.append)
    service.compose_logs()
    rendered = "\n".join(output)
    assert "bootstrap.log" in rendered
    assert "comfyui.log" in rendered
    assert "comfyui-relay.log: missing" in rendered
    assert "backend ready" in rendered
    assert "private-token" not in rendered
    assert "hunter2" not in rendered
    assert "private-bearer" not in rendered
    for fragment in (
        "civitai-private",
        "json-private",
        "dict-private",
        "password-private",
        "secret-private",
    ):
        assert fragment not in rendered
    assert "[REDACTED]" in rendered


def test_mutating_error_produces_sanitized_bounded_bootstrap_log(tmp_path):
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.preflight = lambda: (_ for _ in ()).throw(
        cli.docker.DockerError(
            "DOCKER_DAEMON_UNAVAILABLE",
            "TOKEN=private-token",
            "Authorization: Bearer private-bearer",
        )
    )
    assert main(["setup", "--comfyui-mode", "disabled"], services=service) == 1
    log = tmp_path / "data/logs/bootstrap.log"
    assert log.is_file()
    content = log.read_text(encoding="utf-8")
    assert "private-token" not in content
    assert "private-bearer" not in content
    assert "DOCKER_DAEMON_UNAVAILABLE" in content


def test_status_and_dry_run_do_not_create_bootstrap_log(tmp_path):
    service = DefaultServices(tmp_path, runner=object(), output_fn=lambda _message: None)
    service.preflight = lambda: None
    service.wait_backend = lambda _port, **_kwargs: False
    service.wait_frontend = lambda _port, **_kwargs: False
    assert main(["status"], services=service) == 0
    assert not (tmp_path / "data/logs/bootstrap.log").exists()

    assert main(["dry-run", "--comfyui-mode", "disabled"], services=service) == 0
    assert not (tmp_path / "data/logs/bootstrap.log").exists()


def test_bootstrap_logging_failure_never_blocks_stop_cleanup(harness):
    harness.bootstrap_log_error = OSError("disk full")
    harness.loaded_state = state(
        ComfyMode.MANAGED,
        root=harness.project_root / "ComfyUI",
        device=DeviceMode.CPU,
    )
    assert main(["stop"], services=harness) == 0
    assert "stop_comfyui" in harness.events


def test_no_arg_audit_uses_resolved_setup_command(harness):
    harness.answers = [False]
    assert main([], services=harness) == 0
    logs = [event[1] for event in harness.events if isinstance(event, tuple) and event[0] == "bootstrap_log"]
    assert logs == ["command=setup begin", "command=setup complete"]


def test_no_arg_audit_uses_resolved_start_command_for_existing_state(harness):
    harness.loaded_state = state(ComfyMode.DISABLED)
    assert main([], services=harness) == 0
    logs = [event[1] for event in harness.events if isinstance(event, tuple) and event[0] == "bootstrap_log"]
    assert logs == ["command=start begin", "command=start complete"]


def test_accepted_reconfigure_keeps_begin_and_complete_audit(harness):
    harness.loaded_state = state(ComfyMode.DISABLED)

    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 0

    logs = [
        event[1]
        for event in harness.events
        if isinstance(event, tuple) and event[0] == "bootstrap_log"
    ]
    assert logs == ["command=reconfigure begin", "command=reconfigure complete"]


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


def test_degraded_corrupt_managed_state_cannot_be_stopped_or_updated(harness):
    corrupt = {
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
    }
    harness.loaded_state = LauncherState.from_json(json.dumps(corrupt))

    assert main(["stop"], services=harness) == 0
    assert "stop_comfyui" not in harness.events
    harness.events.clear()
    assert main(["update-comfyui"], services=harness) == 1
    assert "update_comfyui" not in harness.events


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


def test_existing_managed_runtime_is_device_smoked_before_spawn(tmp_path, monkeypatch):
    root = tmp_path / "ComfyUI"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    (root / "main.py").write_text("# ComfyUI\n", encoding="utf-8")
    (root / "models").mkdir()

    class Runner:
        def __init__(self):
            self.commands = []

        def run(self, args, **_kwargs):
            command = tuple(str(item) for item in args)
            self.commands.append(command)
            return CommandResult(command, 0, "", "")

    runner = Runner()
    service = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)
    service.host = HostInfo("Linux", "x86_64", tmp_path)
    spawned = []

    def fake_start(**kwargs):
        spawned.append(kwargs)
        return ProcessStartResult(
            True,
            "ready",
            state(
                ComfyMode.MANAGED,
                root=root.resolve(),
                device=DeviceMode.NVIDIA,
                pid=4242,
                identity=ProcessIdentity(str(python), "1", "python main.py"),
            ),
        )

    monkeypatch.setattr(cli, "start_comfyui", fake_start)
    result = service.start_comfyui(
        state(ComfyMode.MANAGED, root=root, device=DeviceMode.NVIDIA)
    )

    assert result.managed_pid == 4242
    assert len(spawned) == 1
    assert runner.commands == [
        (str(python.resolve()), "-c", "import torch; assert torch.cuda.is_available()")
    ]


def test_previous_non_default_comfyui_root_is_a_bounded_discovery_candidate(harness):
    root = (harness.project_root / "custom" / "ComfyUI").resolve()
    harness.loaded_state = state(
        ComfyMode.MANAGED, root=root, device=DeviceMode.CPU
    )
    harness.discovered = (ComfyValidation(root, True, root / ".venv/bin/python", ()),)
    harness.answers = [True]

    assert main(["reconfigure", "--comfyui-mode", "managed"], services=harness) == 0
    assert root in harness.candidate_batches[0]
    assert len(harness.candidate_batches[0]) <= 8
    assert harness.saved_state.comfyui_root == root


def test_interactive_user_can_enter_an_existing_comfyui_path(harness):
    root = (harness.project_root / "elsewhere" / "ComfyUI").resolve()
    found = ComfyValidation(root, True, root / ".venv/bin/python", ())
    harness.answers = [True]
    harness.path_answers = [root]
    harness.discovery_batches = [(), (found,)]

    assert main(["setup"], services=harness) == 0
    assert "ask_path" in harness.events
    assert harness.saved_state.comfyui_root == root
    assert not any(
        isinstance(event, tuple) and event[0] == "install" for event in harness.events
    )


def test_noninteractive_discovery_never_prompts_for_another_path(harness):
    assert main(
        ["setup", "--non-interactive", "--comfyui-mode", "disabled"],
        services=harness,
    ) == 0
    assert "ask_path" not in harness.events


def test_running_project_reconfigure_reuses_its_configured_ports(harness):
    harness.loaded_state = state()
    harness.compose_services = frozenset({"backend", "frontend"})
    harness.load_ports = lambda: (8101, 5273)

    assert main(["reconfigure", "--comfyui-mode", "disabled"], services=harness) == 0
    assert "ports" not in harness.events
    assert "running_ports" in harness.events
    assert harness.saved_settings.backend_port == 8101
    assert harness.saved_settings.frontend_port == 5273


def test_running_port_selection_does_not_probe_verified_project_ports(
    tmp_path, monkeypatch
):
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    probed = []

    def available(_host, port):
        probed.append(port)
        return True

    monkeypatch.setattr(cli.docker, "port_available", available)
    selected = service.select_ports_for_running(
        (8102, 5273), (8101, 5273), frozenset({"backend", "frontend"})
    )
    assert selected == (8102, 5273)
    assert 5273 not in probed


def test_backend_only_stack_owns_only_backend_port(tmp_path, monkeypatch):
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    probed = []

    def available(_host, port):
        probed.append(port)
        return port == 5274

    monkeypatch.setattr(cli.docker, "port_available", available)
    selected = service.select_ports_for_running(
        (8101, 5273), (8101, 5273), frozenset({"backend"})
    )
    assert selected == (8101, 5274)
    assert 8101 not in probed
    assert 5273 in probed


def test_frontend_only_stack_owns_only_frontend_port(tmp_path, monkeypatch):
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    probed = []

    def available(_host, port):
        probed.append(port)
        return port == 8102

    monkeypatch.setattr(cli.docker, "port_available", available)
    selected = service.select_ports_for_running(
        (8101, 5273), (8101, 5273), frozenset({"frontend"})
    )
    assert selected == (8102, 5273)
    assert 5273 not in probed
    assert 8101 in probed


def test_external_status_does_not_claim_no_models_when_count_is_unknown(
    tmp_path, monkeypatch
):
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    current = state(ComfyMode.EXTERNAL, root=None)
    monkeypatch.setattr(cli, "probe_comfyui", lambda _url: ComfyProbe(True, 200, None))
    monkeypatch.setattr(service, "query_comfy_model_count", lambda _port: None)
    monkeypatch.setattr(service, "wait_backend", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(service, "wait_frontend", lambda *_args, **_kwargs: False)

    report = service.status(current, docker_available=False)
    assert report["comfy"]["state"] != "no_models"
    assert report["comfy"]["model_count"] is None
    assert report["comfy"]["model_state"] == "unknown"


def test_external_status_reports_no_models_only_for_confirmed_zero(
    tmp_path, monkeypatch
):
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    current = state(ComfyMode.EXTERNAL, root=None)
    monkeypatch.setattr(cli, "probe_comfyui", lambda _url: ComfyProbe(True, 200, None))
    monkeypatch.setattr(service, "query_comfy_model_count", lambda _port: 0)
    monkeypatch.setattr(service, "wait_backend", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(service, "wait_frontend", lambda *_args, **_kwargs: False)

    report = service.status(current, docker_available=False)
    assert report["comfy"]["state"] == "no_models"
    assert report["comfy"]["model_count"] == 0
    assert report["comfy"]["model_state"] == "confirmed"


def test_external_model_query_can_confirm_an_empty_inventory(tmp_path, monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"CheckpointLoaderSimple":{"input":{"required":{"ckpt_name":[[]]}}}}'

    monkeypatch.setattr(cli, "urlopen", lambda *_args, **_kwargs: Response())
    service = DefaultServices(tmp_path, output_fn=lambda _message: None)
    assert service.query_comfy_model_count(8188) == 0


def test_existing_state_dry_run_honors_reconfiguration_flags_without_mutation(harness):
    old_root = (harness.project_root / "old").resolve()
    new_root = (harness.project_root / "new").resolve()
    harness.loaded_state = state(
        ComfyMode.MANAGED, root=old_root, device=DeviceMode.CPU
    )

    assert main(
        [
            "dry-run",
            "--comfyui-mode",
            "managed",
            "--comfyui-path",
            str(new_root),
            "--device",
            "cpu",
            "--backend-port",
            "8101",
            "--frontend-port",
            "5273",
        ],
        services=harness,
    ) == 0
    output = "\n".join(harness.output)
    assert str(new_root) in output
    assert "8101" in output and "5273" in output
    forbidden = {"write_config", "compose_up", "start_comfyui"}
    assert not forbidden.intersection(harness.events)
