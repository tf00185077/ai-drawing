"""Behavior tests for the managed Windows worker versioned runtime."""
from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping, Sequence

import pytest

import worker.windows.updater.runtime as runtime_module
from worker.windows.updater.git_source import UpdateError
from worker.windows.updater.runtime import (
    Activator,
    HealthEvidence,
    RuntimeBuilder,
    RuntimeLayout,
    RuntimeValidationError,
    RuntimeValidator,
    WindowsJunctionOps,
)


COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


@dataclass
class FakeJunctionOps:
    targets: dict[Path, Path] = field(default_factory=dict)
    fail_once: set[str] = field(default_factory=set)

    def _fail(self, operation: str) -> None:
        if operation in self.fail_once:
            self.fail_once.remove(operation)
            raise OSError(f"interrupted at {operation}")

    def create(self, link: Path, target: Path) -> None:
        link = Path(link)
        self._fail(f"create:{link.name}")
        target = Path(target).resolve(strict=True)
        if link.exists() or link in self.targets:
            raise FileExistsError(link)
        link.mkdir(parents=False)
        (link / ".fake-junction-target").write_text(str(target), encoding="utf-8")
        self.targets[link] = target

    def read_target(self, link: Path) -> Path:
        try:
            return self.targets[Path(link)]
        except KeyError as error:
            try:
                target = Path(link, ".fake-junction-target").read_text(encoding="utf-8")
                return Path(target)
            except OSError:
                raise OSError(f"not a managed junction: {link}") from error

    def rename(self, source: Path, destination: Path) -> None:
        source = Path(source)
        destination = Path(destination)
        self._fail(f"rename:{source.name}:{destination.name}")
        if destination.exists() or destination in self.targets:
            raise FileExistsError(destination)
        target = self.targets.pop(source)
        source.rename(destination)
        self.targets[destination] = target

    def remove(self, link: Path) -> None:
        link = Path(link)
        self._fail(f"remove:{link.name}")
        self.targets.pop(link, None)
        (link / ".fake-junction-target").unlink()
        link.rmdir()


@dataclass
class CommandResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class FakeCommands:
    calls: list[tuple[tuple[str, ...], Path | None, float, Mapping[str, str] | None]] = field(
        default_factory=list
    )
    fail_token: str | None = None
    fail_start_token: str | None = None
    start_calls: list[tuple[tuple[str, ...], Path | None, float, Mapping[str, str] | None]] = field(
        default_factory=list
    )
    processes: list["FakeProcess"] = field(default_factory=list)

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        args = tuple(argv)
        self.calls.append((args, cwd, timeout, env))
        if self.fail_token is not None and self.fail_token in args:
            return CommandResult(returncode=9, stderr="TOKEN=must-not-leak install failed")
        if len(args) >= 5 and args[1:4] == ("-3.12", "-m", "venv"):
            python = Path(args[4]) / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.write_text("fake python", encoding="utf-8")
        if "clone" in args:
            clone_root = Path(args[-1])
            clone_root.mkdir(parents=True)
            (clone_root / "requirements.txt").write_text("dependency==1.0\n", encoding="utf-8")
            if clone_root.name == "ComfyUI":
                (clone_root / "main.py").write_text("app = object()\n", encoding="utf-8")
        return CommandResult()

    def start(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> "FakeProcess":
        args = tuple(argv)
        self.start_calls.append((args, cwd, timeout, env))
        if self.fail_start_token is not None and self.fail_start_token in args:
            raise OSError("staged process failed to start")
        process = FakeProcess()
        self.processes.append(process)
        return process


@dataclass
class FakeProcess:
    timeout_once: bool = False
    fail_second_wait: bool = False
    fail_terminate: bool = False
    terminated: bool = False
    killed: bool = False
    waits: list[float] = field(default_factory=list)

    def terminate(self) -> None:
        self.terminated = True
        if self.fail_terminate:
            raise RuntimeError("terminate adapter failed")

    def wait(self, *, timeout: float) -> int:
        self.waits.append(timeout)
        if self.timeout_once and not self.killed:
            raise TimeoutError("still running")
        if self.fail_second_wait and self.killed:
            raise OSError("process survived kill")
        return 0

    def kill(self) -> None:
        self.killed = True


@dataclass
class FakeHealth:
    failure_code: str | None = None
    staged_calls: list[tuple[str, str, str]] = field(default_factory=list)
    fail_production_for: set[str] = field(default_factory=set)
    production_calls: list[tuple[str, str, str]] = field(default_factory=list)
    stop_calls: int = 0
    start_calls: int = 0
    fail_start_count: int = 0

    evidence: HealthEvidence | None = None

    def validate_staged(self, worker_url: str, comfy_url: str, expected_commit: str) -> HealthEvidence:
        self.staged_calls.append((worker_url, comfy_url, expected_commit))
        if self.failure_code is not None:
            raise UpdateError(self.failure_code, "staged health failed")
        return self.evidence or HealthEvidence.complete(expected_commit)

    def validate_production(self, worker_url: str, comfy_url: str, expected_commit: str) -> HealthEvidence:
        self.production_calls.append((worker_url, comfy_url, expected_commit))
        if expected_commit in self.fail_production_for:
            raise UpdateError("WORKER_CONTRACT_FAILED", "production health failed")
        return self.evidence or HealthEvidence.complete(expected_commit)

    def stop_production(self) -> None:
        self.stop_calls += 1

    def start_production(self) -> None:
        self.start_calls += 1
        if self.fail_start_count:
            self.fail_start_count -= 1
            raise OSError("stable bootstrap failed")


def _exported_source(
    root: Path,
    commit: str = COMMIT_A,
    *,
    custom_nodes: list[dict[str, str]] | None = None,
) -> Path:
    root.mkdir()
    (root / "source-commit.txt").write_text(commit + "\n", encoding="utf-8")
    worker = root / "worker" / "windows"
    worker.mkdir(parents=True)
    (worker / "worker.py").write_text("app = object()\n", encoding="utf-8")
    (worker / "requirements.txt").write_text("fastapi==0.116.1\n", encoding="utf-8")
    (worker / "worker-manifest.json").write_text(
        json.dumps(
            {
                "python": "3.12",
                "uv": "0.11.29",
                "comfyui_repository": "https://example.test/ComfyUI.git",
                "comfyui_version": "v0.28.0",
                "pytorch_index": "https://download.pytorch.org/whl/cu130",
                "custom_nodes": custom_nodes or [],
            }
        ),
        encoding="utf-8",
    )
    return root


def _argv_calls(commands: FakeCommands) -> list[tuple[str, ...]]:
    return [call[0] for call in commands.calls]


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction contract")
def test_windows_junction_ops_create_read_rename_and_remove_only_the_link(tmp_path: Path) -> None:
    """Using a directory copy/symlink or deleting the target must make this test fail."""
    target = tmp_path / "target"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    link = tmp_path / "current.next"
    renamed = tmp_path / "current"
    junctions = WindowsJunctionOps()

    junctions.create(link, target)
    assert junctions.read_target(link) == target.resolve(strict=True)
    junctions.rename(link, renamed)
    assert not link.exists()
    assert junctions.read_target(renamed) == target.resolve(strict=True)
    junctions.remove(renamed)

    assert not renamed.exists()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_layout_rejects_non_full_commit_before_resolving_a_release(tmp_path: Path) -> None:
    """Relaxing the full-SHA release boundary must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")

    with pytest.raises(UpdateError) as raised:
        layout.release("main")

    assert raised.value.code == "TARGET_COMMIT_INVALID"


def test_stage_keeps_mutable_data_outside_immutable_release(tmp_path: Path) -> None:
    """Copying mutable models or worker credentials into a release must fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    exported = _exported_source(tmp_path / "export")
    secret = exported / "config" / "worker.json"
    secret.parent.mkdir()
    secret.write_text('{"token":"must-not-copy"}', encoding="utf-8")
    junctions = FakeJunctionOps()

    release = RuntimeBuilder(layout, FakeCommands(), junctions).stage(exported, COMMIT_A)

    assert release == layout.releases / COMMIT_A
    assert junctions.read_target(release / "ComfyUI" / "models") == layout.shared_models
    assert junctions.read_target(release / "ComfyUI" / "input") == layout.shared_input
    assert junctions.read_target(release / "ComfyUI" / "output") == layout.shared_output
    assert junctions.read_target(release / ".cache") == layout.shared_cache
    assert junctions.read_target(release / "cache" / ".partial") == layout.shared_partial
    assert not (release / "config" / "worker.json").exists()


def test_stage_rejects_a_shared_junction_target_outside_the_worker_root(tmp_path: Path) -> None:
    """Dropping canonical target containment must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    outside = tmp_path / "outside-models"
    outside.mkdir()
    unsafe_layout = RuntimeLayout(
        root=layout.root,
        releases=layout.releases,
        shared=layout.shared,
        config=layout.config,
        current=layout.current,
        staging=layout.staging,
        shared_models=outside,
        shared_input=layout.shared_input,
        shared_output=layout.shared_output,
        shared_cache=layout.shared_cache,
        shared_partial=layout.shared_partial,
    )

    with pytest.raises(UpdateError) as raised:
        RuntimeBuilder(unsafe_layout, FakeCommands(), FakeJunctionOps()).stage(
            _exported_source(tmp_path / "export"), COMMIT_A
        )

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert not (layout.releases / COMMIT_A).exists()


def test_stage_rejects_a_reparse_source_instead_of_copying_through_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Following a source reparse point during staging must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    exported = _exported_source(tmp_path / "export")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    linked = exported / "linked.txt"
    linked.write_text("placeholder", encoding="utf-8")
    original_is_symlink = Path.is_symlink

    def reports_reparse(path: Path) -> bool:
        return path == linked or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", reports_reparse)

    with pytest.raises(UpdateError) as raised:
        RuntimeBuilder(layout, FakeCommands(), FakeJunctionOps()).stage(exported, COMMIT_A)

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert not (layout.releases / COMMIT_A).exists()


def test_stage_installs_cuda_index_before_requirements_and_pins_every_repository(tmp_path: Path) -> None:
    """Reordering CUDA or cloning an unpinned repository must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    nodes = [
        {
            "name": "ComfyUI-Node-A",
            "repository": "https://example.test/node-a.git",
            "revision": "1" * 40,
        },
        {
            "name": "ComfyUI-Node-B",
            "repository": "https://example.test/node-b.git",
            "revision": "2" * 40,
        },
    ]
    commands = FakeCommands()

    release = RuntimeBuilder(layout, commands, FakeJunctionOps()).stage(
        _exported_source(tmp_path / "export", custom_nodes=nodes), COMMIT_A
    )

    calls = _argv_calls(commands)
    cuda_call = next(
        index
        for index, argv in enumerate(calls)
        if "torch" in argv and "https://download.pytorch.org/whl/cu130" in argv
    )
    requirements_calls = [index for index, argv in enumerate(calls) if "--requirement" in argv]
    assert requirements_calls
    assert cuda_call < min(requirements_calls)
    assert calls[0][0:4] == ("py", "-3.12", "-m", "venv")
    assert any("uv==0.11.29" in argv for argv in calls)
    staged = layout.staging / COMMIT_A
    assert any(
        argv[:3] == ("git", "-C", str(staged / "ComfyUI"))
        and argv[3:] == ("checkout", "--detach", "v0.28.0")
        for argv in calls
    )
    for node in nodes:
        node_root = staged / "ComfyUI" / "custom_nodes" / node["name"]
        assert any(
            argv[:3] == ("git", "-C", str(node_root))
            and argv[3:] == ("checkout", "--detach", node["revision"])
            for argv in calls
        )
    assert all(timeout > 0 for _, _, timeout, _ in commands.calls)
    assert all(isinstance(argv, tuple) for argv, _, _, _ in commands.calls)


def test_stage_maps_any_nonzero_install_exit_to_safe_runtime_error(tmp_path: Path) -> None:
    """Ignoring a failed checked install command must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    commands = FakeCommands(fail_token="torch")

    with pytest.raises(UpdateError) as raised:
        RuntimeBuilder(layout, commands, FakeJunctionOps()).stage(
            _exported_source(tmp_path / "export"), COMMIT_A
        )

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert "TOKEN=must-not-leak" not in str(raised.value)
    assert not layout.release(COMMIT_A).exists()


def test_stage_rejects_an_unpinned_custom_node_before_running_commands(tmp_path: Path) -> None:
    """Accepting a branch or tag for a custom node must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    commands = FakeCommands()
    exported = _exported_source(
        tmp_path / "export",
        custom_nodes=[
            {
                "name": "ComfyUI-Node",
                "repository": "https://example.test/node.git",
                "revision": "main",
            }
        ],
    )

    with pytest.raises(UpdateError) as raised:
        RuntimeBuilder(layout, commands, FakeJunctionOps()).stage(exported, COMMIT_A)

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert commands.calls == []


def test_stage_rejects_a_movable_comfyui_branch_before_running_commands(tmp_path: Path) -> None:
    """Accepting a movable ComfyUI branch as a version pin must make this test fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    commands = FakeCommands()
    exported = _exported_source(tmp_path / "export")
    manifest_path = exported / "worker" / "windows" / "worker-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["comfyui_version"] = "main"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(UpdateError) as raised:
        RuntimeBuilder(layout, commands, FakeJunctionOps()).stage(exported, COMMIT_A)

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert commands.calls == []


def test_stage_recovers_only_the_same_commit_interrupted_staging_directory(tmp_path: Path) -> None:
    """Rejecting a safe interrupted stage or deleting unknown staging data must fail."""
    layout = RuntimeLayout.create(tmp_path / "worker")
    interrupted = layout.staging / COMMIT_A
    interrupted.mkdir()
    (interrupted / "partial-install.txt").write_text("interrupted", encoding="utf-8")
    unknown = layout.staging / "operator-notes"
    unknown.mkdir()
    (unknown / "keep.txt").write_text("keep", encoding="utf-8")

    release = RuntimeBuilder(layout, FakeCommands(), FakeJunctionOps()).stage(
        _exported_source(tmp_path / "export"), COMMIT_A
    )

    assert release.is_dir()
    assert (unknown / "keep.txt").read_text(encoding="utf-8") == "keep"


def _staged_release(tmp_path: Path, commit: str = COMMIT_A) -> tuple[RuntimeLayout, Path]:
    layout = RuntimeLayout.create(tmp_path / "worker")
    (layout.config / "worker.json").write_text(
        json.dumps({"token": "file-only-secret"}), encoding="utf-8"
    )
    release = RuntimeBuilder(layout, FakeCommands(), FakeJunctionOps()).stage(
        _exported_source(tmp_path / "export", commit), commit
    )
    return layout, release


@pytest.mark.parametrize("junction_parent", ["staging", "validation-state"])
def test_validator_rejects_external_validation_state_junction_before_mutation(
    tmp_path: Path, junction_parent: str
) -> None:
    """Following a validation-state junction before checking it must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    external = tmp_path / "external-validation-state"
    child = (
        external / "validation-state" / COMMIT_A
        if junction_parent == "staging"
        else external / COMMIT_A
    )
    child.mkdir(parents=True)
    sentinel = external / "keep.txt"
    child_sentinel = child / "keep-child.txt"
    sentinel.write_text("keep-root", encoding="utf-8")
    child_sentinel.write_text("keep-child", encoding="utf-8")
    validation_state = (
        layout.staging
        if junction_parent == "staging"
        else layout.staging / "validation-state"
    )
    junctions = WindowsJunctionOps()
    if junction_parent == "staging":
        layout.staging.rmdir()
    junctions.create(validation_state, external)
    commands = FakeCommands()

    try:
        with pytest.raises(UpdateError) as raised:
            RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

        assert raised.value.code == "WORKER_CONTRACT_FAILED"
        assert junctions.read_target(validation_state) == external.resolve(strict=True)
        assert sentinel.read_text(encoding="utf-8") == "keep-root"
        assert child_sentinel.read_text(encoding="utf-8") == "keep-child"
        assert commands.start_calls == []
    finally:
        junctions.remove(validation_state)


def test_validator_starts_both_services_on_distinct_reserved_loopback_ports(tmp_path: Path) -> None:
    """Binding staged services publicly or reusing a port must make this test fail."""
    layout, release = _staged_release(tmp_path)
    commands = FakeCommands()
    health = FakeHealth()

    RuntimeValidator(layout, commands, health).validate(COMMIT_A)

    assert len(commands.start_calls) == 2
    comfy_argv, comfy_cwd, comfy_timeout, comfy_env = commands.start_calls[0]
    worker_argv, worker_cwd, worker_timeout, worker_env = commands.start_calls[1]
    assert comfy_argv[:2] == (str(release / ".venv" / "Scripts" / "python.exe"), str(release / "ComfyUI" / "main.py"))
    assert comfy_argv[2:4] == ("--listen", "127.0.0.1")
    assert worker_argv[:4] == (
        str(release / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "uvicorn",
        "worker:app",
    )
    assert ("--host", "127.0.0.1") == worker_argv[6:8]
    assert comfy_cwd == release / "ComfyUI"
    assert worker_cwd == release / "worker" / "windows"
    assert comfy_timeout > 0 and worker_timeout > 0
    assert comfy_env is not None and comfy_env["PYTHONUTF8"] == "1"
    assert worker_env is not None and worker_env["AI_DRAWING_WORKER_ROOT"] == str(layout.root)
    assert worker_env["AI_DRAWING_WORKER_RELEASE_ROOT"] == str(release)
    assert worker_env["AI_DRAWING_WORKER_CONFIG_PATH"] == str(layout.config / "worker.json")
    state_root = Path(worker_env["AI_DRAWING_WORKER_UPDATE_STATE_ROOT"])
    assert state_root.is_dir()
    assert state_root.is_relative_to(layout.staging)
    assert worker_env["AI_DRAWING_COMFYUI_ROOT"] == str(release / "ComfyUI")
    assert worker_env["AI_DRAWING_WORKER_PARTIAL_ROOT"] == str(
        release / "cache" / ".partial"
    )
    assert worker_env["AI_DRAWING_WORKER_VERIFICATION_ROOT"] == str(
        layout.shared_cache / "verified"
    )
    assert all("file-only-secret" not in value for value in worker_env.values())
    assert len(health.staged_calls) == 1
    worker_url, comfy_url, expected_commit = health.staged_calls[0]
    assert worker_url.startswith("http://127.0.0.1:")
    assert comfy_url.startswith("http://127.0.0.1:")
    assert worker_url != comfy_url
    assert worker_env["AI_DRAWING_COMFYUI_URL"] == comfy_url
    assert expected_commit == COMMIT_A
    assert all(process.terminated for process in commands.processes)


def test_validator_holds_each_reserved_port_until_its_process_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Releasing the Worker reservation before Comfy starts must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    reservations = []
    for _ in range(2):
        reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            reservation.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(1)
        reservations.append(reservation)
    comfy_port = reservations[0].getsockname()[1]
    worker_port = reservations[1].getsockname()[1]
    monkeypatch.setattr(runtime_module, "_reserve_loopback_ports", lambda _count: tuple(reservations))
    commands = FakeCommands()
    original_start = commands.start
    launches = 0

    def can_bind(port: int) -> bool:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
        finally:
            probe.close()
        return True

    def observe_start(*args, **kwargs):
        nonlocal launches
        if launches == 0:
            assert can_bind(comfy_port)
            assert not can_bind(worker_port)
        else:
            assert can_bind(worker_port)
        launches += 1
        return original_start(*args, **kwargs)

    commands.start = observe_start  # type: ignore[method-assign]

    RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

    assert launches == 2


def test_validator_always_terminates_staging_processes_after_cuda_failure(tmp_path: Path) -> None:
    """Leaking staged processes on a failed CUDA check must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()

    with pytest.raises(UpdateError) as raised:
        RuntimeValidator(layout, commands, FakeHealth("CUDA_VALIDATION_FAILED")).validate(COMMIT_A)

    assert raised.value.code == "CUDA_VALIDATION_FAILED"
    assert len(commands.processes) == 2
    assert all(process.terminated for process in commands.processes)


@pytest.mark.parametrize(
    ("change", "error_code"),
    [
        ({"cuda_available": False}, "CUDA_VALIDATION_FAILED"),
        ({"gpu_name": ""}, "CUDA_VALIDATION_FAILED"),
        ({"system_stats_ok": False}, "COMFYUI_VALIDATION_FAILED"),
        ({"object_info_ok": False}, "COMFYUI_VALIDATION_FAILED"),
        ({"authenticated_status_ok": False}, "WORKER_CONTRACT_FAILED"),
        ({"resource_plan_ok": False}, "WORKER_CONTRACT_FAILED"),
        ({"preflight_ok": False}, "WORKER_CONTRACT_FAILED"),
        ({"source_commit": COMMIT_B}, "WORKER_CONTRACT_FAILED"),
    ],
)
def test_validator_requires_every_staged_health_check_and_exact_commit(
    tmp_path: Path, change: dict[str, object], error_code: str
) -> None:
    """Omitting any complete-health signal must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    evidence = replace(HealthEvidence.complete(COMMIT_A), **change)

    with pytest.raises(UpdateError) as raised:
        RuntimeValidator(layout, FakeCommands(), FakeHealth(evidence=evidence)).validate(COMMIT_A)

    assert raised.value.code == error_code


def test_validator_terminates_first_process_when_worker_staging_port_start_fails(tmp_path: Path) -> None:
    """Leaking ComfyUI when the staged Worker cannot start must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands(fail_start_token="uvicorn")

    with pytest.raises(UpdateError) as raised:
        RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

    assert raised.value.code == "WORKER_CONTRACT_FAILED"
    assert len(commands.processes) == 1
    assert commands.processes[0].terminated


def test_validator_kills_a_staging_process_that_ignores_terminate(tmp_path: Path) -> None:
    """Stopping after terminate without a bounded kill fallback must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()
    stubborn = FakeProcess(timeout_once=True)

    def start_stubborn(*_args, **_kwargs):
        process = stubborn if not commands.processes else FakeProcess()
        commands.processes.append(process)
        return process

    commands.start = start_stubborn  # type: ignore[method-assign]

    RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

    assert stubborn.terminated
    assert stubborn.killed
    assert len(stubborn.waits) == 2
    assert all(timeout > 0 for timeout in stubborn.waits)


def test_validator_reports_cleanup_failure_after_attempting_every_process(tmp_path: Path) -> None:
    """Swallowing kill/second-wait failure and returning success must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()
    stubborn = FakeProcess(timeout_once=True, fail_second_wait=True)

    def start_with_stubborn(*args, **kwargs):
        process = stubborn if not commands.processes else FakeProcess()
        commands.processes.append(process)
        return process

    commands.start = start_with_stubborn  # type: ignore[method-assign]

    with pytest.raises(RuntimeValidationError) as raised:
        RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

    assert raised.value.code == "CLEANUP_FAILED"
    assert all(process.terminated for process in commands.processes)
    assert stubborn.killed
    assert len(stubborn.waits) == 2


def test_validator_preserves_primary_health_code_and_chains_cleanup_failure(tmp_path: Path) -> None:
    """Replacing the health failure or hiding cleanup failure must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()
    stubborn = FakeProcess(timeout_once=True, fail_second_wait=True)

    def start_with_stubborn(*args, **kwargs):
        process = stubborn if not commands.processes else FakeProcess()
        commands.processes.append(process)
        return process

    commands.start = start_with_stubborn  # type: ignore[method-assign]

    with pytest.raises(RuntimeValidationError) as raised:
        RuntimeValidator(layout, commands, FakeHealth("CUDA_VALIDATION_FAILED")).validate(COMMIT_A)

    assert raised.value.code == "CUDA_VALIDATION_FAILED"
    assert raised.value.cleanup_code == "CLEANUP_FAILED"
    assert isinstance(raised.value.__cause__, RuntimeValidationError)
    assert raised.value.__cause__.code == "CLEANUP_FAILED"
    assert all(process.terminated for process in commands.processes)


def test_validator_continues_cleaning_other_processes_after_unexpected_adapter_error(
    tmp_path: Path,
) -> None:
    """Stopping cleanup on a non-OSError adapter failure must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()
    normal = FakeProcess()
    failing = FakeProcess(fail_terminate=True)

    def start_in_order(*args, **kwargs):
        process = normal if not commands.processes else failing
        commands.processes.append(process)
        return process

    commands.start = start_in_order  # type: ignore[method-assign]

    with pytest.raises(RuntimeValidationError) as raised:
        RuntimeValidator(layout, commands, FakeHealth()).validate(COMMIT_A)

    assert raised.value.code == "CLEANUP_FAILED"
    assert normal.terminated
    assert failing.terminated


@pytest.mark.parametrize(
    ("failure_point", "signal"),
    [
        ("comfy", KeyboardInterrupt("stop-comfy")),
        ("comfy", SystemExit(21)),
        ("worker", KeyboardInterrupt("stop-worker")),
        ("worker", SystemExit(22)),
        ("probe", KeyboardInterrupt("stop-probe")),
        ("probe", SystemExit(23)),
    ],
    ids=[
        "comfy-keyboard-interrupt",
        "comfy-system-exit",
        "worker-keyboard-interrupt",
        "worker-system-exit",
        "probe-keyboard-interrupt",
        "probe-system-exit",
    ],
)
def test_validator_cleans_every_resource_before_reraising_base_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    signal: BaseException,
) -> None:
    """Letting a BaseException bypass staged cleanup must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    reservations = tuple(runtime_module._reserve_loopback_ports(2))
    monkeypatch.setattr(
        runtime_module, "_reserve_loopback_ports", lambda _count: reservations
    )
    commands = FakeCommands()
    original_start = commands.start
    launches = 0

    def start_or_interrupt(*args, **kwargs):
        nonlocal launches
        point = "comfy" if launches == 0 else "worker"
        launches += 1
        if failure_point == point:
            raise signal
        return original_start(*args, **kwargs)

    commands.start = start_or_interrupt  # type: ignore[method-assign]
    health = FakeHealth()
    if failure_point == "probe":
        def interrupt_probe(*_args, **_kwargs):
            raise signal

        health.validate_staged = interrupt_probe  # type: ignore[method-assign]

    with pytest.raises(type(signal)) as raised:
        RuntimeValidator(layout, commands, health).validate(COMMIT_A)

    assert raised.value is signal
    assert all(reservation.fileno() == -1 for reservation in reservations)
    assert all(process.terminated for process in commands.processes)
    assert len(commands.processes) == {"comfy": 0, "worker": 1, "probe": 2}[
        failure_point
    ]


def test_validator_preserves_base_exception_when_cleanup_also_fails(tmp_path: Path) -> None:
    """Dropping either a SystemExit primary or typed cleanup metadata must make this test fail."""
    layout, _release = _staged_release(tmp_path)
    commands = FakeCommands()
    stubborn = FakeProcess(timeout_once=True, fail_second_wait=True)
    signal = SystemExit(37)

    def start_with_stubborn(*args, **kwargs):
        process = stubborn if not commands.processes else FakeProcess()
        commands.processes.append(process)
        return process

    def interrupt_probe(*_args, **_kwargs):
        raise signal

    commands.start = start_with_stubborn  # type: ignore[method-assign]
    health = FakeHealth()
    health.validate_staged = interrupt_probe  # type: ignore[method-assign]

    with pytest.raises(RuntimeValidationError) as raised:
        RuntimeValidator(layout, commands, health).validate(COMMIT_A)

    assert raised.value.code == "WORKER_CONTRACT_FAILED"
    assert raised.value.cleanup_code == "CLEANUP_FAILED"
    assert raised.value.primary_exception is signal
    assert raised.value.cleanup_failures
    assert isinstance(raised.value.__cause__, RuntimeValidationError)
    assert raised.value.__cause__.code == "CLEANUP_FAILED"
    assert all(process.terminated for process in commands.processes)


def _activation_layout(
    tmp_path: Path,
) -> tuple[RuntimeLayout, FakeJunctionOps, Path, Path]:
    layout = RuntimeLayout.create(tmp_path / "worker")
    release_a = layout.release(COMMIT_A)
    release_b = layout.release(COMMIT_B)
    for release, commit in ((release_a, COMMIT_A), (release_b, COMMIT_B)):
        release.mkdir()
        (release / "source-commit.txt").write_text(commit + "\n", encoding="utf-8")
        (release / ".managed-release.json").write_text(
            json.dumps({"commit": commit, "schema": 1}), encoding="utf-8"
        )
    junctions = FakeJunctionOps()
    junctions.create(layout.current, release_a)
    return layout, junctions, release_a, release_b


def test_failed_production_health_restores_and_verifies_previous_junction(tmp_path: Path) -> None:
    """Leaving an unhealthy target current or skipping rollback health must fail."""
    layout, junctions, release_a, _release_b = _activation_layout(tmp_path)
    health = FakeHealth(fail_production_for={COMMIT_B})

    result = Activator(layout, health, junctions).activate(COMMIT_B)

    assert result.status == "rolled_back"
    assert result.error_code == "ACTIVATION_FAILED_ROLLED_BACK"
    assert junctions.read_target(layout.current) == release_a
    assert [call[2] for call in health.production_calls] == [COMMIT_B, COMMIT_A]
    assert not (layout.root / "current.next").exists()
    assert not (layout.root / "current.previous-switch").exists()


@pytest.mark.parametrize(
    "failure",
    [
        "create:current.next",
        "rename:current:current.previous-switch",
        "rename:current.next:current",
    ],
)
def test_each_junction_transaction_interruption_recovers_previous(
    tmp_path: Path, failure: str
) -> None:
    """Failing any junction transaction step without recovery must fail."""
    layout, junctions, release_a, _release_b = _activation_layout(tmp_path)
    junctions.fail_once.add(failure)
    health = FakeHealth()

    result = Activator(layout, health, junctions).activate(COMMIT_B)

    assert result.status == "rolled_back"
    assert junctions.read_target(layout.current) == release_a
    assert health.production_calls[-1][2] == COMMIT_A
    assert not (layout.root / "current.next").exists()
    assert not (layout.root / "current.previous-switch").exists()


@pytest.mark.parametrize("phase", ["old_renamed", "candidate_current"])
def test_activation_recovers_stale_switch_transaction_before_retry(
    tmp_path: Path, phase: str
) -> None:
    """Ignoring stale next/previous-switch junctions must make this test fail."""
    layout, junctions, release_a, release_b = _activation_layout(tmp_path)
    next_link = layout.root / "current.next"
    switch_link = layout.root / "current.previous-switch"
    junctions.create(next_link, release_b)
    junctions.rename(layout.current, switch_link)
    if phase == "candidate_current":
        junctions.rename(next_link, layout.current)
    junctions.fail_once.add("create:current.next")
    health = FakeHealth()

    result = Activator(layout, health, junctions).activate(COMMIT_B)

    assert result.status == "rolled_back"
    assert junctions.read_target(layout.current) == release_a
    assert not next_link.exists()
    assert not switch_link.exists()


def test_activation_recovers_stale_previous_before_rejecting_invalid_candidate(
    tmp_path: Path,
) -> None:
    """Validating the requested release before stale recovery must make this test fail."""
    layout, junctions, release_a, release_b = _activation_layout(tmp_path)
    next_link = layout.root / "current.next"
    switch_link = layout.root / "current.previous-switch"
    junctions.create(next_link, release_b)
    junctions.rename(layout.current, switch_link)
    junctions.rename(next_link, layout.current)
    (release_b / ".managed-release.json").unlink()

    with pytest.raises(UpdateError) as raised:
        Activator(layout, FakeHealth(), junctions).activate(COMMIT_B)

    assert raised.value.code == "RUNTIME_INSTALL_FAILED"
    assert junctions.read_target(layout.current) == release_a
    assert not next_link.exists()
    assert not switch_link.exists()


def test_failed_rollback_verification_requires_operator_recovery(tmp_path: Path) -> None:
    """Reporting rolled_back without proving the old release healthy must fail."""
    layout, junctions, _release_a, _release_b = _activation_layout(tmp_path)
    health = FakeHealth(fail_production_for={COMMIT_A, COMMIT_B})

    result = Activator(layout, health, junctions).activate(COMMIT_B)

    assert result.status == "recovery_required"
    assert result.error_code == "RECOVERY_REQUIRED"
    assert [call[2] for call in health.production_calls] == [COMMIT_B, COMMIT_A]


def test_success_validates_exact_target_then_retains_only_current_and_previous_known_releases(
    tmp_path: Path,
) -> None:
    """Pruning before health or deleting unknown/staging data must make this test fail."""
    layout, junctions, release_a, release_b = _activation_layout(tmp_path)
    old_known_commit = "c" * 40
    old_known = layout.release(old_known_commit)
    old_known.mkdir()
    (old_known / "source-commit.txt").write_text(old_known_commit + "\n", encoding="utf-8")
    (old_known / ".managed-release.json").write_text(
        json.dumps({"commit": old_known_commit, "schema": 1}), encoding="utf-8"
    )
    mismatched = layout.release("d" * 40)
    mismatched.mkdir()
    (mismatched / "source-commit.txt").write_text("e" * 40 + "\n", encoding="utf-8")
    unknown = layout.releases / "operator-snapshot"
    unknown.mkdir()
    unmarked_commit = "f" * 40
    unmarked = layout.release(unmarked_commit)
    unmarked.mkdir()
    (unmarked / "source-commit.txt").write_text(unmarked_commit + "\n", encoding="utf-8")
    staged = layout.staging / old_known_commit
    staged.mkdir()
    shared_marker = layout.shared_models / "keep.safetensors"
    shared_marker.write_text("keep", encoding="utf-8")
    health = FakeHealth()

    result = Activator(layout, health, junctions).activate(COMMIT_B)

    assert result.status == "ready"
    assert result.current_commit == COMMIT_B
    assert result.previous_commit == COMMIT_A
    assert junctions.read_target(layout.current) == release_b
    assert [call[2] for call in health.production_calls] == [COMMIT_B]
    assert release_a.is_dir() and release_b.is_dir()
    assert not old_known.exists()
    assert mismatched.is_dir()
    assert unknown.is_dir()
    assert unmarked.is_dir()
    assert staged.is_dir()
    assert shared_marker.read_text(encoding="utf-8") == "keep"
