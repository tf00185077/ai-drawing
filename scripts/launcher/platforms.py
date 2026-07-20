from __future__ import annotations

import os
import platform
from pathlib import Path

from .models import DeviceMode, HostInfo
from .runner import Runner


def detect_host(
    system: str | None = None,
    machine: str | None = None,
    home: Path | None = None,
) -> HostInfo:
    return HostInfo(
        system=system if system is not None else platform.system(),
        machine=machine if machine is not None else platform.machine(),
        home=Path(home) if home is not None else Path.home(),
    )


def nvidia_available(runner: Runner) -> bool:
    try:
        return runner.run(["nvidia-smi"]).returncode == 0
    except OSError:
        return False


def choose_device(host: HostInfo, nvidia_available: bool) -> DeviceMode:
    if host.system in {"Windows", "Linux"} and nvidia_available:
        return DeviceMode.NVIDIA
    if host.system == "Darwin" and host.machine.lower() == "arm64":
        return DeviceMode.MPS
    return DeviceMode.CPU


def default_comfyui_root(
    host: HostInfo,
    xdg_data_home: Path | None = None,
) -> Path:
    if host.system == "Windows":
        data_root = host.home / "AppData" / "Local"
    elif host.system == "Darwin":
        data_root = host.home / "Library" / "Application Support"
    else:
        configured_xdg_data_home = xdg_data_home or os.environ.get("XDG_DATA_HOME")
        data_root = (
            Path(configured_xdg_data_home)
            if configured_xdg_data_home
            else host.home / ".local" / "share"
        )
    return data_root / "ai-drawing" / "ComfyUI"


def comfyui_python_candidates(root: Path, host: HostInfo) -> tuple[Path, ...]:
    if host.system == "Windows":
        return (
            root / ".venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python.exe",
            root / "python_embeded" / "python.exe",
        )
    return (
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python",
    )


def process_identity_command(system: str, pid: int) -> list[str]:
    if system == "Windows":
        return [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
        ]
    return ["ps", "-p", str(pid), "-o", "command="]


def read_process_identity(host: HostInfo, pid: int, runner: Runner) -> str | None:
    try:
        result = runner.run(process_identity_command(host.system, pid))
    except OSError:
        return None
    if result.returncode != 0:
        return None
    identity = result.stdout.strip()
    return identity or None
