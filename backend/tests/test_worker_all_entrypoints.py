from __future__ import annotations

import base64
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


def _run_powershell_51_command(command: str) -> subprocess.CompletedProcess[str]:
    """Run a non-mutating compatibility probe in Windows PowerShell Desktop 5.1."""
    parser_command = (
        "$ErrorActionPreference = 'Stop'\n"
        "[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)\n"
        f"{command}\n"
    )
    try:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                parser_command,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except subprocess.CalledProcessError as error:
        pytest.fail(
            "Windows PowerShell 5.1 compatibility probe failed\n"
            f"stdout:\n{error.stdout}\n"
            f"stderr:\n{error.stderr}"
        )


def _powershell_51_ast_prelude(script: Path) -> str:
    return f"""
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile(
    {_ps_quote(script)}, [ref]$Tokens, [ref]$ParseErrors
)
if ($ParseErrors.Count -ne 0) {{
    $Messages = @($ParseErrors | ForEach-Object {{
        "{script}:$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber): $($_.Message)"
    }})
    throw ($Messages -join [Environment]::NewLine)
}}
"""


def _decode_powershell_51_utf8(result: subprocess.CompletedProcess[str]) -> str:
    return base64.b64decode(result.stdout.strip()).decode("utf-8")


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_desktop_parses_every_shipped_worker_script(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    copied = tmp_path / "PowerShell 5.1 paths with spaces" / "新增資料夾"
    copied.mkdir(parents=True)
    scripts = sorted(source.glob("*.ps1"))
    shutil.copy2(source / "Restart-Worker.ps1", copied / "Restart Worker 複本.ps1")
    encoded_paths = base64.b64encode(
        json.dumps([str(path) for path in (*scripts, copied / "Restart Worker 複本.ps1")]).encode()
    ).decode()
    result = _run_powershell_51_command(
        f"""
$Version = $PSVersionTable.PSVersion
if ($PSVersionTable.PSEdition -ne "Desktop" -or $Version.Major -ne 5 -or $Version.Minor -ne 1) {{
    throw "Expected Windows PowerShell Desktop 5.1, got $($PSVersionTable.PSEdition) $Version"
}}
$Json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("{encoded_paths}"))
$Paths = [string[]]($Json | ConvertFrom-Json)
foreach ($Path in $Paths) {{
    $Tokens = $null
    $Errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($Path, [ref]$Tokens, [ref]$Errors)
    if ($Errors.Count -ne 0) {{
        $Messages = @($Errors | ForEach-Object {{
            "$Path`:$($_.Extent.StartLineNumber)`:$($_.Extent.StartColumnNumber): $($_.Message)"
        }})
        throw ($Messages -join [Environment]::NewLine)
    }}
}}
"5.1 Desktop; parsed $($Paths.Count) scripts"
"""
    )

    assert result.stdout.strip() == f"5.1 Desktop; parsed {len(scripts) + 1} scripts"


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_split_preserves_equals_spaces_and_non_ascii_path(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Restart-Worker.ps1"
    expected_root = tmp_path / "Worker 路徑 = 新增資料夾"
    environment_path = tmp_path / "updater env 新增資料夾" / "updater.env"
    environment_path.parent.mkdir()
    environment_path.write_text(
        f"AI_DRAWING_WORKER_ROOT={expected_root}\n", encoding="utf-8"
    )
    result = _run_powershell_51_command(
        _powershell_51_ast_prelude(script)
        + f"""
$Function = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $Node.Name -eq "Get-FixedWorkerRoot"
}}, $true) | Select-Object -First 1
if (-not $Function) {{ throw "Get-FixedWorkerRoot AST not found" }}
Invoke-Expression $Function.Extent.Text
$EnvironmentPath = {_ps_quote(environment_path)}
$Resolved = Get-FixedWorkerRoot
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Resolved))
"""
    )

    assert _decode_powershell_51_utf8(result) == str(expected_root.resolve())


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_constructs_quoted_scheduled_task_actions(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Install-Worker.ps1"
    root = tmp_path / "Worker Root 新增資料夾"
    program_data = tmp_path / "Program Data 新增資料夾"
    result = _run_powershell_51_command(
        _powershell_51_ast_prelude(script)
        + f"""
function New-ScheduledTaskAction {{
    param([string]$Execute, [string]$Argument)
    [pscustomobject]@{{ Execute = $Execute; Argument = $Argument }}
}}
$Root = {_ps_quote(root)}
$env:ProgramData = {_ps_quote(program_data)}
$Actions = @{{}}
foreach ($Name in @("UpdaterTaskAction", "RestartTaskAction")) {{
    $Assignment = $Ast.FindAll({{ param($Node)
        $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
            $Node.Left.Extent.Text -eq ('$' + $Name)
    }}, $true) | Select-Object -First 1
    if (-not $Assignment) {{ throw "$Name AST not found" }}
    Invoke-Expression $Assignment.Extent.Text
    $Actions[$Name] = Get-Variable -Name $Name -ValueOnly
}}
$Json = $Actions | ConvertTo-Json -Compress
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Json))
"""
    )
    actions = json.loads(_decode_powershell_51_utf8(result))

    expected_executable = str(
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    assert actions["UpdaterTaskAction"] == {
        "Execute": expected_executable,
        "Argument": (
            "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
            f'"{program_data}\\AI-Drawing-Worker\\UpdaterBootstrap.ps1"'
        ),
    }
    assert actions["RestartTaskAction"] == {
        "Execute": expected_executable,
        "Argument": (
            "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
            f'"{root}\\Restart-Worker.ps1"'
        ),
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_restart_start_process_quotes_script_path(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Restart-Worker.ps1"
    root = tmp_path / "Worker Root 新增資料夾"
    root.mkdir()
    marker = root / "restart-fixture-ran.txt"
    (root / "Start-Worker.ps1").write_text(
        "[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'restart-fixture-ran.txt'), 'ok')\n",
        encoding="ascii",
    )
    _run_powershell_51_command(
        _powershell_51_ast_prelude(script)
        + f"""
$ArgumentsAssignment = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $Node.Left.Extent.Text -eq '$StartWorkerArguments'
}}, $true) | Select-Object -First 1
$Command = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.CommandAst] -and
        $Node.GetCommandName() -eq "Start-Process"
}}, $true) | Select-Object -First 1
if (-not $ArgumentsAssignment -or -not $Command) {{ throw "restart Start-Process AST not found" }}
$Root = {_ps_quote(root)}
Invoke-Expression $ArgumentsAssignment.Extent.Text
Invoke-Expression $Command.Extent.Text | Out-Null
$Deadline = [DateTime]::UtcNow.AddSeconds(10)
while (-not (Test-Path -LiteralPath {_ps_quote(marker)} -PathType Leaf) -and
       [DateTime]::UtcNow -lt $Deadline) {{ Start-Sleep -Milliseconds 50 }}
if (-not (Test-Path -LiteralPath {_ps_quote(marker)} -PathType Leaf)) {{
    throw "Restart-Worker.ps1 Start-Process did not preserve the quoted script path"
}}
"""
    )

    assert marker.read_text(encoding="utf-8") == "ok"


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_start_worker_quotes_comfy_main_path(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Start-Worker.ps1"
    comfy_root = tmp_path / "Comfy UI 新增資料夾"
    comfy_root.mkdir()
    marker = comfy_root / "comfy-fixture-ran.txt"
    (comfy_root / "main.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    _run_powershell_51_command(
        _powershell_51_ast_prelude(script)
        + f"""
$ComfyArgsAssignment = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $Node.Left.Extent.Text -eq '$ComfyArgs'
}}, $true) | Select-Object -First 1
$ComfyArgumentListAssignment = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $Node.Left.Extent.Text -eq '$ComfyArgumentList'
}}, $true) | Select-Object -First 1
$ProcessAssignment = $Ast.FindAll({{ param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $Node.Left.Extent.Text -eq '$ComfyProcess'
}}, $true) | Select-Object -First 1
if (-not $ComfyArgsAssignment -or -not $ComfyArgumentListAssignment -or -not $ProcessAssignment) {{
    throw "Comfy Start-Process AST not found"
}}
$Python = {_ps_quote(sys.executable)}
$ComfyRoot = {_ps_quote(comfy_root)}
$ComfyStdoutLog = {_ps_quote(tmp_path / 'comfy stdout.log')}
$ComfyStderrLog = {_ps_quote(tmp_path / 'comfy stderr.log')}
Invoke-Expression $ComfyArgsAssignment.Extent.Text
Invoke-Expression $ComfyArgumentListAssignment.Extent.Text
Invoke-Expression $ProcessAssignment.Extent.Text
if (-not $ComfyProcess.WaitForExit(10000)) {{ $ComfyProcess.Kill(); throw "Comfy fixture timed out" }}
if (-not (Test-Path -LiteralPath {_ps_quote(marker)} -PathType Leaf)) {{
    throw ("Comfy fixture did not preserve the quoted main.py path: " +
        [IO.File]::ReadAllText($ComfyStderrLog))
}}
"""
    )

    assert marker.read_text(encoding="utf-8") == "ok"


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_powershell_51_listener_selection_uses_listen_state_and_unique_pids() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Restart-Worker.ps1"
    result = _run_powershell_51_command(
        _powershell_51_ast_prelude(script)
        + """
$Selection = $Ast.FindAll({ param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $Node.Left.Extent.Text -eq '$ListenerPids'
}, $true) | Select-Object -First 1
if (-not $Selection) { throw "listener selection AST not found" }
$Captured = $null
function Get-NetTCPConnection {
    [CmdletBinding()]
    param([int[]]$LocalPort, [string]$State)
    $script:Captured = [pscustomobject]@{ LocalPort = @($LocalPort); State = $State }
    [pscustomobject]@{ OwningProcess = 42 }
    [pscustomobject]@{ OwningProcess = 42 }
    [pscustomobject]@{ OwningProcess = 84 }
}
$Ports = @(8188, 8791)
Invoke-Expression $Selection.Extent.Text
$Record = [pscustomobject]@{ Captured = $Captured; ListenerPids = @($ListenerPids) }
$Json = $Record | ConvertTo-Json -Depth 4 -Compress
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Json))
"""
    )
    record = json.loads(_decode_powershell_51_utf8(result))

    assert record == {
        "Captured": {"LocalPort": [8188, 8791], "State": "Listen"},
        "ListenerPids": [42, 84],
    }


def _run_migration_harness(
    tmp_path: Path, body: str, *, environment: dict[str, str] | None = None
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
    process_environment = dict(os.environ)
    for key, value in (environment or {}).items():
        for existing in tuple(process_environment):
            if existing.casefold() == key.casefold():
                del process_environment[existing]
        process_environment[key] = value
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
        env=process_environment,
        timeout=30,
    )


def _run_updater_bootstrap_harness(
    tmp_path: Path, body: str
) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    harness = tmp_path / "updater bootstrap 測試 with spaces" / "bootstrap-harness.ps1"
    harness.parent.mkdir(parents=True)
    harness.write_text(
        f'. "{repo / "worker/windows/Deploy-UpdaterBootstrap.ps1"}" '
        '-ExpectedCommit "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'
        f"{body}",
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


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_updater_bootstrap_deployment_entrypoint_requires_expected_commit() -> None:
    """Removing the mandatory operator commit must make direct invocation fail."""
    script = Path(__file__).resolve().parents[2] / "worker" / "windows" / "Deploy-UpdaterBootstrap.ps1"

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode != 0
    assert "ExpectedCommit" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows elevated entrypoint contract requires Windows")
def test_updater_bootstrap_deployment_entrypoint_executes_main_but_dot_sourcing_does_not(
    tmp_path: Path,
) -> None:
    """Changing the invocation guard must either skip main or run it while importing."""
    script = Path(__file__).resolve().parents[2] / "worker" / "windows" / "Deploy-UpdaterBootstrap.ps1"
    commit = "a" * 40
    direct = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"""
function New-Object {{
    $Principal = [pscustomobject]@{{}}
    $Principal | Add-Member -MemberType ScriptMethod -Name IsInRole -Value {{
        param($Role) $false
    }}
    return $Principal
}}
try {{
    & {_ps_quote(script)} -ExpectedCommit '{commit}'
}} catch {{
    [Console]::Out.Write($_.Exception.Message)
    exit 1
}}
""",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    dot_sourced = _run_powershell_51_command(
        f"""
function New-Object {{ throw 'dot source must not create a principal' }}
. {_ps_quote(script)} -ExpectedCommit '{commit}'
'dot-sourced'
"""
    )

    assert direct.returncode != 0
    assert direct.stdout == "UPDATER_BOOTSTRAP_ADMIN_REQUIRED"
    assert direct.stderr == ""
    assert dot_sourced.stdout.strip() == "dot-sourced"
    assert dot_sourced.stderr == ""


@pytest.mark.skipif(os.name != "nt", reason="Windows elevated entrypoint contract requires Windows")
def test_updater_bootstrap_deployment_entrypoint_rejects_non_administrator(
    tmp_path: Path,
) -> None:
    """Skipping the administrator gate would allow the fake adapter to be reached."""
    secret = "fake-adapter-admin-secret"
    body = f"""
function New-Object {{
    $Principal = [pscustomobject]@{{}}
    $Principal | Add-Member -MemberType ScriptMethod -Name IsInRole -Value {{
        param($Role) $false
    }}
    return $Principal
}}
function Get-ProductionUpdaterBootstrapAdapter {{ throw '{secret}' }}
try {{
    Invoke-UpdaterBootstrapMain -ExpectedCommit ('a' * 40)
}} catch {{
    [Console]::Out.Write($_.Exception.Message)
}}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "UPDATER_BOOTSTRAP_ADMIN_REQUIRED"
    assert secret not in result.stdout
    assert secret not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows elevated entrypoint contract requires Windows")
def test_updater_bootstrap_deployment_entrypoint_hides_adapter_exception(
    tmp_path: Path,
) -> None:
    """Letting an adapter exception escape would disclose its protected diagnostic."""
    secret = "fake-adapter-exception-secret"
    body = f"""
function New-Object {{
    $Principal = [pscustomobject]@{{}}
    $Principal | Add-Member -MemberType ScriptMethod -Name IsInRole -Value {{
        param($Role) $true
    }}
    return $Principal
}}
function Get-ProductionUpdaterBootstrapAdapter {{ throw '{secret}' }}
try {{
    Invoke-UpdaterBootstrapMain -ExpectedCommit ('a' * 40)
}} catch {{
    [Console]::Out.Write($_.Exception.Message)
}}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "UPDATER_BOOTSTRAP_STAGE_FAILED"
    assert secret not in result.stdout
    assert secret not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows elevated entrypoint contract requires Windows")
def test_updater_bootstrap_deployment_entrypoint_outputs_only_safe_ready_result(
    tmp_path: Path,
) -> None:
    """Serializing an adapter or environment data would expose the injected secret."""
    secret = "fake-adapter-ready-secret"
    body = f"""
function New-Object {{
    $Principal = [pscustomobject]@{{}}
    $Principal | Add-Member -MemberType ScriptMethod -Name IsInRole -Value {{
        param($Role) $true
    }}
    return $Principal
}}
function Get-ProductionUpdaterBootstrapAdapter {{
    [pscustomobject]@{{ diagnostic = '{secret}' }}
}}
function Invoke-UpdaterBootstrapTransaction {{
    param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit, $Adapter)
    [pscustomobject]@{{ status = 'ready'; error_code = $null; backup = $null }}
}}
$Output = @(Invoke-UpdaterBootstrapMain -ExpectedCommit ('a' * 40))
$Output | ConvertTo-Json -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "UPDATER_BOOTSTRAP_READY",
        {"status": "ready", "error_code": None, "backup": None},
    ]
    assert secret not in result.stdout
    assert secret not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows elevated entrypoint contract requires Windows")
@pytest.mark.parametrize(
    ("status", "error_code", "expected"),
    [
        ("failed_before_switch", "UPDATER_BOOTSTRAP_TASK_BUSY", "UPDATER_BOOTSTRAP_TASK_BUSY"),
        ("rolled_back", "UPDATER_BOOTSTRAP_SMOKE_FAILED", "UPDATER_BOOTSTRAP_SMOKE_FAILED"),
        ("recovery_required", "fake-adapter-recovery-secret", "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"),
    ],
)
def test_updater_bootstrap_deployment_entrypoint_returns_fixed_terminal_errors(
    tmp_path: Path, status: str, error_code: str, expected: str
) -> None:
    """Passing through an adapter result error would leak a protected diagnostic."""
    body = f"""
function New-Object {{
    $Principal = [pscustomobject]@{{}}
    $Principal | Add-Member -MemberType ScriptMethod -Name IsInRole -Value {{
        param($Role) $true
    }}
    return $Principal
}}
function Get-ProductionUpdaterBootstrapAdapter {{
    [pscustomobject]@{{ diagnostic = 'fake-adapter-object-secret' }}
}}
function Invoke-UpdaterBootstrapTransaction {{
    param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit, $Adapter)
    [pscustomobject]@{{
        status = '{status}'
        error_code = '{error_code}'
        backup = 'backup-is-not-public-output'
    }}
}}
try {{
    Invoke-UpdaterBootstrapMain -ExpectedCommit ('a' * 40)
}} catch {{
    [Console]::Out.Write($_.Exception.Message)
}}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert result.stdout == expected
    assert "fake-adapter" not in result.stdout
    assert "fake-adapter" not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_updater_bootstrap_deployment_parses_on_windows_powershell_51() -> None:
    """A syntax incompatible with Windows PowerShell 5.1 must make this test fail."""
    repo = Path(__file__).resolve().parents[2]
    script = repo / "worker" / "windows" / "Deploy-UpdaterBootstrap.ps1"

    result = _run_powershell_51_command(
        f"""
$Version = $PSVersionTable.PSVersion
if ($PSVersionTable.PSEdition -ne "Desktop" -or $Version.Major -ne 5 -or $Version.Minor -ne 1) {{
    throw "Expected Windows PowerShell Desktop 5.1, got $($PSVersionTable.PSEdition) $Version"
}}
$Tokens = $null
$ParseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    {_ps_quote(script)}, [ref]$Tokens, [ref]$ParseErrors
)
if ($ParseErrors.Count -ne 0) {{
    throw ($ParseErrors | ForEach-Object {{ $_.Message }} | Out-String)
}}
"5.1 Desktop; parsed Deploy-UpdaterBootstrap.ps1"
"""
    )

    assert result.stdout.strip() == "5.1 Desktop; parsed Deploy-UpdaterBootstrap.ps1"


def _updater_bootstrap_adapter_script(fail_stage: str | None = None) -> str:
    fail_value = "" if fail_stage is None else fail_stage
    return f"""
$Events = [System.Collections.Generic.List[string]]::new()
$FailStage = '{fail_value}'
$Adapter = [pscustomobject]@{{
    ValidateContext = {{ param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
        [void]$Events.Add('validate-context')
    }}
    AcquireLock = {{ param($ProgramDataRoot)
        [void]$Events.Add('acquire-lock')
    }}
    StopUpdaterTask = {{
        [void]$Events.Add('stop-updater-task')
    }}
    Stage = {{ param($RepositoryRoot, $WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
        [void]$Events.Add('stage')
        'staging-token'
    }}
    ValidateStage = {{ param($Staging)
        [void]$Events.Add('validate-stage')
    }}
    Backup = {{ param($WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
        [void]$Events.Add('backup')
        'backup-token'
    }}
    Activate = {{ param($Staging, $WorkerRoot, $ProgramDataRoot)
        [void]$Events.Add('activate')
        if ($FailStage -eq 'activate') {{ throw 'adapter activate failure must remain private' }}
    }}
    Protect = {{ param($WorkerRoot, $ProgramDataRoot)
        [void]$Events.Add('protect')
        if ($FailStage -eq 'protect') {{ throw 'adapter protect failure must remain private' }}
    }}
    Smoke = {{ param($WorkerRoot, $ProgramDataRoot)
        [void]$Events.Add('smoke')
        if ($FailStage -eq 'smoke') {{ throw 'adapter smoke failure must remain private' }}
    }}
    ValidateTask = {{ param($ProgramDataRoot)
        [void]$Events.Add('validate-task')
        if ($FailStage -eq 'validate-task') {{ throw 'adapter task failure must remain private' }}
    }}
    CleanupSuccess = {{ param($Staging)
        [void]$Events.Add('cleanup-success')
    }}
    Rollback = {{ param($Backup, $WorkerRoot, $ProgramDataRoot)
        [void]$Events.Add('rollback')
    }}
    ValidateRollback = {{ param($WorkerRoot, $ProgramDataRoot)
        [void]$Events.Add('validate-rollback')
    }}
    ReleaseLock = {{ param($ProgramDataRoot)
        [void]$Events.Add('release-lock')
    }}
}}
"""


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell transaction contract requires Windows")
def test_updater_bootstrap_deployment_transaction_commits_in_order(tmp_path: Path) -> None:
    """Skipping a transaction stage or cleanup/release ordering must make this test fail."""
    body = _updater_bootstrap_adapter_script() + """
$Result = Invoke-UpdaterBootstrapTransaction -RepositoryRoot 'repository-root' `
  -WorkerRoot 'worker-root' -ProgramDataRoot 'program-data-root' `
  -ExpectedCommit 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' -Adapter $Adapter
[pscustomobject]@{ result=$Result; events=$Events } | ConvertTo-Json -Depth 6 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "ready"
    assert record["events"] == [
        "validate-context",
        "acquire-lock",
        "stop-updater-task",
        "stage",
        "validate-stage",
        "backup",
        "activate",
        "protect",
        "smoke",
        "validate-task",
        "cleanup-success",
        "release-lock",
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell transaction contract requires Windows")
@pytest.mark.parametrize(
    ("fail_stage", "error_code", "expected_events"),
    [
        (
            "activate",
            "UPDATER_BOOTSTRAP_ACTIVATION_FAILED",
            [
                "validate-context", "acquire-lock", "stop-updater-task", "stage",
                "validate-stage", "backup", "activate", "rollback",
                "validate-rollback", "release-lock",
            ],
        ),
        (
            "protect",
            "UPDATER_BOOTSTRAP_STAGE_FAILED",
            [
                "validate-context", "acquire-lock", "stop-updater-task", "stage",
                "validate-stage", "backup", "activate", "protect", "rollback",
                "validate-rollback", "release-lock",
            ],
        ),
        (
            "smoke",
            "UPDATER_BOOTSTRAP_SMOKE_FAILED",
            [
                "validate-context", "acquire-lock", "stop-updater-task", "stage",
                "validate-stage", "backup", "activate", "protect", "smoke", "rollback",
                "validate-rollback", "release-lock",
            ],
        ),
        (
            "validate-task",
            "UPDATER_BOOTSTRAP_TASK_INVALID",
            [
                "validate-context", "acquire-lock", "stop-updater-task", "stage",
                "validate-stage", "backup", "activate", "protect", "smoke",
                "validate-task", "rollback", "validate-rollback", "release-lock",
            ],
        ),
    ],
)
def test_updater_bootstrap_deployment_transaction_rolls_back_failed_switches(
    tmp_path: Path, fail_stage: str, error_code: str, expected_events: list[str]
) -> None:
    """Leaking adapter errors or omitting rollback validation must make this test fail."""
    body = _updater_bootstrap_adapter_script(fail_stage) + """
$Result = Invoke-UpdaterBootstrapTransaction -RepositoryRoot 'repository-root' `
  -WorkerRoot 'worker-root' -ProgramDataRoot 'program-data-root' `
  -ExpectedCommit 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' -Adapter $Adapter
[pscustomobject]@{ result=$Result; events=$Events } | ConvertTo-Json -Depth 6 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert record["result"]["error_code"] == error_code
    assert "adapter" not in record["result"]["error_code"]
    assert record["events"] == expected_events


def _create_bootstrap_test_repository(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    repository = tmp_path / "repository with spaces"
    subprocess.run(
        ["git.exe", "init", "--bare", "--initial-branch=main", str(origin)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git.exe", "init", "--initial-branch=main", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git.exe", "-C", str(repository), "config", "user.name", "Bootstrap Test"],
        check=True,
    )
    subprocess.run(
        [
            "git.exe",
            "-C",
            str(repository),
            "config",
            "user.email",
            "bootstrap@example.invalid",
        ],
        check=True,
    )
    source = repository / "worker" / "windows"
    updater = source / "updater"
    updater.mkdir(parents=True)
    for relative in (
        "__init__.py",
        "cli.py",
        "runtime.py",
        "windows_runtime.py",
        "state.py",
    ):
        (updater / relative).write_text(f"# tracked {relative}\n", encoding="utf-8")
    (source / "UpdaterBootstrap.ps1").write_text(
        "$ErrorActionPreference = 'Stop'\n", encoding="utf-8"
    )
    subprocess.run(
        ["git.exe", "-C", str(repository), "add", "worker/windows"], check=True
    )
    subprocess.run(
        ["git.exe", "-C", str(repository), "commit", "-m", "bootstrap fixture"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git.exe", "-C", str(repository), "remote", "add", "origin", str(origin)],
        check=True,
    )
    subprocess.run(
        ["git.exe", "-C", str(repository), "push", "-u", "origin", "main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return repository


def _mutate_bootstrap_repository(repository: Path, mutation: str) -> None:
    if mutation == "wrong_path" or mutation == "expected_commit_differs":
        return
    if mutation == "wrong_branch":
        subprocess.run(
            ["git.exe", "-C", str(repository), "checkout", "-b", "other"],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    if mutation == "wrong_origin":
        other_origin = repository.parent / "other-origin.git"
        subprocess.run(
            ["git.exe", "clone", "--bare", str(repository), str(other_origin)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git.exe",
                "-C",
                str(repository),
                "remote",
                "set-url",
                "origin",
                str(other_origin),
            ],
            check=True,
        )
        return
    tracked = repository / "worker" / "windows" / "updater" / "state.py"
    tracked.write_text("# changed tracked state\n", encoding="utf-8")
    if mutation == "origin_main_differs":
        subprocess.run(
            ["git.exe", "-C", str(repository), "add", str(tracked)], check=True
        )
        subprocess.run(
            ["git.exe", "-C", str(repository), "commit", "-m", "local commit"],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    if mutation != "tracked_dirty":
        raise AssertionError(f"unknown bootstrap repository mutation: {mutation}")


def _run_bootstrap_repository_preflight(
    repository: Path, mutation: str
) -> subprocess.CompletedProcess[str]:
    expected_commit = subprocess.run(
        ["git.exe", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if mutation == "expected_commit_differs":
        expected_commit = "0" * 40
    trusted_root = repository.parent / "different trusted root" if mutation == "wrong_path" else repository
    body = f"""
Assert-UpdaterBootstrapRepositoryState `
  -RepositoryRoot {_ps_quote(repository)} `
  -ExpectedCommit {_ps_quote(expected_commit)} `
  -TrustedRepositoryRoot {_ps_quote(trusted_root)} `
  -TrustedRemoteUrl {_ps_quote(repository.parent / 'origin.git')}
"""
    return _run_updater_bootstrap_harness(repository.parent, body)


@pytest.mark.skipif(os.name != "nt", reason="Windows Git preflight requires Windows")
@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("wrong_path", "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"),
        ("wrong_branch", "UPDATER_BOOTSTRAP_BRANCH_INVALID"),
        ("wrong_origin", "UPDATER_BOOTSTRAP_REMOTE_INVALID"),
        ("origin_main_differs", "UPDATER_BOOTSTRAP_SOURCE_STALE"),
        ("expected_commit_differs", "UPDATER_BOOTSTRAP_COMMIT_MISMATCH"),
        ("tracked_dirty", "UPDATER_BOOTSTRAP_SOURCE_DIRTY"),
    ],
)
def test_updater_bootstrap_deployment_rejects_untrusted_repository_state(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    _mutate_bootstrap_repository(repository, mutation)

    result = _run_bootstrap_repository_preflight(repository, mutation)

    assert result.returncode != 0
    assert expected in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows production trust boundary requires Windows")
def test_updater_bootstrap_deployment_production_repository_boundary_is_fixed(
    tmp_path: Path,
) -> None:
    body = f"""
$Captured = $null
function Assert-UpdaterBootstrapRepositoryState {{
    param($RepositoryRoot, $ExpectedCommit, $TrustedRepositoryRoot, $TrustedRemoteUrl)
    $script:Captured = [pscustomobject]@{{
        repository = $RepositoryRoot
        commit = $ExpectedCommit
        trusted_repository = $TrustedRepositoryRoot
        trusted_remote = $TrustedRemoteUrl
    }}
}}
$Command = Get-Command Assert-TrustedUpdaterBootstrapRepository
$script:UpdaterBootstrapRepositoryRoot = "C:\\untrusted"
$script:UpdaterBootstrapRemoteUrl = "https://example.invalid/untrusted.git"
Assert-TrustedUpdaterBootstrapRepository -RepositoryRoot {_ps_quote(tmp_path)} `
  -ExpectedCommit {'a' * 40}
[pscustomobject]@{{
    captured = $Captured
    root_override = $Command.Parameters.ContainsKey("TrustedRepositoryRoot")
    remote_override = $Command.Parameters.ContainsKey("TrustedRemoteUrl")
}} | ConvertTo-Json -Depth 4 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["captured"] == {
        "repository": str(tmp_path),
        "commit": "a" * 40,
        "trusted_repository": r"D:\code\ai-drawing",
        "trusted_remote": "https://github.com/tf00185077/ai-drawing.git",
    }
    assert record["root_override"] is False
    assert record["remote_override"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows Git preflight requires Windows")
@pytest.mark.parametrize("expected_commit", ["abc", "A" * 40])
def test_updater_bootstrap_deployment_repository_rejects_malformed_expected_commit(
    tmp_path: Path, expected_commit: str
) -> None:
    result = _run_updater_bootstrap_harness(
        tmp_path,
        f"Assert-UpdaterBootstrapExpectedCommit -ExpectedCommit {_ps_quote(expected_commit)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_COMMIT_INVALID" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows Git staging requires Windows")
def test_updater_bootstrap_deployment_staging_ignores_untracked_repository_files(
    tmp_path: Path,
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    untracked = repository / "worker" / "windows" / "updater" / "untracked-sentinel.txt"
    untracked.write_text("must not be staged\n", encoding="utf-8")
    worker_root = tmp_path / "worker root"
    worker_root.mkdir()
    security = Path(__file__).resolve().parents[2] / "worker" / "windows" / "WorkerSecurity.ps1"
    expected_commit = subprocess.run(
        ["git.exe", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    body = f"""
. {_ps_quote(security)}
$ExpectedCommit = {_ps_quote(expected_commit)}
Assert-UpdaterBootstrapRepositoryState -RepositoryRoot {_ps_quote(repository)} `
  -ExpectedCommit $ExpectedCommit -TrustedRepositoryRoot {_ps_quote(repository)} `
  -TrustedRemoteUrl {_ps_quote(repository.parent / 'origin.git')}
$CurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$Staging = New-UpdaterBootstrapStage -RepositoryRoot {_ps_quote(repository)} `
  -WorkerRoot {_ps_quote(worker_root)} -ExpectedCommit $ExpectedCommit `
  -OwnerSid $CurrentSid -AllowedSids @($CurrentSid)
Assert-UpdaterBootstrapStageStructure -StagingPath $Staging
[pscustomobject]@{{
  staging = $Staging
  sentinel = Test-Path -LiteralPath (Join-Path $Staging "updater\\untracked-sentinel.txt")
}} | ConvertTo-Json -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["sentinel"] is False
    assert Path(record["staging"]).is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows production staging requires Windows")
def test_updater_bootstrap_deployment_production_context_keeps_security_functions_for_staging(
    tmp_path: Path,
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    project = Path(__file__).resolve().parents[2]
    shutil.copy2(
        project / "worker" / "windows" / "WorkerSecurity.ps1",
        repository / "worker" / "windows" / "WorkerSecurity.ps1",
    )
    worker_root = tmp_path / "worker root"
    program_data = tmp_path / "program data"
    worker_root.mkdir()
    program_data.mkdir()
    expected_commit = subprocess.run(
        ["git.exe", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    body = f"""
function Assert-UpdaterBootstrapElevation {{}}
function Assert-TrustedUpdaterBootstrapRepository {{
    param($RepositoryRoot, $ExpectedCommit)
}}
function Assert-UpdaterBootstrapWorkerPaths {{
    param($WorkerRoot, $ProgramDataRoot, $ExpectedCommit)
}}
Assert-UpdaterBootstrapProductionContext -RepositoryRoot {_ps_quote(repository)} `
  -WorkerRoot {_ps_quote(worker_root)} -ProgramDataRoot {_ps_quote(program_data)} `
  -ExpectedCommit {_ps_quote(expected_commit)}
$CurrentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$Staging = New-UpdaterBootstrapStage -RepositoryRoot {_ps_quote(repository)} `
  -WorkerRoot {_ps_quote(worker_root)} -ExpectedCommit {_ps_quote(expected_commit)} `
  -OwnerSid $CurrentSid -AllowedSids @($CurrentSid)
Assert-UpdaterBootstrapStageStructure -StagingPath $Staging
[pscustomobject]@{{
    staging = $Staging
    missing_security_functions = @(@(
            "New-SecureUpdaterDirectory",
            "Assert-SecureUpdaterTree",
            "Protect-UpdaterTree"
        ) | Where-Object {{
            -not (Get-Command $_ -CommandType Function -ErrorAction SilentlyContinue)
        }})
}} | ConvertTo-Json -Depth 3 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert Path(record["staging"]).is_dir()
    assert record["missing_security_functions"] == []


def test_updater_bootstrap_deployment_has_no_per_file_hash_gate() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "worker"
        / "windows"
        / "Deploy-UpdaterBootstrap.ps1"
    )
    text = script.read_text(encoding="utf-8").lower()
    for forbidden in (
        "get-filehash",
        "sha256",
        "sha-256",
        "hashalgorithm",
        "digest-manifest",
    ):
        assert forbidden not in text


@pytest.mark.skipif(os.name != "nt", reason="Windows elevation contract requires Windows")
def test_updater_bootstrap_deployment_elevation_rejects_non_administrator(
    tmp_path: Path,
) -> None:
    result = _run_updater_bootstrap_harness(
        tmp_path, "Assert-UpdaterBootstrapElevation -AdministratorProbe { $false }"
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_ELEVATION_REQUIRED" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows repository context requires Windows")
@pytest.mark.parametrize("marker", ["wrong marker", "AI-Drawing NVIDIA Worker"])
def test_updater_bootstrap_deployment_repository_context_rejects_invalid_worker_tree(
    tmp_path: Path, marker: str
) -> None:
    worker_root = tmp_path / "worker"
    program_data = tmp_path / "program data"
    worker_root.mkdir()
    program_data.mkdir()
    (worker_root / ".ai-drawing-worker-owned").write_text(marker, encoding="utf-8")
    security = Path(__file__).resolve().parents[2] / "worker" / "windows" / "WorkerSecurity.ps1"
    body = f"""
. {_ps_quote(security)}
Assert-UpdaterBootstrapWorkerPaths -WorkerRoot {_ps_quote(worker_root)} `
  -ProgramDataRoot {_ps_quote(program_data)} -ExpectedCommit {'a' * 40}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode != 0
    assert "Task 7 migration is required" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse contract requires Windows")
@pytest.mark.parametrize(
    "nested",
    [
        True,
        False,
    ],
)
def test_updater_bootstrap_deployment_generic_reparse_tree_is_rejected(
    tmp_path: Path, nested: bool
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "must-not-be-read.txt").write_text("sentinel", encoding="utf-8")
    if nested:
        candidate = tmp_path / "candidate-root"
        candidate.mkdir()
        junction = candidate / "escape"
    else:
        candidate = tmp_path / "candidate-junction"
        junction = candidate
    created = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"New-Item -ItemType Junction -Path {_ps_quote(junction)} -Target {_ps_quote(outside)} | Out-Null",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")

    result = _run_updater_bootstrap_harness(
        tmp_path,
        f"Assert-UpdaterBootstrapNoReparseTree -Path {_ps_quote(candidate)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr
    assert (outside / "must-not-be-read.txt").read_text(encoding="utf-8") == "sentinel"


def _create_bootstrap_test_junction(junction: Path, outside: Path) -> None:
    outside.mkdir()
    created = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"New-Item -ItemType Junction -Path {_ps_quote(junction)} -Target {_ps_quote(outside)} | Out-Null",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")


@pytest.mark.skipif(os.name != "nt", reason="Windows source reparse contract requires Windows")
def test_updater_bootstrap_deployment_staging_rejects_source_updater_reparse(
    tmp_path: Path,
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    updater = repository / "worker" / "windows" / "updater"
    _create_bootstrap_test_junction(updater / "escape", tmp_path / "outside-source")
    worker_root = tmp_path / "worker"
    worker_root.mkdir()
    expected_commit = subprocess.run(
        ["git.exe", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = _run_updater_bootstrap_harness(
        tmp_path,
        f"New-UpdaterBootstrapStage -RepositoryRoot {_ps_quote(repository)} "
        f"-WorkerRoot {_ps_quote(worker_root)} -ExpectedCommit {_ps_quote(expected_commit)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows installed updater reparse contract requires Windows")
def test_updater_bootstrap_deployment_context_rejects_installed_updater_reparse(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    security = repository / "worker" / "windows" / "WorkerSecurity.ps1"
    security.parent.mkdir(parents=True)
    shutil.copy2(
        Path(__file__).resolve().parents[2] / "worker" / "windows" / "WorkerSecurity.ps1",
        security,
    )
    worker_root = tmp_path / "worker"
    worker_root.mkdir()
    _create_bootstrap_test_junction(
        worker_root / "updater", tmp_path / "outside-installed-updater"
    )
    program_data = tmp_path / "program data"
    program_data.mkdir()
    body = f"""
function Assert-UpdaterBootstrapElevation {{}}
function Assert-TrustedUpdaterBootstrapRepository {{
    param($RepositoryRoot, $ExpectedCommit)
}}
Assert-UpdaterBootstrapProductionContext -RepositoryRoot {_ps_quote(repository)} `
  -WorkerRoot {_ps_quote(worker_root)} -ProgramDataRoot {_ps_quote(program_data)} `
  -ExpectedCommit {'a' * 40}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows staging reparse contract requires Windows")
def test_updater_bootstrap_deployment_staging_rejects_existing_staging_reparse(
    tmp_path: Path,
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    worker_root = tmp_path / "worker"
    deployment_root = worker_root / "updater-deployment-owned"
    deployment_root.mkdir(parents=True)
    expected_commit = subprocess.run(
        ["git.exe", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    staging = deployment_root / f"staging-{expected_commit}"
    _create_bootstrap_test_junction(staging, tmp_path / "outside-staging")

    result = _run_updater_bootstrap_harness(
        tmp_path,
        f"New-UpdaterBootstrapStage -RepositoryRoot {_ps_quote(repository)} "
        f"-WorkerRoot {_ps_quote(worker_root)} -ExpectedCommit {_ps_quote(expected_commit)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows ProgramData reparse contract requires Windows")
def test_updater_bootstrap_deployment_context_rejects_program_data_reparse(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    security = repository / "worker" / "windows" / "WorkerSecurity.ps1"
    security.parent.mkdir(parents=True)
    shutil.copy2(
        Path(__file__).resolve().parents[2] / "worker" / "windows" / "WorkerSecurity.ps1",
        security,
    )
    worker_root = tmp_path / "worker"
    worker_root.mkdir()
    program_data = tmp_path / "program data"
    program_data.mkdir()
    _create_bootstrap_test_junction(
        program_data / "escape", tmp_path / "outside-program-data"
    )
    body = f"""
function Assert-UpdaterBootstrapElevation {{}}
function Assert-TrustedUpdaterBootstrapRepository {{
    param($RepositoryRoot, $ExpectedCommit)
}}
Assert-UpdaterBootstrapProductionContext -RepositoryRoot {_ps_quote(repository)} `
  -WorkerRoot {_ps_quote(worker_root)} -ProgramDataRoot {_ps_quote(program_data)} `
  -ExpectedCommit {'a' * 40}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr


def test_updater_bootstrap_deployment_task_stop_is_isolated_to_updater() -> None:
    """Touching Worker/Restart processes or starting a task must make this test fail."""
    script = (
        Path(__file__).resolve().parents[2]
        / "worker"
        / "windows"
        / "Deploy-UpdaterBootstrap.ps1"
    )
    script_text = script.read_text(encoding="utf-8")
    start = script_text.index("function Stop-UpdaterBootstrapTask")
    stop_block = script_text[start : script_text.index("\nfunction ", start + 1)]

    assert '"AI-Drawing Worker Updater"' in stop_block
    assert "Get-ScheduledTask" in stop_block
    assert "Stop-ScheduledTask" in stop_block
    for forbidden in ("AI-Drawing NVIDIA Worker", "AI-Drawing NVIDIA Worker Restart"):
        assert forbidden not in stop_block
    assert "Stop-Process" not in stop_block
    assert "Start-ScheduledTask" not in script_text


@pytest.mark.skipif(os.name != "nt", reason="Windows task polling requires Windows")
def test_updater_bootstrap_deployment_task_polling_waits_until_ready(
    tmp_path: Path,
) -> None:
    body = """
$States = New-Object "System.Collections.Generic.Queue[string]"
foreach ($State in @("Running", "Running", "Ready")) { $States.Enqueue($State) }
$Queries = New-Object "System.Collections.Generic.List[string]"
$Stops = New-Object "System.Collections.Generic.List[string]"
$Waits = New-Object "System.Collections.Generic.List[int]"
Stop-UpdaterBootstrapTask `
  -TaskLookup { param($Name)
    [void]$Queries.Add($Name)
    [pscustomobject]@{ State = $States.Dequeue() }
  } `
  -TaskStopper { param($Name) [void]$Stops.Add($Name) } `
  -Delay { param($Milliseconds) [void]$Waits.Add($Milliseconds) } `
  -UtcNow { [DateTime]::Parse("2026-08-02T00:00:00Z").ToUniversalTime() }
[pscustomobject]@{ queries=$Queries; stops=$Stops; waits=$Waits } |
  ConvertTo-Json -Depth 4 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record == {
        "queries": [
            "AI-Drawing Worker Updater",
            "AI-Drawing Worker Updater",
            "AI-Drawing Worker Updater",
        ],
        "stops": ["AI-Drawing Worker Updater"],
        "waits": [200],
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows task timeout requires Windows")
def test_updater_bootstrap_deployment_task_timeout_is_busy_before_backup(
    tmp_path: Path,
) -> None:
    body = """
$Events = New-Object "System.Collections.Generic.List[string]"
$Times = New-Object "System.Collections.Generic.Queue[datetime]"
$Times.Enqueue([DateTime]::Parse("2026-08-02T00:00:00Z").ToUniversalTime())
$Times.Enqueue([DateTime]::Parse("2026-08-02T00:00:31Z").ToUniversalTime())
$Adapter = [pscustomobject]@{
  ValidateContext = { [void]$Events.Add("validate") }
  AcquireLock = { [void]$Events.Add("lock") }
  StopUpdaterTask = {
    [void]$Events.Add("stop")
    Stop-UpdaterBootstrapTask `
      -TaskLookup { param($Name) [pscustomobject]@{ State = "Running" } } `
      -TaskStopper { param($Name) } -Delay { param($Milliseconds) } `
      -UtcNow { $Times.Dequeue() }
  }
  Stage = { [void]$Events.Add("stage") }
  ValidateStage = {}
  Backup = { [void]$Events.Add("backup"); "backup" }
  Activate = {}
  Protect = {}
  Smoke = {}
  ValidateTask = {}
  CleanupSuccess = {}
  Rollback = {}
  ValidateRollback = {}
  ReleaseLock = { [void]$Events.Add("release") }
}
$Result = Invoke-UpdaterBootstrapTransaction -RepositoryRoot "repository" `
  -WorkerRoot "worker" -ProgramDataRoot "program-data" `
  -ExpectedCommit "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" -Adapter $Adapter
[pscustomobject]@{ result=$Result; events=$Events } | ConvertTo-Json -Depth 5 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"] == {
        "status": "failed_before_switch",
        "error_code": "UPDATER_BOOTSTRAP_TASK_BUSY",
        "backup": None,
    }
    assert record["events"] == ["validate", "lock", "stop", "release"]


@pytest.mark.skipif(os.name != "nt", reason="Windows transaction lock requires Windows")
def test_updater_bootstrap_deployment_task_lock_is_exclusive_and_released(
    tmp_path: Path,
) -> None:
    program_data = tmp_path / "program data"
    program_data.mkdir()
    body = f"""
function Assert-SecureUpdaterTree {{ param($Path) }}
Enter-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}
$LockPath = Join-Path {_ps_quote(program_data)} "updater-bootstrap-deployment.lock"
$ExistsWhileHeld = Test-Path -LiteralPath $LockPath -PathType Leaf
$SecondError = $null
try {{
  Enter-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}
}} catch {{
  $SecondError = $_.Exception.Message
}}
Exit-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}
[pscustomobject]@{{
  exists_while_held=$ExistsWhileHeld
  second_error=$SecondError
  exists_after_release=(Test-Path -LiteralPath $LockPath)
}} | ConvertTo-Json -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "exists_while_held": True,
        "second_error": "UPDATER_BOOTSTRAP_TRANSACTION_BUSY",
        "exists_after_release": False,
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows process lock requires Windows")
def test_updater_bootstrap_deployment_task_lock_excludes_another_process(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[2]
    deployment_script = repo / "worker" / "windows" / "Deploy-UpdaterBootstrap.ps1"
    program_data = tmp_path / "program data"
    program_data.mkdir()
    holder_script = tmp_path / "lock holder.ps1"
    holder_script.write_text(
        f'. {_ps_quote(deployment_script)} '
        '-ExpectedCommit "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'
        "function Assert-SecureUpdaterTree { param($Path) }\n"
        f"Enter-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}\n"
        '[Console]::Out.WriteLine("READY")\n'
        "[Console]::Out.Flush()\n"
        "[void][Console]::In.ReadLine()\n"
        f"Exit-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}\n",
        encoding="utf-8",
    )
    holder = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(holder_script),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert holder.stdout is not None
    try:
        assert holder.stdout.readline().strip() == "READY"
        contender = _run_updater_bootstrap_harness(
            tmp_path,
            "function Assert-SecureUpdaterTree { param($Path) }\n"
            f"Enter-UpdaterBootstrapTransactionLock -ProgramDataRoot {_ps_quote(program_data)}",
        )
        assert contender.returncode != 0
        assert "UPDATER_BOOTSTRAP_TRANSACTION_BUSY" in contender.stderr
    finally:
        remaining_stdout, holder_stderr = holder.communicate(input="release\n", timeout=10)
    assert holder.returncode == 0, holder_stderr + remaining_stdout
    assert not (program_data / "updater-bootstrap-deployment.lock").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lock release requires Windows")
def test_updater_bootstrap_deployment_task_lock_release_failure_is_fixed_result(
    tmp_path: Path,
) -> None:
    body = _updater_bootstrap_adapter_script() + """
$Adapter.ReleaseLock = { throw "private release secret" }
$Result = Invoke-UpdaterBootstrapTransaction -RepositoryRoot "repository" `
  -WorkerRoot "worker" -ProgramDataRoot "program-data" `
  -ExpectedCommit "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" -Adapter $Adapter
$Result | ConvertTo-Json -Depth 5 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "status": "recovery_required",
        "error_code": "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED",
        "backup": "backup-token",
    }
    assert "private release secret" not in result.stdout
    assert "private release secret" not in result.stderr


def _create_updater_bootstrap_switch_fixture(tmp_path: Path) -> SimpleNamespace:
    commit = "b" * 40
    worker_root = tmp_path / "worker root"
    installed_updater = worker_root / "updater"
    deployment_root = worker_root / "updater-deployment-owned"
    staging = deployment_root / f"staging-{commit}"
    staged_updater = staging / "updater"
    program_data = tmp_path / "program data"
    program_data_deployment_root = program_data / "updater-bootstrap-deployment-owned"
    bootstrap_staging_root = program_data_deployment_root / f"staging-{commit}"
    bootstrap_staging = bootstrap_staging_root / "UpdaterBootstrap.ps1"
    installed_updater.mkdir(parents=True)
    staged_updater.mkdir(parents=True)
    bootstrap_staging_root.mkdir(parents=True)
    (installed_updater / "marker.txt").write_text("old-updater", encoding="utf-8")
    for relative in ("__init__.py", "cli.py", "runtime.py", "windows_runtime.py", "state.py"):
        (staged_updater / relative).write_text(f"# new {relative}\n", encoding="utf-8")
    (staged_updater / "marker.txt").write_text("new-updater", encoding="utf-8")
    (program_data / "UpdaterBootstrap.ps1").write_text("old-bootstrap", encoding="utf-8")
    (staging / "UpdaterBootstrap.ps1").write_text("new-bootstrap", encoding="utf-8")
    bootstrap_staging.write_text("new-bootstrap", encoding="utf-8")

    sentinels: list[Path] = []
    for relative in ("models", "shared", "releases/release-one"):
        sentinel = worker_root / relative / "must-remain.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text(relative, encoding="utf-8")
        sentinels.append(sentinel)
    current_target = tmp_path / "outside current"
    current_sentinel = current_target / "must-remain.txt"
    _create_bootstrap_test_junction(worker_root / "current", current_target)
    current_sentinel.write_text("current", encoding="utf-8")
    sentinels.append(current_sentinel)
    return SimpleNamespace(
        commit=commit,
        worker_root=worker_root,
        installed_updater=installed_updater,
        deployment_root=deployment_root,
        staging=staging,
        program_data=program_data,
        program_data_deployment_root=program_data_deployment_root,
        bootstrap_staging_root=bootstrap_staging_root,
        bootstrap_staging=bootstrap_staging,
        updater_backup=deployment_root / f"backup-{commit}",
        bootstrap_backup=program_data / f"UpdaterBootstrap.ps1.backup-{commit}",
        sentinels=sentinels,
    )


def _updater_bootstrap_filesystem_adapter_script(
    fixture: SimpleNamespace, fail_stage: str | None = None
) -> str:
    fail_value = "" if fail_stage is None else fail_stage
    return f"""
$FailStage = {_ps_quote(fail_value)}
$Protected = New-Object "System.Collections.Generic.List[string]"
$Asserted = New-Object "System.Collections.Generic.List[string]"
$Moves = New-Object "System.Collections.Generic.List[object]"
$script:RollbackSmokeCalls = 0
function Protect-UpdaterTree {{ param($Path) [void]$Protected.Add([IO.Path]::GetFullPath($Path)) }}
function Assert-SecureUpdaterTree {{ param($Path) [void]$Asserted.Add([IO.Path]::GetFullPath($Path)) }}
function Invoke-UpdaterBootstrapImportSmoke {{
  param($WorkerRoot, $ProgramDataRoot)
  $script:RollbackSmokeCalls += 1
  if ($FailStage -eq "rollback-smoke") {{ throw "UPDATER_BOOTSTRAP_IMPORT_FAILED" }}
}}
function Move-Item {{
  param($LiteralPath, $Destination, $ErrorAction)
  $SourcePath = [IO.Path]::GetFullPath([string]$LiteralPath)
  $DestinationPath = [IO.Path]::GetFullPath([string]$Destination)
  [void]$Moves.Add([pscustomobject]@{{ source=$SourcePath; destination=$DestinationPath }})
  if (
    $SourcePath -eq [IO.Path]::GetFullPath({_ps_quote(fixture.bootstrap_staging)}) -and
    $DestinationPath -eq [IO.Path]::GetFullPath({_ps_quote(fixture.program_data / 'UpdaterBootstrap.ps1')})
  ) {{
    if ($FailStage -eq "activate-second-move") {{
      throw "injected second activation move failure"
    }}
    if ($FailStage -eq "activate-partial-bootstrap") {{
      [IO.File]::WriteAllText($DestinationPath, "partial-new-bootstrap")
      throw "injected partial bootstrap destination failure"
    }}
  }}
  Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath `
    -Destination $Destination -ErrorAction Stop
}}
$ProductionAdapter = Get-ProductionUpdaterBootstrapAdapter
$StagingPath = {_ps_quote(fixture.staging)}
$Adapter = [pscustomobject]@{{
  ValidateContext = {{}}
  AcquireLock = {{}}
  StopUpdaterTask = {{}}
  Stage = {{ $StagingPath }}
  ValidateStage = $ProductionAdapter.ValidateStage
  Backup = $ProductionAdapter.Backup
  Activate = {{ param($Staging, $WorkerRoot, $ProgramDataRoot)
    & $ProductionAdapter.Activate $Staging $WorkerRoot $ProgramDataRoot
    if ($FailStage -eq "activate") {{ throw "private activation failure" }}
  }}
  Protect = $ProductionAdapter.Protect
  Smoke = {{
    if ($FailStage -in @("smoke", "rollback-smoke")) {{ throw "private smoke failure" }}
  }}
  ValidateTask = {{}}
  CleanupSuccess = $ProductionAdapter.CleanupSuccess
  Rollback = $ProductionAdapter.Rollback
  ValidateRollback = $ProductionAdapter.ValidateRollback
  ReleaseLock = {{}}
}}
$Result = Invoke-UpdaterBootstrapTransaction -RepositoryRoot "repository" `
  -WorkerRoot {_ps_quote(fixture.worker_root)} `
  -ProgramDataRoot {_ps_quote(fixture.program_data)} `
  -ExpectedCommit {_ps_quote(fixture.commit)} -Adapter $Adapter
[pscustomobject]@{{
  result=$Result
  protected=$Protected
  asserted=$Asserted
  moves=$Moves
  rollback_smoke_calls=$script:RollbackSmokeCalls
}} | ConvertTo-Json -Depth 7 -Compress
"""


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap staging requires Windows")
def test_updater_bootstrap_deployment_switch_stages_bootstrap_on_program_data_volume(
    tmp_path: Path,
) -> None:
    commit = "c" * 40
    worker_staging = (
        tmp_path
        / "worker root"
        / "updater-deployment-owned"
        / f"staging-{commit}"
    )
    worker_staging.mkdir(parents=True)
    (worker_staging / "UpdaterBootstrap.ps1").write_text(
        "new-bootstrap", encoding="utf-8"
    )
    program_data = tmp_path / "program data"
    program_data.mkdir()
    expected_stage_root = (
        program_data / "updater-bootstrap-deployment-owned" / f"staging-{commit}"
    )
    body = f"""
$Protected = New-Object "System.Collections.Generic.List[string]"
$Asserted = New-Object "System.Collections.Generic.List[string]"
function New-SecureUpdaterDirectory {{
  param($Path)
  [void][IO.Directory]::CreateDirectory($Path)
}}
function Protect-UpdaterTree {{ param($Path) [void]$Protected.Add([IO.Path]::GetFullPath($Path)) }}
function Assert-SecureUpdaterTree {{ param($Path) [void]$Asserted.Add([IO.Path]::GetFullPath($Path)) }}
$Stage = New-UpdaterBootstrapProgramDataStage `
  -WorkerStagingPath {_ps_quote(worker_staging)} `
  -ProgramDataRoot {_ps_quote(program_data)} -ExpectedCommit {_ps_quote(commit)}
[pscustomobject]@{{ stage=$Stage; protected=$Protected; asserted=$Asserted }} |
  ConvertTo-Json -Depth 4 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert Path(record["stage"]) == expected_stage_root
    assert (expected_stage_root / "UpdaterBootstrap.ps1").read_text(
        encoding="utf-8"
    ) == "new-bootstrap"
    assert str(expected_stage_root) in record["protected"]
    assert str(expected_stage_root) in record["asserted"]


@pytest.mark.skipif(os.name != "nt", reason="Windows directory switch requires Windows")
def test_updater_bootstrap_deployment_switch_installs_new_and_retains_backup(
    tmp_path: Path,
) -> None:
    fixture = _create_updater_bootstrap_switch_fixture(tmp_path)

    result = _run_updater_bootstrap_harness(
        tmp_path, _updater_bootstrap_filesystem_adapter_script(fixture)
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "ready"
    assert (fixture.installed_updater / "marker.txt").read_text(encoding="utf-8") == "new-updater"
    assert (fixture.program_data / "UpdaterBootstrap.ps1").read_text(encoding="utf-8") == "new-bootstrap"
    assert (fixture.updater_backup / "marker.txt").read_text(encoding="utf-8") == "old-updater"
    assert fixture.bootstrap_backup.read_text(encoding="utf-8") == "old-bootstrap"
    assert not fixture.staging.exists()
    assert fixture.updater_backup.is_dir()
    assert fixture.bootstrap_backup.is_file()
    assert not fixture.bootstrap_staging_root.exists()
    assert {
        "source": str(fixture.bootstrap_staging),
        "destination": str(fixture.program_data / "UpdaterBootstrap.ps1"),
    } in record["moves"]
    protected = {Path(path) for path in record["protected"]}
    asserted = {Path(path) for path in record["asserted"]}
    assert {fixture.installed_updater, fixture.program_data} <= protected
    assert {fixture.installed_updater, fixture.program_data} <= asserted
    for sentinel in fixture.sentinels:
        assert sentinel.read_text(encoding="utf-8") in {
            "models", "shared", "releases/release-one", "current"
        }


@pytest.mark.skipif(os.name != "nt", reason="Windows directory rollback requires Windows")
@pytest.mark.parametrize(
    ("fail_stage", "error_code"),
    [
        ("activate", "UPDATER_BOOTSTRAP_ACTIVATION_FAILED"),
        ("activate-second-move", "UPDATER_BOOTSTRAP_ACTIVATION_FAILED"),
        ("activate-partial-bootstrap", "UPDATER_BOOTSTRAP_ACTIVATION_FAILED"),
        ("smoke", "UPDATER_BOOTSTRAP_SMOKE_FAILED"),
    ],
)
def test_updater_bootstrap_deployment_switch_failure_restores_old_paths(
    tmp_path: Path, fail_stage: str, error_code: str
) -> None:
    fixture = _create_updater_bootstrap_switch_fixture(tmp_path)

    result = _run_updater_bootstrap_harness(
        tmp_path, _updater_bootstrap_filesystem_adapter_script(fixture, fail_stage)
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert record["result"]["error_code"] == error_code
    assert (fixture.installed_updater / "marker.txt").read_text(encoding="utf-8") == "old-updater"
    assert (fixture.program_data / "UpdaterBootstrap.ps1").read_text(encoding="utf-8") == "old-bootstrap"
    assert record["rollback_smoke_calls"] == 1
    for sentinel in fixture.sentinels:
        assert sentinel.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows rollback smoke requires Windows")
def test_updater_bootstrap_deployment_rollback_smoke_failure_requires_recovery(
    tmp_path: Path,
) -> None:
    fixture = _create_updater_bootstrap_switch_fixture(tmp_path)

    result = _run_updater_bootstrap_harness(
        tmp_path,
        _updater_bootstrap_filesystem_adapter_script(fixture, "rollback-smoke"),
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "recovery_required"
    assert record["result"]["error_code"] == "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"
    assert (fixture.installed_updater / "marker.txt").read_text(encoding="utf-8") == "old-updater"
    assert (fixture.program_data / "UpdaterBootstrap.ps1").read_text(encoding="utf-8") == "old-bootstrap"
    assert record["rollback_smoke_calls"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows backup boundary requires Windows")
@pytest.mark.parametrize("backup_kind", ["updater", "bootstrap"])
def test_updater_bootstrap_deployment_switch_rejects_backup_reparse_before_move(
    tmp_path: Path, backup_kind: str
) -> None:
    fixture = _create_updater_bootstrap_switch_fixture(tmp_path)
    candidate = (
        fixture.updater_backup if backup_kind == "updater" else fixture.bootstrap_backup
    )
    outside = tmp_path / f"outside {backup_kind} backup"
    _create_bootstrap_test_junction(candidate, outside)
    sentinel = outside / "must-not-be-read.txt"
    sentinel.write_text("outside", encoding="utf-8")

    result = _run_updater_bootstrap_harness(
        tmp_path,
        "$Adapter = Get-ProductionUpdaterBootstrapAdapter\n"
        f"& $Adapter.Backup {_ps_quote(fixture.worker_root)} "
        f"{_ps_quote(fixture.program_data)} {_ps_quote(fixture.commit)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_REPARSE_POINT" in result.stderr
    assert (fixture.installed_updater / "marker.txt").read_text(encoding="utf-8") == "old-updater"
    assert (fixture.program_data / "UpdaterBootstrap.ps1").read_text(encoding="utf-8") == "old-bootstrap"
    assert sentinel.read_text(encoding="utf-8") == "outside"


@pytest.mark.skipif(os.name != "nt", reason="Windows partial backup requires Windows")
def test_updater_bootstrap_deployment_switch_compensates_partial_backup(
    tmp_path: Path,
) -> None:
    fixture = _create_updater_bootstrap_switch_fixture(tmp_path)
    body = f"""
function Protect-UpdaterTree {{ param($Path) }}
function Assert-SecureUpdaterTree {{ param($Path) }}
$script:MoveCount = 0
function Move-Item {{
  param($LiteralPath, $Destination, $ErrorAction)
  $script:MoveCount += 1
  if ($script:MoveCount -eq 2) {{ throw "injected bootstrap backup failure" }}
  Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath `
    -Destination $Destination -ErrorAction Stop
}}
$Adapter = Get-ProductionUpdaterBootstrapAdapter
$Failure = $null
try {{
  & $Adapter.Backup {_ps_quote(fixture.worker_root)} `
    {_ps_quote(fixture.program_data)} {_ps_quote(fixture.commit)} | Out-Null
}} catch {{
  $Failure = $_.Exception.Message
}}
[pscustomobject]@{{ failure=$Failure; moves=$script:MoveCount }} |
  ConvertTo-Json -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "failure": "injected bootstrap backup failure",
        "moves": 3,
    }
    assert (fixture.installed_updater / "marker.txt").read_text(encoding="utf-8") == "old-updater"
    assert (fixture.program_data / "UpdaterBootstrap.ps1").read_text(encoding="utf-8") == "old-bootstrap"
    assert not fixture.updater_backup.exists()
    assert not fixture.bootstrap_backup.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows updater smoke requires Windows")
def test_updater_bootstrap_deployment_smoke_uses_owned_python_and_fixed_config(
    tmp_path: Path,
) -> None:
    worker_root = tmp_path / "worker root"
    updater_python = worker_root / "updater-runtime" / "Scripts" / "python.exe"
    updater_python.parent.mkdir(parents=True)
    updater_python.write_text("probe", encoding="utf-8")
    (worker_root / "updater").mkdir()
    program_data = tmp_path / "program data"
    program_data.mkdir()
    body = f"""
$Calls = New-Object "System.Collections.Generic.List[object]"
Invoke-UpdaterBootstrapSmoke -WorkerRoot {_ps_quote(worker_root)} `
  -ProgramDataRoot {_ps_quote(program_data)} `
  -PythonInvoker {{ param($Python, $Arguments)
    [void]$Calls.Add([pscustomobject]@{{
      python=$Python
      arguments=@($Arguments)
      location=(Get-Location).Path
    }})
    0
  }}
$Calls | ConvertTo-Json -Depth 5 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    calls = json.loads(result.stdout)
    assert calls == [
        {
            "python": str(updater_python),
            "arguments": [
                "-B",
                "-c",
                "from updater.cli import ProductionUpdaterServices; "
                "ProductionUpdaterServices.from_program_data(); "
                "import updater.runtime, updater.windows_runtime, updater.state",
            ],
            "location": str(worker_root),
        },
        {
            "python": str(updater_python),
            "arguments": ["-B", "-m", "updater.recovery"],
            "location": str(worker_root),
        },
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows updater smoke requires Windows")
def test_updater_bootstrap_deployment_smoke_discards_private_stderr(
    tmp_path: Path,
) -> None:
    worker_root = tmp_path / "worker root"
    updater_python = worker_root / "updater-runtime" / "Scripts" / "python.exe"
    updater_python.parent.mkdir(parents=True)
    updater_python.write_text("probe", encoding="utf-8")
    (worker_root / "updater").mkdir()
    program_data = tmp_path / "program data"
    program_data.mkdir()
    secret = "Bearer-smoke-stderr-must-not-leak"
    body = f"""
$Failure = $null
try {{
  Invoke-UpdaterBootstrapImportSmoke -WorkerRoot {_ps_quote(worker_root)} `
    -ProgramDataRoot {_ps_quote(program_data)} `
    -PythonInvoker {{ param($Python, $Arguments)
      Write-Error {_ps_quote(secret)} -ErrorAction Continue
      1
    }}
}} catch {{
  $Failure = $_.Exception.Message
}}
[pscustomobject]@{{ failure=$Failure }} | ConvertTo-Json -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"failure": "UPDATER_BOOTSTRAP_IMPORT_FAILED"}
    assert secret not in result.stdout
    assert secret not in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows task action validation requires Windows")
def test_updater_bootstrap_deployment_task_action_is_fixed_and_never_started(
    tmp_path: Path,
) -> None:
    program_data = tmp_path / "program data"
    program_data.mkdir()
    (program_data / "UpdaterBootstrap.ps1").write_text("fixture", encoding="utf-8")
    expected_executable = (
        Path(os.environ["SystemRoot"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    expected_arguments = (
        "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
        f'"{program_data}\\UpdaterBootstrap.ps1"'
    )
    body = f"""
$ExpectedAction = [pscustomobject]@{{
  Execute={_ps_quote(expected_executable)}
  Arguments={_ps_quote(expected_arguments)}
}}
$Cases = @(
  [pscustomobject]@{{ name="valid"; actions=@($ExpectedAction) }},
  [pscustomobject]@{{ name="wrong-executable"; actions=@([pscustomobject]@{{ Execute="pwsh.exe"; Arguments=$ExpectedAction.Arguments }}) }},
  [pscustomobject]@{{ name="wrong-arguments"; actions=@([pscustomobject]@{{ Execute=$ExpectedAction.Execute; Arguments="-File wrong.ps1" }}) }},
  [pscustomobject]@{{ name="extra-action"; actions=@($ExpectedAction, $ExpectedAction) }}
)
$Queries = New-Object "System.Collections.Generic.List[string]"
$Results = New-Object "System.Collections.Generic.List[object]"
foreach ($Case in $Cases) {{
  $script:TaskCase = [pscustomobject]@{{ State="Ready"; Actions=@($Case.actions) }}
  try {{
    Assert-UpdaterBootstrapScheduledTaskAction -ProgramDataRoot {_ps_quote(program_data)} `
      -TaskLookup {{ param($Name) [void]$Queries.Add($Name); $script:TaskCase }}
    [void]$Results.Add([pscustomobject]@{{ name=$Case.name; result="ok" }})
  }} catch {{
    [void]$Results.Add([pscustomobject]@{{ name=$Case.name; result=$_.Exception.Message }})
  }}
}}
[pscustomobject]@{{ results=$Results; queries=$Queries }} | ConvertTo-Json -Depth 5 -Compress
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["results"] == [
        {"name": "valid", "result": "ok"},
        {"name": "wrong-executable", "result": "UPDATER_BOOTSTRAP_TASK_INVALID"},
        {"name": "wrong-arguments", "result": "UPDATER_BOOTSTRAP_TASK_INVALID"},
        {"name": "extra-action", "result": "UPDATER_BOOTSTRAP_TASK_INVALID"},
    ]
    assert record["queries"] == ["AI-Drawing Worker Updater"] * 4


@pytest.mark.skipif(os.name != "nt", reason="Windows staging contract requires Windows")
def test_updater_bootstrap_deployment_staging_requires_structural_files(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    (staging / "updater").mkdir(parents=True)
    for relative in ("__init__.py", "cli.py", "runtime.py", "windows_runtime.py"):
        (staging / "updater" / relative).write_text("fixture\n", encoding="utf-8")
    (staging / "UpdaterBootstrap.ps1").write_text("fixture\n", encoding="utf-8")

    result = _run_updater_bootstrap_harness(
        tmp_path,
        f"Assert-UpdaterBootstrapStageStructure -StagingPath {_ps_quote(staging)}",
    )

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_STAGE_INVALID" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows staging adapter requires Windows")
def test_updater_bootstrap_deployment_staging_adapter_enforces_structure(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "incomplete staging"
    staging.mkdir()
    body = f"""
$Adapter = Get-ProductionUpdaterBootstrapAdapter
& $Adapter.ValidateStage {_ps_quote(staging)}
"""

    result = _run_updater_bootstrap_harness(tmp_path, body)

    assert result.returncode != 0
    assert "UPDATER_BOOTSTRAP_STAGE_INVALID" in result.stderr


def _run_worker_root_harness(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    helper = repo / "worker" / "windows" / "WorkerRoot.ps1"
    harness = tmp_path / "worker-root-harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". {_ps_quote(helper)}\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows root contract requires Windows")
def test_direct_d_root_accepts_only_the_canonical_install_path(tmp_path: Path) -> None:
    accepted = _run_worker_root_harness(
        tmp_path,
        "Resolve-WorkerInstallRoot -Path 'D:\\code\\AI-Drawing-Worker'",
    )
    assert accepted.returncode == 0, accepted.stderr
    assert accepted.stdout.strip().casefold() == r"D:\code\AI-Drawing-Worker".casefold()

    for invalid in (
        r"AI-Drawing-Worker",
        r"\\server\share\AI-Drawing-Worker",
        "D:\\",
        r"D:\code\ai-drawing",
        "D:\\code\\AI-Drawing-Worker ",
        r"C:\AI-Drawing-Worker",
    ):
        rejected = _run_worker_root_harness(
            tmp_path,
            f"Resolve-WorkerInstallRoot -Path {_ps_quote(invalid)} | Out-Null",
        )
        assert rejected.returncode != 0, invalid


@pytest.mark.skipif(os.name != "nt", reason="Windows root contract requires Windows")
def test_direct_d_root_rejects_a_reparse_parent_without_following_it(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    link = tmp_path / "link"
    outside.mkdir()
    created = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", f"New-Item -ItemType Junction -Path {_ps_quote(link)} -Target {_ps_quote(outside)} | Out-Null"],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip(created.stderr)
    result = _run_worker_root_harness(
        tmp_path,
        f"Assert-WorkerInstallParentNoReparse -Path {_ps_quote(link / 'worker')} | Out-Null",
    )
    assert result.returncode != 0
    assert "WORKER_ROOT_REPARSE" in result.stderr


def test_clean_install_cleanup_is_plan_hashed_and_fixed_scope() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "worker/windows/Clean-Install-Worker.ps1").read_text(encoding="utf-8")

    for path in (
        r"C:\AI-Drawing-Worker",
        r"C:\AI-Drawing-Worker-Source",
        r"C:\ProgramData\AI-Drawing-Worker",
        r"D:\code\AI-Drawing-Worker",
        r"D:\code\AI-Drawing-Worker-Source",
    ):
        assert path in script
    assert "D:\\code\\ai-drawing" in script
    assert "Get-CleanInstallDeletionPlan" in script
    assert "Invoke-CleanInstallDeletion" in script
    assert "ExpectedPlanSha256" in script
    assert "CLEAN_INSTALL_PLAN_MISMATCH" in script
    assert '$AuthorizationRecords = @($Sorted | ForEach-Object { [pscustomobject]@{ path = $_.path; kind = $_.kind } })' in script
    assert "AI-Drawing-NVIDIA-Worker-fixed-*" in script
    assert "Remove-Item -LiteralPath" in script
    assert "Remove-Item -Path" not in script
    assert '"AI-Drawing Worker One-Click Restart"' in script


def test_direct_d_installer_derives_managed_paths_from_the_validated_root() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")

    assert "param(" in installer
    assert "[string]$Root" in installer
    assert '. (Join-Path $Source "WorkerRoot.ps1")' in installer
    assert "$Root = Resolve-WorkerInstallRoot -Path $Root" in installer
    assert '$SourceRepositoryRoot = "D:\\code\\AI-Drawing-Worker-Source"' in installer
    assert '$SourceRepositoryRoot = Join-Path $Root "source"' not in installer
    assert 'Get-PSDrive -Name ([IO.Path]::GetPathRoot($Root).Substring(0, 1))' in installer
    assert 'C:\\AI-Drawing-Worker"' not in installer
    assert 'C:\\AI-Drawing-Worker-Source' not in installer


def test_direct_d_installer_does_not_prompt_for_dhcp_or_open_the_router() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")

    assert "reserve this Worker IP" not in installer
    assert "Router page" not in installer
    assert 'Start-Process "http://$Gateway"' not in installer


def test_direct_d_installer_can_force_a_new_worker_token_without_printing_it() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")

    assert "[switch]$GenerateNewToken" in installer
    assert "if (-not $GenerateNewToken -and (Test-Path $ExistingConfigPath))" in installer
    assert "RandomNumberGenerator" in installer
    assert 'Write-Host $Token' not in installer
    assert 'Write-Output $Token' not in installer


def test_direct_d_setup_never_invokes_migration_and_rotates_only_before_config_exists() -> None:
    repo = Path(__file__).resolve().parents[2]
    root = repo / "worker/windows"
    cmd = (root / "Setup-D.cmd").read_text(encoding="utf-8")
    setup = (root / "Setup-D.ps1").read_text(encoding="utf-8")

    assert "Setup-D.ps1" in cmd
    assert "Migrate-Worker" not in cmd + setup
    assert 'D:\\code\\AI-Drawing-Worker' in setup
    assert 'Test-Path -LiteralPath (Join-Path $Root "config\\worker.json")' in setup
    assert "GenerateNewToken" in setup
    assert "Install-Worker.ps1" in setup


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
        "WorkerRoot.ps1",
        "Clean-Install-Worker.ps1",
        "Setup-D.ps1",
        "Setup-D.cmd",
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


def test_restart_management_artifacts_are_fixed_and_distributed() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    dist = repo / "dist" / "AI-Drawing-NVIDIA-Worker"
    names = ("restart_contract.py", "Restart-Worker.ps1", "Wait-Restart-Result.ps1", "Restart-Worker.cmd")
    for name in names:
        assert (source / name).is_file()
        assert (dist / name).read_bytes() == (source / name).read_bytes()

    launcher = (source / "Restart-Worker.cmd").read_text(encoding="utf-8")
    assert "AI-Drawing NVIDIA Worker Restart" in launcher
    assert "%*" not in launcher and "%1" not in launcher
    restart = (source / "Restart-Worker.ps1").read_text(encoding="utf-8")
    wait_restart = (source / "Wait-Restart-Result.ps1").read_text(encoding="utf-8")
    for marker in (
        "FileMode]::OpenOrCreate", "FileShare]::None", "8188, 8791", "Get-NetTCPConnection",
        "Start-Worker.ps1", "/system_stats", "/v1/worker/status",
        "/v1/workflows/preflight", "TaskTimeoutSeconds", "request_id",
        "Move-Item", "Select-Object -Skip 5",
    ):
        assert marker in restart
    assert "NVIDIA_WORKER_TOKEN" not in restart
    for script in (restart, wait_restart):
        assert "$Parts = $Line -split '=', 2" in script
        assert ".Split(@('='), 2)" not in script


def test_installer_registers_fixed_restart_task_and_desktop_launcher() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text(encoding="utf-8")
    assert '"AI-Drawing NVIDIA Worker Restart"' in installer
    assert "Restart-Worker.ps1" in installer
    assert "Wait-Restart-Result.ps1" in installer
    assert "一鍵重啟 AI-Drawing Worker.cmd" in installer
    assert "New-ScheduledTaskAction" in installer
    assert "-RunLevel Highest" in installer
    assert "-Trigger" not in installer[installer.index("$RestartTaskAction") :]


def test_start_worker_uses_bounded_curl_comfy_readiness_probe() -> None:
    repo = Path(__file__).resolve().parents[2]
    launcher = (repo / "worker/windows/Start-Worker.ps1").read_text(encoding="utf-8")

    assert 'for ($Attempt = 0; $Attempt -lt 300; $Attempt++)' in launcher
    assert 'curl.exe --silent --fail --max-time 2 --output NUL "http://127.0.0.1:8188/system_stats"' in launcher
    assert "show-error" not in launcher
    assert "if ($LASTEXITCODE -eq 0)" in launcher
    assert 'Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8188/system_stats"' not in launcher
    assert 'Invoke-RestMethod "http://127.0.0.1:8188/system_stats"' not in launcher


def test_start_worker_cmd_persists_scheduled_launcher_output() -> None:
    repo = Path(__file__).resolve().parents[2]
    launcher = (repo / "worker/windows/Start-Worker.cmd").read_text(encoding="utf-8")

    assert 'if not exist "%~dp0shared\\logs" mkdir "%~dp0shared\\logs"' in launcher
    assert 'launcher.stdout.log' in launcher
    assert 'launcher.stderr.log' in launcher


def test_start_worker_exposes_root_updater_package_to_worker_runtime() -> None:
    repo = Path(__file__).resolve().parents[2]
    launcher = (repo / "worker/windows/Start-Worker.ps1").read_text(encoding="utf-8")

    assert '[Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")' in launcher
    assert '$env:PYTHONPATH = $Root' in launcher
    assert "[IO.Path]::PathSeparator" in launcher


def test_distribution_zip_uses_canonical_names_and_exact_source_bytes() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    archive = repo / "dist" / "AI-Drawing-NVIDIA-Worker.zip"
    with zipfile.ZipFile(archive) as package:
        assert all("\\\\" not in name for name in package.namelist())
        for path in source.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                name = path.relative_to(source).as_posix()
                assert package.read(name) == path.read_bytes()


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
def test_migration_inventory_skips_only_verified_managed_runtime_junctions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "worker"
    release = root / "releases" / MIGRATION_COMMIT
    shared_models = root / "shared" / "models"
    config = root / "config" / "worker.json"
    release.mkdir(parents=True)
    shared_models.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"token": "secret"}), encoding="utf-8")
    (release / "source-commit.txt").write_text(MIGRATION_COMMIT + "\n", encoding="utf-8")
    (release / ".managed-release.json").write_text(
        json.dumps({"schema": 1, "commit": MIGRATION_COMMIT}), encoding="utf-8"
    )
    (release / "ComfyUI").mkdir()
    body = f"""
New-Item -ItemType Junction -Path {_ps_quote(release / 'ComfyUI' / 'models')} -Target {_ps_quote(shared_models)} | Out-Null
New-Item -ItemType Junction -Path {_ps_quote(root / 'current')} -Target {_ps_quote(release)} | Out-Null
Get-MigrationInventory -Root {_ps_quote(root)} -ConfigPath {_ps_quote(config)} | ConvertTo-Json -Depth 8 -Compress
"""

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    inventory = json.loads(result.stdout)
    assert "current" not in inventory["file_digests"]
    assert all(not path.startswith("releases/") for path in inventory["file_digests"])
    assert "config/worker.json" in inventory["file_digests"]


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


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_installed_migration_asset_keeps_updater_on_c_until_transaction_switch(
    tmp_path: Path,
) -> None:
    program_data = tmp_path / "ProgramData"
    config_root = program_data / "AI-Drawing-Worker"
    config_root.mkdir(parents=True)
    updater_path = config_root / "updater.env"
    updater_bytes = (
        "AI_DRAWING_PROJECT_ROOT=D:\\code\\ai-drawing\r\n"
        "AI_DRAWING_WORKER_ROOT=C:\\AI-Drawing-Worker\r\n"
        "AI_DRAWING_WORKER_REMOTE=origin\r\n"
        "AI_DRAWING_WORKER_BRANCH=main\r\n"
    ).encode()
    updater_path.write_bytes(updater_bytes)
    body = """
Install-FixedMigrationEnvironment -ProgramDataRoot $script:MigrationProgramDataRoot
$Context = Get-ProductionMigrationContext
[pscustomobject]@{
  source_root=$Context.source_root
  target_root=$Context.target_root
  updater_sha256=(Get-MigrationSha256 -Path $script:MigrationEnvironmentPath)
  migration_text=[IO.File]::ReadAllText((Join-Path $script:MigrationProgramDataRoot 'migration.env'))
} | ConvertTo-Json -Compress
"""

    result = _run_migration_harness(
        tmp_path, body, environment={"ProgramData": str(program_data)}
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["source_root"] == r"C:\AI-Drawing-Worker"
    assert record["target_root"] == r"D:\code\AI-Drawing-Worker"
    assert record["updater_sha256"] == hashlib.sha256(updater_bytes).hexdigest()
    assert record["migration_text"] == (
        "AI_DRAWING_WORKER_MIGRATION_TARGET=D:\\code\\AI-Drawing-Worker\r\n"
    )


def test_migration_main_bootstraps_legacy_install_before_reading_context() -> None:
    repo = Path(__file__).resolve().parents[2]
    text = (repo / "worker" / "windows" / "Migrate-Worker.ps1").read_text()

    bootstrap = text.index("function Initialize-ProductionMigrationPrerequisites")
    main = text.index("function Invoke-MigrationMain")
    bootstrap_call = text.index("Initialize-ProductionMigrationPrerequisites", main)
    context_call = text.index("Get-ProductionMigrationContext", main)

    assert bootstrap < main < bootstrap_call < context_call
    assert "AI_DRAWING_PROJECT_ROOT" in text[bootstrap:main]
    assert "AI-Drawing Worker Updater" in text[bootstrap:main]
    assert "New-SecureUpdaterDirectory" in text[bootstrap:main]


def _migration_adapter_script(
    source: Path,
    target: Path,
    *,
    fail_mode: str = "",
    ready_after: int = 1,
    clock_step_ms: int = 120_000,
    verify_real_acl: bool = False,
) -> str:
    verify_real_acl_literal = "$true" if verify_real_acl else "$false"
    return f"""
$Events = New-Object 'System.Collections.Generic.List[string]'
$SourceRoot = {_ps_quote(source)}
$TargetRoot = {_ps_quote(target)}
$FailMode = {_ps_quote(fail_mode)}
$ReadyAfter = {ready_after}
$ClockStepMs = {clock_step_ms}
$VerifyRealAcl = {verify_real_acl_literal}
$Clock = @{{ now=[int64]0 }}
$HealthAttempts = @{{}}
$HealthCallTimeouts = New-Object 'System.Collections.Generic.List[int]'
$HealthWaits = New-Object 'System.Collections.Generic.List[int]'
$TaskState = [ordered]@{{
  worker=[ordered]@{{ action='legacy-worker'; principal='interactive-highest'; settings='login' }}
  updater=[ordered]@{{ action='programdata-bootstrap'; principal='system-highest'; settings='ignore-new' }}
  restart=[ordered]@{{ action='legacy-restart'; principal='interactive-highest'; settings='on-demand' }}
}}
$InitialTaskStateJson = $TaskState | ConvertTo-Json -Depth 8 -Compress
$Adapter = @{{
  GetSourceInventory = {{
    param($Root, $ConfigPath)
    $Events.Add('inventory-source')
    return Get-MigrationInventory -Root $Root -ConfigPath $ConfigPath
  }}
  GetFreeBytes = {{ param($Root) $Events.Add('get-free-bytes'); [int64]1TB }}
  InitializeTarget = {{
    param($Root)
    $Events.Add('initialize-target')
    if (-not [IO.Directory]::Exists($Root)) {{ [IO.Directory]::CreateDirectory($Root) | Out-Null }}
  }}
  AssertSecureTarget = {{
    param($Root)
    $Events.Add('verify-secure-target')
    if ($VerifyRealAcl) {{
      $AllowedSids = @('S-1-5-18', 'S-1-5-32-544')
      $InsecurePaths = New-Object 'System.Collections.Generic.List[string]'
      foreach ($File in @(Get-MigrationTreeNoFollow -Root $Root)) {{
        $Relative = $File.FullName.Substring($Root.TrimEnd('\\').Length).TrimStart('\\').Replace('\\', '/')
        $Events.Add('acl-check:' + $Relative)
        $Acl = Get-Acl -LiteralPath $File.FullName -ErrorAction Stop
        $Owner = $Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        $Rules = @($Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        $BadRules = @($Rules | Where-Object {{
          $AllowedSids -notcontains $_.IdentityReference.Value -or
          $_.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
          ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne [Security.AccessControl.FileSystemRights]::FullControl
        }})
        if ($Owner -ne 'S-1-5-18' -or $Rules.Count -eq 0 -or $BadRules.Count -gt 0) {{
          $InsecurePaths.Add($Relative)
        }}
      }}
      if ($InsecurePaths.Count -gt 0) {{ throw 'MIGRATION_TARGET_SECURITY_INVALID' }}
    }}
  }}
  GetMonotonicMilliseconds = {{ [int64]$Clock.now }}
  WaitForHealthRetry = {{
    param($Milliseconds)
    $HealthWaits.Add([int]$Milliseconds)
    $Clock.now += [Math]::Max([int64]$Milliseconds, [int64]$ClockStepMs)
  }}
  ProtectTarget = {{ param($Root) $Events.Add('protect-target') }}
  CaptureSwitchState = {{
    param($Path)
    $Events.Add('capture-switch')
    return @{{ environment_bytes=[IO.File]::ReadAllBytes($Path); task_json=$InitialTaskStateJson }}
  }}
  RestoreSwitchState = {{
    param($State)
    [IO.File]::WriteAllBytes($EnvironmentPath, [byte[]]$State.environment_bytes)
    $Restored = $State.task_json | ConvertFrom-Json
    foreach ($Name in @('worker', 'updater', 'restart')) {{
      $TaskState[$Name]['action'] = [string]$Restored.$Name.action
      $TaskState[$Name]['principal'] = [string]$Restored.$Name.principal
      $TaskState[$Name]['settings'] = [string]$Restored.$Name.settings
    }}
    $Events.Add('restore-switch')
  }}
  SwitchTaskActions = {{
    param($Root)
    if ($FailMode -eq 'after-env') {{ throw 'injected switch failure after env' }}
    $Index = 0
    foreach ($Name in @('worker', 'updater', 'restart')) {{
      $Index += 1
      $TaskState[$Name]['action'] = 'managed-' + $Name
      $TaskState[$Name]['principal'] = 'changed-' + $Name
      $TaskState[$Name]['settings'] = 'changed-' + $Name
      $Events.Add('switch-task:' + $Name)
      if ($FailMode -eq ('after-task' + $Index)) {{ throw 'injected partial task switch' }}
    }}
    $Events.Add('switch-tasks:' + [IO.Path]::GetFileName($Root))
  }}
  StopWorker = {{ param($Root) $Events.Add('stop:' + [IO.Path]::GetFileName($Root)) }}
  StartWorker = {{
    param($Root)
    $Configured = (Read-FixedMigrationEnvironment -Path $EnvironmentPath).AI_DRAWING_WORKER_ROOT
    $Events.Add('start:' + [IO.Path]::GetFileName($Root) + ':env=' + [IO.Path]::GetFileName($Configured))
  }}
  ValidateWorker = {{
    param($Root, $Mode, $ExpectedCommit, $ExpectedTokenHash, $CallTimeoutSeconds)
    $HealthCallTimeouts.Add([int]$CallTimeoutSeconds)
    if (-not $HealthAttempts.ContainsKey($Mode)) {{ $HealthAttempts[$Mode] = 0 }}
    $HealthAttempts[$Mode] += 1
    if ($Mode -eq 'staged') {{
      $Configured = (Read-FixedMigrationEnvironment -Path $EnvironmentPath).AI_DRAWING_WORKER_ROOT
      if ($Configured -ne $SourceRoot) {{ throw 'staged validation observed an early env switch' }}
      if (-not (Test-Path -LiteralPath (Join-Path $TargetRoot ('releases\\' + $ExpectedCommit + '\\worker\\windows\\worker.py')))) {{
        throw 'staged release was not copied first'
      }}
    }}
    $Events.Add('health:' + $Mode)
    $RequiredAttempts = $(if ($Mode -eq 'staged') {{ 1 }} else {{ $ReadyAfter }})
    $Healthy = $Mode -ne $FailMode -and $HealthAttempts[$Mode] -ge $RequiredAttempts
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
    assert events.index("initialize-target") < events.index("verify-secure-target")
    assert events.index("verify-secure-target") < events.index("inventory-source")
    assert events.index("inventory-source") < events.index("get-free-bytes")
    assert events.index("get-free-bytes") < events.index("capture-switch")
    assert events.index("verify-secure-target") < events.index("protect-target")
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
    assert events.index("restore-switch") < events.index(
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


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
@pytest.mark.parametrize("fail_mode", ["after-env", "after-task1", "after-task2", "after-task3"])
def test_each_partial_switch_failure_restores_exact_env_and_complete_task_state(
    tmp_path: Path, fail_mode: str
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    source_before = _tree_snapshot(source)
    environment_before = environment_path.read_bytes()
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(source, target, fail_mode=fail_mode)
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{
  result=$Result
  environment_base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($EnvironmentPath))
  task_json=($TaskState | ConvertTo-Json -Depth 8 -Compress)
  initial_task_json=$InitialTaskStateJson
  events=$Events
}} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert record["environment_base64"] == base64.b64encode(environment_before).decode()
    assert json.loads(record["task_json"]) == json.loads(record["initial_task_json"])
    assert record["events"].count("restore-switch") == 1
    assert source.is_dir()
    assert _tree_snapshot(source) == source_before


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_production_health_polls_until_delayed_worker_is_ready_without_real_sleep(
    tmp_path: Path,
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(
            source, target, ready_after=3, clock_step_ms=1_000
        )
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{
  result=$Result
  attempts=$HealthAttempts
  call_timeouts=$HealthCallTimeouts
  waits=$HealthWaits
}} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "ready"
    assert record["attempts"]["production-before-backup"] == 3
    assert record["attempts"]["production-after-backup"] == 3
    assert len(record["waits"]) == 4
    assert all(0 < timeout <= 10 for timeout in record["call_timeouts"])


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_production_health_deadline_rolls_back_with_bounded_calls_without_real_sleep(
    tmp_path: Path,
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(
            source,
            target,
            fail_mode="production-before-backup",
            clock_step_ms=60_000,
        )
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{
  result=$Result
  attempts=$HealthAttempts
  call_timeouts=$HealthCallTimeouts
  waits=$HealthWaits
  elapsed_ms=$Clock.now
}} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "rolled_back"
    assert record["result"]["error_code"] == "MIGRATION_HEALTH_FAILED"
    assert record["attempts"]["production-before-backup"] >= 2
    assert record["elapsed_ms"] >= 120_000
    assert record["waits"]
    assert all(0 < timeout <= 10 for timeout in record["call_timeouts"])


def _create_temp_junction(link: Path, target: Path) -> None:
    created = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"New-Item -ItemType Junction -Path {_ps_quote(link)} "
            f"-Target {_ps_quote(target)} | Out-Null",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_target_ancestor_junction_fails_before_initialize_or_external_mutation(
    tmp_path: Path,
) -> None:
    source, _unused_target, environment_path, _token = _migration_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("external", encoding="utf-8")
    redirected_parent = tmp_path / "redirected-parent"
    _create_temp_junction(redirected_parent, outside)
    target = redirected_parent / "managed-worker"
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

    assert result.returncode != 0 or json.loads(result.stdout)["result"]["error_code"] == "MIGRATION_REPARSE_POINT"
    if result.stdout:
        assert "initialize-target" not in json.loads(result.stdout)["events"]
    assert sentinel.read_text(encoding="utf-8") == "external"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"]


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration requires Windows")
def test_existing_target_acl_is_verified_before_inventory_copy_or_mutation(
    tmp_path: Path,
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    target.mkdir()
    (target / ".ai-drawing-worker-owned").write_text(
        "AI-Drawing NVIDIA Worker\n", encoding="utf-8"
    )
    for relative in (
        "releases/permissive.txt",
        "shared/permissive.txt",
        "unknown/permissive.txt",
    ):
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_sentinel = outside / "sentinel.txt"
    outside_sentinel.write_text("external", encoding="utf-8")
    source_before = _tree_snapshot(source)
    target_before = _tree_snapshot(target)
    target_directories_before = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_dir()
    }
    body = (
        f"$EnvironmentPath = {_ps_quote(environment_path)}\n"
        + _migration_adapter_script(source, target, verify_real_acl=True)
        + f"""
$Result = Invoke-WorkerMigrationTransaction -SourceRoot $SourceRoot -TargetRoot $TargetRoot `
  -EnvironmentPath $EnvironmentPath -Commit '{MIGRATION_COMMIT}' -Adapter $Adapter -ReserveBytes 1
[pscustomobject]@{{ result=$Result; events=$Events }} | ConvertTo-Json -Depth 8 -Compress
"""
    )

    result = _run_migration_harness(tmp_path, body)

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["result"]["status"] == "failed_before_switch"
    assert record["result"]["error_code"] == "MIGRATION_TARGET_SECURITY_INVALID"
    assert record["events"][:2] == ["initialize-target", "verify-secure-target"]
    checked_paths = {
        event.removeprefix("acl-check:")
        for event in record["events"]
        if event.startswith("acl-check:")
    }
    assert {
        "releases/permissive.txt",
        "shared/permissive.txt",
        "unknown/permissive.txt",
    } <= checked_paths
    assert "inventory-source" not in record["events"]
    assert "get-free-bytes" not in record["events"]
    assert "capture-switch" not in record["events"]
    assert "protect-target" not in record["events"]
    assert _tree_snapshot(source) == source_before
    assert _tree_snapshot(target) == target_before
    assert {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_dir()
    } == target_directories_before
    assert outside_sentinel.read_text(encoding="utf-8") == "external"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"]


@pytest.mark.skipif(os.name != "nt", reason="PowerShell migration contract requires Windows")
def test_preexisting_target_tree_junction_fails_before_copying_external_sentinel(
    tmp_path: Path,
) -> None:
    source, target, environment_path, _token = _migration_fixture(tmp_path)
    target.mkdir()
    (target / ".ai-drawing-worker-owned").write_text(
        "AI-Drawing NVIDIA Worker\n", encoding="utf-8"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("external", encoding="utf-8")
    _create_temp_junction(target / "escape", outside)
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

    assert result.returncode != 0 or json.loads(result.stdout)["result"]["error_code"] == "MIGRATION_REPARSE_POINT"
    assert sentinel.read_text(encoding="utf-8") == "external"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"]
    assert not (target / "releases").exists()


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

    for name in ("Start-Worker.ps1", "Start-Worker.cmd", "WorkerPaths.ps1"):
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
