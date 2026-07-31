"""Export an exact, fetched Git commit without altering the source checkout."""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_URL_CREDENTIALS = re.compile(r"://[^/\s@]+@")
_SECRET_VALUE = re.compile(
    r"(?i)\b(?:token|secret|password|api[_-]?key|authorization|bearer)\b\s*(?:=|:)?\s*[^\s,;]+"
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{number}" for number in range(1, 10)), *(f"LPT{number}" for number in range(1, 10))}
)
_REF_WILDCARDS = frozenset("*?[")


class UpdateError(RuntimeError):
    """A checked source export failed with an updater-safe error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class GitSource:
    """Read only the configured remote branch and export its exact commit."""

    def __init__(self, root: Path, remote: str, branch: str) -> None:
        self.root = Path(root)
        self.remote = remote
        self.branch = branch

    def export_commit(self, target_commit: str, destination: Path) -> Path:
        """Fetch one configured branch, verify its exact commit, then archive it safely."""
        if not _COMMIT_PATTERN.fullmatch(target_commit):
            raise UpdateError("TARGET_COMMIT_INVALID", "target commit must be a 40-character lowercase SHA")
        destination = Path(destination)
        if destination.exists():
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "export destination must not already exist")

        remote_ref = self._validated_remote_ref()
        self._git("remote", "get-url", self.remote)
        self._git("fetch", "--no-tags", "--no-recurse-submodules", self.remote, f"+refs/heads/{self.branch}:{remote_ref}")
        fetched_commit = self._fetched_commit()
        if fetched_commit != target_commit:
            raise UpdateError("WINDOWS_REMOTE_HEAD_MISMATCH", "requested commit is not the fetched remote branch head")

        self._require_worker_source(target_commit)
        archive = self._git_bytes("archive", "--format=tar", target_commit)
        return self._write_export(destination, archive, target_commit)

    def _validated_remote_ref(self) -> str:
        if _is_unsafe_selector(self.remote) or _is_unsafe_selector(self.branch):
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "configured remote or branch is invalid")
        remote_ref = f"refs/remotes/{self.remote}/{self.branch}"
        try:
            self._git("check-ref-format", "--branch", self.branch)
            self._git("check-ref-format", remote_ref)
        except UpdateError as error:
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "configured remote or branch is invalid") from error
        return remote_ref

    def _fetched_commit(self) -> str:
        remote_ref = f"refs/remotes/{self.remote}/{self.branch}"
        fetched_commit = self._git("rev-parse", "--verify", f"{remote_ref}^{{commit}}")
        if not _COMMIT_PATTERN.fullmatch(fetched_commit):
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "fetched remote branch did not resolve to one commit")
        return fetched_commit

    def _git(self, *args: str) -> str:
        result = self._run_git(*args)
        return result.stdout.decode("utf-8", errors="replace").strip()

    def _git_bytes(self, *args: str) -> bytes:
        return self._run_git(*args).stdout

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UpdateError("GIT_COMMAND_FAILED", "git command could not complete") from error
        if result.returncode:
            raise UpdateError("GIT_COMMAND_FAILED", _redact(result.stderr.decode("utf-8", errors="replace")))
        return result

    def _require_worker_source(self, commit: str) -> None:
        try:
            self._git("cat-file", "-e", f"{commit}^{{commit}}:worker/windows/worker.py")
            if self._git("cat-file", "-t", f"{commit}:worker/windows/worker.py") != "blob":
                raise UpdateError("GIT_COMMAND_FAILED", "worker source is not a file")
        except UpdateError as error:
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "requested commit is missing the Windows worker source") from error

    def _write_export(self, destination: Path, archive: bytes, commit: str) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging_parent = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
        staging = staging_parent / destination.name
        try:
            self._safe_extract_archive(archive, staging)
            (staging / "source-commit.txt").write_text(commit + "\n", encoding="utf-8")
            os.replace(staging, destination)
        except Exception:
            shutil.rmtree(staging_parent, ignore_errors=True)
            raise
        try:
            staging_parent.rmdir()
        except OSError:
            pass
        return destination

    def _safe_extract_archive(self, archive: bytes, destination: Path) -> None:
        """Extract only canonical regular files/directories below a newly created root."""
        destination = Path(destination)
        if destination.exists():
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive destination must not already exist")
        destination.mkdir(parents=True)
        root = destination.resolve(strict=True)
        seen_paths: dict[str, str] = {}
        try:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as contents:
                for member in contents:
                    relative = _canonical_archive_path(member.name)
                    member_kind = "directory" if member.isdir() else "file" if member.isfile() else "other"
                    _reject_windows_path_collision(relative, member_kind, seen_paths)
                    output = destination.joinpath(*relative.parts)
                    resolved_output = output.resolve(strict=False)
                    if not resolved_output.is_relative_to(root):
                        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive member escapes the export root")
                    if member.isdir():
                        output.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        output.parent.mkdir(parents=True, exist_ok=True)
                        source = contents.extractfile(member)
                        if source is None:
                            raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive member could not be read")
                        with source, output.open("xb") as target:
                            shutil.copyfileobj(source, target)
                    else:
                        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains a non-file member")
        except (tarfile.TarError, OSError, ValueError) as error:
            if isinstance(error, UpdateError):
                raise
            raise UpdateError("SOURCE_REPOSITORY_INVALID", "Git archive could not be safely extracted") from error


def _canonical_archive_path(raw_path: str) -> PurePosixPath:
    if not raw_path or "\\" in raw_path:
        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains a non-canonical path")
    path = PurePosixPath(raw_path)
    if (
        raw_path != path.as_posix()
        or not path.parts
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(_is_unsafe_windows_component(part) for part in path.parts)
    ):
        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains a non-canonical path")
    return path


def _is_unsafe_windows_component(component: str) -> bool:
    base_name = component.split(".", 1)[0].upper()
    return (
        ":" in component
        or component.endswith((".", " "))
        or any(ord(character) < 32 for character in component)
        or base_name in _WINDOWS_RESERVED_NAMES
    )


def _reject_windows_path_collision(relative: PurePosixPath, kind: str, seen_paths: dict[str, str]) -> None:
    if kind == "other":
        return
    key = "/".join(part.casefold() for part in relative.parts)
    if key in seen_paths:
        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains colliding Windows paths")
    parent_keys = ("/".join(part.casefold() for part in relative.parts[:index]) for index in range(1, len(relative.parts)))
    if any(seen_paths.get(parent) == "file" for parent in parent_keys):
        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains file-directory path collisions")
    if kind == "file" and any(existing.startswith(key + "/") for existing in seen_paths):
        raise UpdateError("SOURCE_REPOSITORY_INVALID", "archive contains file-directory path collisions")
    seen_paths[key] = kind


def _is_unsafe_selector(value: str) -> bool:
    return not value or value.startswith("-") or any(character.isspace() or character in _REF_WILDCARDS for character in value)


def _redact(stderr: str) -> str:
    redacted = _URL_CREDENTIALS.sub("://[REDACTED]@", stderr)
    redacted = _SECRET_VALUE.sub("[REDACTED]", redacted)
    return redacted.strip() or "git command failed"
