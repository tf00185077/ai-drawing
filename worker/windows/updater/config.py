"""Strict, non-evaluating configuration for the Windows worker updater."""
from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


ALLOWED_KEYS = {
    "AI_DRAWING_PROJECT_ROOT",
    "AI_DRAWING_WORKER_ROOT",
    "AI_DRAWING_WORKER_REMOTE",
    "AI_DRAWING_WORKER_BRANCH",
}
OWNERSHIP_MARKER = ".ai-drawing-worker-owned"
OWNERSHIP_MARKER_CONTENTS = "AI-Drawing NVIDIA Worker"
EXPECTED_REMOTE_URL_PATH = Path("config") / "expected-remote-url.txt"
DRIVE_FIXED = 3
DRIVE_REMOTE = 4


class UpdaterConfigError(ValueError):
    """The updater configuration cannot safely identify a managed worker."""


@dataclass(frozen=True)
class UpdaterConfig:
    project_root: Path
    worker_root: Path
    remote: str
    branch: str
    expected_remote_url: str


def load_updater_config(env_path: Path) -> UpdaterConfig:
    """Load a fixed-key env file without invoking a shell or expanding values."""
    values = _parse_env_file(Path(env_path))
    project_root = _resolve_local_directory(values["AI_DRAWING_PROJECT_ROOT"], "project root")
    worker_root = _resolve_local_directory(values["AI_DRAWING_WORKER_ROOT"], "worker root")
    _ensure_distinct_roots(project_root, worker_root)
    _require_git_root(project_root, "project root")
    _require_owned_worker_root(worker_root)

    remote = values["AI_DRAWING_WORKER_REMOTE"]
    branch = values["AI_DRAWING_WORKER_BRANCH"]
    if not remote or remote.startswith("-") or any(character.isspace() for character in remote):
        raise UpdaterConfigError("worker remote must be a non-empty remote name")
    if not branch or branch.startswith("-") or any(character.isspace() for character in branch):
        raise UpdaterConfigError("worker branch must be a non-empty branch name")

    expected_remote_url = _read_expected_remote_url(worker_root)
    project_remote_url = _git_remote_url(project_root, remote)
    if _normalize_remote_url(project_remote_url) != expected_remote_url:
        raise UpdaterConfigError("project remote URL does not match the worker expected remote URL")
    return UpdaterConfig(
        project_root=project_root,
        worker_root=worker_root,
        remote=remote,
        branch=branch,
        expected_remote_url=_normalize_remote_url(expected_remote_url),
    )


def _parse_env_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise UpdaterConfigError("unable to read updater environment file") from error

    values: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UpdaterConfigError(f"malformed updater environment line {number}")
        key, value = line.split("=", 1)
        if not key or key != key.strip() or not key.isidentifier():
            raise UpdaterConfigError(f"malformed updater environment line {number}")
        if key not in ALLOWED_KEYS:
            raise UpdaterConfigError(f"unknown updater environment key: {key}")
        if key in values:
            raise UpdaterConfigError(f"duplicate updater environment key: {key}")
        if value != value.strip():
            raise UpdaterConfigError(f"padded updater environment value for: {key}")
        values[key] = value

    missing = ALLOWED_KEYS - values.keys()
    if missing:
        raise UpdaterConfigError("missing required updater environment keys")
    return values


def _resolve_local_directory(raw_path: str, label: str) -> Path:
    if not raw_path or raw_path.startswith(("\\\\", "//")):
        raise UpdaterConfigError(f"{label} must be a local path")
    path = Path(raw_path)
    if not path.is_absolute():
        raise UpdaterConfigError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise UpdaterConfigError(f"{label} does not exist") from error
    if not resolved.is_dir():
        raise UpdaterConfigError(f"{label} must be a directory")
    if str(resolved).startswith(("\\\\", "//")) or _get_drive_type(resolved) == DRIVE_REMOTE:
        raise UpdaterConfigError(f"{label} must resolve to a local drive")
    return resolved


def _get_drive_type(path: Path) -> int:
    """Return the Windows drive type for a resolved path, without invoking a shell."""
    if os.name != "nt":
        return DRIVE_FIXED
    root = path.anchor or f"{path.drive}\\"
    return int(ctypes.windll.kernel32.GetDriveTypeW(root))


def _ensure_distinct_roots(project_root: Path, worker_root: Path) -> None:
    if project_root == worker_root:
        raise UpdaterConfigError("project and worker roots must differ")
    if project_root.is_relative_to(worker_root) or worker_root.is_relative_to(project_root):
        raise UpdaterConfigError("project and worker roots must not contain one another")


def _require_git_root(path: Path, label: str) -> None:
    if not (path / ".git").exists():
        raise UpdaterConfigError(f"{label} must contain .git")


def _require_owned_worker_root(worker_root: Path) -> None:
    marker_path = worker_root / OWNERSHIP_MARKER
    try:
        marker_contents = marker_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise UpdaterConfigError("worker root is missing the ownership marker") from error
    if marker_contents != OWNERSHIP_MARKER_CONTENTS:
        raise UpdaterConfigError("worker root ownership marker is invalid")


def _read_expected_remote_url(worker_root: Path) -> str:
    try:
        value = (worker_root / EXPECTED_REMOTE_URL_PATH).read_text(encoding="utf-8")
    except OSError as error:
        raise UpdaterConfigError("worker expected remote URL is missing") from error
    return _normalize_remote_url(value)


def _git_remote_url(root: Path, remote: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", remote],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    url = result.stdout.strip()
    if result.returncode or not url:
        raise UpdaterConfigError("configured git remote has no URL")
    return url


def _normalize_remote_url(url: str) -> str:
    normalized = url.strip().replace("\\", "/")
    while normalized.endswith("/"):
        normalized = normalized[:-1]
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if not normalized:
        raise UpdaterConfigError("configured git remote has an invalid URL")
    return normalized
