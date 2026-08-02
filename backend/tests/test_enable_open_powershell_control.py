from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPOSITORY_ROOT
    / "worker"
    / "windows"
    / "Enable-Open-PowerShell-Control.ps1"
)


def _script_text() -> str:
    assert SCRIPT.is_file(), f"deployment script is missing: {SCRIPT}"
    return SCRIPT.read_text(encoding="utf-8")


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def test_deployment_requires_an_elevated_administrator_process() -> None:
    """Removing the current-principal Administrator guard must fail this test."""
    script = _script_text()

    assert "[Security.Principal.WindowsIdentity]::GetCurrent()" in script
    assert "Security.Principal.WindowsPrincipal" in script
    assert ".IsInRole(" in script
    assert "[Security.Principal.WindowsBuiltInRole]::Administrator" in script
    assert "ADMINISTRATOR_REQUIRED" in script


def test_deployment_has_fixed_direct_d_drive_roots_and_commit_parameter() -> None:
    """Changing the one-time source or installed runtime boundary must fail."""
    script = _script_text()

    assert '[ValidatePattern(\'^[0-9a-fA-F]{40}$\')]' in script
    assert "[string]$ExpectedCommit" in script
    assert '$SourceWindowsRoot = "D:\\code\\ai-drawing\\worker\\windows"' in script
    assert '$InstalledWorkerRoot = "D:\\code\\AI-Drawing-Worker"' in script
    assert 'Join-Path $InstalledWorkerRoot "current\\worker\\windows"' in script


def test_deployment_fetches_and_requires_head_origin_main_and_expected_commit() -> None:
    """Dropping either requested version check must fail this test."""
    script = _script_text()

    assert "git.exe -C $RepositoryRoot fetch origin main" in script
    assert "git.exe -C $RepositoryRoot rev-parse HEAD" in script
    assert "git.exe -C $RepositoryRoot rev-parse origin/main" in script
    assert "$HeadCommit -ne $OriginMainCommit" in script
    assert "$HeadCommit -ne $ExpectedCommit" in script
    assert "$OriginMainCommit -ne $ExpectedCommit" in script


def test_deployment_stops_and_starts_only_the_existing_worker_task() -> None:
    """Targeting another scheduled task must fail this test."""
    script = _script_text()

    assert '$TaskName = "AI-Drawing NVIDIA Worker"' in script
    assert "AI-Drawing NVIDIA Worker Restart" not in script
    task_actions = re.findall(
        r"(?im)^\s*(?:Stop|Start)-ScheduledTask\b[^\r\n]*", script
    )
    assert len(task_actions) == 2
    assert any(line.lstrip().startswith("Stop-ScheduledTask") for line in task_actions)
    assert any(line.lstrip().startswith("Start-ScheduledTask") for line in task_actions)
    assert all("-TaskName $TaskName" in line for line in task_actions)


def test_deployment_copies_only_the_two_control_runtime_files_directly() -> None:
    """Staging or omitting either direct runtime copy must fail this test."""
    script = _script_text()

    copy_lines = re.findall(r"(?im)^\s*Copy-Item\b[^\r\n]*", script)
    assert len(copy_lines) == 2
    assert all("-LiteralPath" in line and "-Force" in line for line in copy_lines)
    assert any(
        'Join-Path $SourceWindowsRoot "worker.py"' in line
        and 'Join-Path $InstalledWindowsRoot "worker.py"' in line
        for line in copy_lines
    )
    assert any(
        'Join-Path $SourceWindowsRoot "powershell_control.py"' in line
        and 'Join-Path $InstalledWindowsRoot "powershell_control.py"' in line
        for line in copy_lines
    )


def test_deployment_stops_only_port_8791_listeners() -> None:
    """Touching ComfyUI or selecting a non-listener process must fail this test."""
    script = _script_text()

    listener_queries = re.findall(
        r"Get-NetTCPConnection\s+-State\s+Listen\s+-LocalPort\s+(\d+)", script
    )
    assert len(listener_queries) >= 2
    assert set(listener_queries) == {"8791"}
    assert "Select-Object -ExpandProperty OwningProcess -Unique" in script
    assert "Stop-Process -Id $ListenerPid" in script
    assert "8188" not in script


def test_deployment_waits_for_the_worker_listener_and_reports_readiness() -> None:
    """Returning before the 8791 listener appears must fail this test."""
    script = _script_text()

    assert ".AddSeconds(60)" in script
    assert "OPEN_POWERSHELL_CONTROL_READY" in script
    assert "WORKER_8791_NOT_LISTENING" in script
    assert "exit 0" in script


def test_deployment_excludes_broader_security_update_and_recovery_machinery() -> None:
    """Reintroducing out-of-scope deployment machinery must fail this test."""
    script = _script_text().casefold()
    forbidden = (
        "get-filehash",
        "sha256",
        "assert-secure",
        "set-secure",
        "get-acl",
        "set-acl",
        "owner",
        "releases",
        "resources/plan",
        "workflows/preflight",
        "worker/status",
        "deploy-updaterbootstrap",
        "migrate-worker",
        "invoke-restmethod",
        "invoke-webrequest",
        "new-netfirewallrule",
        "remove-netfirewallrule",
        "remove-item",
    )

    for unexpected in forbidden:
        assert unexpected not in script


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_parses_with_windows_powershell_51_scriptblock_create() -> None:
    """PowerShell syntax newer than Windows PowerShell 5.1 must fail this test."""
    _script_text()
    powershell = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    command = f"""
$ErrorActionPreference = "Stop"
$Version = $PSVersionTable.PSVersion
if ($PSVersionTable.PSEdition -ne "Desktop" -or $Version.Major -ne 5 -or $Version.Minor -ne 1) {{
    throw "Expected Windows PowerShell Desktop 5.1, got $($PSVersionTable.PSEdition) $Version"
}}
$Source = Get-Content -LiteralPath {_ps_quote(SCRIPT)} -Raw -Encoding UTF8
[void][scriptblock]::Create($Source)
"5.1 Desktop; parsed Enable-Open-PowerShell-Control.ps1"
"""

    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.stdout.strip() == (
        "5.1 Desktop; parsed Enable-Open-PowerShell-Control.ps1"
    )
