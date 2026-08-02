"""Concrete, bounded Windows transports for the privileged updater."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .git_source import UpdateError
from .runtime import CommandResult, CommandRunner, HealthEvidence, ProcessHandle


COMMAND_TIMEOUT = 30.0
HTTP_TIMEOUT = 10.0
HEALTH_ATTEMPTS = 30
HEALTH_RETRY_DELAY = 2.0
WORKER_TASK_NAME = "AI-Drawing NVIDIA Worker"
REQUIRED_COMFY_NODE_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)
_URL_CREDENTIALS = re.compile(r"://[^/\s@]+@")
_BEARER_SECRET = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(?:token|secret|password|api[_-]?key|authorization)\b\s*(?:=|:)?\s*[^\s,;]+"
)
_HEALTH_FAILURE_CODES = {
    "comfyui": "COMFYUI_START_TIMEOUT",
    "worker_status": "WORKER_START_TIMEOUT",
    "worker_preflight": "WORKER_PREFLIGHT_FAILED",
}
_RETRYABLE_HEALTH_ERRORS = (
    OSError,
    TimeoutError,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
)


class _HealthProbeStageError(Exception):
    def __init__(self, stage: str) -> None:
        self.stage = stage


@dataclass(frozen=True)
class CompletedCommand:
    returncode: int
    stdout: str
    stderr: str


class SubprocessHandle(ProcessHandle):
    """Translate subprocess timeouts to the runtime's narrow process contract."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    def terminate(self) -> None:
        self._process.terminate()

    def wait(self, *, timeout: float) -> int:
        try:
            return self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise TimeoutError("process did not stop before the deadline") from None

    def kill(self) -> None:
        self._process.kill()


class SubprocessCommandRunner(CommandRunner):
    """Run fixed argv commands without a shell, console window, or raw output."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        args = _validated_argv(argv, timeout)
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                timeout=timeout,
                env=_merged_environment(env),
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_creation_flags(),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("command did not complete before the deadline") from None
        return CompletedCommand(
            returncode=result.returncode,
            stdout=_redact(result.stdout),
            stderr=_redact(result.stderr),
        )

    def start(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> ProcessHandle:
        args = _validated_argv(argv, timeout)
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=_merged_environment(env),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=_creation_flags(),
        )
        return SubprocessHandle(process)


class ScheduledTaskController:
    """Start and stop only the installer-owned production Worker task."""

    def __init__(self, commands: CommandRunner) -> None:
        self._commands = commands

    def stop_production(self) -> None:
        self._checked(("schtasks.exe", "/End", "/TN", WORKER_TASK_NAME))

    def start_production(self) -> None:
        self._checked(("schtasks.exe", "/Run", "/TN", WORKER_TASK_NAME))

    def _checked(self, argv: Sequence[str]) -> None:
        try:
            result = self._commands.run(argv, cwd=None, timeout=COMMAND_TIMEOUT, env=None)
        except (OSError, TimeoutError) as error:
            raise UpdateError("RECOVERY_REQUIRED", "production task command could not complete") from error
        if result.returncode:
            raise UpdateError("RECOVERY_REQUIRED", "production task command failed")


class WorkerTokenProvider:
    """Read the bearer token only from the canonical installer-owned config file."""

    def __init__(self, worker_root: Path, config_path: Path) -> None:
        self._worker_root = Path(worker_root)
        self._config_path = Path(config_path)

    def read(self) -> str:
        try:
            root = self._worker_root.resolve(strict=True)
            expected = (root / "config" / "worker.json").resolve(strict=True)
            actual = self._config_path.resolve(strict=True)
            if actual != expected or not actual.is_file():
                raise OSError("worker token config is not canonical")
            value = json.loads(actual.read_text(encoding="utf-8"))
            token = value.get("token") if isinstance(value, dict) else None
            if not isinstance(token, str) or not token or "\r" in token or "\n" in token:
                raise ValueError("worker token is invalid")
            return token
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            raise UpdateError("UPDATER_CONFIG_INVALID", "worker authentication config is invalid") from error


class UrllibJsonTransport:
    """Minimal JSON transport whose failures never include response/request bodies."""

    def __init__(self) -> None:
        # Authenticated loopback requests must never inherit machine/user proxy settings.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Any,
        timeout: float,
    ) -> Any:
        _require_loopback_http_url(url)
        data = None
        request_headers = dict(headers)
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        with self._opener.open(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8"))


class HttpHealthProbe:
    """Prove complete local ComfyUI and authenticated Worker health."""

    def __init__(
        self,
        token_provider: WorkerTokenProvider,
        production: ScheduledTaskController,
        *,
        transport: Any | None = None,
        attempts: int = HEALTH_ATTEMPTS,
        retry_delay: float = HEALTH_RETRY_DELAY,
    ) -> None:
        if attempts < 1 or retry_delay < 0:
            raise ValueError("health retry policy is invalid")
        self._token_provider = token_provider
        self._production = production
        self._transport = transport or UrllibJsonTransport()
        self._attempts = attempts
        self._retry_delay = retry_delay

    def validate_staged(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence:
        return self._validate(worker_url, comfy_url, expected_commit)

    def validate_production(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence:
        return self._validate(worker_url, comfy_url, expected_commit)

    def stop_production(self) -> None:
        self._production.stop_production()

    def start_production(self) -> None:
        self._production.start_production()

    def _validate(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence:
        _require_loopback_http_url(worker_url)
        _require_loopback_http_url(comfy_url)
        failed_stage = "comfyui"
        for attempt in range(self._attempts):
            try:
                return self._read_evidence(worker_url, comfy_url, expected_commit)
            except _HealthProbeStageError as error:
                failed_stage = error.stage
                if attempt + 1 < self._attempts:
                    time.sleep(self._retry_delay)
        raise UpdateError(
            _HEALTH_FAILURE_CODES[failed_stage], "local runtime health validation failed"
        )

    def _read_evidence(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence:
        system_stats = self._health_request(
            "comfyui",
            "GET",
            f"{comfy_url}/system_stats",
            headers={},
            body=None,
        )
        token = self._token_provider.read()
        authorization = {"Authorization": f"Bearer {token}"}
        status = self._health_request(
            "worker_status",
            "GET",
            f"{worker_url}/v1/worker/status",
            headers=authorization,
            body=None,
        )
        preflight = self._health_request(
            "worker_preflight",
            "POST",
            f"{worker_url}/v1/workflows/preflight",
            headers=authorization,
            body={"node_types": list(REQUIRED_COMFY_NODE_TYPES)},
        )
        devices = system_stats.get("devices", []) if isinstance(system_stats, dict) else []
        cuda_devices = [
            device
            for device in devices
            if isinstance(device, dict)
            and str(device.get("type", "")).casefold() == "cuda"
        ]
        gpu_name = str(cuda_devices[0].get("name", "")) if cuda_devices else ""
        return HealthEvidence(
            cuda_available=bool(cuda_devices),
            gpu_name=gpu_name,
            system_stats_ok=(
                isinstance(system_stats, dict)
                and isinstance(system_stats.get("devices"), list)
            ),
            authenticated_status_ok=(
                isinstance(status, dict)
                and type(status.get("protocol_version")) is int
                and status.get("protocol_version") == 2
                and type(status.get("update_capability")) is int
                and status.get("update_capability") == 1
                and status.get("source_commit") == expected_commit
                and status.get("comfyui") == "ready"
            ),
            preflight_ok=(
                isinstance(preflight, dict)
                and preflight.get("ready") is True
                and preflight.get("missing_node_types") == []
            ),
            source_commit=str(status.get("source_commit", "")) if isinstance(status, dict) else "",
        )

    def _health_request(
        self,
        stage: str,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Any,
    ) -> Any:
        try:
            return self._transport.request_json(
                method, url, headers=headers, body=body, timeout=HTTP_TIMEOUT
            )
        except _RETRYABLE_HEALTH_ERRORS:
            raise _HealthProbeStageError(stage) from None


def _validated_argv(argv: Sequence[str], timeout: float) -> list[str]:
    if (
        isinstance(argv, (str, bytes))
        or not argv
        or timeout <= 0
        or any(not isinstance(argument, str) or not argument or "\x00" in argument for argument in argv)
    ):
        raise ValueError("command invocation is invalid")
    return list(argv)


def _merged_environment(overrides: Mapping[str, str] | None) -> dict[str, str] | None:
    if overrides is None:
        return None
    if any(not isinstance(key, str) or not isinstance(value, str) or "\x00" in key + value for key, value in overrides.items()):
        raise ValueError("command environment is invalid")
    return {**os.environ, **overrides}


def _creation_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _require_loopback_http_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise ValueError("health URL is invalid") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("health URL must be explicit loopback HTTP")


def _redact(value: str) -> str:
    redacted = _URL_CREDENTIALS.sub("://[REDACTED]@", value)
    redacted = _BEARER_SECRET.sub("Bearer [REDACTED]", redacted)
    redacted = _NAMED_SECRET.sub("[REDACTED]", redacted)
    return redacted
