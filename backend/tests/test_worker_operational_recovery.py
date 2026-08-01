"""Cross-module regressions for first update, restart, and crash recovery."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

from worker.windows.updater.state import UpdateStateStore


COMMIT = "a" * 40


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
    assert "-m updater.recovery" in start
    assert start.index("-m updater.recovery") < start.index('$Current = Join-Path $Root "current"')


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
