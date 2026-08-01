from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
import zipfile

import pytest

from app.api.civitai_easy import GenerateLikeRequest
from app.schemas.civitai_recipe_variants import CivitaiRecipeVariantGenerateRequest
from app.schemas.civitai_recipe_variation_sets import CivitaiRecipeVariationSetCreateRequest
from app.schemas.gallery import RerunRequest
from app.schemas.generate import GenerateWanKeyframesVideoRequest
from app.schemas.lora_train import LoraSmokeTestRequest
from app.schemas.style_preset_workflows import TestStylePresetWorkflowRequest
from app.services import nvidia_worker


MIGRATION_COMMIT = "a" * 40


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_migration_harness(
    tmp_path: Path, body: str
) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Migrate-Worker.ps1"
    harness = tmp_path / "migration-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". {_ps_quote(script)}\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def _migration_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    source = tmp_path / "legacy-worker"
    target = tmp_path / "managed-worker"
    program_data = tmp_path / "ProgramData" / "AI-Drawing-Worker"
    token = "Bearer-fixture-migration-secret"
    files = {
        ".ai-drawing-worker-owned": "AI-Drawing NVIDIA Worker\n",
        "app/worker.py": "print('legacy worker')\n",
        "config/worker.json": json.dumps(
            {"token": token, "cache_gb": 100, "minimum_free_gb": 1}
        ),
        "config/expected-remote-url.txt": "https://example.invalid/repo\n",
        "runtime/python/python.exe": "fake-python",
        "runtime/ComfyUI/main.py": "print('fake comfy')\n",
        "runtime/ComfyUI/models/model.bin": "model-bytes",
        "runtime/ComfyUI/input/request.png": "input-bytes",
        "runtime/ComfyUI/output/result.png": "output-bytes",
        "runtime/logs/comfyui.stdout.log": "old-log\n",
        "shared/cache/cache.bin": "cache-bytes",
        "shared/partial/download.part": "partial-bytes",
        "updater/cli.py": "pass\n",
        "updater-runtime/Scripts/python.exe": "fake-updater-python",
        "Start-Worker.cmd": "@echo off\n",
        "Start-Worker.ps1": "$ErrorActionPreference = 'Stop'\n",
        "Uninstall-Worker.cmd": "@echo off\n",
        "UpdaterBootstrap.ps1": "$ErrorActionPreference = 'Stop'\n",
        "WorkerSecurity.ps1": "$ErrorActionPreference = 'Stop'\n",
        "worker-manifest.json": "{}\n",
        "requirements.txt": "fastapi\n",
    }
    for relative, contents in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    program_data.mkdir(parents=True)
    (program_data / "updater.env").write_text(
        "\n".join(
            (
                f"AI_DRAWING_PROJECT_ROOT={tmp_path / 'source-repository'}",
                f"AI_DRAWING_WORKER_ROOT={source}",
                "AI_DRAWING_WORKER_REMOTE=origin",
                "AI_DRAWING_WORKER_BRANCH=main",
                "",
            )
        ),
        encoding="utf-8",
    )
    return source, target, program_data / "updater.env", token


def _tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.parametrize(
    "model, payload",
    [
        (GenerateLikeRequest, {"locator": 1}),
        (RerunRequest, {}),
        (TestStylePresetWorkflowRequest, {}),
        (LoraSmokeTestRequest, {}),
        (GenerateWanKeyframesVideoRequest, {"images": ["a.png", "b.png"], "prompt": "x"}),
    ],
)
def test_product_generation_contracts_default_local_and_accept_worker(model, payload) -> None:
    assert model.model_validate(payload).execution_target == "local"
    assert model.model_validate({**payload, "execution_target": "worker"}).execution_target == "worker"
    with pytest.raises(Exception):
        model.model_validate({**payload, "execution_target": "auto"})


def test_strict_civitai_generation_contracts_expose_execution_target() -> None:
    assert "execution_target" in CivitaiRecipeVariantGenerateRequest.model_fields
    assert "execution_target" in CivitaiRecipeVariationSetCreateRequest.model_fields


def _resource_settings(root: Path):
    for name in ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras", "controlnet", "upscale_models", "clip_vision", "audio", "models"):
        (root / name).mkdir(exist_ok=True)
    return SimpleNamespace(
        comfyui_checkpoints_dir=str(root / "checkpoints"),
        comfyui_diffusion_models_dir=str(root / "diffusion_models"),
        comfyui_text_encoders_dir=str(root / "text_encoders"),
        comfyui_vae_dir=str(root / "vae"),
        comfyui_loras_dir=str(root / "loras"),
        comfyui_controlnet_dir=str(root / "controlnet"),
        comfyui_upscale_models_dir=str(root / "upscale_models"),
        comfyui_clip_vision_dir=str(root / "clip_vision"),
        comfyui_audio_models_dir=str(root / "audio"),
        comfyui_models_dir=str(root / "models"),
    )


def test_resource_manifest_covers_dualclip_clipvision_and_gguf(tmp_path, monkeypatch) -> None:
    settings = _resource_settings(tmp_path)
    monkeypatch.setattr(nvidia_worker, "get_settings", lambda: settings)
    files = {
        "text_encoders": ["clip_l.safetensors", "t5xxl.safetensors"],
        "clip_vision": ["clip_vision_h.safetensors"],
        "diffusion_models": ["wan.gguf", "qwen.gguf"],
    }
    for kind, names in files.items():
        for name in names:
            (tmp_path / kind / name).write_bytes(name.encode())
    workflow = {
        "1": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": files["text_encoders"][0], "clip_name2": files["text_encoders"][1]}},
        "2": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": files["clip_vision"][0]}},
        "3": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": files["diffusion_models"][0]}},
        "4": {"class_type": "GGUFLoaderKJ", "inputs": {"model_name": files["diffusion_models"][1], "extra_model_name": "none"}},
    }
    assert {(item.kind, item.name) for item in nvidia_worker.workflow_resources(workflow)} == {
        (kind, name) for kind, names in files.items() for name in names
    }


def test_worker_manifest_is_pinned_and_distribution_matches_source() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    manifest = json.loads((source / "worker-manifest.json").read_text())
    assert manifest["cache_gb"] == 100
    assert manifest["minimum_free_gb"] == 20
    assert manifest["custom_nodes"]
    assert all(item.get("repository") and item.get("revision") for item in manifest["custom_nodes"])
    dist = repo / "dist" / "AI-Drawing-NVIDIA-Worker"
    for name in (
        "worker.py",
        "worker-manifest.json",
        "Install-Worker.ps1",
        "Migrate-Worker.ps1",
        "Start-Worker.ps1",
        "UpdaterBootstrap.ps1",
        "WorkerSecurity.ps1",
        "requirements.txt",
        "README.md",
        "updater/cli.py",
        "updater/config.py",
        "updater/git_source.py",
        "updater/runtime.py",
        "updater/request_lock.py",
        "updater/state.py",
        "updater/windows_runtime.py",
    ):
        assert (dist / name).read_bytes() == (source / name).read_bytes()


def test_worker_distribution_archive_matches_updater_source_bytes() -> None:
    """Shipping a stale or incomplete updater inside the ZIP must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    archive = repo / "dist" / "AI-Drawing-NVIDIA-Worker.zip"
    with zipfile.ZipFile(archive) as package:
        names = {
            "Migrate-Worker.ps1",
            "UpdaterBootstrap.ps1",
            "WorkerSecurity.ps1",
            "updater/cli.py",
            "updater/config.py",
            "updater/git_source.py",
            "updater/runtime.py",
            "updater/request_lock.py",
            "updater/state.py",
            "updater/windows_runtime.py",
        }
        for name in names:
            packaged = package.read(name)
            assert packaged == (source / name).read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_migration_inventory_uses_canonical_paths_and_hashes_without_secret_output(
    tmp_path: Path,
) -> None:
    """Returning raw config/token values or skipping per-file digests must fail."""
    root = tmp_path / "worker"
    config = root / "config" / "worker.json"
    payload = root / "runtime" / "payload.bin"
    secret = "Bearer-inventory-must-not-leak"
    config.parent.mkdir(parents=True)
    payload.parent.mkdir(parents=True)
    config.write_text(json.dumps({"token": secret, "cache_gb": 100}), encoding="utf-8")
    payload.write_bytes(b"payload")

    result = _run_migration_harness(
        tmp_path,
        f"Get-MigrationInventory -Root {_ps_quote(root)} "
        f"-ConfigPath {_ps_quote(config)} | ConvertTo-Json -Depth 8 -Compress",
    )

    assert result.returncode == 0, result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr
    inventory = json.loads(result.stdout)
    expected_files = [config, payload]
    assert inventory["canonical_path"].casefold() == str(root.resolve()).casefold()
    assert inventory["file_count"] == 2
    assert inventory["total_bytes"] == sum(path.stat().st_size for path in expected_files)
    assert inventory["config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    assert inventory["token_sha256"] == hashlib.sha256(secret.encode()).hexdigest()
    assert inventory["file_digests"] == {
        "config/worker.json": hashlib.sha256(config.read_bytes()).hexdigest(),
        "runtime/payload.bin": hashlib.sha256(payload.read_bytes()).hexdigest(),
    }


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_migration_inventory_fails_closed_on_reparse_without_following_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "worker"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("must-not-be-read", encoding="utf-8")
    junction = root / "escape"
    created = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"New-Item -ItemType Junction -Path {_ps_quote(junction)} "
            f"-Target {_ps_quote(outside)} | Out-Null",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")

    result = _run_migration_harness(
        tmp_path,
        f"Get-MigrationInventory -Root {_ps_quote(root)} "
        f"-ConfigPath {_ps_quote(root / 'missing.json')} | Out-Null",
    )

    assert result.returncode != 0
    assert "MIGRATION_REPARSE_POINT" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "must-not-be-read"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_migration_capacity_requires_temporary_copy_plus_reserve(tmp_path: Path) -> None:
    too_small = _run_migration_harness(
        tmp_path,
        "Assert-MigrationCapacity -SourceBytes 100 -AvailableBytes 149 -ReserveBytes 50",
    )
    exact = _run_migration_harness(
        tmp_path,
        "Assert-MigrationCapacity -SourceBytes 100 -AvailableBytes 150 -ReserveBytes 50; "
        "[Console]::Out.Write('ok')",
    )

    assert too_small.returncode != 0
    assert "MIGRATION_FREE_SPACE_INSUFFICIENT" in too_small.stderr
    assert exact.returncode == 0, exact.stderr
    assert exact.stdout == "ok"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_migration_env_rejects_unknown_key_without_echoing_value(tmp_path: Path) -> None:
    env_path = tmp_path / "updater.env"
    secret = "Bearer-env-must-not-leak"
    env_path.write_text(f"UNKNOWN={secret}\n", encoding="utf-8")

    result = _run_migration_harness(
        tmp_path,
        f"Read-FixedMigrationEnvironment -Path {_ps_quote(env_path)} | Out-Null",
    )

    assert result.returncode != 0
    assert "MIGRATION_CONFIG_INVALID" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr


def _migration_adapter_script(
    source: Path,
    target: Path,
    *,
    fail_mode: str = "",
) -> str:
    return f"""
$Events = New-Object 'System.Collections.Generic.List[string]'
$SourceRoot = {_ps_quote(source)}
$TargetRoot = {_ps_quote(target)}
$FailMode = {_ps_quote(fail_mode)}
$Adapter = @{{
  GetFreeBytes = {{ param($Root) [int64]1TB }}
  ProtectTarget = {{ param($Root) $Events.Add('protect-target') }}
  CaptureTaskActions = {{
    $Events.Add('capture-tasks')
    return @(@{{ name='AI-Drawing NVIDIA Worker'; execute='legacy'; arguments=''; working_directory='' }})
  }}
  SwitchTaskActions = {{ param($Root) $Events.Add('switch-tasks:' + [IO.Path]::GetFileName($Root)) }}
  RestoreTaskActions = {{ param($Actions) $Events.Add('restore-tasks') }}
  StopWorker = {{ param($Root) $Events.Add('stop:' + [IO.Path]::GetFileName($Root)) }}
  StartWorker = {{
    param($Root)
    $Configured = (Read-FixedMigrationEnvironment -Path $EnvironmentPath).AI_DRAWING_WORKER_ROOT
    $Events.Add('start:' + [IO.Path]::GetFileName($Root) + ':env=' + [IO.Path]::GetFileName($Configured))
  }}
  ValidateWorker = {{
    param($Root, $Mode, $ExpectedCommit, $ExpectedTokenHash)
    if ($Mode -eq 'staged') {{
      $Configured = (Read-FixedMigrationEnvironment -Path $EnvironmentPath).AI_DRAWING_WORKER_ROOT
      if ($Configured -ne $SourceRoot) {{ throw 'staged validation observed an early env switch' }}
      if (-not (Test-Path -LiteralPath (Join-Path $TargetRoot ('releases\\' + $ExpectedCommit + '\\worker\\windows\\worker.py')))) {{
        throw 'staged release was not copied first'
      }}
    }}
    $Events.Add('health:' + $Mode)
    $Healthy = $Mode -ne $FailMode
    return @{{
      cuda_available=$Healthy
      gpu_name=$(if ($Healthy) {{ 'Fake CUDA GPU' }} else {{ '' }})
      status_ok=$Healthy
      resource_plan_ok=$Healthy
      preflight_ok=$Healthy
      object_info_ok=$Healthy
      source_commit=$ExpectedCommit
      token_sha256=$ExpectedTokenHash
    }}
  }}
}}
"""


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_transaction_copies_and_validates_d_before_switch_then_backs_up_c(
    tmp_path: Path,
) -> None:
    source, target, environment_path, token = _migration_fixture(tmp_path)
    before = _tree_snapshot(source)
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(source, target)
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{ result=$Result; events=$Events }} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    events = record["events"]
    assert events.index("health:staged") < events.index("switch-tasks:managed-worker")
    assert events.index("health:staged") < events.index("stop:legacy-worker")
    assert events[-2:] == ["start:managed-worker:env=managed-worker", "health:production-after-backup"]
    assert record["result"]["status"] == "ready"
    backup = Path(record["result"]["backup_root"])
    assert not source.exists()
    assert backup.is_dir()
    assert _tree_snapshot(backup) == before
    release = target / "releases" / MIGRATION_COMMIT
    assert (release / "worker" / "windows" / "worker.py").is_file()
    assert (release / "ComfyUI" / "main.py").is_file()
    assert (target / "shared" / "models" / "model.bin").is_file()
    assert (target / "current").resolve() == release.resolve()
    assert (release / "ComfyUI" / "models").resolve() == (
        target / "shared" / "models"
    ).resolve()
    env_text = environment_path.read_text(encoding="utf-8")
    assert f"AI_DRAWING_WORKER_ROOT={target}" in env_text
    assert token not in result.stdout
    assert token not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_transaction_failure_restores_task_env_and_starts_unchanged_c(
    tmp_path: Path,
) -> None:
    source, target, environment_path, token = _migration_fixture(tmp_path)
    before = _tree_snapshot(source)
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(
            source, target, fail_mode="production-before-backup"
        )
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{ result=$Result; events=$Events }} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert record["result"]["error_code"] == "MIGRATION_HEALTH_FAILED"
    events = record["events"]
    assert events.index("restore-tasks") < events.index(
        "start:legacy-worker:env=legacy-worker"
    )
    assert source.is_dir()
    assert _tree_snapshot(source) == before
    assert (target / "shared" / "models" / "model.bin").is_file()
    env_text = environment_path.read_text(encoding="utf-8")
    assert f"AI_DRAWING_WORKER_ROOT={source}" in env_text
    assert token not in result.stdout
    assert token not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_post_backup_failure_restores_c_before_starting_legacy_worker(
    tmp_path: Path,
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    before = _tree_snapshot(source)
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(
            source, target, fail_mode="production-after-backup"
        )
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{ result=$Result; events=$Events }} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert source.is_dir()
    assert _tree_snapshot(source) == before
    assert record["events"][-1] == "start:legacy-worker:env=legacy-worker"


def test_updater_bootstrap_uses_fixed_programdata_config_and_updater_owned_python() -> None:
    """Allowing Invoke-Expression, CLI selectors, or another Python must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "UpdaterBootstrap.ps1").read_text(
        encoding="utf-8"
    )

    assert "Invoke-Expression" not in text
    assert '"AI_DRAWING_PROJECT_ROOT"' in text
    assert '"AI_DRAWING_WORKER_ROOT"' in text
    assert '"AI_DRAWING_WORKER_REMOTE"' in text
    assert '"AI_DRAWING_WORKER_BRANCH"' in text
    assert 'Join-Path $WorkerRoot "updater-runtime\\Scripts\\python.exe"' in text
    assert '& $UpdaterPython -m updater.cli' in text
    assert "$args" not in text
    assert "Write-Host" not in text
    assert "GetRelativePath" not in text


@pytest.mark.skipif(os.name != "nt", reason="PowerShell bootstrap contract requires Windows")
def test_updater_bootstrap_rejects_unknown_env_without_echoing_value(tmp_path: Path) -> None:
    """Evaluating or printing an unknown env value must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    program_data = tmp_path / "ProgramData"
    config_root = program_data / "AI-Drawing-Worker"
    config_root.mkdir(parents=True)
    secret = "Bearer-bootstrap-must-not-leak"
    (config_root / "updater.env").write_text(
        f"UNKNOWN={secret}\n", encoding="utf-8"
    )
    environment = {**os.environ, "ProgramData": str(program_data)}

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo / "worker" / "windows" / "UpdaterBootstrap.ps1"),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=15,
    )

    assert result.returncode != 0
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_installer_registers_restricted_fixed_on_demand_updater_task() -> None:
    """Passing config/token in a task action or installing a trigger must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "Install-Worker.ps1").read_text(
        encoding="utf-8"
    )

    assert '"AI-Drawing Worker Updater"' in text
    assert "New-ScheduledTaskAction" in text
    assert "New-ScheduledTaskPrincipal" in text
    assert "-RunLevel Highest" in text
    assert "-UserId \"SYSTEM\"" in text
    assert "Register-ScheduledTask" in text
    assert "-Trigger" not in text
    assert "-MultipleInstances IgnoreNew" in text
    assert '. (Join-Path $Source "WorkerSecurity.ps1")' in text
    action_block = text[text.index("$UpdaterTaskAction") : text.index("$UpdaterTaskPrincipal")]
    assert "UpdaterBootstrap.ps1" in action_block
    assert "Token" not in action_block
    assert "updater.env" not in action_block
    assert "AI_DRAWING_" not in action_block
    assert "& $UpdaterPython -m updater.cli" not in text


def test_worker_security_helper_uses_well_known_sids_and_verifies_every_ace() -> None:
    """Localized principals or write-only ACL changes must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "WorkerSecurity.ps1").read_text(
        encoding="utf-8"
    )

    assert 'SecurityIdentifier("S-1-5-18")' in text
    assert 'SecurityIdentifier("S-1-5-32-544")' in text
    assert "SetOwner($script:SystemSid)" in text
    assert "SetAccessRuleProtection($true, $false)" in text
    assert "Set-Acl" in text
    assert "GetAccessRules($true, $true" in text
    assert "AccessControlType" in text
    assert "FileSystemRights" in text
    assert "AreAccessRulesProtected" in text


def test_installer_uses_atomic_acl_directory_creation_for_fixed_roots() -> None:
    """Creating a fixed root before applying its ACL leaves a privilege-escalation race."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "Install-Worker.ps1").read_text(
        encoding="utf-8"
    )

    assert "New-SecureUpdaterDirectory -Path $Root" in text
    assert "New-SecureUpdaterDirectory -Path $ProgramDataRoot" in text
    assert "New-Item -ItemType Directory -Path $Root" not in text
    assert "New-Item -ItemType Directory -Path $ProgramDataRoot" not in text


def _run_security_helper(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    harness = tmp_path / "acl-harness.ps1"
    helper = repo / "worker" / "windows" / "WorkerSecurity.ps1"
    harness.write_text(
        f'$ErrorActionPreference = "Stop"\n. "{helper}"\n{body}\n', encoding="utf-8"
    )
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration requires Windows")
def test_secure_directory_is_created_with_protected_acl_atomically_as_current_user(
    tmp_path: Path,
) -> None:
    root = tmp_path / "atomic-secure-root"
    body = f'''$CurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
New-SecureUpdaterDirectory -Path "{root}" -OwnerSid $CurrentSid -AllowedSids @($CurrentSid)
$Acl = Get-Acl -LiteralPath "{root}"
$Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
[pscustomobject]@{{
  owner = $Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  expected = $CurrentSid.Value
  protected = $Acl.AreAccessRulesProtected
  aces = @($Rules | ForEach-Object {{ [pscustomobject]@{{ sid=$_.IdentityReference.Value; type=[string]$_.AccessControlType; rights=[string]$_.FileSystemRights }} }})
}} | ConvertTo-Json -Depth 5 -Compress'''
    result = _run_security_helper(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["owner"] == record["expected"]
    assert record["protected"] is True
    assert record["aces"] == [
        {
            "sid": record["expected"],
            "type": "Allow",
            "rights": "FullControl",
        }
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration requires Windows")
def test_preexisting_worker_root_with_marker_but_insecure_acl_is_rejected(tmp_path: Path) -> None:
    """Trusting the ownership marker without validating the tree ACL must make this test fail."""
    root = tmp_path / "worker"
    root.mkdir()
    (root / ".ai-drawing-worker-owned").write_text(
        "AI-Drawing NVIDIA Worker\n", encoding="utf-8"
    )
    result = _run_security_helper(
        tmp_path,
        f'Assert-ExistingWorkerRoot -Path "{root}"',
    )

    assert result.returncode != 0
    assert "Task 7" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse integration requires Windows")
def test_security_tree_walk_rejects_junction_without_following_it(tmp_path: Path) -> None:
    root = tmp_path / "worker"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "must-not-be-walked.txt").write_text("sentinel", encoding="utf-8")
    junction = root / "escape"
    created = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f'New-Item -ItemType Junction -Path "{junction}" -Target "{outside}" | Out-Null',
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")

    result = _run_security_helper(
        tmp_path,
        f'Get-UpdaterTreeNoFollow -Path "{root}" | Out-Null',
    )

    assert result.returncode != 0
    assert "Task 7" in result.stderr
    assert (outside / "must-not-be-walked.txt").read_text(encoding="utf-8") == "sentinel"


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration requires Windows")
def test_secure_updater_tree_removes_everyone_and_has_only_system_admin_aces(tmp_path: Path) -> None:
    """Leaving a low-privilege ACE or the wrong owner after hardening must make this test fail."""
    principal = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    if principal.casefold() != "true":
        pytest.skip("setting the SYSTEM owner requires an elevated Windows test process")

    root = tmp_path / "secure"
    body = f'''$Root = "{root}"
New-SecureUpdaterDirectory -Path $Root
New-Item -ItemType Directory -Path (Join-Path $Root "updater") | Out-Null
[IO.File]::WriteAllText((Join-Path $Root "updater\\cli.py"), "pass`n")
$Acl = Get-Acl -LiteralPath $Root
$Everyone = New-Object Security.Principal.SecurityIdentifier("S-1-1-0")
$Rule = New-Object Security.AccessControl.FileSystemAccessRule($Everyone, "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow")
$Acl.AddAccessRule($Rule)
Set-Acl -LiteralPath $Root -AclObject $Acl
Protect-UpdaterTree -Path $Root
Assert-SecureUpdaterTree -Path $Root
$Result = foreach ($Item in @($Root, (Join-Path $Root "updater"), (Join-Path $Root "updater\\cli.py"))) {{
  $Verified = Get-Acl -LiteralPath $Item
  $Rules = $Verified.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])
  [pscustomobject]@{{
    path = $Item
    owner = $Verified.GetOwner([Security.Principal.SecurityIdentifier]).Value
    protected = $Verified.AreAccessRulesProtected
    aces = @($Rules | ForEach-Object {{ [pscustomobject]@{{ sid=$_.IdentityReference.Value; type=[string]$_.AccessControlType; rights=[string]$_.FileSystemRights }} }})
  }}
}}
$Result | ConvertTo-Json -Depth 5 -Compress'''
    result = _run_security_helper(tmp_path, body)

    assert result.returncode == 0, result.stderr
    records = json.loads(result.stdout)
    allowed = {"S-1-5-18", "S-1-5-32-544"}
    for record in records:
        assert record["owner"] == "S-1-5-18"
        assert record["protected"] is True
        assert record["aces"]
        assert {ace["sid"] for ace in record["aces"]} <= allowed
        assert all(ace["type"] == "Allow" and "FullControl" in ace["rights"] for ace in record["aces"])


def test_installer_preserves_token_and_shared_data_contract() -> None:
    """Regenerating an existing token or removing shared storage must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "Install-Worker.ps1").read_text(
        encoding="utf-8"
    )

    assert "$ExistingConfig.token" in text
    assert "if (-not $Token)" in text
    for directory in ("shared\\models", "shared\\cache", "shared\\partial", "shared\\input", "shared\\output"):
        assert directory in text
    assert "Remove-Item $Shared" not in text
    assert "UTF8Encoding -ArgumentList $false" in text
    assert "WriteAllText" in text


@pytest.mark.skipif(os.name != "nt", reason="Windows Worker launcher requires Windows process semantics")
def test_installed_worker_launcher_redirects_comfyui_output_to_rotated_logs(tmp_path) -> None:
    """Catch a regression to an attached ComfyUI console whose output can block Python."""
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    root = tmp_path / "AI-Drawing-Worker"
    (root / "config").mkdir(parents=True)
    comfy_root = root / "runtime" / "ComfyUI"
    comfy_root.mkdir(parents=True)
    logs = root / "runtime" / "logs"
    logs.mkdir()

    for name in ("Start-Worker.ps1", "Start-Worker.cmd"):
        shutil.copy2(source / name, root / name)
    start_script = root / "Start-Worker.ps1"
    start_script.write_text(
        start_script.read_text(encoding="utf-8").replace(
            '$Root = "C:\\AI-Drawing-Worker"',
            f'$Root = "{root}"',
        ),
        encoding="utf-8",
    )
    (root / "config" / "python-path.txt").write_text(sys.executable, encoding="utf-8")
    (logs / "comfyui.stdout.log").write_text("old stdout\n", encoding="utf-8")
    (logs / "comfyui.stderr.log").write_text("old stderr\n", encoding="utf-8")
    (comfy_root / "main.py").write_text(
        """import os
import sys
import threading
import time
from pathlib import Path

Path(__file__).with_name(\"fixture.pid\").write_text(str(os.getpid()))
def write_output():
    while True:
        print(\"comfy stdout fixture\", flush=True)
        print(\"comfy stderr fixture\", file=sys.stderr, flush=True)
        time.sleep(0.1)
threading.Thread(target=write_output, daemon=True).start()
while True:
    time.sleep(1)
""",
        encoding="utf-8",
    )

    launcher = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(start_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    fixture_pid_path = comfy_root / "fixture.pid"
    stdout_log = logs / "comfyui.stdout.log"
    stderr_log = logs / "comfyui.stderr.log"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not fixture_pid_path.exists():
            time.sleep(0.1)
        assert fixture_pid_path.exists(), "ComfyUI fixture was not launched"

        while time.monotonic() < deadline:
            if (
                (logs / "comfyui.stdout.previous.log").exists()
                and (logs / "comfyui.stderr.previous.log").exists()
                and "comfy stdout fixture" in stdout_log.read_bytes().decode("utf-8", errors="replace")
                and "comfy stderr fixture" in stderr_log.read_bytes().decode("utf-8", errors="replace")
            ):
                break
            time.sleep(0.1)

        assert (logs / "comfyui.stdout.previous.log").read_text(encoding="utf-8") == "old stdout\n"
        assert (logs / "comfyui.stderr.previous.log").read_text(encoding="utf-8") == "old stderr\n"
        assert "comfy stdout fixture" in stdout_log.read_bytes().decode("utf-8", errors="replace")
        assert "comfy stderr fixture" in stderr_log.read_bytes().decode("utf-8", errors="replace")
    finally:
        launcher.terminate()
        try:
            launcher.wait(timeout=5)
        except subprocess.TimeoutExpired:
            launcher.kill()
            launcher.wait(timeout=5)
        if fixture_pid_path.exists():
            subprocess.run(
                ["taskkill.exe", "/PID", fixture_pid_path.read_text(encoding="utf-8").strip(), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
