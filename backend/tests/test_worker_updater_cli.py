"""Privileged Windows updater orchestration and production adapter contracts."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from worker.windows.updater.git_source import UpdateError
from worker.windows.updater.cli import (
    EXIT_FAILED_BEFORE_ACTIVATION,
    EXIT_INVALID_INVOCATION,
    EXIT_READY,
    EXIT_RECOVERY_REQUIRED,
    EXIT_ROLLED_BACK,
    main,
)
from worker.windows.updater.runtime import ActivationResult, HealthEvidence
from worker.windows.updater.state import UpdateStateStore
from worker.windows.updater.windows_runtime import (
    HttpHealthProbe,
    ScheduledTaskController,
    SubprocessCommandRunner,
    SubprocessHandle,
    WorkerTokenProvider,
    UrllibJsonTransport,
)


REQUIRED_COMFY_NODE_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)


@dataclass
class FakeResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class RecordingCommands:
    calls: list[tuple[tuple[str, ...], Path | None, float, Mapping[str, str] | None]] = field(
        default_factory=list
    )
    result: FakeResult = field(default_factory=FakeResult)

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> FakeResult:
        self.calls.append((tuple(argv), cwd, timeout, env))
        return self.result


def test_subprocess_runner_uses_argv_and_redacts_captured_output() -> None:
    """Returning child token text or relying on a command shell must make this test fail."""
    result = SubprocessCommandRunner().run(
        (
            sys.executable,
            "-c",
            "import sys; print('Bearer stdout-secret'); print('TOKEN=stderr-secret', file=sys.stderr)",
        ),
        cwd=None,
        timeout=10,
        env={"AI_DRAWING_TEST_VALUE": "literal"},
    )

    assert result.returncode == 0
    assert "stdout-secret" not in result.stdout
    assert "stderr-secret" not in result.stderr
    assert "[REDACTED]" in result.stdout
    assert "[REDACTED]" in result.stderr


def test_subprocess_runner_starts_a_bounded_detached_argv_process() -> None:
    """Returning a raw Popen or using a shell string must make this test fail."""
    handle = SubprocessCommandRunner().start(
        (sys.executable, "-c", "print('Bearer child-secret')"),
        cwd=None,
        timeout=10,
        env=None,
    )

    assert handle.wait(timeout=10) == 0


def test_subprocess_runner_translates_timeout_without_captured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def time_out(*args: Any, **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(
            cmd=["tool", "Bearer argv-secret"],
            timeout=1,
            output="Bearer stdout-secret",
            stderr="TOKEN=stderr-secret",
        )

    monkeypatch.setattr(subprocess, "run", time_out)
    with pytest.raises(TimeoutError) as raised:
        SubprocessCommandRunner().run(("tool",), cwd=None, timeout=1, env=None)

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True
    assert "secret" not in str(raised.value)


def test_subprocess_handle_timeout_is_safe_for_runtime_cleanup() -> None:
    class TimedOutProcess:
        def wait(self, *, timeout: float) -> int:
            raise subprocess.TimeoutExpired(
                cmd=["runtime", "Bearer argv-secret"],
                timeout=timeout,
                output="Bearer stdout-secret",
                stderr="TOKEN=stderr-secret",
            )

    with pytest.raises(TimeoutError) as raised:
        SubprocessHandle(TimedOutProcess()).wait(timeout=1)  # type: ignore[arg-type]

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True
    assert "secret" not in str(raised.value)


def test_scheduled_task_controller_uses_only_the_fixed_worker_task() -> None:
    """Allowing a caller-selected task or command must make this test fail."""
    commands = RecordingCommands()
    controller = ScheduledTaskController(commands)

    controller.stop_production()
    controller.start_production()

    assert [call[0] for call in commands.calls] == [
        ("schtasks.exe", "/End", "/TN", "AI-Drawing NVIDIA Worker"),
        ("schtasks.exe", "/Run", "/TN", "AI-Drawing NVIDIA Worker"),
    ]
    assert all(call[2] > 0 for call in commands.calls)


def _token_provider(tmp_path: Path, token: str = "very-secret-token") -> WorkerTokenProvider:
    worker_root = tmp_path / "worker"
    config_root = worker_root / "config"
    config_root.mkdir(parents=True)
    config_path = config_root / "worker.json"
    config_path.write_text(json.dumps({"token": token}), encoding="utf-8")
    return WorkerTokenProvider(worker_root, config_path)


@dataclass
class RecordingTransport:
    responses: dict[tuple[str, str], Any]
    calls: list[tuple[str, str, Mapping[str, str], Any, float]] = field(default_factory=list)

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Any,
        timeout: float,
    ) -> Any:
        self.calls.append((method, url, dict(headers), body, timeout))
        response = self.responses[(method, url)]
        if isinstance(response, BaseException):
            raise response
        return response


def _complete_health_responses(
    worker_url: str, comfy_url: str, commit: str
) -> dict[tuple[str, str], Any]:
    return {
        ("GET", f"{comfy_url}/system_stats"): {
            "devices": [{"type": "cuda", "name": "NVIDIA RTX"}]
        },
        ("GET", f"{comfy_url}/object_info"): {
            node_type: {} for node_type in REQUIRED_COMFY_NODE_TYPES
        },
        ("GET", f"{worker_url}/v1/worker/status"): {
            "protocol_version": 2,
            "update_capability": 1,
            "source_commit": commit,
            "comfyui": "ready",
        },
        ("POST", f"{worker_url}/v1/resources/plan"): {"missing": []},
        ("POST", f"{worker_url}/v1/workflows/preflight"): {
            "ready": True,
            "missing_node_types": [],
        },
    }


def test_http_health_probe_returns_complete_typed_evidence_without_retaining_token(tmp_path: Path) -> None:
    """Skipping any authenticated health boundary or retaining the token must make this test fail."""
    commit = "a" * 40
    worker_url = "http://127.0.0.1:8791"
    comfy_url = "http://127.0.0.1:8188"
    transport = RecordingTransport(_complete_health_responses(worker_url, comfy_url, commit))
    provider = _token_provider(tmp_path)
    probe = HttpHealthProbe(provider, ScheduledTaskController(RecordingCommands()), transport=transport)

    evidence = probe.validate_staged(worker_url, comfy_url, commit)

    assert evidence == HealthEvidence(
        cuda_available=True,
        gpu_name="NVIDIA RTX",
        system_stats_ok=True,
        object_info_ok=True,
        authenticated_status_ok=True,
        resource_plan_ok=True,
        preflight_ok=True,
        source_commit=commit,
    )
    assert [call[:2] for call in transport.calls] == [
        ("GET", f"{comfy_url}/system_stats"),
        ("GET", f"{comfy_url}/object_info"),
        ("GET", f"{worker_url}/v1/worker/status"),
        ("POST", f"{worker_url}/v1/resources/plan"),
        ("POST", f"{worker_url}/v1/workflows/preflight"),
    ]
    assert all(call[2] == {"Authorization": "Bearer very-secret-token"} for call in transport.calls[2:])
    assert transport.calls[-1][3] == {"node_types": list(REQUIRED_COMFY_NODE_TYPES)}
    assert "very-secret-token" not in repr(probe)
    assert "very-secret-token" not in repr(provider)


def test_http_health_probe_maps_transport_exception_without_token_text(tmp_path: Path) -> None:
    """Serializing an HTTP exception containing a bearer token must make this test fail."""
    worker_url = "http://127.0.0.1:8791"
    comfy_url = "http://127.0.0.1:8188"
    transport = RecordingTransport(
        {
            ("GET", f"{comfy_url}/system_stats"): OSError(
                "Bearer very-secret-token could not connect"
            )
        }
    )
    probe = HttpHealthProbe(
        _token_provider(tmp_path),
        ScheduledTaskController(RecordingCommands()),
        transport=transport,
        attempts=1,
        retry_delay=0,
    )

    with pytest.raises(UpdateError) as raised:
        probe.validate_production(worker_url, comfy_url, "a" * 40)

    assert raised.value.code == "WORKER_CONTRACT_FAILED"
    assert "very-secret-token" not in str(raised.value)


@pytest.mark.parametrize(
    ("response_key", "replacement", "evidence_field"),
    [
        ("status", {"protocol_version": 1, "update_capability": 1, "source_commit": "a" * 40, "comfyui": "ready"}, "authenticated_status_ok"),
        ("status", {"protocol_version": 2, "update_capability": 0, "source_commit": "a" * 40, "comfyui": "ready"}, "authenticated_status_ok"),
        ("status", {"protocol_version": 2, "update_capability": 1, "source_commit": "b" * 40, "comfyui": "ready"}, "authenticated_status_ok"),
        ("status", {"protocol_version": 2, "update_capability": 1, "source_commit": "a" * 40, "comfyui": "unavailable"}, "authenticated_status_ok"),
        ("system", {"devices": [{"type": "cpu", "name": "CPU"}]}, "cuda_available"),
        ("system", {"devices": [{"type": "cuda", "name": ""}]}, "gpu_name"),
        ("objects", {"KSampler": {}}, "object_info_ok"),
        ("plan", {"missing": [{"kind": "models"}]}, "resource_plan_ok"),
        ("preflight", {"ready": False, "missing_node_types": []}, "preflight_ok"),
        ("preflight", {"ready": True, "missing_node_types": ["KSampler"]}, "preflight_ok"),
    ],
)
def test_http_health_probe_rejects_incomplete_exact_contract(
    tmp_path: Path,
    response_key: str,
    replacement: Any,
    evidence_field: str,
) -> None:
    """Treating a partial/malformed health response as complete must make this test fail."""
    commit = "a" * 40
    worker_url = "http://127.0.0.1:8791"
    comfy_url = "http://127.0.0.1:8188"
    responses = _complete_health_responses(worker_url, comfy_url, commit)
    keys = {
        "status": ("GET", f"{worker_url}/v1/worker/status"),
        "system": ("GET", f"{comfy_url}/system_stats"),
        "objects": ("GET", f"{comfy_url}/object_info"),
        "plan": ("POST", f"{worker_url}/v1/resources/plan"),
        "preflight": ("POST", f"{worker_url}/v1/workflows/preflight"),
    }
    responses[keys[response_key]] = replacement
    probe = HttpHealthProbe(
        _token_provider(tmp_path),
        ScheduledTaskController(RecordingCommands()),
        transport=RecordingTransport(responses),
        attempts=1,
    )

    evidence = probe.validate_staged(worker_url, comfy_url, commit)

    assert not getattr(evidence, evidence_field)


def test_urllib_transport_bypasses_proxy_and_sends_authorization_only_to_loopback_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Using the process-global proxy-aware opener must make this test fail."""
    target_headers: list[str | None] = []
    proxy_headers: list[str | None] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            target_headers.append(self.headers.get("Authorization"))
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    class ProxyHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            proxy_headers.append(self.headers.get("Authorization"))
            body = b'{"proxied":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    target_thread.start()
    proxy_thread.start()
    proxy_url = f"http://127.0.0.1:{proxy.server_port}"
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda _host: False)
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy_url}))
    )
    try:
        response = UrllibJsonTransport().request_json(
            "GET",
            f"http://127.0.0.1:{target.server_port}/health",
            headers={"Authorization": "Bearer target-only-secret"},
            body=None,
            timeout=5,
        )
    finally:
        urllib.request.install_opener(None)
        target.shutdown()
        proxy.shutdown()
        target.server_close()
        proxy.server_close()
        target_thread.join(timeout=5)
        proxy_thread.join(timeout=5)

    assert response == {"ok": True}
    assert target_headers == ["Bearer target-only-secret"]
    assert proxy_headers == []


def test_token_provider_rejects_noncanonical_config_location(tmp_path: Path) -> None:
    """Reading a token from a caller-selected file outside config must make this test fail."""
    worker_root = tmp_path / "worker"
    worker_root.mkdir()
    outside = tmp_path / "worker.json"
    outside.write_text(json.dumps({"token": "secret"}), encoding="utf-8")

    with pytest.raises(UpdateError) as raised:
        WorkerTokenProvider(worker_root, outside).read()

    assert raised.value.code == "UPDATER_CONFIG_INVALID"


class RecordingStateStore(UpdateStateStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.states: list[str] = []

    def transition(self, next_state: str) -> None:
        super().transition(next_state)
        self.states.append(next_state)

    def fail(self, error_code: str, message: str) -> None:
        super().fail(error_code, message)
        self.states.append(self.read_public()["state"])

    def terminal_failure(self, next_state: str, error_code: str, message: str) -> None:
        super().terminal_failure(next_state, error_code, message)
        self.states.append(next_state)


@dataclass
class FakeUpdaterServices:
    root: Path
    fail_at: str | None = None
    failure: BaseException = field(
        default_factory=lambda: UpdateError("RUNTIME_INSTALL_FAILED", "install failed")
    )
    activation_result: ActivationResult = field(
        default_factory=lambda: ActivationResult("ready", "a" * 40, "b" * 40)
    )
    release_exists: bool = False
    calls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.state = RecordingStateStore(self.root / "state")
        self.state.queue("request-1", "a" * 40)

    @property
    def states(self) -> list[str]:
        return self.state.states

    def claim_request(self):
        self.calls.append("claim")
        return self.state.read_active_request()

    def candidate_exists(self, target_commit: str) -> bool:
        self.calls.append("candidate")
        return self.release_exists

    def fetch(self, target_commit: str) -> Path:
        self.calls.append("fetch")
        self._maybe_fail("fetch")
        exported = self.root / "exported"
        exported.mkdir(exist_ok=True)
        return exported

    def install(self, exported: Path, target_commit: str) -> Path:
        self.calls.append("install")
        self._maybe_fail("install")
        self.release_exists = True
        return self.root / "release"

    def validate(self, target_commit: str) -> Path:
        self.calls.append("validate")
        self._maybe_fail("validate")
        return self.root / "release"

    def activate(self, target_commit: str, on_restarting):
        self.calls.append("activate")
        self._maybe_fail("activate")
        on_restarting()
        return self.activation_result

    def _maybe_fail(self, phase: str) -> None:
        if self.fail_at == phase:
            raise self.failure


def _advance(store: UpdateStateStore, target: str) -> None:
    path = ["fetching", "staging", "installing", "validating", "activating", "restarting"]
    for state in path[: path.index(target) + 1]:
        store.transition(state)


def test_updater_cli_accepts_no_options_paths_or_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Parsing or echoing an untrusted CLI argument must make this test fail."""
    services = FakeUpdaterServices(tmp_path)

    result = main(["--command", "Bearer command-secret"], services=services)

    assert result == EXIT_INVALID_INVOCATION
    assert services.calls == []
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_updater_cli_advances_success_states(tmp_path: Path) -> None:
    """Skipping or reordering one durable state must make this test fail."""
    services = FakeUpdaterServices(tmp_path)

    assert main([], services=services) == EXIT_READY
    assert services.states == [
        "fetching",
        "staging",
        "installing",
        "validating",
        "activating",
        "restarting",
        "ready",
    ]
    assert services.calls == ["claim", "candidate", "fetch", "install", "validate", "activate"]


def test_updater_cli_treats_terminal_request_acknowledgement_as_success(tmp_path: Path) -> None:
    services = FakeUpdaterServices(tmp_path)
    services.claim_request = lambda: None  # type: ignore[method-assign]

    assert main([], services=services) == EXIT_READY
    assert services.calls == []


@pytest.mark.parametrize(
    ("phase", "error_code", "expected_state", "exit_code"),
    [
        ("fetch", "WINDOWS_REMOTE_HEAD_MISMATCH", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("install", "INSUFFICIENT_DISK_SPACE", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("install", "RUNTIME_INSTALL_FAILED", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("validate", "CUDA_VALIDATION_FAILED", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("validate", "COMFYUI_VALIDATION_FAILED", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("validate", "WORKER_CONTRACT_FAILED", "failed_before_activation", EXIT_FAILED_BEFORE_ACTIVATION),
        ("activate", "RECOVERY_REQUIRED", "recovery_required", EXIT_RECOVERY_REQUIRED),
    ],
)
def test_updater_cli_maps_typed_failures_to_terminal_state(
    tmp_path: Path,
    phase: str,
    error_code: str,
    expected_state: str,
    exit_code: int,
) -> None:
    """Publishing an unstable code or wrong terminal state must make this test fail."""
    services = FakeUpdaterServices(
        tmp_path,
        fail_at=phase,
        failure=UpdateError(error_code, "Bearer must-not-leak TOKEN=also-secret"),
    )

    assert main([], services=services) == exit_code
    public = services.state.read_public()
    private = json.loads(services.state.private_path.read_text(encoding="utf-8"))
    assert public == {"state": expected_state, "error_code": error_code}
    assert "must-not-leak" not in private["error_message"]
    assert "also-secret" not in private["error_message"]


def test_updater_cli_records_typed_rollback_result(tmp_path: Path) -> None:
    """Flattening a proven rollback into generic recovery must make this test fail."""
    services = FakeUpdaterServices(
        tmp_path,
        activation_result=ActivationResult(
            "rolled_back", "b" * 40, "b" * 40, "ACTIVATION_FAILED_ROLLED_BACK"
        ),
    )

    assert main([], services=services) == EXIT_ROLLED_BACK
    assert services.state.read_public() == {
        "state": "rolled_back",
        "error_code": "ACTIVATION_FAILED_ROLLED_BACK",
    }


@pytest.mark.parametrize(
    ("resume_state", "release_exists", "expected_calls"),
    [
        ("staging", False, ["claim", "candidate", "fetch", "install", "validate", "activate"]),
        ("installing", True, ["claim", "candidate", "validate", "activate"]),
        ("validating", True, ["claim", "candidate", "validate", "activate"]),
        ("activating", True, ["claim", "candidate", "activate"]),
        ("restarting", True, ["claim", "candidate", "activate"]),
    ],
)
def test_updater_cli_resumes_forward_from_durable_state(
    tmp_path: Path,
    resume_state: str,
    release_exists: bool,
    expected_calls: list[str],
) -> None:
    """Restarting from fetching or moving state backward must make this test fail."""
    services = FakeUpdaterServices(tmp_path, release_exists=release_exists)
    _advance(services.state, resume_state)
    services.states.clear()

    assert main([], services=services) == EXIT_READY
    assert services.calls == expected_calls
    assert services.state.read_public() == {"state": "ready"}
