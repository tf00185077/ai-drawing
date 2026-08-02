from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest


WORKER_WINDOWS_ROOT = Path(__file__).resolve().parents[2] / "worker" / "windows"
if str(WORKER_WINDOWS_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_WINDOWS_ROOT))

from powershell_control import PowerShellCommandManager, PowerShellCommandNotFound


def wait_for_terminal(manager: PowerShellCommandManager, command_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        command = manager.get(command_id)
        if command["state"] in {"completed", "failed", "cancelled"}:
            return command
        time.sleep(0.01)
    raise AssertionError(f"command {command_id} did not become terminal")


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
        self._factory.release(returncode=-15)

    def kill(self) -> None:
        self.killed = True
        self._factory.release(returncode=-9)

    def wait(self, timeout: float | None = None) -> int | None:
        if not self._factory._released.wait(timeout):
            raise TimeoutError("fake process did not exit")
        self.returncode = self._factory.returncode
        return self.returncode


class FakeProcessFactory:
    def __init__(self) -> None:
        self.argv: list[str] | None = None
        self.cwd: str | None = None
        self.script: str | None = None
        self.stdout = ""
        self.stderr = ""
        self.returncode = 0
        self.processes: list[FakeProcess] = []
        self._released = threading.Event()

    def __call__(self, argv: list[str], **kwargs: object) -> FakeProcess:
        self.argv = argv
        self.cwd = kwargs["cwd"]  # type: ignore[assignment,index]
        process = FakeProcess(self)
        self.processes.append(process)
        return process

    def release(self, *, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self._released.set()


def test_submit_runs_script_with_fixed_powershell_contract() -> None:
    factory = FakeProcessFactory()
    manager = PowerShellCommandManager(process_factory=factory, max_terminal_records=2)

    command = manager.submit(
        script="Get-ChildItem C:\\\nWrite-Output '螳梧・'",
        working_directory=r"D:\code\ai-drawing",
    )

    assert command["state"] == "running"
    factory.release(returncode=0, stdout="螳梧・\n", stderr="")
    terminal = wait_for_terminal(manager, command["command_id"])
    assert terminal["state"] == "completed"
    assert terminal["exit_code"] == 0
    assert factory.script == "Get-ChildItem C:\\\nWrite-Output '螳梧・'"
    assert factory.cwd == r"D:\code\ai-drawing"
    assert factory.argv == [
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "-",
    ]


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

    cancelled = manager.cancel(command["command_id"])

    assert cancelled["state"] == "running"
    terminal = wait_for_terminal(manager, command["command_id"])
    assert terminal["state"] == "cancelled"
    assert factory.processes[0].terminated is True


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
