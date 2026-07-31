# One-Click Windows Worker Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a desktop launcher that restarts the Windows Worker and ComfyUI with one double-click, no per-run UAC prompt, and verified success or actionable failure output.

**Architecture:** A fixed, highest-privilege scheduled task runs `C:\AI-Drawing-Worker\Restart-Worker.ps1`; the desktop launcher can only invoke that named task and poll its result. The restart script serializes concurrent attempts, stops only listeners on 8188/8791, starts the existing Worker bootstrap, authenticates local health checks without logging the token, and atomically publishes a redacted result.

**Tech Stack:** Windows PowerShell 5.1, Task Scheduler (`schtasks.exe`), Windows Firewall-independent loopback HTTP checks, Python 3.11 pytest for distribution contract tests.

---

## File Map

- Create `worker/windows/Restart-Worker.ps1`: privileged restart orchestration, lock, health checks, bounded logs, and result serialization.
- Create `worker/windows/Restart-Worker.cmd`: desktop-facing fixed task invocation and result polling UI.
- Modify `worker/windows/Install-Worker.ps1`: deploy both files, register the restart scheduled task, and place the launcher on the current user's desktop.
- Modify `worker/windows/Uninstall-Worker.cmd`: remove the restart scheduled task and desktop launcher without deleting runtime/model data.
- Modify `scripts/build-windows-worker.ps1`: no logic change expected; its wildcard copy must include the two new source files.
- Modify `backend/tests/test_worker_all_entrypoints.py`: assert distribution parity and security invariants for restart artifacts.
- Modify `docs/PROGRESS.md`: record the completed capability and real-host verification.

### Task 1: Define Restart Artifact Contracts

**Files:**
- Modify: `backend/tests/test_worker_all_entrypoints.py`
- Create: `worker/windows/Restart-Worker.ps1`
- Create: `worker/windows/Restart-Worker.cmd`

- [ ] **Step 1: Write failing distribution and security contract tests**

Add tests that require the new artifacts and lock down their privilege boundary:

```python
def test_worker_distribution_contains_restart_artifacts() -> None:
    repo = Path(__file__).resolve().parents[2]
    source = repo / "worker" / "windows"
    dist = repo / "dist" / "AI-Drawing-NVIDIA-Worker"
    for name in ("Restart-Worker.ps1", "Restart-Worker.cmd"):
        assert (source / name).is_file()
        assert (dist / name).read_bytes() == (source / name).read_bytes()


def test_restart_launcher_has_no_general_command_surface() -> None:
    repo = Path(__file__).resolve().parents[2]
    launcher = (repo / "worker/windows/Restart-Worker.cmd").read_text()
    lowered = launcher.lower()
    assert "ai-drawing nvidia worker restart" in lowered
    assert "%*" not in launcher
    assert "%1" not in launcher
    assert "powershell -command" not in lowered


def test_restart_script_redacts_token_and_targets_only_worker_ports() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "worker/windows/Restart-Worker.ps1").read_text()
    assert "8188, 8791" in script
    assert "Get-NetTCPConnection" in script
    assert "worker.json" in script
    assert "Authorization" in script
    assert "NVIDIA_WORKER_TOKEN" not in script
    assert "ConvertTo-Json" in script
    assert "Move-Item" in script
```

- [ ] **Step 2: Build the distribution and verify the tests fail**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
```

Expected: FAIL because `Restart-Worker.ps1` and `Restart-Worker.cmd` do not exist.

- [ ] **Step 3: Add the restart script skeleton and fixed desktop launcher**

Create `Restart-Worker.ps1` with constants and focused functions:

```powershell
$ErrorActionPreference = "Stop"
$Root = "C:\AI-Drawing-Worker"
$Runtime = Join-Path $Root "runtime\restart"
$ResultPath = Join-Path $Runtime "result.json"
$LockPath = Join-Path $Runtime "restart.lock"
$LogPath = Join-Path $Runtime ("restart-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$Ports = @(8188, 8791)
$TaskTimeoutSeconds = 120

function Write-AtomicJson([hashtable]$Value) {
    $Temporary = "$ResultPath.tmp"
    [IO.File]::WriteAllText(
        $Temporary,
        ($Value | ConvertTo-Json -Depth 4),
        (New-Object Text.UTF8Encoding($false))
    )
    Move-Item -LiteralPath $Temporary -Destination $ResultPath -Force
}
```

Create `Restart-Worker.cmd` as a fixed task caller; it must not forward arguments:

```batch
@echo off
setlocal
title AI-Drawing Worker Restart
schtasks.exe /Run /TN "AI-Drawing NVIDIA Worker Restart" >nul 2>&1
if errorlevel 1 (
  echo FAILED: could not start the privileged restart task.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\AI-Drawing-Worker\Wait-Restart-Result.ps1"
exit /b %errorlevel%
```

Keep result polling in a separate installed script, `Wait-Restart-Result.ps1`, so the batch launcher remains declarative and quoting-safe. Add that filename to the distribution test list.

- [ ] **Step 4: Rebuild and verify artifact contract tests pass**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
```

Expected: PASS for artifact presence, parity, fixed task name, no forwarded arguments, explicit ports, and atomic result writing.

- [ ] **Step 5: Commit the artifact contracts**

```powershell
git add worker/windows/Restart-Worker.ps1 worker/windows/Restart-Worker.cmd worker/windows/Wait-Restart-Result.ps1 backend/tests/test_worker_all_entrypoints.py dist/AI-Drawing-NVIDIA-Worker dist/AI-Drawing-NVIDIA-Worker.zip
git commit -m "test(worker): define one-click restart contracts"
```

### Task 2: Implement Restart, Health Verification, and Result Polling

**Files:**
- Modify: `worker/windows/Restart-Worker.ps1`
- Modify: `worker/windows/Wait-Restart-Result.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Add failing tests for lock, redaction, health checks, timeout, and bounded logs**

Add source-contract tests for the behaviors that must be present in the PowerShell implementation:

```python
def test_restart_script_has_lock_health_timeout_and_bounded_logs() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "worker/windows/Restart-Worker.ps1").read_text()
    for required in (
        "FileMode]::CreateNew",
        "Get-NetTCPConnection",
        "Stop-Process",
        "Start-Worker.ps1",
        "/system_stats",
        "/v1/worker/status",
        "/v1/workflows/preflight",
        "TaskTimeoutSeconds",
        "Select-Object -Skip 5",
    ):
        assert required in script
    assert "token =" not in script.casefold()


def test_restart_result_waiter_has_freshness_timeout_and_exit_codes() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "worker/windows/Wait-Restart-Result.ps1").read_text()
    assert "Get-Date" in script
    assert "120" in script
    assert 'status -eq "ready"' in script.casefold()
    assert "exit 0" in script
    assert "exit 1" in script
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
```

Expected: FAIL listing the missing orchestration and polling markers.

- [ ] **Step 3: Implement exclusive lock and pre-stop validation**

Implement lock acquisition with `FileMode.CreateNew`; validate these files before stopping anything:

```powershell
$Required = @(
    (Join-Path $Root "Start-Worker.ps1"),
    (Join-Path $Root "config\worker.json"),
    (Join-Path $Root "config\python-path.txt")
)
foreach ($Path in $Required) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required Worker file is missing: $Path"
    }
}
$LockStream = [IO.File]::Open(
    $LockPath,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write,
    [IO.FileShare]::None
)
```

If lock creation fails, write `status=busy` without exposing internal data and exit non-zero. Always dispose the stream and remove the lock in `finally`.

- [ ] **Step 4: Implement targeted stop, detached start, and health polling**

Resolve unique listener PIDs only from `$Ports`, stop them, launch the existing bootstrap hidden, then poll authenticated endpoints:

```powershell
$ListenerPids = Get-NetTCPConnection -LocalPort $Ports -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($ListenerPid in $ListenerPids) {
    Stop-Process -Id $ListenerPid -Force -ErrorAction Stop
}

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $Root "Start-Worker.ps1")
)

$Config = Get-Content (Join-Path $Root "config\worker.json") -Raw | ConvertFrom-Json
$Headers = @{ Authorization = "Bearer $($Config.token)" }
$Deadline = (Get-Date).AddSeconds($TaskTimeoutSeconds)
do {
    try {
        Invoke-RestMethod "http://127.0.0.1:8188/system_stats" -TimeoutSec 3 | Out-Null
        $Status = Invoke-RestMethod "http://127.0.0.1:8791/v1/worker/status" -Headers $Headers -TimeoutSec 3
        $Preflight = Invoke-RestMethod "http://127.0.0.1:8791/v1/workflows/preflight" -Method Post -Headers $Headers -ContentType "application/json" -Body '{"node_types":[]}' -TimeoutSec 5
        if ($Status.comfyui -eq "ready" -and $Preflight.ready -eq $true) { break }
    } catch { }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $Deadline)
```

Never serialize `$Config`, `$Headers`, exception request headers, or response objects to logs.

- [ ] **Step 5: Implement atomic results and bounded logs**

On success write only:

```powershell
Write-AtomicJson @{
    status = "ready"
    timestamp = (Get-Date).ToString("o")
    message = "Worker and ComfyUI are ready."
}
```

On failure write `status=failed`, timestamp, and a sanitized fixed-category message. Keep only the five newest `restart-*.log` files:

```powershell
Get-ChildItem $Runtime -Filter "restart-*.log" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 5 |
    Remove-Item -Force
```

- [ ] **Step 6: Implement the result waiter UI**

Capture invocation time, ignore stale result files, poll for 125 seconds, print green `READY` on success, and pause with the log directory on failure. Do not read `worker.json` in the desktop process.

- [ ] **Step 7: Rebuild and run focused tests**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit restart behavior**

```powershell
git add worker/windows/Restart-Worker.ps1 worker/windows/Wait-Restart-Result.ps1 backend/tests/test_worker_all_entrypoints.py dist/AI-Drawing-NVIDIA-Worker dist/AI-Drawing-NVIDIA-Worker.zip
git commit -m "feat(worker): add verified restart orchestration"
```

### Task 3: Integrate Installer, Scheduled Task, Desktop Launcher, and Uninstall

**Files:**
- Modify: `worker/windows/Install-Worker.ps1`
- Modify: `worker/windows/Uninstall-Worker.cmd`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing installer integration tests**

```python
def test_installer_registers_fixed_restart_task_and_desktop_launcher() -> None:
    repo = Path(__file__).resolve().parents[2]
    installer = (repo / "worker/windows/Install-Worker.ps1").read_text()
    assert 'AI-Drawing NVIDIA Worker Restart' in installer
    assert 'Restart-Worker.ps1' in installer
    assert 'Wait-Restart-Result.ps1' in installer
    assert '一鍵重啟 AI-Drawing Worker.cmd' in installer
    assert '/RL HIGHEST' in installer
    assert '/SC ONCE' in installer


def test_uninstaller_removes_restart_task_and_launcher_only() -> None:
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "worker/windows/Uninstall-Worker.cmd").read_text()
    assert 'AI-Drawing NVIDIA Worker Restart' in script
    assert '一鍵重啟 AI-Drawing Worker.cmd' in script
    assert 'Remove-Item $Root -Recurse' not in script
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
```

Expected: FAIL because the installer and uninstaller do not reference restart artifacts.

- [ ] **Step 3: Deploy restart artifacts in the installer**

Add the three fixed copies beside existing Worker copies:

```powershell
Copy-Item (Join-Path $Source "Restart-Worker.ps1") (Join-Path $Root "Restart-Worker.ps1") -Force
Copy-Item (Join-Path $Source "Wait-Restart-Result.ps1") (Join-Path $Root "Wait-Restart-Result.ps1") -Force
Copy-Item (Join-Path $Source "Restart-Worker.cmd") (Join-Path $Root "Restart-Worker.cmd") -Force
```

- [ ] **Step 4: Register the on-demand highest-privilege task**

Create a dormant one-time task with a past start time; it exists for `/Run` and has no recurring trigger:

```powershell
$RestartTaskName = "AI-Drawing NVIDIA Worker Restart"
$RestartAction = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Root\Restart-Worker.ps1`""
schtasks.exe /Create /TN $RestartTaskName /SC ONCE /ST 00:00 /SD 01/01/2000 /RL HIGHEST /TR $RestartAction /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to register the Worker restart task." }
```

Use Task Scheduler XML instead if the local Windows version rejects a past `/SD`; keep the task on-demand only and highest privilege.

- [ ] **Step 5: Install the desktop launcher**

Copy to the current desktop returned by `[Environment]::GetFolderPath("Desktop")`:

```powershell
$DesktopLauncher = Join-Path $Desktop "一鍵重啟 AI-Drawing Worker.cmd"
Copy-Item (Join-Path $Source "Restart-Worker.cmd") $DesktopLauncher -Force
```

- [ ] **Step 6: Extend uninstall cleanup without deleting runtime data**

Delete the two scheduled tasks and desktop launcher. Leave `C:\AI-Drawing-Worker`, models, runtime, cache, configuration, and pairing file intact.

- [ ] **Step 7: Rebuild and run all focused Worker tests**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_routing.py backend/tests/test_worker_resources.py backend/tests/test_worker_pairing.py backend/tests/test_worker_all_entrypoints.py -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit installer integration**

```powershell
git add worker/windows/Install-Worker.ps1 worker/windows/Uninstall-Worker.cmd backend/tests/test_worker_all_entrypoints.py dist/AI-Drawing-NVIDIA-Worker dist/AI-Drawing-NVIDIA-Worker.zip
git commit -m "feat(worker): install one-click restart launcher"
```

### Task 4: Install and Verify on This Windows Host

**Files:**
- Modify: `docs/PROGRESS.md`
- Runtime deployment: `C:\AI-Drawing-Worker\Restart-Worker.ps1`
- Runtime deployment: `C:\AI-Drawing-Worker\Wait-Restart-Result.ps1`
- Runtime deployment: desktop `一鍵重啟 AI-Drawing Worker.cmd`

- [ ] **Step 1: Record baseline identity and health without exposing the token**

Capture current token hash, model/cache directory sizes, listener PIDs, CUDA device, authenticated status, and preflight. Compare only the token hash after installation.

- [ ] **Step 2: Run the updated installer elevated**

Run the built distribution installer as Administrator. Preserve existing config and ensure external program exit codes are checked. If the existing installer compatibility defects remain, deploy only restart artifacts and scheduled task with a dedicated elevated setup script rather than reinstalling Python or PyTorch.

- [ ] **Step 3: Verify the task and desktop launcher**

Run:

```powershell
schtasks.exe /Query /TN "AI-Drawing NVIDIA Worker Restart" /FO LIST /V
Get-Item "$([Environment]::GetFolderPath('Desktop'))\一鍵重啟 AI-Drawing Worker.cmd"
```

Expected: task exists, Run Level is Highest, and launcher exists.

- [ ] **Step 4: Execute the desktop launcher once**

Double-click or invoke the launcher without elevation. Expected: no UAC prompt; previous listener PIDs disappear; new PIDs listen on 8188/8791; launcher prints `READY` within 120 seconds.

- [ ] **Step 5: Verify authenticated health, preflight, CUDA, and preservation**

Use the installed token internally to verify status and preflight. Run the Worker Python CUDA check. Confirm token hash, models, cache, and partial resource files match the baseline.

- [ ] **Step 6: Verify repeated invocation and concurrent lock behavior**

Run the launcher twice in quick succession. Expected: one restart proceeds; the other reports `busy` without stopping the newly started services. Run once more after completion and expect `READY`.

- [ ] **Step 7: Verify failure reporting safely**

Temporarily make a copied test bootstrap path unavailable through a controlled test task, not the production task. Expected: result is `failed`, log contains no bearer token, and the production task remains unchanged. Remove the controlled test task afterward.

- [ ] **Step 8: Update progress and commit verification evidence**

Add a dated entry to `docs/PROGRESS.md` covering the launcher, task privilege boundary, health checks, tests, and real-host acceptance. Commit only project files:

```powershell
git add docs/PROGRESS.md
git commit -m "docs(progress): record one-click worker restart"
```

### Task 5: Final Regression and Handoff

**Files:**
- Verify only; no expected code changes.

- [ ] **Step 1: Run the focused regression suite**

```powershell
py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_routing.py backend/tests/test_worker_resources.py backend/tests/test_worker_pairing.py backend/tests/test_worker_all_entrypoints.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Rebuild from a clean distribution directory**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py::test_worker_manifest_is_pinned_and_distribution_matches_source -q
```

Expected: PASS and a regenerated `dist/AI-Drawing-NVIDIA-Worker.zip`.

- [ ] **Step 3: Perform final live health verification**

Confirm ports 8188/8791, authenticated Worker status, empty-node preflight, CUDA device name, scheduled task presence, desktop launcher presence, and latest result `status=ready`.

- [ ] **Step 4: Report recovery instructions**

Document that manual recovery remains:

```powershell
Start-Process "C:\AI-Drawing-Worker\Start-Worker.cmd"
```

and that restart logs live under `C:\AI-Drawing-Worker\runtime\restart` with no token content.
