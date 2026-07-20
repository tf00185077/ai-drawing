from pathlib import Path

import pytest

from launcher.models import DeviceMode, HostInfo, ProcessIdentity
from launcher.platforms import (
    choose_device,
    comfyui_python_candidates,
    default_comfyui_root,
    detect_host,
    nvidia_available,
    process_identity_command,
    read_process_identity,
)
from launcher.runner import CommandResult


class FakeRunner:
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.calls: list[tuple[str, ...]] = []

    def run(self, args, **_kwargs) -> CommandResult:
        self.calls.append(tuple(args))
        return self.result


def test_detect_host_uses_injected_values():
    assert detect_host("Linux", "x86_64", Path("/home/test")) == HostInfo(
        "Linux", "x86_64", Path("/home/test")
    )


def test_windows_nvidia_uses_nvidia_device():
    host = HostInfo("Windows", "AMD64", Path("C:/Users/Test User"))

    assert choose_device(host, nvidia_available=True) is DeviceMode.NVIDIA


def test_linux_nvidia_uses_nvidia_device():
    host = HostInfo("Linux", "x86_64", Path("/home/test"))

    assert choose_device(host, nvidia_available=True) is DeviceMode.NVIDIA


def test_apple_silicon_uses_mps():
    host = HostInfo("Darwin", "arm64", Path("/Users/test"))

    assert choose_device(host, nvidia_available=False) is DeviceMode.MPS
    assert default_comfyui_root(host) == Path(
        "/Users/test/Library/Application Support/ai-drawing/ComfyUI"
    )


def test_intel_macos_uses_cpu():
    host = HostInfo("Darwin", "x86_64", Path("/Users/test"))

    assert choose_device(host, nvidia_available=True) is DeviceMode.CPU


def test_rosetta_translation_is_rejected_with_stable_diagnostic(tmp_path):
    from launcher.cli import DefaultServices, LauncherError

    result = CommandResult(
        ("sysctl", "-in", "sysctl.proc_translated"), 0, "1\n", ""
    )
    runner = FakeRunner(result)
    services = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)
    services.host = HostInfo("Darwin", "x86_64", Path("/Users/test"))

    with pytest.raises(LauncherError) as caught:
        services.detect_device()

    assert caught.value.code == "UNSUPPORTED_NATIVE_ARCHITECTURE"
    assert "arm64" in caught.value.hint
    assert runner.calls == [("sysctl", "-in", "sysctl.proc_translated")]


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(0, "0\n"), (1, "")],
)
def test_native_or_unqueryable_intel_macos_remains_cpu(tmp_path, returncode, stdout):
    from launcher.cli import DefaultServices

    command = ("sysctl", "-in", "sysctl.proc_translated")
    runner = FakeRunner(CommandResult(command, returncode, stdout, ""))
    services = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)
    services.host = HostInfo("Darwin", "x86_64", Path("/Users/test"))

    assert services.detect_device() is DeviceMode.CPU
    assert runner.calls == [command]


def test_native_apple_silicon_does_not_query_rosetta(tmp_path):
    from launcher.cli import DefaultServices

    runner = FakeRunner(CommandResult(("unused",), 1, "", ""))
    services = DefaultServices(tmp_path, runner=runner, output_fn=lambda _message: None)
    services.host = HostInfo("Darwin", "arm64", Path("/Users/test"))

    assert services.detect_device() is DeviceMode.MPS
    assert runner.calls == []


def test_linux_without_nvidia_uses_cpu():
    host = HostInfo("Linux", "x86_64", Path("/home/test"))

    assert choose_device(host, nvidia_available=False) is DeviceMode.CPU


def test_linux_default_root_uses_xdg_data_home_with_unicode_and_spaces():
    host = HostInfo("Linux", "x86_64", Path("/home/Test User"))

    assert default_comfyui_root(
        host, Path("/data/使用者 資料")
    ) == Path("/data/使用者 資料/ai-drawing/ComfyUI")


def test_linux_default_root_falls_back_to_local_share():
    host = HostInfo("Linux", "x86_64", Path("/home/Test User"))

    assert default_comfyui_root(host) == Path(
        "/home/Test User/.local/share/ai-drawing/ComfyUI"
    )


def test_windows_default_root_uses_local_app_data():
    host = HostInfo("Windows", "AMD64", Path("C:/Users/Test User"))

    assert default_comfyui_root(host) == Path(
        "C:/Users/Test User/AppData/Local/ai-drawing/ComfyUI"
    )


def test_unix_python_candidates_include_dot_venv_and_venv_in_order():
    root = Path("/opt/Comfy UI")
    host = HostInfo("Linux", "x86_64", Path("/home/test"))

    assert comfyui_python_candidates(root, host) == (
        root / ".venv/bin/python",
        root / "venv/bin/python",
    )


def test_windows_python_candidates_include_virtualenvs_and_portable_python():
    root = Path("C:/Comfy UI")
    host = HostInfo("Windows", "AMD64", Path("C:/Users/test"))

    assert comfyui_python_candidates(root, host) == (
        root / ".venv/Scripts/python.exe",
        root / "venv/Scripts/python.exe",
        root / "python_embeded/python.exe",
    )


def test_nvidia_available_runs_nvidia_smi():
    runner = FakeRunner(CommandResult(("nvidia-smi",), 0, "GPU", ""))

    assert nvidia_available(runner) is True
    assert runner.calls == [("nvidia-smi",)]


def test_nvidia_available_returns_false_when_command_fails():
    runner = FakeRunner(CommandResult(("nvidia-smi",), 1, "", "not found"))

    assert nvidia_available(runner) is False


def test_process_identity_commands_are_platform_specific():
    windows = process_identity_command("Windows", 42)
    linux = process_identity_command("Linux", 42)

    assert windows[:3] == ["powershell", "-NoProfile", "-Command"]
    assert "ExecutablePath" in windows[3]
    assert "CreationDate" in windows[3]
    assert "CommandLine" in windows[3]
    assert linux[-2:] == ["Linux", "42"]
    assert "python" in Path(linux[0]).name.lower()


@pytest.mark.parametrize("pid", [True, "42; Remove-Item C:\\", 0, -1])
def test_process_identity_command_rejects_non_positive_builtin_integer_pids(pid):
    with pytest.raises(ValueError, match="positive integer"):
        process_identity_command("Windows", pid)


def test_read_process_identity_parses_full_process_instance():
    host = HostInfo("Linux", "x86_64", Path("/home/test"))
    payload = (
        '{"executable":"/venv/bin/python","started_at":"123456",'
        '"command_line":"python main.py --port 8188"}\n'
    )
    runner = FakeRunner(CommandResult(("python",), 0, payload, ""))

    assert read_process_identity(host, 42, runner) == ProcessIdentity(
        executable="/venv/bin/python",
        started_at="123456",
        command_line="python main.py --port 8188",
    )
    assert runner.calls[0][-2:] == ("Linux", "42")


def test_read_process_identity_returns_none_for_failed_or_empty_command():
    host = HostInfo("Linux", "x86_64", Path("/home/test"))
    failed = FakeRunner(CommandResult(("ps",), 1, "", "no process"))
    empty = FakeRunner(CommandResult(("ps",), 0, " \n", ""))

    assert read_process_identity(host, 42, failed) is None
    assert read_process_identity(host, 42, empty) is None


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        '{"executable":"python","started_at":"","command_line":"python"}',
    ],
)
def test_read_process_identity_rejects_incomplete_payload(payload):
    host = HostInfo("Linux", "x86_64", Path("/home/test"))
    runner = FakeRunner(CommandResult(("python",), 0, payload, ""))

    assert read_process_identity(host, 42, runner) is None
