from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from .comfyui import probe_comfyui
from .constants import STATE_SCHEMA_VERSION
from .models import ComfyMode, DeviceMode, HostInfo, LauncherState, ProcessIdentity
from .platforms import read_process_identity
from .runner import Runner


@dataclass(frozen=True)
class ProcessStartResult:
    started: bool
    reason: str
    state: LauncherState | None
    pid: int | None = None


@dataclass(frozen=True)
class ProcessStopResult:
    stopped: bool
    reason: str
    state: LauncherState


def _validate_port(port: int) -> int:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 to 65535")
    return port


def build_comfyui_command(
    root: Path,
    python: Path,
    device: DeviceMode,
    port: int,
) -> list[str]:
    command = [
        str(Path(python)),
        str(Path(root) / "main.py"),
        "--listen",
        "127.0.0.1",
        "--port",
        str(_validate_port(port)),
    ]
    if device is DeviceMode.CPU:
        command.append("--cpu")
    return command


def process_spawn_options(host: HostInfo) -> dict[str, object]:
    if host.system == "Windows":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": detached | new_group | no_window}
    return {"start_new_session": True}


def termination_command(host: HostInfo, pid: int) -> list[str]:
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    if host.system == "Windows":
        return ["taskkill", "/PID", str(pid), "/T", "/F"]
    return ["kill", "-TERM", f"-{pid}"]


def terminate_spawned_process(pid: int, runner: Runner, host: HostInfo) -> bool:
    try:
        result = runner.run(termination_command(host, pid))
    except OSError:
        return False
    return result.returncode == 0


def terminate_if_identity_matches(
    pid: int,
    expected_identity: ProcessIdentity | None,
    runner: Runner,
    host: HostInfo,
) -> str:
    """Terminate only when the live command line still matches the captured child."""
    if not expected_identity:
        return "identity_unavailable"
    current_identity = read_process_identity(host, pid, runner)
    if current_identity is None:
        return "process_not_found"
    if current_identity != expected_identity:
        return "identity_mismatch"
    if not terminate_spawned_process(pid, runner, host):
        return "termination_failed"
    return "terminated"


def _probe_ready(
    probe: Callable[..., object],
    base_url: str,
    timeout: float,
) -> bool:
    try:
        result = probe(base_url, timeout=timeout)
    except (OSError, TimeoutError):
        return False
    if isinstance(result, bool):
        return result
    return bool(getattr(result, "running", False))


def _validate_readiness_timing(timeout: float, interval: float) -> None:
    if timeout <= 0:
        raise ValueError("readiness_timeout must be positive")
    if interval <= 0:
        raise ValueError("poll_interval must be positive")


def _spawn_logged_process(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    host: HostInfo,
    popen: Callable[..., Any],
) -> Any:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        return popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            **process_spawn_options(host),
        )


def start_comfyui(
    *,
    root: Path,
    python: Path,
    device: DeviceMode,
    port: int,
    host: HostInfo,
    runner: Runner,
    project_root: Path,
    probe: Callable[..., object] = probe_comfyui,
    popen: Callable[..., Any] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    readiness_timeout: float = 60.0,
    poll_interval: float = 0.5,
) -> ProcessStartResult:
    root = Path(root).resolve()
    python = Path(python).resolve()
    port = _validate_port(port)
    _validate_readiness_timing(readiness_timeout, poll_interval)
    command = build_comfyui_command(root, python, device, port)
    try:
        process = _spawn_logged_process(
            command,
            cwd=root,
            log_path=Path(project_root).resolve() / "data/logs/comfyui.log",
            host=host,
            popen=popen,
        )
    except OSError:
        return ProcessStartResult(False, "spawn_failed", None)

    pid = getattr(process, "pid", None)
    if type(pid) is not int or pid <= 0:
        return ProcessStartResult(False, "invalid_pid", None)

    if process.poll() is not None:
        return ProcessStartResult(False, "process_exited", None, pid)
    spawned_identity = read_process_identity(host, pid, runner)
    if spawned_identity is None:
        return ProcessStartResult(False, "initial_identity_unavailable", None, pid)
    base_url = f"http://127.0.0.1:{port}"
    deadline = monotonic() + readiness_timeout
    while True:
        if process.poll() is not None:
            return ProcessStartResult(False, "process_exited", None, pid)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        ready = _probe_ready(probe, base_url, min(2.0, remaining))
        if monotonic() >= deadline:
            break
        if ready:
            identity = read_process_identity(host, pid, runner)
            if identity is None:
                terminate_if_identity_matches(pid, spawned_identity, runner, host)
                return ProcessStartResult(False, "identity_unavailable", None, pid)
            if spawned_identity is not None and identity != spawned_identity:
                return ProcessStartResult(
                    False,
                    "process_identity_mismatch",
                    None,
                    pid,
                )
            state = LauncherState(
                schema_version=STATE_SCHEMA_VERSION,
                comfy_mode=ComfyMode.MANAGED,
                comfyui_root=root,
                device=device,
                comfyui_port=port,
                managed_pid=pid,
                managed_identity=identity,
            )
            return ProcessStartResult(True, "ready", state, pid)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(poll_interval, remaining))

    cleanup = terminate_if_identity_matches(pid, spawned_identity, runner, host)
    reason = "readiness_timeout"
    if cleanup != "terminated":
        reason = f"readiness_timeout_cleanup_{cleanup}"
    return ProcessStartResult(False, reason, None, pid)


def _clear_managed_ownership(state: LauncherState) -> LauncherState:
    return replace(state, managed_pid=None, managed_identity=None)


def stop_comfyui(
    state: LauncherState,
    runner: Runner,
    host: HostInfo,
) -> ProcessStopResult:
    if state.comfy_mode is not ComfyMode.MANAGED:
        return ProcessStopResult(False, "external_instance", state)
    if state.managed_pid is None or not isinstance(
        state.managed_identity,
        ProcessIdentity,
    ):
        return ProcessStopResult(False, "no_managed_process", _clear_managed_ownership(state))

    current_identity = read_process_identity(host, state.managed_pid, runner)
    if current_identity is None:
        return ProcessStopResult(False, "process_not_found", _clear_managed_ownership(state))
    if current_identity != state.managed_identity:
        return ProcessStopResult(
            False,
            "process_identity_mismatch",
            _clear_managed_ownership(state),
        )

    termination = terminate_if_identity_matches(
        state.managed_pid,
        state.managed_identity,
        runner,
        host,
    )
    if termination == "identity_mismatch":
        return ProcessStopResult(
            False,
            "process_identity_mismatch",
            _clear_managed_ownership(state),
        )
    if termination == "process_not_found":
        return ProcessStopResult(
            False,
            "process_not_found",
            _clear_managed_ownership(state),
        )
    if termination != "terminated":
        return ProcessStopResult(False, "termination_failed", state)
    return ProcessStopResult(True, "stopped", _clear_managed_ownership(state))


# The plan names this operation explicitly; retain the clearer public alias.
stop_managed_process = stop_comfyui
