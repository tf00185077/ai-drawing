from __future__ import annotations

from collections import Counter
import json
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


def _powershell_51() -> Path:
    return (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )


def _run_powershell_51_parser(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(_powershell_51()),
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


def _deployment_ast_summary(script: Path = SCRIPT) -> dict[str, object]:
    command = f"""
$ErrorActionPreference = "Stop"
$Tokens = $null
$ParseErrors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile(
    {_ps_quote(script)}, [ref]$Tokens, [ref]$ParseErrors
)
if ($ParseErrors.Count -ne 0) {{
    throw ($ParseErrors | ForEach-Object {{ $_.Message }} | Out-String)
}}
$CommandAsts = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.CommandAst]
}}, $true))
$CommandNames = @($CommandAsts | ForEach-Object {{ $_.GetCommandName() }})
$CommandShapes = @($CommandAsts | ForEach-Object {{
    [pscustomobject]@{{
        name = $_.GetCommandName()
        elements = @($_.CommandElements | ForEach-Object {{ $_.Extent.Text }})
    }}
}})
$AssignmentAsts = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.AssignmentStatementAst]
}}, $true))
$AssignmentTargets = @($AssignmentAsts | ForEach-Object {{ $_.Left.Extent.Text }})
$AssignmentShapes = @($AssignmentAsts | ForEach-Object {{
    $Assignment = $_
    $RightCommands = @($Assignment.Right.FindAll({{
        param($Node)
        $Node -is [Management.Automation.Language.CommandAst]
    }}, $true))
    $RightPipelines = @($Assignment.Right.FindAll({{
        param($Node)
        $Node -is [Management.Automation.Language.PipelineAst]
    }}, $true))
    [pscustomobject]@{{
        target = $Assignment.Left.Extent.Text
        rhs_type = $Assignment.Right.GetType().Name
        rhs_expression_type = $(
            if ($Assignment.Right -is [Management.Automation.Language.CommandExpressionAst]) {{
                $Assignment.Right.Expression.GetType().Name
            }} else {{
                $null
            }}
        )
        rhs_text = $Assignment.Right.Extent.Text
        rhs_pipeline_count = $RightPipelines.Count
        rhs_pipeline_elements = @($RightPipelines | ForEach-Object {{
            $_.PipelineElements | ForEach-Object {{
                if ($_ -is [Management.Automation.Language.CommandAst]) {{
                    $_.GetCommandName()
                }} else {{
                    $_.GetType().Name
                }}
            }}
        }})
        rhs_commands = @($RightCommands | ForEach-Object {{
            [pscustomobject]@{{
                name = $_.GetCommandName()
                elements = @($_.CommandElements | ForEach-Object {{ $_.Extent.Text }})
            }}
        }})
    }}
}})
$ForEachAsts = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.ForEachStatementAst]
}}, $true))
$ForEachShapes = @($ForEachAsts | ForEach-Object {{
    $BodyAssignments = @($_.Body.FindAll({{
        param($Node)
        $Node -is [Management.Automation.Language.AssignmentStatementAst]
    }}, $true))
    $BodyCommands = @($_.Body.FindAll({{
        param($Node)
        $Node -is [Management.Automation.Language.CommandAst]
    }}, $true))
    [pscustomobject]@{{
        variable = $_.Variable.Extent.Text
        condition = $_.Condition.Extent.Text
        body_assignment_targets = @($BodyAssignments | ForEach-Object {{
            $_.Left.Extent.Text
        }})
        body_commands = @($BodyCommands | ForEach-Object {{
            [pscustomobject]@{{
                name = $_.GetCommandName()
                elements = @($_.CommandElements | ForEach-Object {{ $_.Extent.Text }})
            }}
        }})
    }}
}})
$ParameterNames = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.ParameterAst]
}}, $true) | ForEach-Object {{ $_.Name.Extent.Text }})
$ListenerVariableUses = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.VariableExpressionAst]
}}, $true) | Where-Object {{
    $_.VariablePath.UserPath -imatch
        '^(?:(?:global|local|private|script):)?ListenerPids?$'
}} | ForEach-Object {{
    $Variable = $_
    $Parent = $Variable.Parent
    $Grandparent = $(if ($null -ne $Parent) {{ $Parent.Parent }} else {{ $null }})
    $GreatGrandparent = $(
        if ($null -ne $Grandparent) {{ $Grandparent.Parent }} else {{ $null }}
    )
    $IsStopProcessIdArgument = $false
    if ($Parent -is [Management.Automation.Language.CommandAst]) {{
        $Elements = @($Parent.CommandElements)
        $IsStopProcessIdArgument = (
            $Parent.GetCommandName() -eq "Stop-Process" -and
            $Elements.Count -eq 6 -and
            $Elements[1] -is [Management.Automation.Language.CommandParameterAst] -and
            $Elements[1].ParameterName -eq "Id" -and
            [object]::ReferenceEquals($Elements[2], $Variable)
        )
    }}
    [pscustomobject]@{{
        name = $Variable.VariablePath.UserPath
        text = $Variable.Extent.Text
        parent_type = $(
            if ($null -ne $Parent) {{ $Parent.GetType().Name }} else {{ $null }}
        )
        grandparent_type = $(
            if ($null -ne $Grandparent) {{ $Grandparent.GetType().Name }} else {{ $null }}
        )
        great_grandparent_type = $(
            if ($null -ne $GreatGrandparent) {{
                $GreatGrandparent.GetType().Name
            }} else {{
                $null
            }}
        )
        is_assignment_target = (
            $Parent -is [Management.Automation.Language.AssignmentStatementAst] -and
            [object]::ReferenceEquals($Parent.Left, $Variable)
        )
        is_foreach_variable = (
            $Parent -is [Management.Automation.Language.ForEachStatementAst] -and
            [object]::ReferenceEquals($Parent.Variable, $Variable)
        )
        is_foreach_condition = (
            $Parent -is [Management.Automation.Language.CommandExpressionAst] -and
            $Grandparent -is [Management.Automation.Language.PipelineAst] -and
            $GreatGrandparent -is [Management.Automation.Language.ForEachStatementAst] -and
            [object]::ReferenceEquals($GreatGrandparent.Condition, $Grandparent)
        )
        is_stop_process_id_argument = $IsStopProcessIdArgument
    }}
}})
$TryStatements = @($Ast.FindAll({{
    param($Node)
    $Node -is [Management.Automation.Language.TryStatementAst]
}}, $true))
$TryData = @($TryStatements | ForEach-Object {{
    [pscustomobject]@{{
        body_commands = @($_.Body.FindAll({{
            param($Node)
            $Node -is [Management.Automation.Language.CommandAst]
        }}, $true) | ForEach-Object {{ $_.GetCommandName() }})
        finally_commands = @($_.Finally.FindAll({{
            param($Node)
            $Node -is [Management.Automation.Language.CommandAst]
        }}, $true) | ForEach-Object {{ $_.GetCommandName() }})
    }}
}})
[pscustomobject]@{{
    command_names = $CommandNames
    dynamic_command_count = @($CommandNames | Where-Object {{ $null -eq $_ }}).Count
    assignment_targets = $AssignmentTargets
    try_statements = $TryData
    listener_stop_dataflow = [pscustomobject]@{{
        assignments = $AssignmentShapes
        commands = $CommandShapes
        foreach_statements = $ForEachShapes
        parameter_names = $ParameterNames
        variable_uses = $ListenerVariableUses
    }}
}} | ConvertTo-Json -Depth 5 -Compress
"""
    result = _run_powershell_51_parser(command)
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def _normalized_variable_name(value: str) -> str:
    match = re.fullmatch(
        r"\$\{?(?:(?:global|local|private|script):)?([^}]+)\}?",
        value,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"not a variable expression: {value}"
    return "$" + match.group(1).casefold()


def _assert_listener_stop_dataflow_shape(summary: dict[str, object]) -> None:
    dataflow = summary["listener_stop_dataflow"]
    assignments = dataflow["assignments"]

    def assignments_to(variable: str) -> list[dict[str, object]]:
        return [
            assignment
            for assignment in assignments
            if _normalized_variable_name(assignment["target"]) == variable.casefold()
        ]

    worker_port_assignments = assignments_to("$WorkerPort")
    assert len(worker_port_assignments) == 1
    assert worker_port_assignments[0]["rhs_type"] == "CommandExpressionAst"
    assert worker_port_assignments[0]["rhs_expression_type"] == "ConstantExpressionAst"
    assert worker_port_assignments[0]["rhs_text"] == "8791"
    assert worker_port_assignments[0]["rhs_pipeline_count"] == 0
    assert worker_port_assignments[0]["rhs_pipeline_elements"] == []
    assert worker_port_assignments[0]["rhs_commands"] == []

    listener_assignments = assignments_to("$ListenerPids")
    assert len(listener_assignments) == 1
    assert listener_assignments[0]["rhs_type"] == "CommandExpressionAst"
    assert listener_assignments[0]["rhs_expression_type"] == "ArrayExpressionAst"
    assert listener_assignments[0]["rhs_pipeline_count"] == 1
    assert listener_assignments[0]["rhs_pipeline_elements"] == [
        "Get-NetTCPConnection",
        "Select-Object",
    ]
    assert listener_assignments[0]["rhs_commands"] == [
        {
            "name": "Get-NetTCPConnection",
            "elements": "Get-NetTCPConnection -State Listen "
            "-LocalPort $WorkerPort -ErrorAction SilentlyContinue",
        },
        {
            "name": "Select-Object",
            "elements": "Select-Object -ExpandProperty OwningProcess -Unique",
        },
    ]

    assert assignments_to("$ListenerPid") == []
    assert all(
        _normalized_variable_name(name) != "$listenerpid"
        for name in dataflow["parameter_names"]
    )

    listener_loops = [
        loop
        for loop in dataflow["foreach_statements"]
        if _normalized_variable_name(loop["variable"]) == "$listenerpid"
    ]
    assert len(listener_loops) == 1
    listener_loop = listener_loops[0]
    assert _normalized_variable_name(listener_loop["condition"]) == "$listenerpids"
    assert listener_loop["body_assignment_targets"] == []
    assert listener_loop["body_commands"] == [
        {
            "name": "Stop-Process",
            "elements": "Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
        }
    ]

    listener_pids_uses = [
        use
        for use in dataflow["variable_uses"]
        if _normalized_variable_name("$" + use["name"]) == "$listenerpids"
    ]
    assert listener_pids_uses == [
        {
            "name": "ListenerPids",
            "text": "$ListenerPids",
            "parent_type": "AssignmentStatementAst",
            "grandparent_type": "StatementBlockAst",
            "great_grandparent_type": "TryStatementAst",
            "is_assignment_target": True,
            "is_foreach_variable": False,
            "is_foreach_condition": False,
            "is_stop_process_id_argument": False,
        },
        {
            "name": "ListenerPids",
            "text": "$ListenerPids",
            "parent_type": "CommandExpressionAst",
            "grandparent_type": "PipelineAst",
            "great_grandparent_type": "ForEachStatementAst",
            "is_assignment_target": False,
            "is_foreach_variable": False,
            "is_foreach_condition": True,
            "is_stop_process_id_argument": False,
        },
    ]

    listener_pid_uses = [
        use
        for use in dataflow["variable_uses"]
        if _normalized_variable_name("$" + use["name"]) == "$listenerpid"
    ]
    assert listener_pid_uses == [
        {
            "name": "ListenerPid",
            "text": "$ListenerPid",
            "parent_type": "ForEachStatementAst",
            "grandparent_type": "StatementBlockAst",
            "great_grandparent_type": "TryStatementAst",
            "is_assignment_target": False,
            "is_foreach_variable": True,
            "is_foreach_condition": False,
            "is_stop_process_id_argument": False,
        },
        {
            "name": "ListenerPid",
            "text": "$ListenerPid",
            "parent_type": "CommandAst",
            "grandparent_type": "PipelineAst",
            "great_grandparent_type": "StatementBlockAst",
            "is_assignment_target": False,
            "is_foreach_variable": False,
            "is_foreach_condition": False,
            "is_stop_process_id_argument": True,
        },
    ]

    stop_process_commands = [
        command
        for command in dataflow["commands"]
        if command["name"] == "Stop-Process"
    ]
    assert stop_process_commands == [
        {
            "name": "Stop-Process",
            "elements": [
                "Stop-Process",
                "-Id",
                "$ListenerPid",
                "-Force",
                "-ErrorAction",
                "Stop",
            ],
        }
    ]


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


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_command_ast_uses_only_the_approved_command_vocabulary() -> None:
    """Adding any executable command outside the narrow deployment must fail."""
    summary = _deployment_ast_summary()

    assert summary["dynamic_command_count"] == 0
    assert Counter(summary["command_names"]) == Counter(
        {
            "Copy-Item": 3,
            "Get-NetTCPConnection": 2,
            "Get-ScheduledTask": 1,
            "Join-Path": 10,
            "New-Object": 1,
            "Select-Object": 1,
            "Set-StrictMode": 1,
            "Start-ScheduledTask": 1,
            "Start-Sleep": 1,
            "Stop-Process": 1,
            "Stop-ScheduledTask": 1,
            "Test-Path": 4,
            "Write-Output": 1,
            "git.exe": 3,
        }
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_protected_targets_have_one_fixed_assignment() -> None:
    """Reassigning a root, task, or listener port must fail this test."""
    script = _script_text()
    summary = _deployment_ast_summary()
    protected_targets = (
        "$RepositoryRoot",
        "$SourceWindowsRoot",
        "$InstalledWorkerRoot",
        "$InstalledWindowsRoot",
        "$TaskName",
        "$WorkerPort",
    )
    normalized_assignments = [
        re.sub(
            r"^\$\{?(?:(?:global|local|private|script):)?([^}]+)\}?$",
            r"$\1",
            assignment,
            flags=re.IGNORECASE,
        ).casefold()
        for assignment in summary["assignment_targets"]
    ]

    for target in protected_targets:
        assert normalized_assignments.count(target.casefold()) == 1

    assert re.findall(r'"(?:[A-Za-z]:\\|\\\\)[^"\r\n]+"', script) == [
        '"D:\\code\\ai-drawing"',
        '"D:\\code\\ai-drawing\\worker\\windows"',
        '"D:\\code\\AI-Drawing-Worker"',
    ]
    assert re.search(r"'(?:[A-Za-z]:\\|\\\\)", script) is None
    assert script.count('"AI-Drawing NVIDIA Worker"') == 1
    assert "$WorkerPort = 8791" in script
    listener_targets = re.findall(r"-LocalPort\s+([^\s|\r\n]+)", script)
    assert len(listener_targets) >= 2
    assert set(listener_targets) == {"$WorkerPort"}


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
        r"(?im)^[ \t]*(?:Stop|Start)-ScheduledTask\b[^\r\n]*", script
    )
    assert task_actions == [
        "        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop",
        "    Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop",
    ]


def test_deployment_copies_only_the_three_open_control_runtime_files_directly() -> None:
    """The API, process manager, and fixed launcher must deploy together."""
    script = _script_text()

    copy_lines = re.findall(r"(?im)^[ \t]*Copy-Item\b[^\r\n]*", script)
    assert copy_lines == [
        "    Copy-Item -LiteralPath "
        '(Join-Path $SourceWindowsRoot "worker.py") -Destination '
        '(Join-Path $InstalledWindowsRoot "worker.py") -Force',
        "    Copy-Item -LiteralPath "
        '(Join-Path $SourceWindowsRoot "powershell_control.py") -Destination '
        '(Join-Path $InstalledWindowsRoot "powershell_control.py") -Force',
        "    Copy-Item -LiteralPath "
        '(Join-Path $SourceWindowsRoot "Start-Worker.ps1") -Destination '
        '(Join-Path $InstalledWorkerRoot "Start-Worker.ps1") -Force',
    ]


def test_deployment_checks_both_sources_and_target_before_shutdown() -> None:
    """Stopping the Worker before all copy paths exist must fail this test."""
    script = _script_text()
    source_worker_guard = (
        'Test-Path -LiteralPath (Join-Path $SourceWindowsRoot "worker.py") '
        "-PathType Leaf"
    )
    source_control_guard = (
        'Test-Path -LiteralPath (Join-Path $SourceWindowsRoot '
        '"powershell_control.py") -PathType Leaf'
    )
    source_launcher_guard = (
        'Test-Path -LiteralPath (Join-Path $SourceWindowsRoot '
        '"Start-Worker.ps1") -PathType Leaf'
    )
    installed_target_guard = (
        "Test-Path -LiteralPath $InstalledWindowsRoot -PathType Container"
    )
    shutdown_boundary = script.index("$WorkerTask = Get-ScheduledTask")

    for guard in (
        source_worker_guard,
        source_control_guard,
        source_launcher_guard,
        installed_target_guard,
    ):
        assert script.count(guard) == 1
        assert script.index(guard) < shutdown_boundary


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_restarts_the_task_from_finally_after_stop_and_copy() -> None:
    """Moving the task restart outside the destructive phase's finally must fail."""
    summary = _deployment_ast_summary()

    assert len(summary["try_statements"]) == 1
    deployment_try = summary["try_statements"][0]
    assert deployment_try["body_commands"].count("Stop-ScheduledTask") == 1
    assert deployment_try["body_commands"].count("Stop-Process") == 1
    assert deployment_try["body_commands"].count("Copy-Item") == 3
    assert "Start-ScheduledTask" not in deployment_try["body_commands"]
    assert deployment_try["finally_commands"] == ["Start-ScheduledTask"]


def test_deployment_stops_only_port_8791_listeners() -> None:
    """Touching ComfyUI or selecting a non-listener process must fail this test."""
    script = _script_text()

    listener_queries = re.findall(
        r"(?im)^[ \t]*Get-NetTCPConnection\b[^\r\n]*", script
    )
    assert listener_queries == [
        "        Get-NetTCPConnection -State Listen -LocalPort $WorkerPort "
        "-ErrorAction SilentlyContinue |",
        "        Get-NetTCPConnection -State Listen -LocalPort $WorkerPort "
        "-ErrorAction SilentlyContinue",
    ]
    assert "Select-Object -ExpandProperty OwningProcess -Unique" in script
    assert re.findall(r"(?im)^[ \t]*Stop-Process\b[^\r\n]*", script) == [
        "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop"
    ]
    assert "8188" not in script


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_listener_stop_has_a_single_ast_dataflow() -> None:
    """Reassigning listener or loop PID data before Stop-Process must fail."""
    summary = _deployment_ast_summary()

    _assert_listener_stop_dataflow_shape(summary)


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (
            "$WorkerPort = 8791",
            "$WorkerPort = 9999",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    $ListenerPids = @(1234)\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    $ListenerPids.SetValue(1234, 0)\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    $CapturedPids = $ListenerPids\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    $FirstPid = $ListenerPids[0]\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    $SelectedPids = @($ListenerPids | Select-Object -First 1)\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
        (
            "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
            "        $ListenerPid = 1234\n"
            "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
        ),
        (
            "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
            "        $CapturedPid = $ListenerPid\n"
            "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
        ),
        (
            "        Stop-Process -Id $ListenerPid -Force -ErrorAction Stop",
            "        Stop-Process -Id $PID -Force -ErrorAction Stop",
        ),
        (
            "    foreach ($ListenerPid in $ListenerPids) {",
            "    foreach ($ListenerPid in @()) {}\n"
            "    foreach ($ListenerPid in $ListenerPids) {",
        ),
    ),
    ids=(
        "different-port",
        "listener-list-reassignment",
        "listener-list-member-invocation",
        "listener-list-alias",
        "listener-list-index",
        "listener-list-extra-pipeline",
        "iterator-reassignment",
        "iterator-alias",
        "different-stop-id",
        "second-iterator-loop",
    ),
)
def test_deployment_listener_stop_dataflow_rejects_unsafe_mutations(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    """Each unsafe PID dataflow mutation must be rejected by AST inspection."""
    source = _script_text()
    assert source.count(needle) == 1
    unsafe_script = tmp_path / "unsafe-listener-dataflow.ps1"
    unsafe_script.write_text(source.replace(needle, replacement), encoding="utf-8")

    summary = _deployment_ast_summary(unsafe_script)
    with pytest.raises(AssertionError):
        _assert_listener_stop_dataflow_shape(summary)


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
        "start-bitstransfer",
        "curl",
        "wget",
        "netsh",
        "firewall",
        "new-netfirewallrule",
        "remove-netfirewallrule",
        "remove-item",
        "clear-item",
        "clear-content",
        "set-content",
        "move-item",
        "rename-item",
    )

    for unexpected in forbidden:
        assert unexpected not in script


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 requires Windows")
def test_deployment_parses_with_windows_powershell_51_scriptblock_create() -> None:
    """PowerShell syntax newer than Windows PowerShell 5.1 must fail this test."""
    _script_text()
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

    result = _run_powershell_51_parser(command)

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.stdout.strip() == (
        "5.1 Desktop; parsed Enable-Open-PowerShell-Control.ps1"
    )
