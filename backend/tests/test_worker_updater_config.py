"""Boundary tests for the Windows worker updater configuration."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from worker.windows.updater import config as updater_config
from worker.windows.updater.config import UpdaterConfigError, load_updater_config


EXPECTED_REMOTE = "https://github.com/example/ai-drawing.git"
OWNERSHIP_MARKER = ".ai-drawing-worker-owned"


def _git_repo(path: Path, *, remote: str = EXPECTED_REMOTE) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return path


def _owned_worker_root(
    path: Path,
    *,
    expected_remote: str = EXPECTED_REMOTE,
    marker_contents: str = "AI-Drawing NVIDIA Worker\n",
) -> Path:
    path.mkdir(parents=True)
    (path / OWNERSHIP_MARKER).write_text(marker_contents, encoding="utf-8")
    config_directory = path / "config"
    config_directory.mkdir()
    (config_directory / "expected-remote-url.txt").write_text(expected_remote + "\n", encoding="utf-8")
    return path


def _env_file_values(tmp_path: Path, project: str | Path, worker: str | Path, **overrides: str) -> Path:
    values = {
        "AI_DRAWING_PROJECT_ROOT": str(project),
        "AI_DRAWING_WORKER_ROOT": str(worker),
        "AI_DRAWING_WORKER_REMOTE": "origin",
        "AI_DRAWING_WORKER_BRANCH": "main",
    }
    values.update(overrides)
    path = tmp_path / "updater.env"
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    return path


def _env_file(tmp_path: Path, project: Path, worker: Path) -> Path:
    return _env_file_values(tmp_path, project, worker)


def test_config_accepts_distinct_local_owned_roots(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")

    config = load_updater_config(_env_file(tmp_path, project, worker))

    assert config.project_root == project.resolve()
    assert config.worker_root == worker.resolve()
    assert config.remote == "origin"
    assert config.branch == "main"
    assert config.expected_remote_url == "https://github.com/example/ai-drawing"


def test_config_accepts_owned_worker_root_without_git_metadata(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")

    load_updater_config(_env_file(tmp_path, project, worker))

    assert not (worker / ".git").exists()


def test_config_rejects_resolved_path_on_remote_windows_drive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")
    checked_paths: list[Path] = []

    def remote_drive(path: Path) -> int:
        checked_paths.append(path)
        return updater_config.DRIVE_REMOTE

    monkeypatch.setattr(updater_config, "_get_drive_type", remote_drive)

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file(tmp_path, project, worker))

    assert checked_paths == [project.resolve()]


@pytest.mark.parametrize(
    ("project", "worker"),
    [
        (r"\\server\share\repo", r"D:\\worker"),
        (r"D:\\code", r"D:\\code\\worker"),
        (r"D:\\same", r"D:\\same"),
    ],
)
def test_config_rejects_unc_nested_or_equal_roots(tmp_path: Path, project: str, worker: str) -> None:
    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file_values(tmp_path, project, worker))


@pytest.mark.parametrize(
    "contents",
    [
        "UNKNOWN_KEY=value\n",
        "AI_DRAWING_WORKER_BRANCH=main\nAI_DRAWING_WORKER_BRANCH=stable\n",
        "AI_DRAWING_PROJECT_ROOT\n",
        "=missing-key\n",
    ],
)
def test_config_rejects_unknown_duplicate_and_malformed_env_lines(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "updater.env"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(UpdaterConfigError):
        load_updater_config(path)


def test_config_rejects_worker_without_ownership_marker(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = tmp_path / "runtime"
    worker.mkdir()

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file(tmp_path, project, worker))


def test_config_rejects_worker_with_wrong_ownership_marker_contents(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime", marker_contents="managed by AI Drawing\n")

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file(tmp_path, project, worker))


def test_config_rejects_project_with_wrong_remote_url(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source", remote="https://github.com/example/other.git")
    worker = _owned_worker_root(tmp_path / "runtime")

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file(tmp_path, project, worker))


def test_config_rejects_missing_expected_remote_url_file(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")
    (worker / "config" / "expected-remote-url.txt").unlink()

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file(tmp_path, project, worker))


def test_config_rejects_empty_branch(tmp_path: Path) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file_values(tmp_path, project, worker, AI_DRAWING_WORKER_BRANCH=""))


@pytest.mark.parametrize("key", ["AI_DRAWING_WORKER_REMOTE", "AI_DRAWING_WORKER_BRANCH"])
def test_config_rejects_padded_remote_or_branch(tmp_path: Path, key: str) -> None:
    project = _git_repo(tmp_path / "source")
    worker = _owned_worker_root(tmp_path / "runtime")

    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file_values(tmp_path, project, worker, **{key: " main"}))
