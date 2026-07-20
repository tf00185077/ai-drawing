from __future__ import annotations

import os
import platform
import json
import sys
from pathlib import Path

from .models import DeviceMode, HostInfo, ProcessIdentity
from .runner import Runner


class UnsupportedNativeArchitecture(RuntimeError):
    """Raised when Apple Silicon is running this launcher through Rosetta."""

    code = "UNSUPPORTED_NATIVE_ARCHITECTURE"
    message = "偵測到 Rosetta/x86_64 程序，無法安全設定 Apple Silicon runtime。"
    hint = "請關閉目前終端，改用原生 arm64 終端後重新執行。"


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


def ensure_native_macos_architecture(host: HostInfo, runner: Runner) -> None:
    """Reject translated Apple Silicon while allowing native Intel macOS."""
    if host.system != "Darwin" or host.machine.lower() != "x86_64":
        return
    command = ["sysctl", "-in", "sysctl.proc_translated"]
    try:
        result = runner.run(command)
    except OSError:
        return
    if result.returncode == 0 and result.stdout.strip() == "1":
        raise UnsupportedNativeArchitecture(UnsupportedNativeArchitecture.message)


def detect_device(host: HostInfo, runner: Runner) -> DeviceMode:
    """Detect an explicit runtime mode without silently accepting Rosetta."""
    ensure_native_macos_architecture(host, runner)
    has_nvidia = (
        nvidia_available(runner) if host.system in {"Windows", "Linux"} else False
    )
    return choose_device(host, has_nvidia)


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
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    if system == "Windows":
        script = (
            f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}';"
            "if ($null -ne $p) {"
            "@{executable=$p.ExecutablePath;"
            "started_at=$p.CreationDate.ToUniversalTime().ToString('o');"
            "command_line=$p.CommandLine} | ConvertTo-Json -Compress}"
        )
        return [
            "powershell",
            "-NoProfile",
            "-Command",
            script,
        ]
    helper = r'''
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

system, raw_pid = sys.argv[1:]
pid = int(raw_pid)
if system == "Linux":
    proc = Path("/proc") / str(pid)
    def start_token():
        tail = (proc / "stat").read_text(encoding="utf-8").rpartition(")")[2]
        ticks = tail.split()[19]
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        return f"{boot_id}:{ticks}"
    before = start_token()
    executable = os.readlink(proc / "exe")
    command_line = " ".join(
        os.fsdecode(part) for part in (proc / "cmdline").read_bytes().split(b"\0") if part
    )
    after = start_token()
else:
    def ps(field):
        return subprocess.run(
            ["ps", "-p", str(pid), "-o", f"{field}="],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    before = ps("lstart")
    buffer = ctypes.create_string_buffer(4096)
    libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
    length = libproc.proc_pidpath(pid, buffer, len(buffer))
    executable = os.fsdecode(buffer.raw[:length]) if length > 0 else ""
    command_line = ps("command")
    after = ps("lstart")
if before == after and executable and command_line:
    print(json.dumps({
        "executable": executable,
        "started_at": before,
        "command_line": command_line,
    }))
'''
    return [sys.executable, "-c", helper, system, str(pid)]


def read_process_identity(
    host: HostInfo,
    pid: int,
    runner: Runner,
) -> ProcessIdentity | None:
    try:
        result = runner.run(process_identity_command(host.system, pid))
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return ProcessIdentity.from_value(payload)
