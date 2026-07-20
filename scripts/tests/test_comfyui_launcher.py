from __future__ import annotations

from pathlib import Path

import pytest

from launcher.comfyui import (
    ComfyInstallError,
    InstallTargetNotEmpty,
    build_install_plan,
    discover_comfyui,
    install_comfyui,
    prepare_staging_target,
    probe_comfyui,
    staging_path,
    update_comfyui,
    validate_comfyui_root,
)
from launcher.models import ComfyMode, DeviceMode, HostInfo
from launcher.runner import CommandResult


WINDOWS = HostInfo("Windows", "AMD64", Path("C:/Users/test"))
LINUX = HostInfo("Linux", "x86_64", Path("/home/test"))


def make_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("# ComfyUI\n", encoding="utf-8")
    (root / "models").mkdir()
    return root


class FakeRunner:
    def __init__(self, fail_when=None, old_commit: str = "abc123"):
        self.commands: list[tuple[tuple[str, ...], Path | None]] = []
        self.fail_when = fail_when or (lambda _args: False)
        self.old_commit = old_commit

    def run(self, args, cwd=None, env=None, check=False, capture=True):
        command = tuple(str(arg) for arg in args)
        self.commands.append((command, cwd))
        if command[:3] == ("git", "rev-parse", "HEAD"):
            return CommandResult(command, 0, self.old_commit + "\n", "")
        if command[:2] == ("git", "clone"):
            make_root(Path(command[-1]))
        if command[:2] == ("uv", "venv"):
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


def test_prepare_staging_removes_only_stale_staging(tmp_path):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    stale = staging_path(target)
    stale.mkdir()
    (stale / "partial.txt").write_text("partial", encoding="utf-8")

    prepared = prepare_staging_target(target)

    assert prepared == stale
    assert prepared.is_dir()
    assert list(prepared.iterdir()) == []
    assert target.is_dir()


def flattened_args(plan):
    return [arg for command in plan.commands for arg in command.args]


def test_nvidia_plan_is_pinned(tmp_path):
    plan = build_install_plan(tmp_path / "ComfyUI", DeviceMode.NVIDIA)
    args = flattened_args(plan)

    assert "v0.28.0" in args
    assert "3.12" in args
    assert "https://download.pytorch.org/whl/cu130" in args
    assert "torch.cuda.is_available()" in plan.commands[-1].args[-1]


def test_mps_plan_uses_default_torch_wheels_and_asserts_mps(tmp_path):
    plan = build_install_plan(tmp_path / "ComfyUI", DeviceMode.MPS)
    torch_command = plan.commands[3].args

    assert "--index-url" not in torch_command
    assert "torch.backends.mps.is_available()" in plan.commands[-1].args[-1]


def test_cpu_plan_uses_cpu_torch_index(tmp_path):
    plan = build_install_plan(tmp_path / "ComfyUI", DeviceMode.CPU)
    args = flattened_args(plan)

    assert "https://download.pytorch.org/whl/cpu" in args
    assert plan.commands[-1].args[-1] == "import torch"


def test_install_plan_has_exact_staged_sequence_and_no_content_downloads(tmp_path):
    target = tmp_path / "ComfyUI"
    plan = build_install_plan(target, DeviceMode.CPU)

    assert [command.args[:2] for command in plan.commands] == [
        ("git", "clone"),
        ("uv", "python"),
        ("uv", "venv"),
        ("uv", "pip"),
        ("uv", "pip"),
        (str(plan.python), "-c"),
    ]
    assert plan.commands[2].args == (
        "uv",
        "venv",
        "--python",
        "3.12",
        str(plan.staging / ".venv"),
    )
    joined = " ".join(flattened_args(plan)).lower()
    assert "custom_nodes" not in joined
    assert "models/" not in joined


def test_install_promotes_staging_only_after_success(tmp_path):
    target = tmp_path / "ComfyUI"
    runner = FakeRunner()

    result = install_comfyui(target, DeviceMode.CPU, runner, host=LINUX)

    assert result.root == target.resolve()
    assert result.valid is True
    assert target.is_dir()
    assert not staging_path(target).exists()
    assert len(runner.commands) == 6


def test_smoke_failure_cleans_staging_and_does_not_publish_target(tmp_path):
    target = tmp_path / "ComfyUI"
    runner = FakeRunner(fail_when=lambda args: len(args) > 1 and args[1] == "-c")

    with pytest.raises(ComfyInstallError, match="smoke"):
        install_comfyui(target, DeviceMode.NVIDIA, runner, host=LINUX)

    assert not target.exists()
    assert not staging_path(target).exists()


def test_update_reinstalls_pinned_version_without_cloning(tmp_path):
    root = make_root(tmp_path / "ComfyUI")
    runner = FakeRunner(old_commit="old123")

    result = update_comfyui(root, DeviceMode.CPU, runner, host=LINUX)

    commands = [command for command, _cwd in runner.commands]
    assert result == "v0.28.0"
    assert commands[0] == ("git", "rev-parse", "HEAD")
    assert commands[1] == (
        "git",
        "fetch",
        "--depth",
        "1",
        "origin",
        "tag",
        "v0.28.0",
    )
    assert commands[2] == ("git", "checkout", "--detach", "v0.28.0")
    assert commands[4] == (
        "uv",
        "venv",
        "--clear",
        "--python",
        "3.12",
        str(root / ".venv"),
    )
    assert not any(command[:2] == ("git", "clone") for command in commands)
    assert commands[-1][1] == "-c"


def test_update_restores_old_commit_when_smoke_fails(tmp_path):
    root = make_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: len(args) > 1 and args[1] == "-c",
        old_commit="old123",
    )

    with pytest.raises(ComfyInstallError, match="restored old123"):
        update_comfyui(root, DeviceMode.MPS, runner, host=LINUX)

    commands = [command for command, _cwd in runner.commands]
    assert commands[-1] == ("git", "checkout", "--detach", "old123")


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
):
    root = make_root(tmp_path / "ComfyUI")
    runner = FakeRunner(
        fail_when=lambda args: args[: len(failed_prefix)] == failed_prefix,
        old_commit="old123",
    )

    with pytest.raises(ComfyInstallError, match="restored old123"):
        update_comfyui(root, DeviceMode.CPU, runner, host=LINUX)

    commands = [command for command, _cwd in runner.commands]
    assert commands[-1] == ("git", "checkout", "--detach", "old123")


def test_failed_promotion_restores_preexisting_empty_target(tmp_path, monkeypatch):
    target = tmp_path / "ComfyUI"
    target.mkdir()
    runner = FakeRunner()
    original_replace = Path.replace

    def fail_staging_promotion(path, destination):
        if path == staging_path(target):
            raise OSError("promotion failed")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_staging_promotion)

    with pytest.raises(OSError, match="promotion failed"):
        install_comfyui(target, DeviceMode.CPU, runner, host=LINUX)

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert not staging_path(target).exists()
