from __future__ import annotations

import json
import os
import shutil
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


class InstallTargetNotEmpty(RuntimeError):
    """Raised rather than overwriting a user's existing installation."""


class ComfyInstallError(RuntimeError):
    """Raised when a managed install or update cannot be completed safely."""


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


def resolve_uv_binary(
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Resolve the pinned wrapper binary, with a direct-Python fallback."""
    environment = os.environ if environ is None else environ
    configured = environment.get(UV_BINARY_ENV)
    candidate = Path(configured) if configured else None
    if candidate is None:
        discovered = which("uv")
        candidate = Path(discovered) if discovered else None
    if candidate is None:
        raise ComfyInstallError(
            "UV_BINARY_MISSING: run setup.ps1/setup.sh or install uv and retry"
        )
    if not candidate.is_absolute():
        raise ComfyInstallError(
            "UV_BINARY_INVALID: AI_DRAWING_UV_BIN must be an absolute path"
        )
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ComfyInstallError(
            "UV_BINARY_INVALID: configured uv binary does not exist"
        )
    return resolved


def _plan_uv_binary(uv_bin: Path | None) -> Path:
    resolved = resolve_uv_binary() if uv_bin is None else Path(uv_bin)
    if not resolved.is_absolute():
        raise ComfyInstallError("UV_BINARY_INVALID: uv binary must be absolute")
    return resolved


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


def staging_path(target: Path) -> Path:
    target = Path(target)
    return target.with_name(f".{target.name}.staging")


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


def _remove_staging(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def prepare_staging_target(target: Path) -> Path:
    """Prepare a known sibling staging path without replacing user data."""
    target = Path(target)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise InstallTargetNotEmpty(f"install target is not empty: {target}")
    staging = staging_path(target)
    _remove_staging(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    return staging


def _venv_python(root: Path, host: HostInfo) -> Path:
    if host.system == "Windows":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


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
    clear_venv: bool = False,
    uv_bin: Path | None = None,
) -> tuple[PlannedCommand, ...]:
    uv = _plan_uv_binary(uv_bin)
    python = _venv_python(root, host)
    venv_args = [str(uv), "venv"]
    if clear_venv:
        venv_args.append("--clear")
    venv_args.extend(("--python", COMFYUI_PYTHON, str(root / ".venv")))
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
    uv_bin: Path | None = None,
) -> InstallPlan:
    target = Path(target).resolve()
    staging = staging_path(target)
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
    try:
        ensure_native_macos_architecture(actual_host, runner)
    except UnsupportedNativeArchitecture as error:
        raise UnsupportedComfyArchitecture(
            "native arm64 architecture is required; Rosetta is unsupported"
        ) from error
    resolved_uv = _plan_uv_binary(uv_bin)
    target_was_empty = final_target.is_dir() and not any(final_target.iterdir())
    prepared = prepare_staging_target(final_target)
    plan = build_install_plan(final_target, device, actual_host, uv_bin=resolved_uv)
    if prepared != plan.staging:
        raise ComfyInstallError("prepared staging target does not match install plan")
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
    except Exception:
        try:
            _remove_staging(plan.staging)
        finally:
            if target_was_empty and not final_target.exists():
                final_target.mkdir()
        raise
    return validate_comfyui_root(final_target, actual_host)


def update_comfyui(
    root: Path,
    device: DeviceMode,
    runner: Runner,
    host: HostInfo | None = None,
    *,
    uv_bin: Path | None = None,
) -> str:
    """Update explicitly to the stable pin and restore the prior commit on failure."""
    actual_host = host or detect_host()
    try:
        ensure_native_macos_architecture(actual_host, runner)
    except UnsupportedNativeArchitecture as error:
        raise UnsupportedComfyArchitecture(
            "native arm64 architecture is required; Rosetta is unsupported"
        ) from error
    resolved_uv = _plan_uv_binary(uv_bin)
    installation = validate_comfyui_root(root, actual_host)
    if not installation.valid:
        raise ComfyInstallError(
            "invalid ComfyUI root: " + ", ".join(installation.issues)
        )
    root = installation.root
    revision = PlannedCommand(
        "read current commit",
        ("git", "rev-parse", "HEAD"),
        cwd=root,
    )
    try:
        result = runner.run(revision.args, cwd=revision.cwd)
    except OSError as error:
        raise ComfyInstallError(f"read current commit command failed: {error}") from error
    old_commit = result.stdout.strip()
    if result.returncode != 0 or not old_commit:
        detail = result.stderr.strip() or "no commit returned"
        raise ComfyInstallError(f"read current commit command failed: {detail}")

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
            clear_venv=True,
            uv_bin=resolved_uv,
        ),
    )
    try:
        for command in update_commands:
            _run_required(runner, command)
        updated = validate_comfyui_root(root, actual_host)
        if not updated.controllable:
            raise ComfyInstallError("validation failed after update")
    except Exception as error:
        rollback = PlannedCommand(
            "rollback",
            ("git", "checkout", "--detach", old_commit),
            cwd=root,
        )
        try:
            _run_required(runner, rollback)
        except ComfyInstallError as rollback_error:
            raise ComfyInstallError(
                f"update failed ({error}); rollback to {old_commit} failed: {rollback_error}"
            ) from error
        raise ComfyInstallError(
            f"update failed ({error}); restored {old_commit}"
        ) from error
    return COMFYUI_VERSION
