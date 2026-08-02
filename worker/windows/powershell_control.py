"""In-memory lifecycle management for arbitrary Windows PowerShell commands."""
from __future__ import annotations

import subprocess
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable


_DEFAULT_POWERSHELL_EXECUTABLE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
_UTF8_STDIN_BOOTSTRAP = (
    "$Utf8 = New-Object System.Text.UTF8Encoding($false, $true); "
    "[Console]::InputEncoding = $Utf8; "
    "[Console]::OutputEncoding = $Utf8; "
    "$OutputEncoding = $Utf8; "
    "$Source = [Console]::In.ReadToEnd(); "
    "& ([ScriptBlock]::Create($Source))"
)
_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


class PowerShellCommandNotFound(KeyError):
    pass


class PowerShellCommandManager:
    def __init__(
        self,
        *,
        process_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        max_terminal_records: int = 100,
        powershell_executable: str | None = None,
    ) -> None:
        self._process_factory = process_factory
        self._max_terminal_records = max_terminal_records
        self._powershell_executable = powershell_executable or _DEFAULT_POWERSHELL_EXECUTABLE
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._cancelled: set[str] = set()
        self._terminating: set[str] = set()
        self._terminal_order: deque[str] = deque()

    def submit(self, *, script: str, working_directory: str | None) -> dict[str, Any]:
        command_id = str(uuid.uuid4())
        timestamp = self._utc_timestamp()
        record: dict[str, Any] = {
            "command_id": command_id,
            "state": "running",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "created_at": timestamp,
            "started_at": timestamp,
            "finished_at": None,
        }
        with self._lock:
            self._records[command_id] = record
            snapshot = dict(record)
        threading.Thread(
            target=self._run_command,
            args=(command_id, script, working_directory),
            daemon=True,
        ).start()
        return snapshot

    def get(self, command_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._record(command_id))

    def cancel(self, command_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._record(command_id)
            if record["state"] in _TERMINAL_STATES:
                return dict(record)
            self._cancelled.add(command_id)
            record.update(state="cancelled", finished_at=self._utc_timestamp())
            self._terminal_order.append(command_id)
            snapshot = dict(record)
            self._trim_terminal_records()
            process = self._processes.get(command_id)
            should_terminate = process is not None and self._begin_termination(command_id)

        if should_terminate:
            threading.Thread(
                target=self._terminate_process,
                args=(process,),
                daemon=True,
            ).start()
        return snapshot

    def _run_command(self, command_id: str, script: str, working_directory: str | None) -> None:
        try:
            process = self._process_factory(
                [
                    self._powershell_executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    _UTF8_STDIN_BOOTSTRAP,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=working_directory,
            )
        except Exception as error:
            self._finish(command_id, exit_code=None, stdout="", stderr=str(error))
            return

        with self._lock:
            self._processes[command_id] = process
            should_terminate = command_id in self._cancelled and self._begin_termination(command_id)
        if should_terminate:
            self._terminate_process(process)

        try:
            stdout, stderr = process.communicate(input=script)
            exit_code = process.returncode
        except Exception as error:
            stdout, stderr, exit_code = "", str(error), getattr(process, "returncode", None)

        self._finish(command_id, exit_code=exit_code, stdout=stdout, stderr=stderr)

    def _finish(self, command_id: str, *, exit_code: int | None, stdout: str, stderr: str) -> None:
        with self._lock:
            record = self._records.get(command_id)
            if record is None:
                self._processes.pop(command_id, None)
                self._cancelled.discard(command_id)
                self._terminating.discard(command_id)
                return
            if record["state"] == "cancelled":
                record.update(exit_code=exit_code, stdout=stdout, stderr=stderr)
            else:
                record.update(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    state="completed" if exit_code == 0 else "failed",
                    finished_at=self._utc_timestamp(),
                )
                self._terminal_order.append(command_id)
                self._trim_terminal_records()
            self._processes.pop(command_id, None)
            self._cancelled.discard(command_id)
            self._terminating.discard(command_id)

    def _begin_termination(self, command_id: str) -> bool:
        if command_id in self._terminating:
            return False
        self._terminating.add(command_id)
        return True

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        except ProcessLookupError:
            pass

    def _trim_terminal_records(self) -> None:
        while len(self._terminal_order) > self._max_terminal_records:
            expired_id = self._terminal_order.popleft()
            self._records.pop(expired_id, None)

    def _record(self, command_id: str) -> dict[str, Any]:
        try:
            return self._records[command_id]
        except KeyError as error:
            raise PowerShellCommandNotFound(command_id) from error

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
