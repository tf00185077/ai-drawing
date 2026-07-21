from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

import pytest

from launcher.models import (
    ComfyMode,
    DeviceMode,
    HostInfo,
    LauncherState,
    ProcessIdentity,
)
from launcher.runner import CommandResult
from launcher.processes import (
    build_comfyui_command,
    process_spawn_options,
    start_comfyui,
    stop_comfyui,
)


WINDOWS = HostInfo("Windows", "AMD64", Path("C:/Users/test"))
LINUX = HostInfo("Linux", "x86_64", Path("/home/test"))


def _state(
    mode: ComfyMode,
    *,
    pid: int | None = None,
    identity: ProcessIdentity | str | None = None,
) -> LauncherState:
    return LauncherState(
        schema_version=1,
        comfy_mode=mode,
        comfyui_root=Path("/opt/ComfyUI"),
        device=DeviceMode.CPU,
        comfyui_port=8188,
        managed_pid=pid,
        managed_identity=identity,
    )


def _identity(
    command_line: str = "python main.py --port 8188",
    *,
    executable: str = "/venv/bin/python",
    started_at: str = "123456",
) -> ProcessIdentity:
    return ProcessIdentity(executable, started_at, command_line)


class FakeRunner:
    def __init__(
        self,
        identity: ProcessIdentity | None = None,
        terminate_code: int = 0,
    ):
        self.identity = identity
        self.terminate_code = terminate_code
        self.commands: list[list[str]] = []

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        is_identity = command[0] not in {"kill", "taskkill"}
        if is_identity:
            return CommandResult(
                args=tuple(command),
                returncode=0 if self.identity is not None else 1,
                stdout=(
                    json.dumps(asdict(self.identity)) + "\n"
                    if self.identity is not None
                    else ""
                ),
                stderr="",
            )
        return CommandResult(
            args=tuple(command),
            returncode=self.terminate_code,
            stdout="",
            stderr="",
        )


class SequencedIdentityRunner(FakeRunner):
    def __init__(self, identities: list[ProcessIdentity | None]):
        super().__init__()
        self.identities = iter(identities)

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = [str(arg) for arg in args]
        self.commands.append(command)
        if command[0] not in {"kill", "taskkill"}:
            identity = next(self.identities)
            return CommandResult(
                args=tuple(command),
                returncode=0 if identity is not None else 1,
                stdout=json.dumps(asdict(identity)) + "\n" if identity else "",
                stderr="",
            )
        return CommandResult(tuple(command), 0, "", "")


@dataclass
class FakeProcess:
    pid: int = 4242
    returncode: int | None = None

    def poll(self):
        return self.returncode


class CleanupHandleProcess(FakeProcess):
    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode
        self.cleanup_calls: list[object] = []
        self.wait_count = 0

    def terminate(self):
        self.cleanup_calls.append("terminate")
        if self.mode == "failed":
            raise OSError("terminate failed")

    def wait(self, timeout):
        self.cleanup_calls.append(("wait", timeout))
        self.wait_count += 1
        if self.mode == "killed" and self.wait_count == 1:
            raise subprocess.TimeoutExpired("fake-child", timeout)
        if self.mode == "failed":
            raise subprocess.TimeoutExpired("fake-child", timeout)
        self.returncode = 0
        return 0

    def kill(self):
        self.cleanup_calls.append("kill")
        if self.mode == "failed":
            raise OSError("kill failed")


class FakePopen:
    def __init__(self, process: FakeProcess | None = None):
        self.process = process or FakeProcess()
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(([str(arg) for arg in args], kwargs))
        return self.process


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.now += duration


def test_comfyui_command_adds_cpu_only_for_cpu(tmp_path):
    root = tmp_path / "Comfy UI"
    python = root / ".venv" / "bin" / "python"

    cpu = build_comfyui_command(root, python, DeviceMode.CPU, 8188)
    nvidia = build_comfyui_command(root, python, DeviceMode.NVIDIA, 8188)
    mps = build_comfyui_command(root, python, DeviceMode.MPS, 8188)

    assert cpu == [
        str(python),
        str(root / "main.py"),
        "--listen",
        "127.0.0.1",
        "--port",
        "8188",
        "--cpu",
    ]
    assert "--cpu" not in nvidia
    assert "--cpu" not in mps


def test_windows_spawn_is_hidden_and_detached():
    options = process_spawn_options(WINDOWS)

    assert options["creationflags"] != 0
    assert "start_new_session" not in options


def test_unix_spawn_uses_new_session():
    options = process_spawn_options(LINUX)

    assert options["start_new_session"] is True
    assert "creationflags" not in options


def test_ready_process_records_managed_state_only_after_probe(tmp_path):
    root = tmp_path / "ComfyUI"
    python = root / ".venv" / "bin" / "python"
    popen = FakePopen()
    runner = FakeRunner(
        identity=_identity(
            f"{python} {root / 'main.py'} --port 8188",
            executable=str(python),
        )
    )
    probe_calls: list[str] = []

    def probe(url: str, timeout: float):
        probe_calls.append(url)
        return len(probe_calls) == 2

    result = start_comfyui(
        root=root,
        python=python,
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=probe,
        popen=popen,
        sleep=lambda _: None,
        readiness_timeout=1,
        poll_interval=0.1,
    )

    assert result.started is True
    assert result.reason == "ready"
    assert len(probe_calls) == 2
    assert result.state is not None
    assert result.state.comfy_mode is ComfyMode.MANAGED
    assert result.state.managed_pid == 4242
    assert result.state.managed_identity == runner.identity
    args, options = popen.calls[0]
    assert args[-1] == "--cpu"
    assert options["start_new_session"] is True


def test_readiness_timeout_does_not_record_state_and_cleans_up(tmp_path):
    root = tmp_path / "ComfyUI"
    python = root / ".venv" / "bin" / "python"
    popen = FakePopen()
    runner = FakeRunner(
        identity=_identity(
            f"{python} {root / 'main.py'} --port 8188",
            executable=str(python),
        )
    )

    result = start_comfyui(
        root=root,
        python=python,
        device=DeviceMode.NVIDIA,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=lambda *_args, **_kwargs: False,
        popen=popen,
        sleep=lambda _: None,
        readiness_timeout=0.2,
        poll_interval=0.1,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout"
    assert result.state is None
    assert len(runner.commands) == 3
    assert runner.commands[-1] == ["kill", "-TERM", "-4242"]


def test_timeout_cleanup_refuses_to_kill_reused_pid(tmp_path):
    root = tmp_path / "ComfyUI"
    python = root / ".venv" / "bin" / "python"
    runner = SequencedIdentityRunner(
        [
            _identity(
                f"{python} {root / 'main.py'} --port 8188",
                executable=str(python),
            ),
            _identity("unrelated --server", executable="/usr/bin/unrelated"),
        ]
    )

    result = start_comfyui(
        root=root,
        python=python,
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=lambda *_args, **_kwargs: False,
        popen=FakePopen(),
        sleep=lambda _: None,
        readiness_timeout=0.1,
        poll_interval=0.1,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout_cleanup_identity_mismatch"
    assert all(command[0] != "kill" for command in runner.commands)


def test_initial_identity_capture_failure_terminates_exact_popen_handle(tmp_path):
    probes: list[str] = []
    runner = FakeRunner(identity=None)
    process = CleanupHandleProcess("terminated")

    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=lambda url, **_kwargs: probes.append(url) or True,
        popen=FakePopen(process),
    )

    assert result.started is False
    assert result.reason == "initial_identity_unavailable_cleanup_terminated"
    assert result.state is None
    assert result.pid == 4242
    assert probes == []
    assert len(runner.commands) == 1
    assert process.cleanup_calls == ["terminate", ("wait", 2.0)]


def test_initial_identity_cleanup_timeout_kills_only_exact_popen_handle(tmp_path):
    runner = FakeRunner(identity=None)
    process = CleanupHandleProcess("killed")

    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=lambda *_args, **_kwargs: True,
        popen=FakePopen(process),
    )

    assert result.reason == "initial_identity_unavailable_cleanup_killed"
    assert result.state is None
    assert result.pid == 4242
    assert process.cleanup_calls == [
        "terminate",
        ("wait", 2.0),
        "kill",
        ("wait", 2.0),
    ]
    assert all(command[0] not in {"kill", "taskkill"} for command in runner.commands)


def test_initial_identity_cleanup_failure_reports_spawned_pid_without_state(tmp_path):
    runner = FakeRunner(identity=None)
    process = CleanupHandleProcess("failed")

    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=lambda *_args, **_kwargs: True,
        popen=FakePopen(process),
    )

    assert result.reason == "initial_identity_unavailable_cleanup_failed"
    assert result.state is None
    assert result.pid == 4242
    assert process.poll() is None
    assert process.cleanup_calls == ["terminate", "kill"]
    assert all(command[0] not in {"kill", "taskkill"} for command in runner.commands)


def test_comfyui_readiness_uses_real_monotonic_deadline(tmp_path):
    clock = FakeClock()
    probe_timeouts: list[float] = []
    runner = FakeRunner(identity=_identity())

    def probe(_url: str, timeout: float):
        probe_timeouts.append(timeout)
        if len(probe_timeouts) == 2:
            clock.now += timeout
        return False

    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=probe,
        popen=FakePopen(),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        readiness_timeout=2.5,
        poll_interval=1.0,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout"
    assert probe_timeouts == [2.0, 1.5]
    assert clock.sleeps == [1.0]
    assert clock.now == 2.5
    assert runner.commands[-1] == ["kill", "-TERM", "-4242"]


def test_probe_success_after_deadline_is_timeout_not_owned(tmp_path):
    clock = FakeClock()
    runner = FakeRunner(identity=_identity())

    def slow_probe(_url: str, timeout: float):
        clock.now += timeout
        return True

    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=LINUX,
        runner=runner,
        project_root=tmp_path,
        probe=slow_probe,
        popen=FakePopen(),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        readiness_timeout=0.25,
        poll_interval=0.1,
    )

    assert result.started is False
    assert result.reason == "readiness_timeout"
    assert result.state is None
    assert clock.now == 0.25


def test_exited_process_fails_without_waiting_for_timeout(tmp_path):
    popen = FakePopen(FakeProcess(returncode=3))
    result = start_comfyui(
        root=tmp_path / "ComfyUI",
        python=tmp_path / "python",
        device=DeviceMode.CPU,
        port=8188,
        host=WINDOWS,
        runner=FakeRunner(),
        project_root=tmp_path,
        probe=lambda *_args, **_kwargs: False,
        popen=popen,
        sleep=lambda _: pytest.fail("must not sleep after the child exits"),
    )

    assert result.started is False
    assert result.reason == "process_exited"
    assert result.state is None


def test_external_is_never_stopped():
    runner = FakeRunner(identity=_identity())

    result = stop_comfyui(_state(ComfyMode.EXTERNAL), runner, LINUX)

    assert result.stopped is False
    assert result.reason == "external_instance"
    assert runner.commands == []


def test_pid_reuse_is_not_terminated_and_stale_ownership_is_cleared():
    runner = FakeRunner(identity=_identity("unrelated.exe --serve"))
    state = _state(
        ComfyMode.MANAGED,
        pid=42,
        identity=_identity(),
    )

    result = stop_comfyui(state, runner, WINDOWS)

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert len(runner.commands) == 1
    assert result.state.managed_pid is None
    assert result.state.managed_identity is None


def test_pid_reuse_between_identity_check_and_signal_is_not_terminated():
    identity = _identity()
    runner = SequencedIdentityRunner(
        [identity, _identity("unrelated --server", executable="/usr/bin/unrelated")]
    )

    result = stop_comfyui(
        _state(ComfyMode.MANAGED, pid=42, identity=identity),
        runner,
        LINUX,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert all(command[0] != "kill" for command in runner.commands)
    assert result.state.managed_pid is None


@pytest.mark.parametrize(
    "replacement",
    [
        _identity(started_at="654321"),
        _identity(executable="/different/python"),
    ],
)
def test_identical_command_line_with_different_process_instance_is_not_terminated(
    replacement,
):
    identity = _identity()
    runner = FakeRunner(identity=replacement)

    result = stop_comfyui(
        _state(ComfyMode.MANAGED, pid=42, identity=identity),
        runner,
        LINUX,
    )

    assert result.stopped is False
    assert result.reason == "process_identity_mismatch"
    assert len(runner.commands) == 1


def test_missing_process_clears_stale_ownership_without_termination():
    runner = FakeRunner(identity=None)
    state = _state(
        ComfyMode.MANAGED,
        pid=42,
        identity=_identity(),
    )

    result = stop_comfyui(state, runner, LINUX)

    assert result.stopped is False
    assert result.reason == "process_not_found"
    assert len(runner.commands) == 1
    assert result.state.managed_pid is None


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (WINDOWS, ["taskkill", "/PID", "42", "/T", "/F"]),
        (LINUX, ["kill", "-TERM", "-42"]),
    ],
)
def test_managed_identity_match_terminates_owned_process(host, expected):
    identity = _identity("python main.py --listen 127.0.0.1 --port 8188")
    runner = FakeRunner(identity=identity)

    result = stop_comfyui(
        _state(ComfyMode.MANAGED, pid=42, identity=identity),
        runner,
        host,
    )

    assert result.stopped is True
    assert result.reason == "stopped"
    assert runner.commands[-1] == expected
    assert result.state.managed_pid is None
