from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

import launcher.comfyui as comfyui_module
from launcher.comfyui import (
    ComfyInstallError,
    ComfyInstallCleanupPending,
    ComfyUpdateError,
    OwnedTemporaryDirectory,
    UpdateOutcome,
    InstallTargetNotEmpty,
    build_install_plan,
    discover_comfyui,
    install_comfyui,
    prepare_staging_target,
    probe_comfyui,
    resolve_uv_binary,
    smoke_comfyui_runtime,
    update_comfyui,
    validate_comfyui_root,
)
from launcher.models import ComfyMode, DeviceMode, HostInfo
from launcher.runner import CommandResult


WINDOWS = HostInfo("Windows", "AMD64", Path("C:/Users/test"))
LINUX = HostInfo("Linux", "x86_64", Path("/home/test"))


@pytest.fixture
def uv_bin(tmp_path):
    name = "uv.exe" if os.name == "nt" else "uv"
    path = (tmp_path / "fake-tools" / name).resolve()
    path.parent.mkdir()
    path.touch()
    if os.name != "nt":
        path.chmod(0o755)
    return path


def make_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("# ComfyUI\n", encoding="utf-8")
    (root / "models").mkdir()
    return root


def make_managed_root(root: Path, host: HostInfo = LINUX) -> Path:
    root = make_root(root)
    (root / ".git").mkdir()
    python = (
        root / ".venv/Scripts/python.exe"
        if host.system == "Windows"
        else root / ".venv/bin/python"
    )
    python.parent.mkdir(parents=True)
    python.touch()
    (root / ".venv/old-environment.txt").write_text("exact-old", encoding="utf-8")
    (root / "requirements.txt").write_text("# fake\n", encoding="utf-8")
    return root


class FakeRunner:
    def __init__(self, fail_when=None, old_commit: str = "abc123"):
        self.commands: list[tuple[tuple[str, ...], Path | None]] = []
        self.fail_when = fail_when or (lambda _args: False)
        self.old_commit = old_commit

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = tuple(str(arg) for arg in args)
        self.commands.append((command, cwd))
        if command == ("git", "rev-parse", "--show-toplevel"):
            return CommandResult(command, 0, str(Path(cwd).resolve()) + "\n", "")
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return CommandResult(command, 0, self.old_commit + "\n", "")
        if command[:2] == ("git", "clone"):
            make_root(Path(command[-1]))
        if len(command) > 1 and Path(command[0]).name in {"uv", "uv.exe"} and command[1] == "venv":
            venv = Path(command[-1])
            for python in (
                venv / "Scripts" / "python.exe",
                venv / "bin" / "python",
            ):
                python.parent.mkdir(parents=True, exist_ok=True)
                python.touch()
        failed = self.fail_when(command)
        return CommandResult(command, 1 if failed else 0, "", "failed" if failed else "")


class FakeResponse:
    status = 200

    def read(self):
        return b'{"system": {"os": "test"}}'

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_root_validation_requires_main_and_models(tmp_path):
    root = tmp_path / "ComfyUI"
    root.mkdir()

    missing_both = validate_comfyui_root(root, LINUX)
    assert missing_both.valid is False
    assert missing_both.issues == ("missing_main_py", "missing_models_directory")

    (root / "main.py").touch()
    missing_models = validate_comfyui_root(root, LINUX)
    assert missing_models.valid is False
    assert missing_models.issues == ("missing_models_directory",)


def test_root_validation_finds_venv_and_portable_python(tmp_path):
    venv_root = make_root(tmp_path / "venv-root")
    venv_python = venv_root / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    portable_root = make_root(tmp_path / "portable-root")
    portable_python = portable_root / "python_embeded" / "python.exe"
    portable_python.parent.mkdir()
    portable_python.touch()

    assert validate_comfyui_root(venv_root, WINDOWS).python == venv_python
    assert validate_comfyui_root(portable_root, WINDOWS).python == portable_python


def test_discovery_is_bounded_and_deduplicates_candidates(tmp_path):
    parent = tmp_path / "not-a-root"
    nested = make_root(parent / "deep" / "ComfyUI")
    explicit = make_root(tmp_path / "explicit")

    assert discover_comfyui((parent,), LINUX) == ()
    found = discover_comfyui((explicit, explicit, nested), LINUX)
    assert tuple(item.root for item in found) == (explicit.resolve(), nested.resolve())


def test_running_probe_is_always_external():
    requested = []

    def http_get(url, *, timeout):
        requested.append((url, timeout))
        return FakeResponse()

    result = probe_comfyui("http://127.0.0.1:8188/", http_get=http_get)

    assert result.running is True
    assert result.mode is ComfyMode.EXTERNAL
    assert requested == [("http://127.0.0.1:8188/system_stats", 2.0)]


def test_failed_probe_is_not_running():
    requested = []

    def unavailable(url, *, timeout):
        requested.append((url, timeout))
        raise OSError("connection refused")

    result = probe_comfyui("http://127.0.0.1:8188", http_get=unavailable)

    assert result.running is False
    assert result.mode is None
    assert requested == [("http://127.0.0.1:8188/system_stats", 2.0)]


def test_install_refuses_nonempty_target(tmp_path):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    (target / "user.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(InstallTargetNotEmpty):
        prepare_staging_target(target)


def test_prepare_staging_never_touches_preexisting_staging_like_directory(tmp_path):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    sentinel = tmp_path / ".ComfyUI.staging"
    sentinel.mkdir()
    (sentinel / "user.txt").write_text("keep", encoding="utf-8")
    unknown = tmp_path / ".ComfyUI.staging-user-owned"
    unknown.mkdir()
    (unknown / "user.txt").write_text("also-keep", encoding="utf-8")

    prepared = prepare_staging_target(target)

    assert prepared.path != sentinel
    assert prepared.path.parent == target.parent
    assert prepared.path.name.startswith(".ComfyUI.staging-")
    assert prepared.path.is_dir()
    assert list(prepared.path.iterdir()) == []
    assert (sentinel / "user.txt").read_text(encoding="utf-8") == "keep"
    assert (unknown / "user.txt").read_text(encoding="utf-8") == "also-keep"
    assert target.is_dir()
    assert prepared.cleanup() == comfyui_module.CleanupOutcome(False, prepared.path)


def test_prepare_staging_allocates_a_unique_owned_directory_each_time(tmp_path):
    target = tmp_path / "ComfyUI"

    first = prepare_staging_target(target)
    second = prepare_staging_target(target)

    assert first.path != second.path
    assert first.path.is_dir()
    assert second.path.is_dir()
    assert first.cleanup().pending_path == first.path
    assert second.cleanup().pending_path == second.path


def test_owned_nonempty_cleanup_fails_closed_and_retains_payload(tmp_path):
    owned = OwnedTemporaryDirectory.create(parent=tmp_path, prefix="owned-")
    (owned.path / "payload.txt").write_text("keep", encoding="utf-8")

    result = owned.cleanup()

    assert result.cleaned is False
    assert result.pending_path == owned.path
    assert (owned.path / "payload.txt").read_text(encoding="utf-8") == "keep"


def test_owned_empty_cleanup_is_always_retained_fail_closed(tmp_path):
    owned = OwnedTemporaryDirectory.create(parent=tmp_path, prefix="owned-")

    result = owned.cleanup()

    assert result.cleaned is False
    assert result.pending_path == owned.path
    assert owned.path.is_dir()


def test_owned_cleanup_does_not_trust_path_exists_false_negative(
    tmp_path,
    monkeypatch,
):
    owned = OwnedTemporaryDirectory.create(parent=tmp_path, prefix="owned-")
    original_exists = Path.exists

    def false_negative(path):
        if path == owned.path:
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", false_negative)

    result = owned.cleanup()

    assert result.cleaned is False
    assert result.pending_path == owned.path


def test_owned_cleanup_has_no_pre_remove_callback_window(tmp_path):
    owned = OwnedTemporaryDirectory.create(parent=tmp_path, prefix="owned-")
    (owned.path / "original.txt").write_text("original", encoding="utf-8")

    result = owned.cleanup()

    assert result.cleaned is False
    assert result.pending_path == owned.path
    assert "before_remove" not in inspect.signature(owned.cleanup).parameters
    assert (owned.path / "original.txt").read_text(encoding="utf-8") == "original"


def flattened_args(plan):
    return [arg for command in plan.commands for arg in command.args]


def test_uv_binary_resolves_exported_absolute_cache_path(tmp_path):
    uv = (tmp_path / "cache" / ("uv.exe" if os.name == "nt" else "uv")).resolve()
    uv.parent.mkdir()
    uv.touch()
    if os.name != "nt":
        uv.chmod(0o755)

    assert resolve_uv_binary(
        environ={"AI_DRAWING_UV_BIN": str(uv)},
        which=lambda _name: None,
    ) == uv


def test_uv_binary_missing_has_stable_diagnostic():
    with pytest.raises(ComfyInstallError, match="UV_BINARY_MISSING"):
        resolve_uv_binary(environ={}, which=lambda _name: None)


def test_every_install_dependency_command_uses_injected_absolute_uv(tmp_path, uv_bin):
    plan = install_plan(tmp_path, DeviceMode.CPU, uv_bin)

    dependency_commands = plan.commands[1:-1]
    assert dependency_commands
    assert all(command.args[0] == str(uv_bin) for command in dependency_commands)
    assert not any(command.args[0] == "uv" for command in plan.commands)


def test_accelerated_smoke_failure_is_explicit_and_never_falls_back(tmp_path):
    python = (tmp_path / "python").resolve()
    runner = FakeRunner(fail_when=lambda args: len(args) > 1 and args[1] == "-c")

    with pytest.raises(ComfyInstallError, match="smoke"):
        smoke_comfyui_runtime(python, DeviceMode.MPS, runner)

    assert runner.commands == [
        ((str(python), "-c", "import torch; assert torch.backends.mps.is_available()"), None)
    ]


def make_invalid_uv(tmp_path: Path, kind: str) -> Path:
    if kind == "missing":
        return (tmp_path / "missing" / ("uv.exe" if os.name == "nt" else "uv")).resolve()
    if kind == "directory":
        path = (tmp_path / "uv-directory").resolve()
        path.mkdir()
        return path
    path = (tmp_path / ("uv.txt" if os.name == "nt" else "uv-no-exec")).resolve()
    path.touch()
    if os.name != "nt":
        path.chmod(0o644)
    return path


@pytest.mark.parametrize("kind", ["missing", "directory", "non_executable"])
def test_invalid_uv_rejected_before_install_staging_or_runner_side_effects(
    tmp_path,
    kind,
):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    invalid_uv = make_invalid_uv(tmp_path, kind)
    runner = FakeRunner()

    with pytest.raises(ComfyInstallError, match="UV_BINARY_INVALID"):
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            project_root=tmp_path / "project",
            uv_bin=invalid_uv,
        )

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert not list(tmp_path.glob(".ComfyUI.staging-*"))
    assert runner.commands == []


@pytest.mark.parametrize("kind", ["missing", "directory", "non_executable"])
def test_invalid_uv_rejected_before_update_git_or_filesystem_mutation(tmp_path, kind):
    root = make_root(tmp_path / "ComfyUI")
    marker = root / "user-marker.txt"
    marker.write_text("keep", encoding="utf-8")
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    invalid_uv = make_invalid_uv(tmp_path, kind)
    runner = FakeRunner(old_commit="old123")

    with pytest.raises(ComfyInstallError, match="UV_BINARY_INVALID"):
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=invalid_uv,
        )

    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert runner.commands == []


@pytest.mark.parametrize("operation", ["install", "update"])
def test_invalid_uv_precedes_macos_architecture_and_git_runner_boundaries(
    tmp_path,
    operation,
):
    invalid_uv = (tmp_path / "missing/uv").resolve()
    runner = FakeRunner()
    macos = HostInfo("Darwin", "x86_64", Path("/Users/test"))

    with pytest.raises(ComfyInstallError, match="UV_BINARY_INVALID"):
        if operation == "install":
            install_comfyui(
                tmp_path / "target",
                DeviceMode.CPU,
                runner,
                host=macos,
                project_root=tmp_path / "project",
                uv_bin=invalid_uv,
            )
        else:
            update_comfyui(
                make_managed_root(tmp_path / "ComfyUI"),
                DeviceMode.CPU,
                runner,
                host=macos,
                owned_root=tmp_path / "ComfyUI",
                uv_bin=invalid_uv,
            )

    assert runner.commands == []


def install_plan(tmp_path, device, uv_bin):
    return build_install_plan(
        tmp_path / "ComfyUI",
        device,
        staging=tmp_path / ".ComfyUI.staging-owned",
        uv_bin=uv_bin,
    )


def test_nvidia_plan_is_pinned(tmp_path, uv_bin):
    plan = install_plan(tmp_path, DeviceMode.NVIDIA, uv_bin)
    args = flattened_args(plan)

    assert "v0.28.0" in args
    assert "3.12" in args
    assert "https://download.pytorch.org/whl/cu130" in args
    assert "torch.cuda.is_available()" in plan.commands[-1].args[-1]


def test_mps_plan_uses_default_torch_wheels_and_asserts_mps(tmp_path, uv_bin):
    plan = install_plan(tmp_path, DeviceMode.MPS, uv_bin)
    torch_command = plan.commands[3].args

    assert "--index-url" not in torch_command
    assert "torch.backends.mps.is_available()" in plan.commands[-1].args[-1]


def test_cpu_plan_uses_cpu_torch_index(tmp_path, uv_bin):
    plan = install_plan(tmp_path, DeviceMode.CPU, uv_bin)
    args = flattened_args(plan)

    assert "https://download.pytorch.org/whl/cpu" in args
    assert plan.commands[-1].args[-1] == "import torch"


def test_install_plan_has_exact_staged_sequence_and_no_content_downloads(tmp_path, uv_bin):
    target = tmp_path / "ComfyUI"
    plan = build_install_plan(
        target,
        DeviceMode.CPU,
        staging=tmp_path / ".ComfyUI.staging-owned",
        uv_bin=uv_bin,
    )

    assert [command.args[:2] for command in plan.commands] == [
        ("git", "clone"),
        (str(uv_bin), "python"),
        (str(uv_bin), "venv"),
        (str(uv_bin), "pip"),
        (str(uv_bin), "pip"),
        (str(plan.python), "-c"),
    ]
    assert plan.commands[2].args == (
        str(uv_bin),
        "venv",
        "--python",
        "3.12",
        str(plan.staging / ".venv"),
    )
    joined = " ".join(flattened_args(plan)).lower()
    assert "custom_nodes" not in joined
    assert "models/" not in joined


def test_install_promotes_staging_only_after_success(tmp_path, uv_bin):
    target = tmp_path / "ComfyUI"
    sentinel = tmp_path / ".ComfyUI.staging"
    sentinel.mkdir()
    (sentinel / "user.txt").write_text("keep", encoding="utf-8")
    runner = FakeRunner()

    result = install_comfyui(
        target,
        DeviceMode.CPU,
        runner,
        host=LINUX,
        project_root=tmp_path / "project",
        uv_bin=uv_bin,
    )

    assert result.root == target.resolve()
    assert result.valid is True
    assert target.is_dir()
    assert (sentinel / "user.txt").read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".ComfyUI.staging-*"))
    assert len(runner.commands) == 6


def test_smoke_failure_cleans_staging_and_does_not_publish_target(tmp_path, uv_bin):
    target = tmp_path / "ComfyUI"
    sentinel = tmp_path / ".ComfyUI.staging"
    sentinel.mkdir()
    (sentinel / "user.txt").write_text("keep", encoding="utf-8")
    runner = FakeRunner(fail_when=lambda args: len(args) > 1 and args[1] == "-c")

    with pytest.raises(ComfyInstallCleanupPending) as raised:
        install_comfyui(
            target,
            DeviceMode.NVIDIA,
            runner,
            host=LINUX,
            project_root=tmp_path / "project",
            uv_bin=uv_bin,
        )

    assert not target.exists()
    assert (sentinel / "user.txt").read_text(encoding="utf-8") == "keep"
    assert raised.value.pending_path.name.startswith(".ComfyUI.staging-")
    assert raised.value.pending_path.is_dir()
    assert "cleanup" in raised.value.hint.lower()


def test_update_reinstalls_pinned_version_without_cloning(tmp_path, uv_bin):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")

    result = update_comfyui(
        root,
        DeviceMode.CPU,
        runner,
        host=LINUX,
        owned_root=root,
        uv_bin=uv_bin,
    )

    commands = [command for command, _cwd in runner.commands]
    assert isinstance(result, UpdateOutcome)
    assert result.version == "v0.28.0"
    assert len(result.cleanup_pending) == 2
    assert any(
        path.name.startswith(".ComfyUI.venv-backup-")
        for path in result.cleanup_pending
    )
    assert any(
        path.name.startswith(".ComfyUI.venv.update-new-")
        for path in result.cleanup_pending
    )
    assert commands[0] == ("git", "rev-parse", "--show-toplevel")
    assert commands[1] == ("git", "rev-parse", "HEAD")
    assert commands[2] == (
        "git",
        "fetch",
        "--depth",
        "1",
        "origin",
        "tag",
        "v0.28.0",
    )
    assert commands[3] == ("git", "checkout", "--detach", "v0.28.0")
    assert commands[5][:4] == (str(uv_bin), "venv", "--python", "3.12")
    assert "--clear" not in commands[5]
    assert Path(commands[5][-1]).name == "venv"
    assert ".venv.update-new-" in str(Path(commands[5][-1]).parent)
    assert not any(command[:2] == ("git", "clone") for command in commands)
    assert commands[-1][1] == "-c"
    assert not (root / ".venv/old-environment.txt").exists()
    backup = next(
        path
        for path in result.cleanup_pending
        if path.name.startswith(".ComfyUI.venv-backup-")
    )
    assert backup.is_dir()
    assert (backup / "venv").is_dir()


def test_update_restores_old_commit_when_smoke_fails(tmp_path, uv_bin):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: (
            len(args) > 1
            and args[1] == "-c"
            and ".venv.update-new-" in args[0]
        ),
        old_commit="old123",
    )

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.MPS,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    commands = [command for command, _cwd in runner.commands]
    assert raised.value.code == "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING"
    assert raised.value.hint
    assert commands[-2] == ("git", "checkout", "--detach", "old123")
    assert commands[-1][0] == str(root / ".venv/bin/python")
    assert commands[-1][1] == "-c"
    assert (root / ".venv/old-environment.txt").read_text(encoding="utf-8") == "exact-old"
    pending = list(raised.value.pending_paths)
    assert len(pending) == 2
    assert any(path.name.startswith(".ComfyUI.venv.update-new-") for path in pending)
    assert any(path.name.startswith(".ComfyUI.venv-backup-") for path in pending)
    assert all(str(path) in raised.value.hint for path in pending)
    assert all(path.is_dir() for path in pending)


@pytest.mark.parametrize(
    "failed_prefix",
    [
        ("git", "fetch"),
        ("git", "checkout", "--detach", "v0.28.0"),
    ],
)
def test_update_restores_old_commit_when_fetch_or_checkout_fails(
    tmp_path,
    failed_prefix,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: args[: len(failed_prefix)] == failed_prefix,
        old_commit="old123",
    )

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    commands = [command for command, _cwd in runner.commands]
    assert raised.value.code == "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING"
    assert commands[-2] == ("git", "checkout", "--detach", "old123")
    assert commands[-1][0] == str(root / ".venv/bin/python")
    assert (root / ".venv/old-environment.txt").is_file()
    assert raised.value.pending_paths
    assert all(path.is_dir() for path in raised.value.pending_paths)


@pytest.mark.parametrize("failed_phase", ["venv", "torch", "requirements"])
def test_update_restores_exact_old_environment_when_environment_build_fails(
    tmp_path,
    uv_bin,
    failed_phase,
):
    root = make_managed_root(tmp_path / "ComfyUI")

    def fails(args):
        if failed_phase == "venv":
            return len(args) > 1 and args[1] == "venv"
        if failed_phase == "torch":
            return "torch" in args
        return "-r" in args

    runner = FakeRunner(fail_when=fails, old_commit="old123")

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    commands = [command for command, _cwd in runner.commands]
    assert raised.value.code == "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING"
    assert commands[-2] == ("git", "checkout", "--detach", "old123")
    assert commands[-1][0] == str(root / ".venv/bin/python")
    assert (root / ".venv/old-environment.txt").read_text(encoding="utf-8") == "exact-old"
    assert raised.value.pending_paths
    assert all(path.exists() for path in raised.value.pending_paths)


def test_update_backup_rename_failure_does_not_fetch_or_change_environment(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")
    original_replace = Path.replace

    def fail_old_environment_backup(path, destination):
        if path == root / ".venv":
            raise OSError("backup rename failed")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_old_environment_backup)

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_BACKUP_FAILED"
    assert [command for command, _cwd in runner.commands] == [
        ("git", "rev-parse", "--show-toplevel"),
        ("git", "rev-parse", "HEAD"),
    ]
    assert (root / ".venv/old-environment.txt").is_file()
    assert len(raised.value.pending_paths) == 2
    assert any(
        path.name.startswith(".ComfyUI.venv-backup-")
        for path in raised.value.pending_paths
    )
    assert any(
        path.name.startswith(".ComfyUI.venv.update-new-")
        for path in raised.value.pending_paths
    )
    assert all(path.is_dir() for path in raised.value.pending_paths)


def test_update_activation_rename_failure_restores_old_environment(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")
    original_replace = Path.replace

    def fail_new_environment_activation(path, destination):
        if path.name == "venv" and ".venv.update-new-" in str(path.parent):
            raise OSError("activation failed")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_new_environment_activation)

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_FAILED_RESTORED_CLEANUP_PENDING"
    assert (root / ".venv/old-environment.txt").is_file()
    assert raised.value.pending_paths
    assert all(path.exists() for path in raised.value.pending_paths)


def test_update_rollback_checkout_failure_retains_exact_backup(tmp_path, uv_bin):
    root = make_managed_root(tmp_path / "ComfyUI")

    def fails(args):
        return (
            (len(args) > 1 and args[1] == "-c" and ".venv.update-new-" in args[0])
            or args == ("git", "checkout", "--detach", "old123")
        )

    runner = FakeRunner(fail_when=fails, old_commit="old123")

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert len(backups) == 1
    assert str(backups[0]) in raised.value.hint
    assert (backups[0] / "venv/old-environment.txt").is_file()
    assert not (root / ".venv").exists()


def test_update_restore_rename_failure_retains_exact_backup(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: (
            len(args) > 1 and args[1] == "-c" and ".venv.update-new-" in args[0]
        ),
        old_commit="old123",
    )
    original_replace = Path.replace

    def fail_backup_restore(path, destination):
        if path.name == "venv" and ".venv-backup-" in str(path.parent):
            raise OSError("restore rename failed")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_backup_restore)

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert len(backups) == 1
    assert (backups[0] / "venv/old-environment.txt").is_file()


def test_update_restored_smoke_failure_retains_old_environment_backup(tmp_path, uv_bin):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: len(args) > 1 and args[1] == "-c",
        old_commit="old123",
    )

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert len(backups) == 1
    assert (backups[0] / "venv/old-environment.txt").is_file()
    assert not (root / ".venv").exists()


def test_update_rollback_never_deletes_concurrently_created_unknown_venv(
    tmp_path,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")

    class ConcurrentRunner(FakeRunner):
        def run(self, args, **kwargs):
            command = tuple(str(arg) for arg in args)
            if (
                len(command) > 1
                and command[1] == "-c"
                and ".venv.update-new-" in command[0]
            ):
                unknown = root / ".venv"
                unknown.mkdir()
                (unknown / "user.txt").write_text("never-delete", encoding="utf-8")
            return super().run(args, **kwargs)

    runner = ConcurrentRunner(
        fail_when=lambda args: (
            len(args) > 1 and args[1] == "-c" and ".venv.update-new-" in args[0]
        ),
        old_commit="old123",
    )

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert (root / ".venv/user.txt").read_text(encoding="utf-8") == "never-delete"
    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "venv/old-environment.txt").is_file()


def test_update_rollback_rejects_post_activation_venv_substitution(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")
    original_validate = comfyui_module.validate_comfyui_root
    validations = 0
    retained_new = tmp_path / "retained-activated-new-venv"

    def substitute_after_activation(candidate, host):
        nonlocal validations
        validations += 1
        if validations == 2:
            (root / ".venv").replace(retained_new)
            (root / ".venv").mkdir()
            (root / ".venv/user.txt").write_text("unknown", encoding="utf-8")
        return original_validate(candidate, host)

    monkeypatch.setattr(comfyui_module, "validate_comfyui_root", substitute_after_activation)

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert (root / ".venv/user.txt").read_text(encoding="utf-8") == "unknown"
    assert (retained_new / "bin/python").is_file()
    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "venv/old-environment.txt").is_file()


def test_update_never_opens_activated_venv_check_replace_rollback_window(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")
    original_validate = comfyui_module.validate_comfyui_root
    original_replace = Path.replace
    validations = 0
    unsafe_rollback_calls = []

    def fail_after_activation(candidate, host):
        nonlocal validations
        validations += 1
        if validations == 2:
            raise ComfyInstallError("post-activation validation failed")
        return original_validate(candidate, host)

    def observe_activated_rollback(path, destination):
        if path == root / ".venv" and destination.name == "failed-venv":
            unsafe_rollback_calls.append((path, destination))
        return original_replace(path, destination)

    monkeypatch.setattr(comfyui_module, "validate_comfyui_root", fail_after_activation)
    monkeypatch.setattr(Path, "replace", observe_activated_rollback)

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_ROLLBACK_FAILED"
    assert unsafe_rollback_calls == []
    assert (root / ".venv/bin/python").is_file()
    backups = list(tmp_path.glob(".ComfyUI.venv-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "venv/old-environment.txt").is_file()


def test_update_rejects_root_that_does_not_match_owned_provenance_before_git(
    tmp_path,
    uv_bin,
):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner()

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=tmp_path / "different-root",
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_NOT_OWNED"
    assert runner.commands == []
    assert (root / ".venv/old-environment.txt").is_file()


def test_update_invalid_git_source_has_stable_code_before_backup(tmp_path, uv_bin):
    root = make_managed_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="")

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_SOURCE_INVALID"
    assert raised.value.hint
    assert (root / ".venv/old-environment.txt").is_file()
    assert not list(tmp_path.glob(".ComfyUI.venv-*-*"))


def test_update_rejects_missing_git_root_before_backup_or_fetch(tmp_path, uv_bin):
    root = make_root(tmp_path / "ComfyUI")
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    runner = FakeRunner(old_commit="old123")

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_SOURCE_INVALID"
    assert [command for command, _cwd in runner.commands] == [
        ("git", "rev-parse", "--show-toplevel")
    ]
    assert not list(tmp_path.glob(".ComfyUI.venv-*"))
    assert python.is_file()


def test_update_rejects_nested_root_resolved_to_ancestor_repository(tmp_path, uv_bin):
    ancestor = tmp_path / "ancestor"
    (ancestor / ".git").mkdir(parents=True)
    root = make_root(ancestor / "nested/ComfyUI")
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()

    class AncestorRunner(FakeRunner):
        def run(self, args, **kwargs):
            command = tuple(str(item) for item in args)
            if command == ("git", "rev-parse", "--show-toplevel"):
                self.commands.append((command, kwargs.get("cwd")))
                return CommandResult(command, 0, str(ancestor.resolve()) + "\n", "")
            return super().run(args, **kwargs)

    runner = AncestorRunner(old_commit="old123")

    with pytest.raises(ComfyUpdateError) as raised:
        update_comfyui(
            root,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            owned_root=root,
            uv_bin=uv_bin,
        )

    assert raised.value.code == "COMFYUI_UPDATE_SOURCE_INVALID"
    assert [command for command, _cwd in runner.commands] == [
        ("git", "rev-parse", "--show-toplevel")
    ]
    assert not list(ancestor.glob(".ComfyUI.venv-*"))
    assert python.is_file()


def test_failed_promotion_restores_preexisting_empty_target(tmp_path, monkeypatch, uv_bin):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    runner = FakeRunner()
    original_replace = Path.replace

    def fail_staging_promotion(path, destination):
        if path.name.startswith(".ComfyUI.staging-"):
            raise OSError("promotion failed")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_staging_promotion)

    with pytest.raises(ComfyInstallCleanupPending) as raised:
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            project_root=tmp_path / "project",
            uv_bin=uv_bin,
        )

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert raised.value.pending_path.is_dir()
    assert raised.value.pending_path.name.startswith(".ComfyUI.staging-")


@pytest.mark.parametrize("relative_target", [Path("."), Path("data/ComfyUI")])
def test_install_rejects_repository_target_before_side_effects(
    tmp_path,
    relative_target,
    uv_bin,
):
    assert "project_root" in inspect.signature(install_comfyui).parameters
    project = tmp_path / "repository"
    project.mkdir()
    target = project / relative_target
    runner = FakeRunner()

    with pytest.raises(ComfyInstallError, match="repository"):
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            project_root=project,
            uv_bin=uv_bin,
        )

    assert runner.commands == []
    assert not list(target.resolve().parent.glob(".ComfyUI.staging-*"))
    if relative_target != Path("."):
        assert not target.exists()


def test_install_rejects_nonexistent_child_through_symlink_parent(tmp_path, uv_bin):
    assert "project_root" in inspect.signature(install_comfyui).parameters
    project = tmp_path / "repository"
    project.mkdir()
    link = tmp_path / "repository-link"
    try:
        link.symlink_to(project, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink unavailable: {error}")
    target = link / "future" / "ComfyUI"
    runner = FakeRunner()

    with pytest.raises(ComfyInstallError, match="repository"):
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            project_root=project,
            uv_bin=uv_bin,
        )

    assert runner.commands == []
    assert not target.exists()


def test_install_rejects_canonical_child_without_symlink_privileges(
    tmp_path,
    monkeypatch,
    uv_bin,
):
    """Exercise symlink-parent canonicalization without creating an OS symlink."""
    project = tmp_path / "repository"
    project.mkdir()
    target = tmp_path / "repository-link" / "future" / "ComfyUI"
    canonical_target = project / "future" / "ComfyUI"
    runner = FakeRunner()
    original_resolve = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path == target:
            return canonical_target
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(ComfyInstallError, match="repository"):
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=LINUX,
            project_root=project,
            uv_bin=uv_bin,
        )

    assert runner.commands == []
    assert not target.exists()


def test_install_allows_sibling_target_with_fake_runner(tmp_path, uv_bin):
    assert "project_root" in inspect.signature(install_comfyui).parameters
    project = tmp_path / "repository"
    project.mkdir()
    target = tmp_path / "managed-ComfyUI"
    runner = FakeRunner()

    result = install_comfyui(
        target,
        DeviceMode.CPU,
        runner,
        host=LINUX,
        project_root=project,
        uv_bin=uv_bin,
    )

    assert result.root == target.resolve()
    assert len(runner.commands) == 6


def test_rosetta_install_boundary_never_clones_or_writes(tmp_path, uv_bin):
    assert "project_root" in inspect.signature(install_comfyui).parameters
    project = tmp_path / "repository"
    project.mkdir()
    target = tmp_path / "managed-ComfyUI"
    runner = FakeRunner()
    runner.fail_when = lambda _args: False
    original_run = runner.run

    def translated(args, **kwargs):
        command = tuple(str(arg) for arg in args)
        if command == ("sysctl", "-in", "sysctl.proc_translated"):
            runner.commands.append((command, kwargs.get("cwd")))
            return CommandResult(command, 0, "1\n", "")
        return original_run(args, **kwargs)

    runner.run = translated

    with pytest.raises(ComfyInstallError, match="native"):
        install_comfyui(
            target,
            DeviceMode.CPU,
            runner,
            host=HostInfo("Darwin", "x86_64", Path("/Users/test")),
            project_root=project,
            uv_bin=uv_bin,
        )

    assert [command for command, _cwd in runner.commands] == [
        ("sysctl", "-in", "sysctl.proc_translated")
    ]
    assert not target.exists()
