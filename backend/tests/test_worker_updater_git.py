"""Integration tests for exporting an exact managed-worker Git revision."""
from __future__ import annotations

import io
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from worker.windows.updater.git_source import GitSource, UpdateError


@dataclass
class GitFixture:
    remote: Path
    checkout: Path
    remote_head: str

    def snapshot_worktree(self) -> tuple[str, bytes, bytes]:
        return (
            _git(self.checkout, "status", "--porcelain=v1"),
            (self.checkout / "worker" / "windows" / "worker.py").read_bytes(),
            (self.checkout / "local-only.txt").read_bytes(),
        )


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _git_blob(path: Path, contents: bytes) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "hash-object", "-w", "--stdin"],
        check=True,
        capture_output=True,
        input=contents,
    )
    return result.stdout.decode("ascii").strip()


def _tar_with_member(name: str, *, member_type: bytes = tarfile.REGTYPE, linkname: str = "") -> bytes:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.type = member_type
        member.linkname = linkname
        if member_type == tarfile.REGTYPE:
            member.size = len(b"contents")
            archive.addfile(member, io.BytesIO(b"contents"))
        else:
            archive.addfile(member)
    return payload.getvalue()


@pytest.fixture
def git_fixture(tmp_path: Path) -> GitFixture:
    seed = tmp_path / "seed"
    remote = tmp_path / "remote.git"
    checkout = tmp_path / "checkout"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    _git(tmp_path, "init", "--initial-branch=main", str(seed))
    _git(seed, "config", "user.name", "Updater Test")
    _git(seed, "config", "user.email", "updater@example.test")
    worker = seed / "worker" / "windows"
    worker.mkdir(parents=True)
    (worker / "worker.py").write_text("print('trusted worker')\n", encoding="utf-8")
    (seed / "README.md").write_text("trusted source\n", encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "commit", "--quiet", "-m", "initial worker")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "--quiet", "origin", "main")
    _git(tmp_path, "clone", "--quiet", str(remote), str(checkout))
    (checkout / "worker" / "windows" / "worker.py").write_text("print('local edit')\n", encoding="utf-8")
    (checkout / "local-only.txt").write_text("do not touch\n", encoding="utf-8")
    return GitFixture(remote=remote, checkout=checkout, remote_head=_git(seed, "rev-parse", "HEAD"))


def test_export_requires_target_equal_fetched_remote_head(git_fixture: GitFixture, tmp_path: Path) -> None:
    """Removing the remote-head equality check must make this test fail."""
    source = GitSource(git_fixture.checkout, "origin", "main")

    with pytest.raises(UpdateError, match="WINDOWS_REMOTE_HEAD_MISMATCH"):
        source.export_commit("0" * 40, tmp_path / "export")


def test_export_uses_exact_remote_commit_and_leaves_dirty_checkout_untouched(
    git_fixture: GitFixture, tmp_path: Path
) -> None:
    """Changing export to checkout/archive HEAD must make this test fail."""
    before = git_fixture.snapshot_worktree()

    exported = GitSource(git_fixture.checkout, "origin", "main").export_commit(
        git_fixture.remote_head, tmp_path / "export"
    )

    assert (exported / "worker" / "windows" / "worker.py").read_text(encoding="utf-8") == "print('trusted worker')\n"
    assert (exported / "source-commit.txt").read_text(encoding="utf-8") == git_fixture.remote_head + "\n"
    assert git_fixture.snapshot_worktree() == before


def test_export_reports_a_fetch_failure_without_echoing_tokens(git_fixture: GitFixture, tmp_path: Path) -> None:
    """Removing checked subprocess handling or redaction must make this test fail."""
    missing_remote = tmp_path / "TOKEN=do-not-publish" / "missing.git"
    _git(git_fixture.checkout, "remote", "set-url", "origin", str(missing_remote))

    with pytest.raises(UpdateError) as raised:
        GitSource(git_fixture.checkout, "origin", "main").export_commit(git_fixture.remote_head, tmp_path / "export")

    assert raised.value.code == "GIT_COMMAND_FAILED"
    assert "TOKEN=do-not-publish" not in str(raised.value)


def test_export_rejects_a_remote_name_that_does_not_exist(git_fixture: GitFixture, tmp_path: Path) -> None:
    """Allowing an unconfigured remote must make this test fail."""
    with pytest.raises(UpdateError) as raised:
        GitSource(git_fixture.checkout, "other-origin", "main").export_commit(git_fixture.remote_head, tmp_path / "export")

    assert raised.value.code == "GIT_COMMAND_FAILED"


def test_export_rejects_a_remote_branch_pointing_at_a_noncommit_object(
    git_fixture: GitFixture, tmp_path: Path
) -> None:
    """Dropping commit dereferencing/verification must make this test fail."""
    blob = _git_blob(git_fixture.checkout, b"not a commit\n")
    _git(git_fixture.checkout, "update-ref", "refs/remotes/origin/main", blob)

    with pytest.raises(UpdateError) as raised:
        GitSource(git_fixture.checkout, "origin", "main")._fetched_commit()

    assert raised.value.code == "GIT_COMMAND_FAILED"


def test_export_rejects_a_commit_without_the_worker_source(git_fixture: GitFixture, tmp_path: Path) -> None:
    """Removing the worker-source presence check must make this test fail."""
    seed = git_fixture.remote.parent / "seed"
    (seed / "worker" / "windows" / "worker.py").unlink()
    _git(seed, "add", "-A")
    _git(seed, "commit", "--quiet", "-m", "remove worker")
    _git(seed, "push", "--quiet", "origin", "main")
    missing_worker_commit = _git(seed, "rev-parse", "HEAD")

    with pytest.raises(UpdateError) as raised:
        GitSource(git_fixture.checkout, "origin", "main").export_commit(missing_worker_commit, tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"
    assert not (tmp_path / "export" / "source-commit.txt").exists()


def test_export_rejects_an_archive_member_that_escapes_the_export_root(git_fixture: GitFixture, tmp_path: Path) -> None:
    """Removing canonical archive-member validation must make this test fail."""
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        member = tarfile.TarInfo("../escaped.txt")
        member.size = len(b"not allowed")
        archive.addfile(member, io.BytesIO(b"not allowed"))

    source = GitSource(git_fixture.checkout, "origin", "main")
    with pytest.raises(UpdateError) as raised:
        source._safe_extract_archive(payload.getvalue(), tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"
    assert not (tmp_path / "escaped.txt").exists()


def test_export_rejects_an_archive_symlink_that_could_escape_the_export_root(
    git_fixture: GitFixture, tmp_path: Path
) -> None:
    """Accepting archive symlinks must make this test fail."""
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        member = tarfile.TarInfo("worker/windows/escape-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../../escaped.txt"
        archive.addfile(member)

    source = GitSource(git_fixture.checkout, "origin", "main")
    with pytest.raises(UpdateError) as raised:
        source._safe_extract_archive(payload.getvalue(), tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize(
    "member_name",
    [
        "worker/windows/CON",
        "worker/windows/aux.txt",
        "worker/windows/file.txt:secret",
        "worker/windows/trailing-space ",
        "worker/windows/trailing-dot.",
        "worker/windows/control\x01.txt",
        "/absolute.txt",
        "C:/drive-rooted.txt",
    ],
)
def test_export_rejects_archive_paths_windows_would_normalize_or_omit(
    git_fixture: GitFixture, tmp_path: Path, member_name: str
) -> None:
    """Removing Win32 path validation must make this test fail."""
    source = GitSource(git_fixture.checkout, "origin", "main")

    with pytest.raises(UpdateError) as raised:
        source._safe_extract_archive(_tar_with_member(member_name), tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"


@pytest.mark.parametrize(
    "first,second",
    [
        ("worker/windows/Worker.py", "worker/windows/worker.py"),
        ("worker/windows/component", "worker/windows/COMPONENT/file.py"),
    ],
)
def test_export_rejects_case_insensitive_archive_path_collisions(
    git_fixture: GitFixture, tmp_path: Path, first: str, second: str
) -> None:
    """Removing collision detection must make this test fail."""
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for name in (first, second):
            member = tarfile.TarInfo(name)
            member.size = len(b"contents")
            archive.addfile(member, io.BytesIO(b"contents"))

    source = GitSource(git_fixture.checkout, "origin", "main")
    with pytest.raises(UpdateError) as raised:
        source._safe_extract_archive(payload.getvalue(), tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"


@pytest.mark.parametrize(
    "first,second",
    [
        ("Foo/a.txt", "foo/b.txt"),
        ("Foo/Bar/a.txt", "Foo/bar/b.txt"),
    ],
)
def test_export_rejects_case_variants_in_implicit_parent_directories(
    git_fixture: GitFixture, tmp_path: Path, first: str, second: str
) -> None:
    """Recording only leaf members must make this test fail."""
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for name in (first, second):
            member = tarfile.TarInfo(name)
            member.size = len(b"contents")
            archive.addfile(member, io.BytesIO(b"contents"))

    source = GitSource(git_fixture.checkout, "origin", "main")
    with pytest.raises(UpdateError) as raised:
        source._safe_extract_archive(payload.getvalue(), tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"


class _FetchForbiddenGitSource(GitSource):
    def __init__(self, root: Path, remote: str, branch: str) -> None:
        super().__init__(root, remote, branch)
        self.fetch_attempted = False

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        if args[0] == "fetch":
            self.fetch_attempted = True
            raise AssertionError("fetch must not be reached for invalid selectors")
        return super()._run_git(*args)


@pytest.mark.parametrize(
    ("remote", "branch"),
    [
        ("origin", "main*"),
        ("origin", "--upload-pack=unexpected"),
        ("origin*", "main"),
        ("--upload-pack=unexpected", "main"),
    ],
)
def test_export_rejects_invalid_remote_or_branch_before_fetch(
    git_fixture: GitFixture, tmp_path: Path, remote: str, branch: str
) -> None:
    """Moving selector validation below fetch must make this test fail."""
    source = _FetchForbiddenGitSource(git_fixture.checkout, remote, branch)

    with pytest.raises(UpdateError) as raised:
        source.export_commit(git_fixture.remote_head, tmp_path / "export")

    assert raised.value.code == "SOURCE_REPOSITORY_INVALID"
    assert not source.fetch_attempted


def test_export_disables_recursive_submodule_fetch_even_when_repo_config_enables_it(
    git_fixture: GitFixture, tmp_path: Path
) -> None:
    """Removing --no-recurse-submodules must make this test fail."""
    seed = git_fixture.remote.parent / "seed"
    submodule_remote = tmp_path / "submodule.git"
    submodule_seed = tmp_path / "submodule-seed"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(submodule_remote))
    _git(tmp_path, "init", "--initial-branch=main", str(submodule_seed))
    _git(submodule_seed, "config", "user.name", "Updater Test")
    _git(submodule_seed, "config", "user.email", "updater@example.test")
    (submodule_seed / "helper.py").write_text("version = 1\n", encoding="utf-8")
    _git(submodule_seed, "add", ".")
    _git(submodule_seed, "commit", "--quiet", "-m", "submodule v1")
    _git(submodule_seed, "remote", "add", "origin", str(submodule_remote))
    _git(submodule_seed, "push", "--quiet", "origin", "main")
    subprocess.run(
        ["git", "-C", str(seed), "-c", "protocol.file.allow=always", "submodule", "add", str(submodule_remote), "deps/helper"],
        check=True,
        capture_output=True,
    )
    _git(seed, "add", ".gitmodules", "deps/helper")
    _git(seed, "commit", "--quiet", "-m", "add submodule")
    _git(seed, "push", "--quiet", "origin", "main")

    checkout = tmp_path / "submodule-checkout"
    _git(tmp_path, "clone", "--quiet", str(git_fixture.remote), str(checkout))
    subprocess.run(
        ["git", "-C", str(checkout), "-c", "protocol.file.allow=always", "submodule", "update", "--init"],
        check=True,
        capture_output=True,
    )
    _git(checkout, "config", "fetch.recurseSubmodules", "true")
    _git(checkout / "deps" / "helper", "remote", "set-url", "origin", str(tmp_path / "missing-submodule.git"))

    (submodule_seed / "helper.py").write_text("version = 2\n", encoding="utf-8")
    _git(submodule_seed, "commit", "--quiet", "-am", "submodule v2")
    _git(submodule_seed, "push", "--quiet", "origin", "main")
    subprocess.run(
        ["git", "-C", str(seed), "-c", "protocol.file.allow=always", "submodule", "update", "--remote", "deps/helper"],
        check=True,
        capture_output=True,
    )
    _git(seed, "commit", "--quiet", "-am", "advance submodule")
    _git(seed, "push", "--quiet", "origin", "main")
    target = _git(seed, "rev-parse", "HEAD")

    exported = GitSource(checkout, "origin", "main").export_commit(target, tmp_path / "export")

    assert (exported / "worker" / "windows" / "worker.py").is_file()
