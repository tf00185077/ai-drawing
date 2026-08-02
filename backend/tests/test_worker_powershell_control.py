from __future__ import annotations

import subprocess
import threading
import time
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


WORKER_WINDOWS_ROOT = Path(__file__).resolve().parents[2] / "worker" / "windows"
from worker.windows import powershell_control
from worker.windows.powershell_control import (
    PowerShellCommandManager,
    PowerShellCommandNotFound,
)


class FakePowerShellCommandManager:
    def __init__(self, not_found: type[Exception]) -> None:
        self._not_found = not_found
        self.submitted: dict[str, str | None] | None = None
        self._records = {
            "cmd-1": {
                "command_id": "cmd-1",
                "state": "running",
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "created_at": "2026-08-02T00:00:00+00:00",
                "started_at": "2026-08-02T00:00:00+00:00",
                "finished_at": None,
            }
        }

    def submit(self, *, script: str, working_directory: str | None) -> dict[str, object]:
        self.submitted = {
            "script": script,
            "working_directory": working_directory,
        }
        return dict(self._records["cmd-1"])

    def get(self, command_id: str) -> dict[str, object]:
        try:
            return dict(self._records[command_id])
        except KeyError as error:
            raise self._not_found(command_id) from error

    def cancel(self, command_id: str) -> dict[str, object]:
        record = self.get(command_id)
        record["state"] = "cancelled"
        self._records[command_id] = record
        return dict(record)


def _worker_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "deployed"
    config = root / "config" / "worker.json"
    comfy = root / "runtime" / "ComfyUI"
    partial = root / "cache" / ".partial"
    verification = root / "cache" / "verified"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"token": "secret"}), encoding="utf-8")
    (comfy / "models").mkdir(parents=True)
    partial.mkdir(parents=True)
    verification.mkdir()
    for name, value in {
        "AI_DRAWING_WORKER_ROOT": root,
        "AI_DRAWING_WORKER_RELEASE_ROOT": root,
        "AI_DRAWING_WORKER_CONFIG_PATH": config,
        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT": root,
        "AI_DRAWING_COMFYUI_ROOT": comfy,
        "AI_DRAWING_WORKER_PARTIAL_ROOT": partial,
        "AI_DRAWING_WORKER_VERIFICATION_ROOT": verification,
    }.items():
        monkeypatch.setenv(name, str(value))
    worker_path = WORKER_WINDOWS_ROOT / "worker.py"
    spec = importlib.util.spec_from_file_location("worker_powershell_routes", worker_path)
    assert spec is not None and spec.loader is not None
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker, TestClient(worker.app)


def wait_for_terminal(manager: PowerShellCommandManager, command_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        command = manager.get(command_id)
        if command["state"] in {"completed", "failed", "cancelled"}:
            return command
        time.sleep(0.01)
    raise AssertionError(f"command {command_id} did not become terminal")


def wait_for_process(factory: "FakeProcessFactory") -> FakeProcess:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if factory.processes:
            return factory.processes[0]
        time.sleep(0.01)
    raise AssertionError("command process was not created")


class FakeProcess:
    def __init__(self, factory: "FakeProcessFactory") -> None:
        self._factory = factory
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def communicate(self, input: str | None = None) -> tuple[str, str]:
        self._factory.script = input
        self._factory._released.wait(timeout=2)
        self.returncode = self._factory.returncode
        return self._factory.stdout, self._factory.stderr

    def terminate(self) -> None:
        self.terminated = True
        if self._factory.terminate_exits:
            self._factory.release(returncode=-15)

    def kill(self) -> None:
        self.killed = True
        self._factory.release(returncode=-9)

    def wait(self, timeout: float | None = None) -> int | None:
        self._factory.wait_timeouts.append(timeout)
        if self._factory.wait_times_out and not self.killed:
            raise subprocess.TimeoutExpired("powershell.exe", timeout)
        if not self._factory._released.wait(timeout):
            raise subprocess.TimeoutExpired("powershell.exe", timeout)
        self.returncode = self._factory.returncode
        return self.returncode


class FakeProcessFactory:
    def __init__(self, *, terminate_exits: bool = True, wait_times_out: bool = False) -> None:
        self.argv: list[str] | None = None
        self.cwd: str | None = None
        self.script: str | None = None
        self.stdout = ""
        self.stderr = ""
        self.returncode = 0
        self.processes: list[FakeProcess] = []
        self.terminate_exits = terminate_exits
        self.wait_times_out = wait_times_out
        self.wait_timeouts: list[float | None] = []
        self.kwargs: dict[str, object] | None = None
        self._released = threading.Event()

    def __call__(self, argv: list[str], **kwargs: object) -> FakeProcess:
        self.argv = argv
        self.kwargs = dict(kwargs)
        self.cwd = kwargs["cwd"]  # type: ignore[assignment,index]
        process = FakeProcess(self)
        self.processes.append(process)
        return process

    def release(self, *, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self._released.set()


class DelayedCaptureProcess(FakeProcess):
    def communicate(self, input: str | None = None) -> tuple[str, str]:
        self._factory.script = input
        assert isinstance(self._factory, DelayedCaptureFactory)
        assert self._factory.capture_release.wait(timeout=2)
        self.returncode = self._factory.returncode
        return self._factory.stdout, self._factory.stderr

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout: float | None = None) -> int | None:
        self._factory.wait_timeouts.append(timeout)
        return self.returncode


class DelayedCaptureFactory(FakeProcessFactory):
    def __init__(self, *, block_registration: bool = False) -> None:
        super().__init__(terminate_exits=False)
        self.block_registration = block_registration
        self.factory_entered = threading.Event()
        self.registration_release = threading.Event()
        self.capture_release = threading.Event()

    def __call__(self, argv: list[str], **kwargs: object) -> DelayedCaptureProcess:
        self.factory_entered.set()
        if self.block_registration:
            assert self.registration_release.wait(timeout=2)
        self.argv = argv
        self.kwargs = dict(kwargs)
        self.cwd = kwargs["cwd"]  # type: ignore[assignment,index]
        process = DelayedCaptureProcess(self)
        self.processes.append(process)
        return process


def wait_for_capture_cleanup(
    manager: PowerShellCommandManager, command_id: str
) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with manager._lock:
            active = (
                command_id in manager._processes
                or command_id in manager._cancelled
                or command_id in manager._terminating
            )
        if not active:
            return manager.get(command_id)
        time.sleep(0.01)
    raise AssertionError(f"command {command_id} did not finish output capture")


def test_submit_runs_script_with_fixed_powershell_contract() -> None:
    factory = FakeProcessFactory()
    manager = PowerShellCommandManager(process_factory=factory, max_terminal_records=2)

    command = manager.submit(
        script="Get-ChildItem C:\\\nWrite-Output '完成'",
        working_directory=r"D:\code\ai-drawing",
    )

    assert command["state"] == "running"
    factory.release(returncode=0, stdout="完成\n", stderr="")
    terminal = wait_for_terminal(manager, command["command_id"])
    assert terminal["state"] == "completed"
    assert terminal["exit_code"] == 0
    assert factory.script == "Get-ChildItem C:\\\nWrite-Output '完成'"
    assert factory.cwd == r"D:\code\ai-drawing"
    assert factory.argv == [
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$Utf8 = New-Object System.Text.UTF8Encoding($false, $true); "
            "[Console]::InputEncoding = $Utf8; "
            "[Console]::OutputEncoding = $Utf8; "
            "$OutputEncoding = $Utf8; "
            "$Source = [Console]::In.ReadToEnd(); "
            "& ([ScriptBlock]::Create($Source))"
        ),
    ]
    assert factory.kwargs is not None
    assert factory.kwargs["text"] is True
    assert factory.kwargs["encoding"] == "utf-8"
    assert factory.kwargs["errors"] == "strict"
    assert factory.kwargs["shell"] is False


def test_nonzero_exit_marks_command_failed() -> None:
    factory = FakeProcessFactory()
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="exit 1", working_directory=None)

    factory.release(returncode=1, stdout="", stderr="failed")

    terminal = wait_for_terminal(manager, command["command_id"])
    assert terminal["state"] == "failed"
    assert terminal["exit_code"] == 1
    assert terminal["stderr"] == "failed"


def test_cancel_terminates_running_command_and_preserves_cancelled_state() -> None:
    factory = FakeProcessFactory()
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="Start-Sleep 99", working_directory=None)
    process = wait_for_process(factory)

    cancelled = manager.cancel(command["command_id"])

    assert cancelled["command_id"] == command["command_id"]
    assert cancelled["state"] == "cancelled"
    assert isinstance(cancelled["finished_at"], str) and cancelled["finished_at"]
    terminal = wait_for_terminal(manager, command["command_id"])
    assert terminal["state"] == "cancelled"
    assert process.terminated is True


def test_cancel_before_process_registration_returns_one_terminal_cancelled_state() -> None:
    factory = DelayedCaptureFactory(block_registration=True)
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="Write-Output late", working_directory=None)
    assert factory.factory_entered.wait(timeout=2)

    cancelled = manager.cancel(command["command_id"])

    assert cancelled["state"] == "cancelled"
    finished_at = cancelled["finished_at"]
    factory.returncode = 0
    factory.stdout = "late output"
    factory.registration_release.set()
    process = wait_for_process(factory)
    assert process.terminated is True
    factory.capture_release.set()
    captured = wait_for_capture_cleanup(manager, command["command_id"])
    assert captured["state"] == "cancelled"
    assert captured["finished_at"] == finished_at
    assert captured["stdout"] == "late output"
    assert list(manager._terminal_order).count(command["command_id"]) == 1


def test_cancel_after_process_registration_returns_before_delayed_capture() -> None:
    factory = DelayedCaptureFactory()
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="Write-Output late", working_directory=None)
    process = wait_for_process(factory)

    cancelled = manager.cancel(command["command_id"])

    assert cancelled["state"] == "cancelled"
    assert process.terminated is True
    finished_at = cancelled["finished_at"]
    factory.returncode = 0
    factory.stdout = "captured after cancel"
    factory.capture_release.set()
    captured = wait_for_capture_cleanup(manager, command["command_id"])
    assert captured["state"] == "cancelled"
    assert captured["finished_at"] == finished_at
    assert captured["stdout"] == "captured after cancel"
    assert list(manager._terminal_order).count(command["command_id"]) == 1


def test_cancel_kills_process_after_terminate_wait_times_out() -> None:
    factory = FakeProcessFactory(terminate_exits=False, wait_times_out=True)
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="Start-Sleep 99", working_directory=None)
    process = wait_for_process(factory)

    try:
        manager.cancel(command["command_id"])
        assert process.terminated is True
        assert factory.wait_timeouts == [5]
        assert process.killed is True
    finally:
        factory.release(returncode=-9)

    assert wait_for_terminal(manager, command["command_id"])["state"] == "cancelled"


def test_submit_returns_running_snapshot_when_worker_finishes_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    class InlineThread:
        def __init__(self, *, target: object, args: tuple[object, ...], daemon: bool) -> None:
            self._target = target
            self._args = args

        def start(self) -> None:
            self._target(*self._args)  # type: ignore[operator]

    monkeypatch.setattr(powershell_control.threading, "Thread", InlineThread)
    factory = FakeProcessFactory()
    factory.release(returncode=0)
    manager = PowerShellCommandManager(process_factory=factory)

    submitted = manager.submit(script="Write-Output done", working_directory=None)

    assert submitted["state"] == "running"
    assert manager.get(submitted["command_id"])["state"] == "completed"


def test_unknown_command_raises_not_found() -> None:
    manager = PowerShellCommandManager(process_factory=FakeProcessFactory())

    with pytest.raises(PowerShellCommandNotFound):
        manager.get("does-not-exist")

    with pytest.raises(PowerShellCommandNotFound):
        manager.cancel("does-not-exist")


def test_command_timestamps_are_nonempty_utc_iso_strings() -> None:
    factory = FakeProcessFactory()
    manager = PowerShellCommandManager(process_factory=factory)
    command = manager.submit(script="Write-Output done", working_directory=None)
    factory.release(returncode=0)

    terminal = wait_for_terminal(manager, command["command_id"])
    for field in ("created_at", "started_at", "finished_at"):
        timestamp = terminal[field]
        assert isinstance(timestamp, str) and timestamp
        assert datetime.fromisoformat(timestamp).tzinfo == timezone.utc


def test_terminal_retention_evicts_oldest_terminal_but_keeps_running_command() -> None:
    running_factory = FakeProcessFactory()
    first_factory = FakeProcessFactory()
    second_factory = FakeProcessFactory()
    third_factory = FakeProcessFactory()
    factories = iter((running_factory, first_factory, second_factory, third_factory))
    manager = PowerShellCommandManager(process_factory=lambda *args, **kwargs: next(factories)(*args, **kwargs), max_terminal_records=2)

    running = manager.submit(script="Start-Sleep 99", working_directory=None)
    first = manager.submit(script="Write-Output first", working_directory=None)
    second = manager.submit(script="Write-Output second", working_directory=None)
    third = manager.submit(script="Write-Output third", working_directory=None)

    # The first process remains running; complete the three later submissions.
    first_factory.release(returncode=0)
    wait_for_terminal(manager, first["command_id"])
    second_factory.release(returncode=0)
    wait_for_terminal(manager, second["command_id"])
    third_factory.release(returncode=0)
    wait_for_terminal(manager, third["command_id"])

    assert manager.get(running["command_id"])["state"] == "running"
    with pytest.raises(PowerShellCommandNotFound):
        manager.get(first["command_id"])
    assert manager.get(second["command_id"])["state"] == "completed"
    assert manager.get(third["command_id"])["state"] == "completed"


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_real_windows_powershell_51_round_trips_utf8_text_streams(
    tmp_path: Path,
) -> None:
    executable = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    version = subprocess.run(
        [
            str(executable),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$PSVersionTable.PSEdition + ' ' + $PSVersionTable.PSVersion.ToString()",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        shell=False,
    ).stdout.strip()
    assert version.startswith("Desktop 5.1.")

    stdout = "繁體中文\n日本語\nemoji 😀"
    stderr = "錯誤：繁體中文\nエラー：日本語\nemoji 🚫"
    script = (
        f'$Stdout = "{stdout.replace(chr(10), "`n")}"\n'
        f'$Stderr = "{stderr.replace(chr(10), "`n")}"\n'
        "[Console]::Out.Write($Stdout)\n"
        "[Console]::Error.Write($Stderr)"
    )
    manager = PowerShellCommandManager(powershell_executable=str(executable))

    accepted = manager.submit(script=script, working_directory=str(tmp_path))
    terminal = wait_for_terminal(manager, accepted["command_id"])

    assert terminal["state"] == "completed"
    assert terminal["exit_code"] == 0
    assert terminal["stdout"] == stdout
    assert terminal["stderr"] == stderr
    assert list(tmp_path.iterdir()) == []


def test_powershell_command_routes_are_open_and_delegate_to_the_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker, client = _worker_client(tmp_path, monkeypatch)
    fake_manager = FakePowerShellCommandManager(worker.PowerShellCommandNotFound)
    monkeypatch.setattr(worker, "_powershell_commands", fake_manager)
    payload = {
        "script": "$x = '莉莎'; Remove-Item C:\\untrusted; Write-Output $x",
        "working_directory": r"C:\Windows\System32",
    }

    submitted = client.post("/v1/powershell/commands", json=payload)

    assert submitted.status_code == 202
    assert fake_manager.submitted == payload
    assert "Authorization" not in submitted.request.headers
    status = client.get("/v1/powershell/commands/cmd-1")
    assert status.status_code == 200
    assert status.json() == {
        "command_id": "cmd-1",
        "state": "running",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "created_at": "2026-08-02T00:00:00+00:00",
        "started_at": "2026-08-02T00:00:00+00:00",
        "finished_at": None,
    }
    cancelled = client.post("/v1/powershell/commands/cmd-1/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    unknown = client.get("/v1/powershell/commands/unknown")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == {
        "code": "powershell_command_not_found"
    }
    unknown_cancel = client.post("/v1/powershell/commands/unknown/cancel")
    assert unknown_cancel.status_code == 404
    assert unknown_cancel.json()["detail"] == {
        "code": "powershell_command_not_found"
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"content": b"{", "headers": {"Content-Type": "application/json"}},
        {"json": {"script": 42}},
        {"json": {"script": "Write-Output ok", "working_directory": 42}},
    ],
)
def test_powershell_command_submission_rejects_malformed_request_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object]
) -> None:
    _worker, client = _worker_client(tmp_path, monkeypatch)

    response = client.post("/v1/powershell/commands", **kwargs)

    assert response.status_code == 422
