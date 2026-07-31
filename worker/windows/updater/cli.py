"""Fixed, argument-free privileged orchestration for managed Worker updates."""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, ContextManager, Protocol

from .config import UpdaterConfigError, load_updater_config
from .git_source import GitSource, UpdateError
from .runtime import (
    ActivationResult,
    Activator,
    RuntimeBuilder,
    RuntimeLayout,
    RuntimeValidator,
    WindowsJunctionOps,
)
from .state import (
    PUBLIC_ERROR_CODES,
    ActiveUpdateRequest,
    InvalidUpdateTransition,
    StateStoreError,
    UpdateStateStore,
)
from .windows_runtime import (
    HttpHealthProbe,
    ScheduledTaskController,
    SubprocessCommandRunner,
    WorkerTokenProvider,
)


EXIT_READY = 0
EXIT_INVALID_INVOCATION = 2
EXIT_CONFIG_INVALID = 10
EXIT_FAILED_BEFORE_ACTIVATION = 20
EXIT_ROLLED_BACK = 30
EXIT_RECOVERY_REQUIRED = 40
PROGRAM_DATA_DIRECTORY = "AI-Drawing-Worker"
REQUEST_FILENAME = "update-request.json"

_PRE_ACTIVATION_STATES = {"queued", "fetching", "staging", "installing", "validating"}
_SAFE_MESSAGES = {
    "UPDATE_ALREADY_RUNNING": "another updater process is already running",
    "TARGET_COMMIT_INVALID": "the queued target commit is invalid",
    "MAC_COMMIT_NOT_ORIGIN_MAIN": "the requested commit is not the approved source head",
    "WINDOWS_REMOTE_HEAD_MISMATCH": "the requested commit differs from the fetched branch head",
    "UPDATER_CONFIG_INVALID": "the local updater configuration is invalid",
    "SOURCE_REPOSITORY_INVALID": "the configured source repository could not be verified",
    "INSUFFICIENT_DISK_SPACE": "the managed runtime has insufficient free space",
    "RUNTIME_INSTALL_FAILED": "the candidate runtime could not be installed",
    "CUDA_VALIDATION_FAILED": "the candidate runtime did not prove CUDA health",
    "COMFYUI_VALIDATION_FAILED": "the candidate runtime did not prove ComfyUI health",
    "WORKER_CONTRACT_FAILED": "the candidate runtime did not prove the Worker contract",
    "ACTIVATION_FAILED_ROLLED_BACK": "activation failed and the previous release was restored",
    "RECOVERY_REQUIRED": "automatic recovery could not be proven",
    "UPDATE_FAILED": "the managed update failed",
}


class UpdaterServices(Protocol):
    state: UpdateStateStore

    def claim_request(self) -> ActiveUpdateRequest | None: ...

    def candidate_exists(self, target_commit: str) -> bool: ...

    def fetch(self, target_commit: str) -> Path: ...

    def install(self, exported: Path, target_commit: str) -> Path: ...

    def validate(self, target_commit: str) -> Path: ...

    def activate(
        self, target_commit: str, on_restarting: Callable[[], None]
    ) -> ActivationResult: ...


class ProductionUpdaterServices:
    """Bind the updater's public contracts to fixed local production adapters."""

    def __init__(self, env_path: Path) -> None:
        config = load_updater_config(env_path)
        self.layout = RuntimeLayout.create(config.worker_root)
        state_root = config.worker_root / "config" / "update-owned" / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        self.state = UpdateStateStore(state_root)
        self.request_path = state_root / REQUEST_FILENAME
        self._run_lock_path = state_root / "updater-run.lock"
        self._source = GitSource(config.project_root, config.remote, config.branch)
        commands = SubprocessCommandRunner()
        junctions = WindowsJunctionOps()
        production = ScheduledTaskController(commands)
        health = HttpHealthProbe(
            WorkerTokenProvider(config.worker_root, self.layout.config / "worker.json"),
            production,
        )
        self._builder = RuntimeBuilder(self.layout, commands, junctions)
        self._validator = RuntimeValidator(self.layout, commands, health)
        self._activator = Activator(self.layout, health, junctions)

    @classmethod
    def from_program_data(cls) -> "ProductionUpdaterServices":
        return cls(_program_data_env_path())

    def run_lock(self) -> ContextManager[None]:
        return _RunLock(self._run_lock_path)

    def claim_request(self) -> ActiveUpdateRequest:
        return self.state.claim_queued_request(self.request_path)

    def candidate_exists(self, target_commit: str) -> bool:
        release = self.layout.release(target_commit)
        try:
            return (
                release.is_dir()
                and (release / "source-commit.txt").read_text(encoding="utf-8").strip()
                == target_commit
                and (release / ".managed-release.json").is_file()
            )
        except (OSError, UnicodeError):
            return False

    def fetch(self, target_commit: str) -> Path:
        parent = Path(
            tempfile.mkdtemp(prefix=f"source-{target_commit[:12]}-", dir=self.layout.staging)
        )
        destination = parent / "export"
        try:
            return self._source.export_commit(target_commit, destination)
        except BaseException:
            shutil.rmtree(parent, ignore_errors=True)
            raise

    def install(self, exported: Path, target_commit: str) -> Path:
        try:
            return self._builder.stage(exported, target_commit)
        finally:
            parent = Path(exported).parent
            try:
                if parent.parent.resolve(strict=True) == self.layout.staging.resolve(strict=True):
                    shutil.rmtree(parent, ignore_errors=True)
            except OSError:
                pass

    def validate(self, target_commit: str) -> Path:
        return self._validator.validate(target_commit)

    def activate(
        self, target_commit: str, on_restarting: Callable[[], None]
    ) -> ActivationResult:
        return self._activator.activate(target_commit, on_restarting=on_restarting)


def main(argv: list[str] | None = None, *, services: UpdaterServices | None = None) -> int:
    """Run one fixed queued update; command-line selectors are never accepted."""
    arguments = list(os.sys.argv[1:] if argv is None else argv)
    if arguments:
        return EXIT_INVALID_INVOCATION
    try:
        updater = services or ProductionUpdaterServices.from_program_data()
        lock_factory = getattr(updater, "run_lock", None)
        lock = lock_factory() if callable(lock_factory) else nullcontext()
        with lock:
            return _run_update(updater)
    except (UpdaterConfigError, StateStoreError):
        return EXIT_CONFIG_INVALID
    except UpdateError:
        return EXIT_RECOVERY_REQUIRED
    except (OSError, ValueError):
        return EXIT_RECOVERY_REQUIRED


def _run_update(services: UpdaterServices) -> int:
    request = services.claim_request()
    if request is None:
        return EXIT_CONFIG_INVALID
    target_commit = request.target_commit
    try:
        candidate_exists = services.candidate_exists(target_commit)
        active = _require_active(services.state)
        exported: Path | None = None

        if active.state in _PRE_ACTIVATION_STATES:
            if active.state == "queued":
                services.state.transition("fetching")
                active = _require_active(services.state)
            if not candidate_exists:
                exported = services.fetch(target_commit)
            if active.state == "fetching":
                services.state.transition("staging")
                active = _require_active(services.state)
            if active.state == "staging":
                services.state.transition("installing")
                active = _require_active(services.state)
            if not candidate_exists:
                if exported is None:
                    raise UpdateError("RUNTIME_INSTALL_FAILED", "candidate export is unavailable")
                services.install(exported, target_commit)
                candidate_exists = True
            if active.state == "installing":
                services.state.transition("validating")
                active = _require_active(services.state)
            if active.state == "validating":
                services.validate(target_commit)
                services.state.transition("activating")
                active = _require_active(services.state)

        if active.state not in {"activating", "restarting"}:
            raise InvalidUpdateTransition(f"cannot activate from {active.state}")

        def on_restarting() -> None:
            current = _require_active(services.state)
            if current.state == "activating":
                services.state.transition("restarting")
            elif current.state != "restarting":
                raise InvalidUpdateTransition(
                    f"cannot announce restart from {current.state}"
                )

        result = services.activate(target_commit, on_restarting)
        return _finish_activation(services.state, result)
    except Exception as error:
        return _record_failure(services.state, error)


def _finish_activation(state: UpdateStateStore, result: ActivationResult) -> int:
    current = _require_active(state)
    if result.status == "ready":
        if current.state != "restarting":
            raise InvalidUpdateTransition("activation returned ready before restart was recorded")
        state.transition("ready")
        return EXIT_READY
    if result.status == "rolled_back":
        state.terminal_failure(
            "rolled_back",
            "ACTIVATION_FAILED_ROLLED_BACK",
            _SAFE_MESSAGES["ACTIVATION_FAILED_ROLLED_BACK"],
        )
        return EXIT_ROLLED_BACK
    state.terminal_failure(
        "recovery_required",
        "RECOVERY_REQUIRED",
        _SAFE_MESSAGES["RECOVERY_REQUIRED"],
    )
    return EXIT_RECOVERY_REQUIRED


def _record_failure(state: UpdateStateStore, error: Exception) -> int:
    try:
        active = state.read_active_request()
        if active is None:
            return EXIT_CONFIG_INVALID
        if active.state in {"activating", "restarting"}:
            code = "RECOVERY_REQUIRED"
            state.terminal_failure(
                "recovery_required", code, _SAFE_MESSAGES[code]
            )
            return EXIT_RECOVERY_REQUIRED
        code = _mapped_error_code(error, active.state)
        state.fail(code, _SAFE_MESSAGES[code])
        return EXIT_FAILED_BEFORE_ACTIVATION
    except (InvalidUpdateTransition, StateStoreError, OSError):
        return EXIT_RECOVERY_REQUIRED


def _mapped_error_code(error: Exception, state: str) -> str:
    code = error.code if isinstance(error, UpdateError) else "UPDATE_FAILED"
    if code == "GIT_COMMAND_FAILED":
        return "SOURCE_REPOSITORY_INVALID"
    if code in PUBLIC_ERROR_CODES:
        return code
    return {
        "queued": "TARGET_COMMIT_INVALID",
        "fetching": "SOURCE_REPOSITORY_INVALID",
        "staging": "RUNTIME_INSTALL_FAILED",
        "installing": "RUNTIME_INSTALL_FAILED",
        "validating": "WORKER_CONTRACT_FAILED",
    }.get(state, "UPDATE_FAILED")


def _require_active(state: UpdateStateStore) -> ActiveUpdateRequest:
    active = state.read_active_request()
    if active is None:
        raise StateStoreError("active update request is unavailable")
    return active


def _program_data_env_path() -> Path:
    program_data = os.environ.get("ProgramData")
    if not program_data:
        raise UpdaterConfigError("ProgramData is unavailable")
    return Path(program_data) / PROGRAM_DATA_DIRECTORY / "updater.env"


class _RunLock:
    """Prevent overlapping manual task launches in addition to scheduler policy."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._file: Any | None = None

    def __enter__(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("a+b")
        if self._file.tell() == 0:
            self._file.write(b"0")
            self._file.flush()
        self._file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self._file.close()
            self._file = None
            raise UpdateError("UPDATE_ALREADY_RUNNING", "another updater is active") from error

    def __exit__(self, *_args: object) -> None:
        if self._file is None:
            return
        self._file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None


if __name__ == "__main__":
    raise SystemExit(main())
