"""Versioned, staged runtime construction and activation for Windows workers."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from .git_source import UpdateError


FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")
SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
SAFE_NODE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
COMFY_VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?\Z")
INSTALL_TIMEOUT = 900.0
START_TIMEOUT = 30.0
STOP_TIMEOUT = 15.0
PRODUCTION_WORKER_URL = "http://127.0.0.1:8791"
PRODUCTION_COMFY_URL = "http://127.0.0.1:8188"
RELEASE_MARKER = ".managed-release.json"


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...

    def start(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> "ProcessHandle": ...


class ProcessHandle(Protocol):
    def terminate(self) -> None: ...

    def wait(self, *, timeout: float) -> int: ...

    def kill(self) -> None: ...


@dataclass(frozen=True)
class HealthEvidence:
    cuda_available: bool
    gpu_name: str
    system_stats_ok: bool
    object_info_ok: bool
    authenticated_status_ok: bool
    resource_plan_ok: bool
    preflight_ok: bool
    source_commit: str

    @classmethod
    def complete(cls, source_commit: str) -> "HealthEvidence":
        return cls(True, "NVIDIA GPU", True, True, True, True, True, source_commit)


class RuntimeValidationError(UpdateError):
    """A staged validation failed, optionally together with process cleanup."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        cleanup_code: str | None = None,
        primary_exception: BaseException | None = None,
        cleanup_failures: Sequence[BaseException] = (),
    ) -> None:
        self.cleanup_code = cleanup_code
        self.primary_exception = primary_exception
        self.cleanup_failures = tuple(cleanup_failures)
        super().__init__(code, message)


class HealthProbe(Protocol):
    """Validate the complete authenticated ComfyUI/Worker health contract."""

    def validate_staged(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence: ...

    def validate_production(
        self, worker_url: str, comfy_url: str, expected_commit: str
    ) -> HealthEvidence: ...

    def stop_production(self) -> None: ...

    def start_production(self) -> None: ...


class JunctionOps(Protocol):
    def create(self, link: Path, target: Path) -> None: ...

    def read_target(self, link: Path) -> Path: ...

    def rename(self, source: Path, destination: Path) -> None: ...

    def remove(self, link: Path) -> None: ...


class WindowsJunctionOps:
    """Native directory-junction operations with no shell command execution."""

    def create(self, link: Path, target: Path) -> None:
        link = Path(link)
        target = Path(target).resolve(strict=True)
        if not target.is_dir() or os.path.lexists(link):
            raise OSError("junction target must be a directory and link must not exist")
        link.parent.resolve(strict=True)
        if os.name == "nt":
            _create_windows_junction(link, target)
        else:
            os.symlink(target, link, target_is_directory=True)
        if self.read_target(link) != target:
            self.remove(link)
            raise OSError("created junction target did not match")

    def read_target(self, link: Path) -> Path:
        link = Path(link)
        stat_result = link.lstat()
        if os.name == "nt":
            if getattr(stat_result, "st_reparse_tag", 0) != 0xA0000003:
                raise OSError("path is not a Windows directory junction")
        elif not link.is_symlink():
            raise OSError("path is not a directory link")
        return link.resolve(strict=True)

    def rename(self, source: Path, destination: Path) -> None:
        source = Path(source)
        destination = Path(destination)
        self.read_target(source)
        if os.path.lexists(destination):
            raise OSError("junction rename destination already exists")
        os.rename(source, destination)
        self.read_target(destination)

    def remove(self, link: Path) -> None:
        link = Path(link)
        self.read_target(link)
        # Windows junctions are directory reparse points and are removed with
        # rmdir. The POSIX test implementation uses a real symlink instead.
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


@dataclass(frozen=True)
class RuntimeLayout:
    root: Path
    releases: Path
    shared: Path
    config: Path
    current: Path
    staging: Path
    shared_models: Path
    shared_input: Path
    shared_output: Path
    shared_cache: Path
    shared_partial: Path

    @classmethod
    def create(cls, root: Path) -> "RuntimeLayout":
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve(strict=True)
        releases = root / "releases"
        shared = root / "shared"
        config = root / "config"
        staging = root / "staging"
        shared_models = shared / "models"
        shared_input = shared / "input"
        shared_output = shared / "output"
        shared_cache = shared / "cache"
        shared_partial = shared / "partial"
        for directory in (
            releases,
            config,
            staging,
            shared_models,
            shared_input,
            shared_output,
            shared_cache,
            shared_partial,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            _require_contained(directory, root, "RUNTIME_INSTALL_FAILED")
        return cls(
            root=root,
            releases=releases,
            shared=shared,
            config=config,
            current=root / "current",
            staging=staging,
            shared_models=shared_models,
            shared_input=shared_input,
            shared_output=shared_output,
            shared_cache=shared_cache,
            shared_partial=shared_partial,
        )

    def release(self, commit: str) -> Path:
        if not FULL_SHA.fullmatch(commit):
            raise UpdateError("TARGET_COMMIT_INVALID", "Invalid commit.")
        _require_contained(self.releases, self.root, "RUNTIME_INSTALL_FAILED")
        return self.releases / commit


class RuntimeBuilder:
    """Build a release in staging, then publish it without touching current."""

    def __init__(
        self,
        layout: RuntimeLayout,
        commands: CommandRunner,
        junctions: JunctionOps | None = None,
        bootstrap_python: Path | None = None,
    ) -> None:
        self.layout = layout
        self.commands = commands
        self.junctions = junctions or WindowsJunctionOps()
        self.bootstrap_python = Path(bootstrap_python or sys.executable).resolve()

    def stage(self, exported: Path, commit: str) -> Path:
        release = self.layout.release(commit)
        if release.exists():
            raise UpdateError("RUNTIME_INSTALL_FAILED", "release already exists")
        exported = Path(exported)
        self._validate_export(exported, commit)
        staging_release = self.layout.staging / commit
        if staging_release.exists():
            self._purge_interrupted_stage(staging_release)

        created_links: list[Path] = []
        try:
            shutil.copytree(exported, staging_release)
            mutable_config = staging_release / "config" / "worker.json"
            if mutable_config.exists():
                mutable_config.unlink()
            self._install(staging_release)
            (staging_release / "cache").mkdir(exist_ok=True)
            for link, target in self._shared_links(staging_release):
                if link.exists():
                    if link.is_dir():
                        shutil.rmtree(link)
                    else:
                        link.unlink()
                self._create_checked_junction(staging_release, link, target)
                created_links.append(link)
            _atomic_json(staging_release / RELEASE_MARKER, {"commit": commit, "schema": 1})
            os.replace(staging_release, release)
        except UpdateError:
            self._cleanup_staging(staging_release, created_links)
            raise
        except (OSError, ValueError) as error:
            self._cleanup_staging(staging_release, created_links)
            raise UpdateError("RUNTIME_INSTALL_FAILED", "runtime layout could not be staged") from error
        return release

    def _install(self, release: Path) -> None:
        manifest = self._read_manifest(release)
        venv = release / ".venv"
        python = venv / "Scripts" / "python.exe"
        # The clean installer owns this pinned interpreter; Windows' optional
        # py.exe launcher is intentionally not a runtime prerequisite.
        self._checked((str(self.bootstrap_python), "-m", "venv", str(venv)), cwd=release)
        self._checked(
            (str(python), "-m", "pip", "install", "--disable-pip-version-check", f"uv=={manifest['uv']}"),
            cwd=release,
        )
        self._checked(
            (
                str(python),
                "-m",
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--index-url",
                manifest["pytorch_index"],
                "torch",
                "torchvision",
                "torchaudio",
            ),
            cwd=release,
        )

        comfy_root = release / "ComfyUI"
        self._clone_pinned(manifest["comfyui_repository"], manifest["comfyui_version"], comfy_root, release)
        requirement_files = [release / "worker" / "windows" / "requirements.txt", comfy_root / "requirements.txt"]
        custom_root = comfy_root / "custom_nodes"
        custom_root.mkdir(exist_ok=True)
        for node in manifest["custom_nodes"]:
            node_root = custom_root / node["name"]
            self._clone_pinned(node["repository"], node["revision"], node_root, release)
            node_requirements = node_root / "requirements.txt"
            if node_requirements.is_file():
                requirement_files.append(node_requirements)
        for requirements in requirement_files:
            if not requirements.is_file():
                raise UpdateError("RUNTIME_INSTALL_FAILED", "pinned runtime requirements are missing")
            self._checked(
                (
                    str(python),
                    "-m",
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    "--requirement",
                    str(requirements),
                ),
                cwd=release,
            )

    def _read_manifest(self, release: Path) -> dict[str, Any]:
        try:
            value = json.loads((release / "worker" / "windows" / "worker-manifest.json").read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("manifest is not an object")
            python = _required_safe_version(value, "python")
            uv = _required_safe_version(value, "uv")
            comfy_version = _required_comfy_version(value)
            comfy_repository = _required_https_url(value, "comfyui_repository")
            pytorch_index = _required_https_url(value, "pytorch_index")
            raw_nodes = value.get("custom_nodes")
            if not isinstance(raw_nodes, list):
                raise ValueError("custom_nodes is not a list")
            custom_nodes: list[dict[str, str]] = []
            seen_names: set[str] = set()
            for raw_node in raw_nodes:
                if not isinstance(raw_node, dict):
                    raise ValueError("custom node is not an object")
                name = raw_node.get("name")
                revision = raw_node.get("revision")
                if not isinstance(name, str) or not SAFE_NODE_NAME.fullmatch(name) or name.casefold() in seen_names:
                    raise ValueError("custom node name is invalid or duplicated")
                if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
                    raise ValueError("custom node revision is not a full SHA")
                seen_names.add(name.casefold())
                custom_nodes.append(
                    {
                        "name": name,
                        "repository": _required_https_url(raw_node, "repository"),
                        "revision": revision,
                    }
                )
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "worker runtime manifest is invalid") from error
        return {
            "python": python,
            "uv": uv,
            "comfyui_repository": comfy_repository,
            "comfyui_version": comfy_version,
            "pytorch_index": pytorch_index,
            "custom_nodes": custom_nodes,
        }

    def _clone_pinned(self, repository: str, revision: str, destination: Path, cwd: Path) -> None:
        self._checked(
            ("git", "clone", "--filter=blob:none", "--no-checkout", "--", repository, str(destination)),
            cwd=cwd,
        )
        self._checked(("git", "-C", str(destination), "checkout", "--detach", revision), cwd=cwd)

    def _checked(self, argv: Sequence[str], *, cwd: Path) -> CommandResult:
        if (
            isinstance(argv, (str, bytes))
            or not argv
            or any(not isinstance(argument, str) or "\x00" in argument for argument in argv)
        ):
            raise UpdateError("RUNTIME_INSTALL_FAILED", "runtime command arguments are invalid")
        _require_contained(cwd, self.layout.staging, "RUNTIME_INSTALL_FAILED")
        try:
            result = self.commands.run(tuple(argv), cwd=cwd, timeout=INSTALL_TIMEOUT, env=None)
        except (OSError, TimeoutError) as error:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "runtime install command could not complete") from error
        if result.returncode != 0:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "runtime install command failed")
        return result

    def _purge_interrupted_stage(self, staging_release: Path) -> None:
        _require_contained(staging_release, self.layout.staging, "RUNTIME_INSTALL_FAILED")
        if staging_release.is_symlink() or _is_reparse_point(staging_release):
            raise UpdateError("RUNTIME_INSTALL_FAILED", "interrupted staging path is a reparse point")
        try:
            shutil.rmtree(staging_release)
        except OSError as error:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "interrupted staging could not be removed") from error

    def _validate_export(self, exported: Path, commit: str) -> None:
        try:
            root = exported.resolve(strict=True)
            if not root.is_dir():
                raise OSError("export is not a directory")
            recorded = (root / "source-commit.txt").read_text(encoding="utf-8").strip()
            if recorded != commit:
                raise UpdateError("TARGET_COMMIT_INVALID", "exported source commit does not match target")
            for path in root.rglob("*"):
                if path.is_symlink() or _is_reparse_point(path):
                    raise UpdateError("RUNTIME_INSTALL_FAILED", "exported source contains a reparse point")
                _require_contained(path, root, "RUNTIME_INSTALL_FAILED")
        except UpdateError:
            raise
        except (OSError, UnicodeError) as error:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "exported source is incomplete") from error

    def _shared_links(self, release: Path) -> tuple[tuple[Path, Path], ...]:
        return (
            (release / "ComfyUI" / "models", self.layout.shared_models),
            (release / "ComfyUI" / "input", self.layout.shared_input),
            (release / "ComfyUI" / "output", self.layout.shared_output),
            (release / ".cache", self.layout.shared_cache),
            (release / "cache" / ".partial", self.layout.shared_partial),
        )

    def _create_checked_junction(self, release: Path, link: Path, target: Path) -> None:
        _require_contained(release, self.layout.staging, "RUNTIME_INSTALL_FAILED")
        _require_contained(link.parent, release, "RUNTIME_INSTALL_FAILED")
        canonical_target = _require_contained(target, self.layout.shared, "RUNTIME_INSTALL_FAILED")
        self.junctions.create(link, canonical_target)
        actual_target = self.junctions.read_target(link).resolve(strict=True)
        if actual_target != canonical_target:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "junction target did not match shared storage")

    def _cleanup_staging(self, staging_release: Path, created_links: Sequence[Path]) -> None:
        for link in reversed(created_links):
            try:
                self.junctions.remove(link)
            except OSError:
                pass
        shutil.rmtree(staging_release, ignore_errors=True)


class RuntimeValidator:
    """Launch and validate a candidate release only on reserved loopback ports."""

    def __init__(self, layout: RuntimeLayout, commands: CommandRunner, health: HealthProbe) -> None:
        self.layout = layout
        self.commands = commands
        self.health = health

    def validate(self, commit: str) -> Path:
        release = self.layout.release(commit)
        canonical_release = _require_contained(release, self.layout.releases, "RUNTIME_INSTALL_FAILED")
        try:
            recorded_commit = (canonical_release / "source-commit.txt").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            raise UpdateError("WORKER_CONTRACT_FAILED", "staged release has no readable source commit") from error
        if recorded_commit != commit:
            raise UpdateError("WORKER_CONTRACT_FAILED", "staged release commit does not match target")

        config_path = self.layout.config / "worker.json"
        try:
            canonical_config = _require_contained(
                config_path, self.layout.root, "WORKER_CONTRACT_FAILED"
            )
            if not canonical_config.is_file():
                raise OSError("worker config is not a file")
            comfy_root = _require_contained(
                canonical_release / "ComfyUI", canonical_release, "COMFYUI_VALIDATION_FAILED"
            )
            canonical_state = _prepare_validation_state(self.layout, commit)
        except (OSError, ValueError) as error:
            raise UpdateError(
                "WORKER_CONTRACT_FAILED", "staged Worker roots could not be isolated"
            ) from error

        reservations = _reserve_loopback_ports(2)
        comfy_port, worker_port = (reservation.getsockname()[1] for reservation in reservations)
        comfy_url = f"http://127.0.0.1:{comfy_port}"
        worker_url = f"http://127.0.0.1:{worker_port}"
        processes: list[ProcessHandle] = []
        primary: BaseException | None = None
        primary_traceback = None
        cleanup: RuntimeValidationError | None = None
        try:
            python = canonical_release / ".venv" / "Scripts" / "python.exe"
            reservations[0].close()
            processes.append(
                self._start(
                    (
                        str(python),
                        str(comfy_root / "main.py"),
                        "--listen",
                        "127.0.0.1",
                        "--port",
                        str(comfy_port),
                    ),
                    cwd=comfy_root,
                    env={"PYTHONUTF8": "1"},
                    code="COMFYUI_VALIDATION_FAILED",
                )
            )
            worker_root = canonical_release / "worker" / "windows"
            reservations[1].close()
            processes.append(
                self._start(
                    (
                        str(python),
                        "-m",
                        "uvicorn",
                        "worker:app",
                        "--app-dir",
                        str(worker_root),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(worker_port),
                    ),
                    cwd=worker_root,
                    env={
                        "AI_DRAWING_WORKER_ROOT": str(self.layout.root),
                        "AI_DRAWING_WORKER_RELEASE_ROOT": str(canonical_release),
                        "AI_DRAWING_WORKER_CONFIG_PATH": str(canonical_config),
                        "AI_DRAWING_WORKER_UPDATE_STATE_ROOT": str(canonical_state),
                        "AI_DRAWING_COMFYUI_ROOT": str(comfy_root),
                        "AI_DRAWING_WORKER_PARTIAL_ROOT": str(
                            canonical_release / "cache" / ".partial"
                        ),
                        "AI_DRAWING_WORKER_VERIFICATION_ROOT": str(
                            self.layout.shared_cache / "verified"
                        ),
                        "AI_DRAWING_COMFYUI_URL": comfy_url,
                        "PYTHONUTF8": "1",
                    },
                    code="WORKER_CONTRACT_FAILED",
                )
            )
            evidence = self.health.validate_staged(worker_url, comfy_url, commit)
            _require_complete_health(evidence, commit)
        except BaseException as error:
            primary = error
            primary_traceback = error.__traceback__
        finally:
            cleanup = _cleanup_staged_runtime(reservations, processes)
        if cleanup is not None and primary is not None:
            code = primary.code if isinstance(primary, UpdateError) else "WORKER_CONTRACT_FAILED"
            message = (
                primary.message
                if isinstance(primary, UpdateError)
                else "staged runtime validation was interrupted"
            )
            combined = RuntimeValidationError(
                code,
                message,
                cleanup_code=cleanup.code,
                primary_exception=primary,
                cleanup_failures=cleanup.cleanup_failures,
            )
            raise combined from cleanup
        if cleanup is not None:
            raise cleanup
        if primary is not None:
            if isinstance(primary, UpdateError):
                raise primary.with_traceback(primary_traceback)
            if isinstance(primary, Exception):
                wrapped = RuntimeValidationError(
                    "WORKER_CONTRACT_FAILED",
                    "staged runtime health validation failed",
                    primary_exception=primary,
                )
                raise wrapped from primary
            raise primary.with_traceback(primary_traceback)
        return canonical_release

    def _start(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        code: str,
    ) -> ProcessHandle:
        if isinstance(argv, (str, bytes)) or not argv or any(not isinstance(argument, str) for argument in argv):
            raise UpdateError(code, "staged runtime command arguments are invalid")
        _require_contained(cwd, self.layout.releases, code)
        try:
            return self.commands.start(tuple(argv), cwd=cwd, timeout=START_TIMEOUT, env=dict(env))
        except (OSError, TimeoutError) as error:
            raise UpdateError(code, "staged runtime process could not start") from error


@dataclass(frozen=True)
class ActivationResult:
    status: str
    current_commit: str
    previous_commit: str | None
    error_code: str | None = None


class Activator:
    """Switch current through recoverable junction renames and prove recovery."""

    def __init__(
        self,
        layout: RuntimeLayout,
        health: HealthProbe,
        junctions: JunctionOps | None = None,
    ) -> None:
        self.layout = layout
        self.health = health
        self.junctions = junctions or WindowsJunctionOps()
        self.next = layout.root / "current.next"
        self.previous_switch = layout.root / "current.previous-switch"
        self.journal = layout.root / "activation-journal.json"
        self.lock = layout.root / "activation.lock"

    def activate(
        self, commit: str, on_restarting: Callable[[], None] | None = None
    ) -> ActivationResult:
        with _exclusive_path_lock(self.lock):
            try:
                self._recover_interrupted_switch()
                previous_target, previous_commit = self._current_release()
            except (OSError, UpdateError, ValueError):
                return ActivationResult("recovery_required", "", None, "RECOVERY_REQUIRED")
            target = self._known_release(commit)
            if previous_commit == commit:
                try:
                    if on_restarting is not None:
                        on_restarting()
                    evidence = self.health.validate_production(
                        PRODUCTION_WORKER_URL, PRODUCTION_COMFY_URL, commit
                    )
                    _require_complete_health(evidence, commit)
                except Exception:
                    return ActivationResult("recovery_required", commit, None, "RECOVERY_REQUIRED")
                return ActivationResult("ready", commit, None)

            production_stopped = False
            candidate_current = False
            try:
                self.junctions.create(self.next, target)
                if self.junctions.read_target(self.next).resolve(strict=True) != target:
                    raise UpdateError("RUNTIME_INSTALL_FAILED", "candidate junction target did not match release")
                self._write_journal(commit, previous_commit, "prepared")
                self.health.stop_production()
                production_stopped = True
                self.junctions.rename(self.layout.current, self.previous_switch)
                self._write_journal(commit, previous_commit, "old_renamed")
                self.junctions.rename(self.next, self.layout.current)
                candidate_current = True
                self._write_journal(commit, previous_commit, "candidate_current")
                self.health.start_production()
                if on_restarting is not None:
                    on_restarting()
                evidence = self.health.validate_production(
                    PRODUCTION_WORKER_URL, PRODUCTION_COMFY_URL, commit
                )
                _require_complete_health(evidence, commit)
            except Exception:
                return self._rollback(previous_target, previous_commit, production_stopped or candidate_current)

            try:
                self.junctions.remove(self.previous_switch)
                self.journal.unlink(missing_ok=True)
                self._retain_successful(commit, previous_commit)
            except (OSError, UpdateError, ValueError):
                return ActivationResult("recovery_required", commit, previous_commit, "RECOVERY_REQUIRED")
            return ActivationResult("ready", commit, previous_commit)

    def recover_interrupted_activation(self) -> str | None:
        """Restore a consistent current junction before login startup uses it."""
        with _exclusive_path_lock(self.lock):
            if not any(
                os.path.lexists(path)
                for path in (self.layout.current, self.next, self.previous_switch)
            ):
                # A wholly legacy layout has no managed switch to recover.
                return None
            self._recover_interrupted_switch()
            _target, commit = self._current_release()
            return commit

    def _recover_interrupted_switch(self) -> None:
        has_current = self.layout.current.exists()
        has_next = self.next.exists()
        has_previous = self.previous_switch.exists()
        if has_previous:
            previous_target, _previous_commit = self._junction_release(self.previous_switch)
            if has_current:
                if has_next:
                    self._remove_junction(self.next)
                self.junctions.rename(self.layout.current, self.next)
                self.junctions.rename(self.previous_switch, self.layout.current)
                self._remove_junction(self.next)
            else:
                self.junctions.rename(self.previous_switch, self.layout.current)
                if has_next:
                    self._remove_junction(self.next)
            actual, _commit = self._current_release()
            if actual != previous_target:
                raise UpdateError("RECOVERY_REQUIRED", "interrupted activation restored the wrong release")
        elif has_next:
            if not has_current:
                raise UpdateError("RECOVERY_REQUIRED", "candidate junction exists without a recoverable current")
            self._remove_junction(self.next)
        if self.journal.exists():
            self.journal.unlink()

    def _rollback(
        self,
        previous_target: Path,
        previous_commit: str,
        restart_required: bool,
    ) -> ActivationResult:
        try:
            if restart_required:
                try:
                    self.health.stop_production()
                except Exception:
                    pass
            self._restore_previous(previous_target)
            if restart_required:
                self.health.start_production()
            evidence = self.health.validate_production(
                PRODUCTION_WORKER_URL,
                PRODUCTION_COMFY_URL,
                previous_commit,
            )
            _require_complete_health(evidence, previous_commit)
            self.journal.unlink(missing_ok=True)
        except Exception:
            return ActivationResult(
                "recovery_required",
                self._best_effort_current_commit(),
                previous_commit,
                "RECOVERY_REQUIRED",
            )
        return ActivationResult(
            "rolled_back",
            previous_commit,
            previous_commit,
            "ACTIVATION_FAILED_ROLLED_BACK",
        )

    def _restore_previous(self, previous_target: Path) -> None:
        if self.previous_switch.exists():
            if self.layout.current.exists():
                if self.next.exists():
                    self._remove_junction(self.next)
                self.junctions.rename(self.layout.current, self.next)
            self.junctions.rename(self.previous_switch, self.layout.current)
            if self.next.exists():
                self._remove_junction(self.next)
        elif self.layout.current.exists():
            current_target = self.junctions.read_target(self.layout.current).resolve(strict=True)
            if current_target != previous_target:
                raise UpdateError("RECOVERY_REQUIRED", "previous junction is unavailable")
            if self.next.exists():
                self._remove_junction(self.next)
        else:
            raise UpdateError("RECOVERY_REQUIRED", "previous junction is unavailable")
        restored_target, _commit = self._current_release()
        if restored_target != previous_target:
            raise UpdateError("RECOVERY_REQUIRED", "rollback restored the wrong release")

    def _current_release(self) -> tuple[Path, str]:
        if not self.layout.current.exists():
            raise UpdateError("RECOVERY_REQUIRED", "current junction is missing")
        return self._junction_release(self.layout.current)

    def _junction_release(self, link: Path) -> tuple[Path, str]:
        target = self.junctions.read_target(link).resolve(strict=True)
        try:
            target.relative_to(self.layout.releases.resolve(strict=True))
        except ValueError as error:
            raise UpdateError("RECOVERY_REQUIRED", "junction target escaped releases") from error
        commit = target.name
        known = self._known_release(commit)
        if known != target:
            raise UpdateError("RECOVERY_REQUIRED", "junction target is not a known release")
        return target, commit

    def _known_release(self, commit: str) -> Path:
        release = self.layout.release(commit)
        canonical = _require_contained(release, self.layout.releases, "RUNTIME_INSTALL_FAILED")
        try:
            recorded = (canonical / "source-commit.txt").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "release source commit is unreadable") from error
        if recorded != commit:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "release source commit does not match directory")
        if _managed_release_commit(canonical) != commit:
            raise UpdateError("RUNTIME_INSTALL_FAILED", "release ownership marker is missing or invalid")
        return canonical

    def _remove_junction(self, link: Path) -> None:
        self.junctions.read_target(link)
        self.junctions.remove(link)

    def _write_journal(self, target_commit: str, previous_commit: str, phase: str) -> None:
        _atomic_json(
            self.journal,
            {"phase": phase, "previous_commit": previous_commit, "target_commit": target_commit},
        )

    def _retain_successful(self, current_commit: str, previous_commit: str) -> None:
        keep = {current_commit, previous_commit}
        for candidate in self.layout.releases.iterdir():
            if candidate.name in keep or not FULL_SHA.fullmatch(candidate.name):
                continue
            if candidate.is_symlink() or _is_reparse_point(candidate) or not candidate.is_dir():
                continue
            if _managed_release_commit(candidate) != candidate.name:
                continue
            try:
                recorded = (candidate / "source-commit.txt").read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if recorded != candidate.name:
                continue
            self._remove_release_links(candidate)
            shutil.rmtree(candidate)

    def _remove_release_links(self, release: Path) -> None:
        links = (
            release / "ComfyUI" / "models",
            release / "ComfyUI" / "input",
            release / "ComfyUI" / "output",
            release / ".cache",
            release / "cache" / ".partial",
        )
        for link in links:
            if not link.exists():
                continue
            try:
                target = self.junctions.read_target(link).resolve(strict=True)
                target.relative_to(self.layout.shared.resolve(strict=True))
            except (OSError, ValueError) as error:
                raise UpdateError("RECOVERY_REQUIRED", "release contains an unsafe mutable link") from error
            self.junctions.remove(link)

    def _best_effort_current_commit(self) -> str:
        try:
            _target, commit = self._current_release()
            return commit
        except Exception:
            return ""


def _create_windows_junction(link: Path, target: Path) -> None:
    import ctypes
    import struct
    from ctypes import wintypes

    link.mkdir()
    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    printable = str(target).encode("utf-16-le")
    path_buffer = substitute + b"\x00\x00" + printable + b"\x00\x00"
    reparse = struct.pack(
        "<IHHHHHH",
        0xA0000003,
        8 + len(path_buffer),
        0,
        0,
        len(substitute),
        len(substitute) + 2,
        len(printable),
    ) + path_buffer
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(link),
        0x40000000,
        0,
        None,
        3,
        0x00200000 | 0x02000000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        link.rmdir()
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        returned = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(reparse)
        succeeded = kernel32.DeviceIoControl(
            handle,
            0x000900A4,
            buffer,
            len(reparse),
            None,
            0,
            ctypes.byref(returned),
            None,
        )
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())
    except Exception:
        kernel32.CloseHandle(handle)
        link.rmdir()
        raise
    kernel32.CloseHandle(handle)


def _require_complete_health(evidence: HealthEvidence, expected_commit: str) -> None:
    if not isinstance(evidence, HealthEvidence):
        raise UpdateError("WORKER_CONTRACT_FAILED", "health probe returned no typed evidence")
    if not evidence.cuda_available or not evidence.gpu_name.strip():
        raise UpdateError("CUDA_VALIDATION_FAILED", "staged runtime did not report a CUDA GPU")
    if not evidence.system_stats_ok or not evidence.object_info_ok:
        raise UpdateError("COMFYUI_VALIDATION_FAILED", "ComfyUI health contract is incomplete")
    if (
        not evidence.authenticated_status_ok
        or not evidence.resource_plan_ok
        or not evidence.preflight_ok
        or evidence.source_commit != expected_commit
    ):
        raise UpdateError("WORKER_CONTRACT_FAILED", "Worker health contract or source commit is invalid")


def _managed_release_commit(release: Path) -> str | None:
    try:
        marker = json.loads((release / RELEASE_MARKER).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    if (
        not isinstance(marker, dict)
        or marker.get("schema") != 1
        or not isinstance(marker.get("commit"), str)
        or not FULL_SHA.fullmatch(marker["commit"])
    ):
        return None
    return marker["commit"]


def _require_contained(path: Path, root: Path, code: str) -> Path:
    try:
        canonical_root = Path(root).resolve(strict=True)
        canonical_path = Path(path).resolve(strict=True)
        canonical_path.relative_to(canonical_root)
    except (OSError, ValueError) as error:
        raise UpdateError(code, "runtime path escaped its managed root") from error
    return canonical_path


def _require_no_reparse_directory(path: Path, root: Path, code: str) -> Path:
    path = Path(path)
    root = Path(root)
    try:
        if not path.is_absolute() or not root.is_absolute():
            raise ValueError("runtime path is not absolute")
        path.relative_to(root)
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise ValueError("runtime path contains a reparse point")
        canonical_root = root.resolve(strict=True)
        canonical_path = path.resolve(strict=True)
        canonical_path.relative_to(canonical_root)
        if not canonical_path.is_dir():
            raise OSError("runtime path is not a directory")
    except (OSError, ValueError) as error:
        raise UpdateError(code, "runtime directory failed no-follow validation") from error
    return canonical_path


def _prepare_validation_state(layout: RuntimeLayout, commit: str) -> Path:
    code = "WORKER_CONTRACT_FAILED"
    staging = _require_no_reparse_directory(layout.staging, layout.root, code)
    validation_state = staging / "validation-state"
    if os.path.lexists(validation_state):
        canonical_validation_state = _require_no_reparse_directory(
            validation_state, staging, code
        )
    else:
        validation_state.mkdir()
        canonical_validation_state = _require_no_reparse_directory(
            validation_state, staging, code
        )

    state_root = canonical_validation_state / commit
    if os.path.lexists(state_root):
        _require_no_reparse_directory(state_root, canonical_validation_state, code)
        shutil.rmtree(state_root)
    state_root.mkdir()
    return _require_no_reparse_directory(state_root, canonical_validation_state, code)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, sort_keys=True, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _exclusive_path_lock(path: Path) -> Iterator[None]:
    with path.open("a+b") as lock_file:
        lock_file.seek(0)
        if not lock_file.read(1):
            lock_file.seek(0)
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        _lock_file(lock_file)
        try:
            yield
        finally:
            lock_file.seek(0)
            _unlock_file(lock_file)


def _lock_file(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)


def _unlock_file(lock_file: Any) -> None:
    try:
        import msvcrt
    except ImportError:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    else:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & 0x400)


def _reserve_loopback_ports(count: int) -> tuple[socket.socket, ...]:
    reservations: list[socket.socket] = []
    try:
        for _ in range(count):
            reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if exclusive is not None:
                reservation.setsockopt(socket.SOL_SOCKET, exclusive, 1)
            reservation.bind(("127.0.0.1", 0))
            reservation.listen(1)
            reservations.append(reservation)
    except OSError as error:
        for reservation in reservations:
            reservation.close()
        raise UpdateError("WORKER_CONTRACT_FAILED", "staging loopback ports could not be reserved") from error
    return tuple(reservations)


def _cleanup_staged_runtime(
    reservations: Sequence[socket.socket], processes: Sequence[ProcessHandle]
) -> RuntimeValidationError | None:
    failures: list[BaseException] = []
    for reservation in reservations:
        try:
            reservation.close()
        except BaseException as error:
            failures.append(error)
    for process in reversed(processes):
        failures.extend(_terminate_process(process))
    if not failures:
        return None
    return RuntimeValidationError(
        "CLEANUP_FAILED",
        f"staged runtime cleanup failed in {len(failures)} operation(s)",
        cleanup_failures=failures,
    )


def _terminate_process(process: ProcessHandle) -> list[BaseException]:
    failures: list[BaseException] = []
    try:
        process.terminate()
    except BaseException as error:
        failures.append(error)
    needs_kill = False
    try:
        process.wait(timeout=STOP_TIMEOUT)
    except TimeoutError:
        needs_kill = True
    except BaseException as error:
        failures.append(error)
        needs_kill = True
    if needs_kill:
        try:
            process.kill()
        except BaseException as error:
            failures.append(error)
        try:
            process.wait(timeout=STOP_TIMEOUT)
        except BaseException as error:
            failures.append(error)
    return failures


def _required_safe_version(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if (
        not isinstance(item, str)
        or not SAFE_VERSION.fullmatch(item)
        or item.startswith("-")
        or ".." in item.split("/")
    ):
        raise ValueError(f"{key} is invalid")
    return item


def _required_comfy_version(value: Mapping[str, Any]) -> str:
    item = value.get("comfyui_version")
    if not isinstance(item, str) or not COMFY_VERSION.fullmatch(item):
        raise ValueError("comfyui_version is not an immutable version pin")
    return item


def _required_https_url(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or any(character.isspace() for character in item):
        raise ValueError(f"{key} is invalid")
    parsed = urlsplit(item)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{key} is invalid")
    return item
