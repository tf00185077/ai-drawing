"""Cross-module regressions for first update, restart, and crash recovery."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from worker.windows.updater.state import UpdateStateStore


COMMIT = "a" * 40


def _create_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        pytest.skip(f"junction creation unavailable: {result.stderr or result.stdout}")


def _run_worker_install_helper(command: str) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    helper = repo / "worker/windows/WorkerInstall.ps1"
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f'. "{helper}"; {command}',
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.skipif(os.name != "nt", reason="PowerShell installer integration requires Windows")
def test_installer_checked_uv_install_uses_system_and_stops_on_failure(tmp_path: Path) -> None:
    """Dropping --system or ignoring uv's exit code must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    helper = repo / "worker/windows/WorkerInstall.ps1"
    arguments_path = tmp_path / "uv-args.txt"
    fake_uv = tmp_path / "fake-uv.cmd"
    fake_uv.write_text(
        f'@echo off\r\necho %* > "{arguments_path}"\r\nexit /b 23\r\n',
        encoding="utf-8",
    )
    command = (
        f'. "{helper}"; '
        f'Invoke-WorkerPipInstall -Uv "{fake_uv}" -Python "C:\\runtime\\python.exe" '
        '-Arguments @("-r", "requirements.txt")'
    )

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    assert "INSTALL_DEPENDENCY_FAILED" in result.stderr
    assert arguments_path.read_text(encoding="utf-8").strip() == (
        "pip install --system --break-system-packages --python "
        "C:\\runtime\\python.exe -r requirements.txt"
    )


@pytest.mark.skipif(os.name != "nt", reason="PowerShell installer integration requires Windows")
def test_installer_forces_cuda_wheels_and_fails_when_cuda_is_unavailable(tmp_path: Path) -> None:
    """A same-version CPU torch wheel or a missing final CUDA gate must fail this test."""
    uv_arguments = tmp_path / "uv-args.txt"
    fake_uv = tmp_path / "fake-uv.cmd"
    fake_uv.write_text(
        f'@echo off\r\necho %* > "{uv_arguments}"\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    fake_python = tmp_path / "fake-python.cmd"
    fake_python.write_text("@echo off\r\nexit /b 9\r\n", encoding="utf-8")
    command = (
        f'Invoke-CudaPipInstall -Uv "{fake_uv}" -Python "{fake_python}" '
        '-IndexUrl "https://download.pytorch.org/whl/cu130"; '
        f'Assert-WorkerCudaRuntime -Python "{fake_python}"'
    )

    result = _run_worker_install_helper(command)

    assert result.returncode != 0
    assert "INSTALL_CUDA_UNAVAILABLE" in result.stderr
    arguments = uv_arguments.read_text(encoding="utf-8").strip()
    assert "--index-url https://download.pytorch.org/whl/cu130" in arguments
    assert "--reinstall-package torch" in arguments
    assert "--reinstall-package torchvision" in arguments
    assert "--reinstall-package torchaudio" in arguments


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration requires Windows")
def test_installer_normalizes_only_internal_uv_python_alias(tmp_path: Path) -> None:
    """Leaving uv's validated internal alias must make managed bootstrap fail."""
    python_root = tmp_path / "runtime" / "python"
    concrete = python_root / "cpython-3.12.13-windows-x86_64-none"
    concrete.mkdir(parents=True)
    (concrete / "python.exe").write_bytes(b"concrete-python")
    sentinel = concrete / "sentinel.txt"
    sentinel.write_text("preserved", encoding="utf-8")
    alias = python_root / "cpython-3.12-windows-x86_64-none"
    _create_junction(alias, concrete)
    command = (
        f'$Python = Get-ConcreteInstalledPython -PythonRoot "{python_root}" '
        '-ExpectedVersion "3.12"; '
        f'Remove-TrustedUvPythonAliases -PythonRoot "{python_root}" -SelectedPython $Python; '
        '[pscustomobject]@{python=$Python;alias_exists=(Test-Path -LiteralPath '
        f'"{alias}");target_sentinel=[string](Get-Content -LiteralPath "{sentinel}" -Raw)}} '
        '| ConvertTo-Json -Compress'
    )

    result = _run_worker_install_helper(command)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["alias_exists"] is False
    assert payload["target_sentinel"] == "preserved"
    assert "cpython-3.12.13-windows-x86_64-none" in payload["python"]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration requires Windows")
@pytest.mark.parametrize("alias_name", ["cpython-3.12-windows-x86_64-none", "unexpected-python"])
def test_installer_never_removes_untrusted_python_reparse(tmp_path: Path, alias_name: str) -> None:
    """An external target or an unrecognized alias must remain untouched and fail closed."""
    python_root = tmp_path / "runtime" / "python"
    concrete = python_root / "cpython-3.12.13-windows-x86_64-none"
    concrete.mkdir(parents=True)
    selected_python = concrete / "python.exe"
    selected_python.write_bytes(b"concrete-python")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserved", encoding="utf-8")
    alias = python_root / alias_name
    _create_junction(alias, outside)
    command = (
        f'Remove-TrustedUvPythonAliases -PythonRoot "{python_root}" '
        f'-SelectedPython "{selected_python}"'
    )

    result = _run_worker_install_helper(command)

    assert result.returncode != 0
    assert "INSTALL_PYTHON_REPARSE_UNSAFE" in result.stderr
    assert alias.exists()
    assert sentinel.read_text(encoding="utf-8") == "preserved"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration requires Windows")
def test_startup_resolves_current_to_concrete_managed_release(tmp_path: Path) -> None:
    """Passing the current junction itself to the Worker must make this test fail."""
    root = tmp_path / "worker"
    release = root / "releases" / COMMIT
    release.mkdir(parents=True)
    current = root / "current"
    _create_junction(current, release)
    repo = Path(__file__).resolve().parents[2]
    helper = repo / "worker/windows/WorkerPaths.ps1"
    command = f'. "{helper}"; Resolve-ManagedCurrentRelease -Root "{root}"'

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == release


@pytest.mark.skipif(os.name != "nt", reason="Windows junction integration requires Windows")
def test_startup_rejects_current_junction_outside_releases(tmp_path: Path) -> None:
    """An external current target must remain unusable and untouched."""
    root = tmp_path / "worker"
    (root / "releases").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserved", encoding="utf-8")
    _create_junction(root / "current", outside)
    repo = Path(__file__).resolve().parents[2]
    helper = repo / "worker/windows/WorkerPaths.ps1"
    command = f'. "{helper}"; Resolve-ManagedCurrentRelease -Root "{root}"'

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    assert "WORKER_CURRENT_INVALID" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "preserved"


def test_worker_queue_to_privileged_state_keeps_public_correlation(tmp_path: Path) -> None:
    """The Mac poll contract must survive every privileged state transition."""
    request = tmp_path / "update-request.json"
    request.write_text(
        json.dumps(
            {
                "request_id": "request-1",
                "target_commit": COMMIT,
                "timestamp": "2026-08-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    store = UpdateStateStore(tmp_path)
    active = store.claim_queued_request(request)
    assert active is not None

    for state in (
        "queued",
        "fetching",
        "staging",
        "installing",
        "validating",
        "activating",
        "restarting",
        "ready",
    ):
        if state != "queued":
            store.transition(state)
        public = store.read_public()
        assert public["state"] == state
        assert public["request_id"] == "request-1"
        assert public["target_commit"] == COMMIT
        assert isinstance(public["timestamp"], str) and public["timestamp"]


def test_installer_bootstraps_managed_release_before_worker_start() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")
    conversion = installer.index("Initialize-ManagedWorkerLayout")
    startup = installer.index('Start-Process (Join-Path $Root "Start-Worker.cmd")')
    assert conversion < startup
    block = installer[conversion:startup]
    assert "current" in block
    assert "releases" in block
    assert "source-commit.txt" in block
    assert "MIGRATION" in block


def test_existing_install_is_stopped_before_runtime_copy_and_bootstrap() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")
    stop_task = installer.index("Stop-ScheduledTask")
    stop_ports = installer.index("Get-NetTCPConnection -LocalPort 8188, 8791")
    copy_runtime = installer.index('Copy-Item (Join-Path $Source "worker.py")')
    bootstrap = installer.index("Initialize-ManagedWorkerLayout")
    assert stop_task < copy_runtime < bootstrap
    assert stop_ports < copy_runtime
    assert ".ai-drawing-worker-owned" in installer[:copy_runtime]


def test_installer_refreshes_owned_source_before_managed_bootstrap() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")
    remote_check = installer.index("remote does not match the pinned manifest")
    fetch = installer.index("fetch --prune origin")
    reset = installer.index('reset --hard "origin/$ExpectedBranch"')
    bootstrap = installer.index("Initialize-ManagedWorkerLayout")
    assert remote_check < fetch < reset < bootstrap


def test_updater_runtime_creation_uses_owned_python_not_windows_launcher() -> None:
    repo = Path(__file__).resolve().parents[2]
    runtime = (repo / "worker/windows/updater/runtime.py").read_text(encoding="utf-8")
    assert 'self._checked(("py",' not in runtime
    assert "sys.executable" in runtime


def test_restart_entrypoints_resolve_migrated_root_and_lock_by_handle() -> None:
    repo = Path(__file__).resolve().parents[2]
    root = repo / "worker/windows"
    launcher = (root / "Restart-Worker.cmd").read_text(encoding="utf-8")
    waiter = (root / "Wait-Restart-Result.ps1").read_text(encoding="utf-8")
    task = (root / "Restart-Worker.ps1").read_text(encoding="utf-8")

    assert "%ProgramData%\\AI-Drawing-Worker\\Wait-Restart-Result.ps1" in launcher
    assert "C:\\AI-Drawing-Worker\\Wait-Restart-Result.ps1" not in launcher
    assert "updater.env" in waiter and "AI_DRAWING_WORKER_ROOT" in waiter
    assert "FileMode]::OpenOrCreate" in task
    assert "FileShare]::None" in task
    assert "Remove-Item -LiteralPath $LockPath" not in task


def test_login_startup_runs_fixed_activation_recovery_before_current_resolution() -> None:
    repo = Path(__file__).resolve().parents[2]
    start = (repo / "worker/windows/Start-Worker.ps1").read_text(encoding="utf-8")
    recovery = repo / "worker/windows/updater/recovery.py"
    assert recovery.is_file()
    assert "-B -m updater.recovery" in start
    assert start.index("-m updater.recovery") < start.index('$Current = Join-Path $Root "current"')


def test_login_startup_uses_the_release_partial_junction() -> None:
    repo = Path(__file__).resolve().parents[2]
    start = (repo / "worker/windows/Start-Worker.ps1").read_text(encoding="utf-8")

    assert (
        '$env:AI_DRAWING_WORKER_PARTIAL_ROOT = Join-Path $ReleaseRoot "cache\\.partial"'
        in start
    )


def test_runtime_builder_default_python_is_running_updater_interpreter(tmp_path: Path) -> None:
    from worker.windows.updater.runtime import RuntimeBuilder, RuntimeLayout

    class Commands:
        def run(self, argv, *, cwd, timeout, env=None):  # pragma: no cover - not invoked
            raise AssertionError

    builder = RuntimeBuilder(RuntimeLayout.create(tmp_path / "managed"), Commands())
    assert builder.bootstrap_python == Path(sys.executable).resolve()


def test_login_recovery_skips_activation_that_owns_updater_lock(monkeypatch) -> None:
    """Candidate startup must not deadlock with or undo its owning activation."""
    from worker.windows.updater import recovery
    from worker.windows.updater.git_source import UpdateError

    class Services:
        recovered = False

        @contextmanager
        def run_lock(self):
            raise UpdateError("UPDATE_ALREADY_RUNNING", "active")
            yield

        def recover_activation(self):
            self.recovered = True

    services = Services()
    monkeypatch.setattr(
        recovery.ProductionUpdaterServices,
        "from_program_data",
        classmethod(lambda _cls: services),
    )
    assert recovery.main([]) == recovery.EXIT_READY
    assert services.recovered is False


def test_restart_task_queues_request_arriving_during_ready_exit_window() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")
    assert "$RestartTaskSettings = New-ScheduledTaskSettingsSet" in installer
    assert "-MultipleInstances Queue" in installer


def test_existing_verified_migration_junction_is_retryable() -> None:
    repo = Path(__file__).resolve().parents[2]
    migration = (repo / "worker/windows/Migrate-Worker.ps1").read_text(encoding="utf-8")
    start = migration.index("function New-MigrationJunction")
    end = migration.index("function New-FirstMigrationRelease")
    block = migration[start:end]
    existing = block.index("if (Test-Path -LiteralPath $Link)")
    reject_link = block.index("Assert-MigrationTargetPathNoFollow -Root $Root -Path $Link")
    assert existing < reject_link
