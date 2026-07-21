from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.request import urlopen

from .constants import COMFYUI_PYTHON, COMFYUI_REPOSITORY, COMFYUI_VERSION
from .models import ComfyMode, DeviceMode, HostInfo
from .platforms import (
    comfyui_python_candidates,
    detect_host,
    ensure_native_macos_architecture,
    UnsupportedNativeArchitecture,
)
from .runner import Runner


CUDA_INDEX = "https://download.pytorch.org/whl/cu130"
CPU_INDEX = "https://download.pytorch.org/whl/cpu"
TORCH_PACKAGES = ("torch", "torchvision", "torchaudio")
UV_BINARY_ENV = "AI_DRAWING_UV_BIN"
_WINDOWS_EXECUTABLE_SUFFIXES = frozenset({".exe", ".com", ".bat", ".cmd"})


class InstallTargetNotEmpty(RuntimeError):
    """Raised rather than overwriting a user's existing installation."""


class ComfyInstallError(RuntimeError):
    """Raised when a managed install or update cannot be completed safely."""


class ComfyInstallCleanupPending(ComfyInstallError):
    """Install failed and its owned staging directory requires manual cleanup."""

    def __init__(self, pending_path: Path) -> None:
        self.pending_path = Path(pending_path)
        self.code = "COMFYUI_INSTALL_CLEANUP_PENDING"
        self.message = "ComfyUI install failed and owned staging cleanup is pending."
        self.hint = (
            "Cleanup is pending. After confirming no install is active, inspect and remove "
            f"{self.pending_path}."
        )
        super().__init__(self.message)


class ComfyUpdateError(ComfyInstallError):
    """Structured failure for an update transaction."""

    _DETAILS = {
        "COMFYUI_UPDATE_NOT_OWNED": (
            "ComfyUI update root does not match launcher install provenance.",
            "Run reconfigure and select the launcher-installed ComfyUI root.",
        ),
        "COMFYUI_UPDATE_BACKUP_FAILED": (
            "ComfyUI environment could not be backed up safely.",
            "No update was applied; inspect the managed .venv and retry.",
        ),
        "COMFYUI_UPDATE_SOURCE_INVALID": (
            "Managed ComfyUI source revision could not be verified.",
            "Keep ComfyUI stopped and inspect the managed Git checkout before retrying.",
        ),
        "COMFYUI_UPDATE_FAILED_RESTORED": (
            "ComfyUI update failed; the prior source and environment were restored.",
            "Inspect the update error, then retry while ComfyUI remains stopped.",
        ),
        "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING": (
            "ComfyUI update failed; the prior runtime was restored but cleanup is pending.",
            "The restored runtime is usable; inspect the pending temporary paths.",
        ),
        "COMFYUI_UPDATE_ROLLBACK_FAILED": (
            "ComfyUI update failed and automatic rollback did not complete.",
            "Do not start ComfyUI; preserve the reported backup and repair it manually.",
        ),
        "COMFYUI_UPDATE_CLEANUP_FAILED": (
            "ComfyUI updated but its retained backup could not be finalized.",
            "Keep ComfyUI stopped and inspect the managed update backup before retrying.",
        ),
    }

    def __init__(
        self,
        code: str,
        message: str = "",
        hint: str = "",
        *,
        pending_paths: tuple[Path, ...] = (),
    ) -> None:
        default_message, default_hint = self._DETAILS.get(code, (code, "Inspect logs."))
        self.code = code
        self.message = message or default_message
        self.pending_paths = tuple(Path(path) for path in pending_paths)
        pending_hint = (
            default_hint
            + " Pending: "
            + ", ".join(str(path) for path in self.pending_paths)
            if self.pending_paths
            else default_hint
        )
        self.hint = hint or pending_hint
        super().__init__(self.message)


class UvBinaryError(ComfyInstallError):
    """Structured launcher-facing failure for the uv execution boundary."""

    _DETAILS = {
        "UV_BINARY_MISSING": (
            "找不到啟動器所需的 uv 執行檔。",
            "請透過 setup.ps1/setup.sh 啟動，或安裝 uv 後重試。",
        ),
        "UV_BINARY_INVALID": (
            "啟動器取得的 uv 執行檔無效。",
            "請重新執行 setup wrapper，以重建固定版本的 uv cache。",
        ),
    }

    def __init__(self, code: str) -> None:
        try:
            message, hint = self._DETAILS[code]
        except KeyError as error:
            raise ValueError(f"unsupported uv binary error code: {code}") from error
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"{code}: {message}")

    @classmethod
    def missing(cls) -> UvBinaryError:
        return cls("UV_BINARY_MISSING")

    @classmethod
    def invalid(cls) -> UvBinaryError:
        return cls("UV_BINARY_INVALID")


class InstallTargetInsideProject(ComfyInstallError):
    """Raised when managed installation would write inside this repository."""


class UnsupportedComfyArchitecture(ComfyInstallError):
    """Raised when ComfyUI dependency work would run through Rosetta."""


@dataclass(frozen=True)
class ComfyValidation:
    root: Path
    valid: bool
    python: Path | None
    issues: tuple[str, ...]

    @property
    def controllable(self) -> bool:
        return self.valid and self.python is not None


@dataclass(frozen=True)
class ComfyProbe:
    base_url: str
    running: bool
    mode: ComfyMode | None


@dataclass(frozen=True)
class PlannedCommand:
    name: str
    args: tuple[str, ...]
    cwd: Path | None = None


@dataclass(frozen=True)
class InstallPlan:
    target: Path
    staging: Path
    python: Path
    commands: tuple[PlannedCommand, ...]


@dataclass(frozen=True)
class CleanupOutcome:
    cleaned: bool
    pending_path: Path | None = None


@dataclass(frozen=True)
class UpdateOutcome:
    version: str
    cleanup_pending: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PathIdentity:
    device: int
    inode: int

    @classmethod
    def capture(cls, path: Path) -> PathIdentity:
        identity = path.stat(follow_symlinks=False)
        return cls(identity.st_dev, identity.st_ino)

    def matches(self, path: Path) -> bool:
        try:
            identity = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return False
        return (
            not path.is_symlink()
            and path.is_dir()
            and (identity.st_dev, identity.st_ino) == (self.device, self.inode)
        )


@dataclass(frozen=True)
class OwnedTemporaryDirectory:
    """A uniquely allocated directory removable only while its identity matches."""

    path: Path
    device: int
    inode: int

    @classmethod
    def create(cls, *, parent: Path, prefix: str) -> OwnedTemporaryDirectory:
        parent.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
        identity = path.stat(follow_symlinks=False)
        return cls(path=path, device=identity.st_dev, inode=identity.st_ino)

    def _identity_matches(self) -> bool:
        try:
            identity = self.path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return False
        if self.path.is_symlink() or not self.path.is_dir():
            return False
        return (identity.st_dev, identity.st_ino) == (self.device, self.inode)

    def cleanup(self, *, before_remove=None) -> CleanupOutcome:
        if not self.path.exists():
            return CleanupOutcome(True)
        if not self._identity_matches():
            return CleanupOutcome(False, self.path)
        if before_remove is not None:
            before_remove(self)
        if not self._identity_matches():
            return CleanupOutcome(False, self.path)
        try:
            self.path.rmdir()
        except OSError:
            return CleanupOutcome(False, self.path)
        return CleanupOutcome(True)

    def remove(self) -> None:
        outcome = self.cleanup()
        if not outcome.cleaned:
            raise ComfyInstallError(
                "owned temporary directory cleanup is pending"
            )


def _pending_owned_paths(
    *owned_directories: OwnedTemporaryDirectory,
) -> tuple[Path, ...]:
    return tuple(owned.path for owned in owned_directories if owned.path.exists())


def _cleanup_owned(
    *owned_directories: OwnedTemporaryDirectory,
) -> tuple[Path, ...]:
    pending: list[Path] = []
    for owned in owned_directories:
        outcome = owned.cleanup()
        if not outcome.cleaned and outcome.pending_path is not None:
            pending.append(outcome.pending_path)
    return tuple(pending)


def _rollback_failure(
    *owned_directories: OwnedTemporaryDirectory,
) -> ComfyUpdateError:
    pending = _pending_owned_paths(*owned_directories)
    return ComfyUpdateError(
        "COMFYUI_UPDATE_ROLLBACK_FAILED",
        pending_paths=pending,
    )


def _validate_uv_binary(
    candidate: Path,
    *,
    platform_name: str | None = None,
) -> Path:
    path = Path(candidate)
    if not path.is_absolute():
        raise UvBinaryError.invalid()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise UvBinaryError.invalid() from error
    if not resolved.is_file():
        raise UvBinaryError.invalid()
    actual_platform = os.name if platform_name is None else platform_name
    if actual_platform == "nt":
        executable = resolved.suffix.lower() in _WINDOWS_EXECUTABLE_SUFFIXES
    else:
        executable = os.access(resolved, os.X_OK)
    if not executable:
        raise UvBinaryError.invalid()
    return resolved


def resolve_uv_binary(
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> Path:
    """Resolve the pinned wrapper binary, with a direct-Python fallback."""
    environment = os.environ if environ is None else environ
    configured = environment.get(UV_BINARY_ENV)
    candidate = Path(configured) if configured else None
    if candidate is None:
        discovered = (shutil.which if which is None else which)("uv")
        candidate = Path(discovered) if discovered else None
    if candidate is None:
        raise UvBinaryError.missing()
    return _validate_uv_binary(candidate)


def _plan_uv_binary(uv_bin: Path | None) -> Path:
    if uv_bin is None:
        return resolve_uv_binary()
    return _validate_uv_binary(Path(uv_bin))


def validate_comfyui_root(
    root: Path,
    host: HostInfo | None = None,
) -> ComfyValidation:
    """Validate one exact candidate without searching below it."""
    candidate = Path(root).resolve()
    issues: list[str] = []
    if not (candidate / "main.py").is_file():
        issues.append("missing_main_py")
    if not (candidate / "models").is_dir():
        issues.append("missing_models_directory")
    actual_host = host or detect_host()
    python = next(
        (
            path
            for path in comfyui_python_candidates(candidate, actual_host)
            if path.is_file()
        ),
        None,
    )
    return ComfyValidation(
        root=candidate,
        valid=not issues,
        python=python,
        issues=tuple(issues),
    )


def discover_comfyui(
    candidates: Iterable[Path],
    host: HostInfo | None = None,
) -> tuple[ComfyValidation, ...]:
    """Inspect only supplied roots, preserving order and removing duplicates."""
    found: list[ComfyValidation] = []
    seen: set[str] = set()
    for raw_candidate in candidates:
        candidate = Path(raw_candidate).resolve()
        identity = os.path.normcase(str(candidate))
        if identity in seen:
            continue
        seen.add(identity)
        validation = validate_comfyui_root(candidate, host)
        if validation.valid:
            found.append(validation)
    return tuple(found)


def probe_comfyui(
    base_url: str,
    http_get: Callable[..., object] = urlopen,
    timeout: float = 2.0,
) -> ComfyProbe:
    """Probe an already-running API, which is always externally owned."""
    normalized = base_url.rstrip("/")
    try:
        response = http_get(f"{normalized}/system_stats", timeout=timeout)
        if hasattr(response, "__enter__"):
            with response as opened:
                status = getattr(opened, "status", 200)
                body = opened.read()
        else:
            status = getattr(response, "status", 200)
            body = response.read()
        payload = json.loads(body)
        if status != 200 or not isinstance(payload, dict):
            raise ValueError("invalid ComfyUI response")
    except (OSError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
        return ComfyProbe(base_url=normalized, running=False, mode=None)
    return ComfyProbe(
        base_url=normalized,
        running=True,
        mode=ComfyMode.EXTERNAL,
    )


def validate_install_target(target: Path, project_root: Path) -> Path:
    """Return a canonical target only when it is outside the repository."""
    canonical_target = Path(target).expanduser().resolve(strict=False)
    canonical_project = Path(project_root).expanduser().resolve(strict=False)
    try:
        canonical_target.relative_to(canonical_project)
    except ValueError:
        return canonical_target
    raise InstallTargetInsideProject(
        "managed install target must be outside the canonical repository root"
    )


def prepare_staging_target(target: Path) -> OwnedTemporaryDirectory:
    """Allocate one unique sibling staging directory owned by this call."""
    target = Path(target)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise InstallTargetNotEmpty(f"install target is not empty: {target}")
    return OwnedTemporaryDirectory.create(
        parent=target.parent,
        prefix=f".{target.name}.staging-",
    )


def _venv_python(root: Path, host: HostInfo) -> Path:
    if host.system == "Windows":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _python_in_venv(venv: Path, host: HostInfo) -> Path:
    if host.system == "Windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _torch_args(
    python: Path,
    device: DeviceMode,
    uv_bin: Path,
) -> tuple[str, ...]:
    args = (
        str(uv_bin),
        "pip",
        "install",
        "--python",
        str(python),
        *TORCH_PACKAGES,
    )
    if device is DeviceMode.NVIDIA:
        return (*args, "--index-url", CUDA_INDEX)
    if device is DeviceMode.CPU:
        return (*args, "--index-url", CPU_INDEX)
    return args


def _smoke_code(device: DeviceMode) -> str:
    if device is DeviceMode.NVIDIA:
        return "import torch; assert torch.cuda.is_available()"
    if device is DeviceMode.MPS:
        return "import torch; assert torch.backends.mps.is_available()"
    return "import torch"


def smoke_comfyui_runtime(
    python: Path,
    device: DeviceMode,
    runner: Runner,
) -> None:
    """Assert the selected runtime supports the requested device."""
    _run_required(
        runner,
        PlannedCommand(
            "smoke",
            (str(Path(python).resolve()), "-c", _smoke_code(device)),
        ),
    )


def _environment_commands(
    root: Path,
    device: DeviceMode,
    host: HostInfo,
    venv_path: Path | None = None,
    uv_bin: Path | None = None,
) -> tuple[PlannedCommand, ...]:
    uv = _plan_uv_binary(uv_bin)
    venv = root / ".venv" if venv_path is None else Path(venv_path)
    python = _python_in_venv(venv, host)
    venv_args = [str(uv), "venv", "--python", COMFYUI_PYTHON, str(venv)]
    return (
        PlannedCommand(
            "python",
            (str(uv), "python", "install", COMFYUI_PYTHON),
        ),
        PlannedCommand(
            "venv",
            tuple(venv_args),
        ),
        PlannedCommand("torch", _torch_args(python, device, uv)),
        PlannedCommand(
            "requirements",
            (
                str(uv),
                "pip",
                "install",
                "--python",
                str(python),
                "-r",
                str(root / "requirements.txt"),
            ),
        ),
        PlannedCommand("smoke", (str(python), "-c", _smoke_code(device))),
    )


def build_install_plan(
    target: Path,
    device: DeviceMode,
    host: HostInfo | None = None,
    *,
    staging: Path,
    uv_bin: Path | None = None,
) -> InstallPlan:
    target = Path(target).resolve()
    staging = Path(staging).resolve()
    actual_host = host or detect_host()
    commands = (
        PlannedCommand(
            "clone",
            (
                "git",
                "clone",
                "--branch",
                COMFYUI_VERSION,
                "--depth",
                "1",
                COMFYUI_REPOSITORY,
                str(staging),
            ),
        ),
        *_environment_commands(staging, device, actual_host, uv_bin=uv_bin),
    )
    return InstallPlan(
        target=target,
        staging=staging,
        python=_venv_python(staging, actual_host),
        commands=commands,
    )


def _run_required(runner: Runner, command: PlannedCommand) -> None:
    try:
        result = runner.run(command.args, cwd=command.cwd)
    except OSError as error:
        raise ComfyInstallError(f"{command.name} command failed: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise ComfyInstallError(f"{command.name} command failed: {detail}")


def install_comfyui(
    target: Path,
    device: DeviceMode,
    runner: Runner,
    host: HostInfo | None = None,
    *,
    project_root: Path,
    uv_bin: Path | None = None,
) -> ComfyValidation:
    """Install into staging and publish only a validated, smoke-tested root."""
    actual_host = host or detect_host()
    final_target = validate_install_target(target, project_root)
    resolved_uv = _plan_uv_binary(uv_bin)
    try:
        ensure_native_macos_architecture(actual_host, runner)
    except UnsupportedNativeArchitecture as error:
        raise UnsupportedComfyArchitecture(
            "native arm64 architecture is required; Rosetta is unsupported"
        ) from error
    target_was_empty = final_target.is_dir() and not any(final_target.iterdir())
    prepared = prepare_staging_target(final_target)
    plan = build_install_plan(
        final_target,
        device,
        actual_host,
        staging=prepared.path,
        uv_bin=resolved_uv,
    )
    try:
        for command in plan.commands:
            _run_required(runner, command)
        staged = validate_comfyui_root(plan.staging, actual_host)
        if not staged.controllable:
            raise ComfyInstallError(
                "validation failed: " + ", ".join(staged.issues or ("missing_python",))
            )
        if final_target.exists():
            final_target.rmdir()
        plan.staging.replace(final_target)
    except Exception as error:
        cleanup = prepared.cleanup()
        if target_was_empty and not final_target.exists():
            final_target.mkdir()
        if not cleanup.cleaned and cleanup.pending_path is not None:
            raise ComfyInstallCleanupPending(cleanup.pending_path) from error
        raise
    return validate_comfyui_root(final_target, actual_host)


def update_comfyui(
    root: Path,
    device: DeviceMode,
    runner: Runner,
    host: HostInfo | None = None,
    *,
    owned_root: Path,
    uv_bin: Path | None = None,
) -> UpdateOutcome:
    """Update source and environment as one stopped, rollback-tested transaction."""
    actual_host = host or detect_host()
    requested_root = Path(root).resolve()
    provenance_root = Path(owned_root).resolve()
    if os.path.normcase(str(requested_root)) != os.path.normcase(str(provenance_root)):
        raise ComfyUpdateError("COMFYUI_UPDATE_NOT_OWNED")
    resolved_uv = _plan_uv_binary(uv_bin)
    try:
        ensure_native_macos_architecture(actual_host, runner)
    except UnsupportedNativeArchitecture as error:
        raise UnsupportedComfyArchitecture(
            "native arm64 architecture is required; Rosetta is unsupported"
        ) from error
    installation = validate_comfyui_root(requested_root, actual_host)
    expected_python = _venv_python(requested_root, actual_host)
    old_venv = requested_root / ".venv"
    if (
        not installation.controllable
        or installation.python != expected_python
        or not old_venv.is_dir()
        or old_venv.is_symlink()
    ):
        raise ComfyUpdateError("COMFYUI_UPDATE_NOT_OWNED")
    root = installation.root
    top_level = PlannedCommand(
        "read repository root",
        ("git", "rev-parse", "--show-toplevel"),
        cwd=root,
    )
    try:
        top_level_result = runner.run(top_level.args, cwd=top_level.cwd)
    except OSError as error:
        raise ComfyUpdateError("COMFYUI_UPDATE_SOURCE_INVALID") from error
    top_level_value = top_level_result.stdout.strip()
    try:
        canonical_top_level = Path(top_level_value).resolve(strict=True)
    except (OSError, RuntimeError):
        canonical_top_level = None
    if (
        top_level_result.returncode != 0
        or canonical_top_level != root
        or not (root / ".git").exists()
    ):
        raise ComfyUpdateError("COMFYUI_UPDATE_SOURCE_INVALID")
    revision = PlannedCommand(
        "read current commit",
        ("git", "rev-parse", "HEAD"),
        cwd=root,
    )
    try:
        result = runner.run(revision.args, cwd=revision.cwd)
    except OSError as error:
        raise ComfyUpdateError("COMFYUI_UPDATE_SOURCE_INVALID") from error
    old_commit = result.stdout.strip()
    if result.returncode != 0 or not old_commit:
        raise ComfyUpdateError("COMFYUI_UPDATE_SOURCE_INVALID")

    backup: OwnedTemporaryDirectory | None = None
    fresh: OwnedTemporaryDirectory | None = None
    try:
        backup = OwnedTemporaryDirectory.create(
            parent=root.parent,
            prefix=f".{root.name}.venv-backup-",
        )
        fresh = OwnedTemporaryDirectory.create(
            parent=root.parent,
            prefix=f".{root.name}.venv.update-new-",
        )
        old_venv.replace(backup.path / "venv")
    except Exception as error:
        if backup is not None and (backup.path / "venv").exists():
            if fresh is not None:
                _cleanup_owned(fresh)
            raise _rollback_failure(
                *(owned for owned in (backup, fresh) if owned is not None)
            ) from error
        pending = _cleanup_owned(
            *(owned for owned in (fresh, backup) if owned is not None)
        )
        raise ComfyUpdateError(
            "COMFYUI_UPDATE_BACKUP_FAILED",
            pending_paths=pending,
        ) from error

    assert backup is not None and fresh is not None
    new_venv = fresh.path / "venv"
    update_commands = (
        PlannedCommand(
            "fetch",
            (
                "git",
                "fetch",
                "--depth",
                "1",
                "origin",
                "tag",
                COMFYUI_VERSION,
            ),
            cwd=root,
        ),
        PlannedCommand(
            "checkout",
            ("git", "checkout", "--detach", COMFYUI_VERSION),
            cwd=root,
        ),
        *_environment_commands(
            root,
            device,
            actual_host,
            venv_path=new_venv,
            uv_bin=resolved_uv,
        ),
    )
    new_environment_activated = False
    activated_identity: PathIdentity | None = None
    try:
        for command in update_commands:
            _run_required(runner, command)
        if not _python_in_venv(new_venv, actual_host).is_file():
            raise ComfyInstallError("validation failed after update: missing new python")
        activated_identity = PathIdentity.capture(new_venv)
        new_venv.replace(old_venv)
        if not activated_identity.matches(old_venv):
            raise ComfyInstallError("activated environment identity changed")
        new_environment_activated = True
        updated = validate_comfyui_root(root, actual_host)
        if not updated.controllable or updated.python != expected_python:
            raise ComfyInstallError("validation failed after update")
    except Exception as error:
        try:
            _restore_update_transaction(
                root=root,
                old_commit=old_commit,
                backup=backup,
                fresh=fresh,
                device=device,
                host=actual_host,
                runner=runner,
                new_environment_activated=new_environment_activated,
                activated_identity=activated_identity,
            )
        except Exception as rollback_error:
            raise _rollback_failure(backup, fresh) from rollback_error
        pending = _cleanup_owned(fresh, backup)
        if pending:
            raise ComfyUpdateError(
                "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING",
                pending_paths=pending,
            ) from error
        raise ComfyUpdateError("COMFYUI_UPDATE_FAILED_RESTORED") from error

    pending = _cleanup_owned(fresh, backup)
    return UpdateOutcome(COMFYUI_VERSION, pending)


def _restore_update_transaction(
    *,
    root: Path,
    old_commit: str,
    backup: OwnedTemporaryDirectory,
    fresh: OwnedTemporaryDirectory,
    device: DeviceMode,
    host: HostInfo,
    runner: Runner,
    new_environment_activated: bool,
    activated_identity: PathIdentity | None,
) -> None:
    """Restore both old source and exact old venv, then prove the result works."""
    old_venv = root / ".venv"
    backup_venv = backup.path / "venv"
    _run_required(
        runner,
        PlannedCommand(
            "rollback",
            ("git", "checkout", "--detach", old_commit),
            cwd=root,
        ),
    )
    if new_environment_activated:
        if activated_identity is None or not activated_identity.matches(old_venv):
            raise ComfyInstallError(
                "activated environment identity changed during rollback"
            )
        old_venv.replace(fresh.path / "failed-venv")
    elif old_venv.exists():
        raise ComfyInstallError(
            "unknown environment appeared during rollback; refusing to replace it"
        )
    backup_venv.replace(old_venv)
    try:
        smoke_comfyui_runtime(_venv_python(root, host), device, runner)
    except Exception:
        if old_venv.exists() and not backup_venv.exists():
            old_venv.replace(backup_venv)
        raise
