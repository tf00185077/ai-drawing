# Windows Worker Updater Bootstrap Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-time, administrator-run, transactional deployment path that upgrades the privileged Windows updater from the trusted `D:\code\ai-drawing` main checkout without reinstalling or stopping the production Worker.

**Architecture:** A PowerShell 5.1 entrypoint separates a testable transaction state machine from a production adapter. The adapter validates the Git commit boundary, updater-owned paths, ACLs, task state, and smoke behavior; it stages and switches whole updater directories, retains the previous updater as a small rollback backup, and never performs per-file content hashing or comparison.

**Tech Stack:** Windows PowerShell 5.1 Desktop, ScheduledTasks, Git CLI, Python 3.11 pytest harness, existing `WorkerSecurity.ps1`, deterministic Windows ZIP builder.

---

## File map

- Create `worker/windows/Deploy-UpdaterBootstrap.ps1`: transaction functions, production adapter, elevated operator entrypoint, rollback, safe JSON result.
- Modify `backend/tests/test_worker_all_entrypoints.py`: PowerShell 5.1 parser/runtime tests, fake-adapter transaction tests, production contract assertions, distribution inclusion.
- Modify `worker/windows/README.md`: exact administrator command, success/error handling, remote-smoke gate.
- Modify `docs/PROGRESS.md`: implementation evidence, tests, package SHA-256, and pending live smoke.
- Rebuild `dist/AI-Drawing-NVIDIA-Worker/`: include the deployment script and updated documentation.
- Rebuild `dist/AI-Drawing-NVIDIA-Worker.zip`: publish the canonical package.

## Global constraints

- Preserve `HEAD == origin/main` and mandatory `-ExpectedCommit == HEAD`.
- Do not add `Get-FileHash`, cryptographic file hashing, digest manifests, or source/staging/installed per-file content comparisons to the deployment flow.
- Do not stop, restart, or modify `AI-Drawing NVIDIA Worker`, ComfyUI, releases, models, cache, input, output, pairing, or tokens.
- Stop and inspect only `AI-Drawing Worker Updater`.
- Never print `updater.env`, token values, authorization headers, response bodies, or raw caught exception text.
- Use canonical literal paths and reject reparse points before copying, moving, or removing updater-owned paths.
- Keep `NVIDIA_WORKER_AUTO_UPDATE=false`; do not submit an update request.
- Preserve user-owned untracked `.codex/config.toml` and `scripts/Run-Live-Worker-Migration.ps1`.

### Task 1: Define the transaction and rollback state machine

**Files:**
- Create: `worker/windows/Deploy-UpdaterBootstrap.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Add a PowerShell harness for the new script**

Add a helper beside the migration harness in `backend/tests/test_worker_all_entrypoints.py`:

```python
def _run_updater_bootstrap_harness(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    repo = Path(__file__).resolve().parents[2]
    harness = tmp_path / "新增資料夾 with spaces" / "bootstrap-harness.ps1"
    harness.parent.mkdir(parents=True)
    harness.write_text(
        f'. "{repo / "worker/windows/Deploy-UpdaterBootstrap.ps1"}"\n{body}',
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
```

Add `test_updater_bootstrap_deployment_parses_on_windows_powershell_51` using `[System.Management.Automation.Language.Parser]::ParseFile` and assert zero parser errors under Desktop PowerShell 5.1.

- [ ] **Step 2: Write failing transaction-order tests**

Use a fake adapter whose scriptblocks append fixed event names. Add a success test asserting this exact order:

```python
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
```

Add parametrized failures at `activate`, `protect`, `smoke`, and `validate-task`. Each must assert `rollback`, `validate-rollback`, and `release-lock` occur, the result is `rolled_back`, and the public `error_code` is a fixed stage code rather than the adapter exception text.

- [ ] **Step 3: Run the tests and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "updater_bootstrap_deployment and (parses or transaction)"
```

Expected: fail because `Deploy-UpdaterBootstrap.ps1` and `Invoke-UpdaterBootstrapTransaction` do not exist.

- [ ] **Step 4: Implement the minimal transaction function**

Create `Deploy-UpdaterBootstrap.ps1` with strict mode and a testable function:

```powershell
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-UpdaterBootstrapTransaction {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$WorkerRoot,
        [Parameter(Mandatory = $true)][string]$ProgramDataRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)]$Adapter
    )

    $Stage = "validating-context"
    $Backup = $null
    $LockHeld = $false
    try {
        & $Adapter.ValidateContext $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        & $Adapter.AcquireLock $ProgramDataRoot
        $LockHeld = $true
        & $Adapter.StopUpdaterTask
        $Stage = "staging"
        $Staging = & $Adapter.Stage $RepositoryRoot $WorkerRoot $ProgramDataRoot $ExpectedCommit
        & $Adapter.ValidateStage $Staging
        $Stage = "backing-up"
        $Backup = & $Adapter.Backup $WorkerRoot $ProgramDataRoot $ExpectedCommit
        $Stage = "activating"
        & $Adapter.Activate $Staging $WorkerRoot $ProgramDataRoot
        $Stage = "protecting"
        & $Adapter.Protect $WorkerRoot $ProgramDataRoot
        $Stage = "smoke-testing"
        & $Adapter.Smoke $WorkerRoot $ProgramDataRoot
        $Stage = "validating-task"
        & $Adapter.ValidateTask $ProgramDataRoot
        & $Adapter.CleanupSuccess $Staging
        return [pscustomobject]@{ status = "ready"; error_code = $null; backup = $Backup }
    } catch {
        $Code = Get-UpdaterBootstrapStageErrorCode -Stage $Stage
        if ($null -eq $Backup) {
            return [pscustomobject]@{ status = "failed_before_switch"; error_code = $Code; backup = $null }
        }
        try {
            & $Adapter.Rollback $Backup $WorkerRoot $ProgramDataRoot
            & $Adapter.ValidateRollback $WorkerRoot $ProgramDataRoot
            return [pscustomobject]@{ status = "rolled_back"; error_code = $Code; backup = $Backup }
        } catch {
            return [pscustomobject]@{ status = "recovery_required"; error_code = "UPDATER_BOOTSTRAP_RECOVERY_REQUIRED"; backup = $Backup }
        }
    } finally {
        if ($LockHeld) { & $Adapter.ReleaseLock $ProgramDataRoot }
    }
}
```

Implement `Get-UpdaterBootstrapStageErrorCode` as a closed mapping to `UPDATER_BOOTSTRAP_STAGE_FAILED`, `UPDATER_BOOTSTRAP_ACTIVATION_FAILED`, `UPDATER_BOOTSTRAP_SMOKE_FAILED`, and `UPDATER_BOOTSTRAP_TASK_INVALID`. Never incorporate `$_` into public output.

- [ ] **Step 5: Run the transaction tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add worker/windows/Deploy-UpdaterBootstrap.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): add updater bootstrap transaction"
```

### Task 2: Implement trusted production preflight and secure staging

**Files:**
- Modify: `worker/windows/Deploy-UpdaterBootstrap.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Add failing Git-boundary and no-hash tests**

Add tests that invoke preflight through a temporary Git repository and assert rejection for each condition:

```python
@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("wrong_path", "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"),
        ("wrong_branch", "UPDATER_BOOTSTRAP_BRANCH_INVALID"),
        ("wrong_origin", "UPDATER_BOOTSTRAP_REMOTE_INVALID"),
        ("origin_main_differs", "UPDATER_BOOTSTRAP_SOURCE_STALE"),
        ("expected_commit_differs", "UPDATER_BOOTSTRAP_COMMIT_MISMATCH"),
        ("tracked_dirty", "UPDATER_BOOTSTRAP_SOURCE_DIRTY"),
    ],
)
def test_updater_bootstrap_rejects_untrusted_repository_state(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    repository = _create_bootstrap_test_repository(tmp_path)
    _mutate_bootstrap_repository(repository, mutation)
    result = _run_bootstrap_repository_preflight(repository, mutation)
    assert result.returncode != 0
    assert expected in result.stderr
```

Define the three named helpers immediately above this test: the first creates
a local bare `origin` plus a `main` checkout at one commit, the second applies
exactly the named mutation, and the third dot-sources the deployment script and
invokes `Assert-TrustedUpdaterBootstrapRepository`. The helpers must not mock
Git output; they exercise `git.exe` against the temporary repositories.

Add a passing case with an untracked sentinel and assert staging does not contain it. Add a static prohibition test:

```python
text = script.read_text(encoding="utf-8").lower()
for forbidden in ("get-filehash", "sha256", "sha-256", "hashalgorithm", "digest-manifest"):
    assert forbidden not in text
```

The strings may exist in tests and documentation, but none may exist in `Deploy-UpdaterBootstrap.ps1`.

- [ ] **Step 2: Add failing path and structural tests**

Cover non-elevated rejection, invalid Worker ownership marker, insecure ACL, and reparse points in source/updater/staging/backup/ProgramData paths. Add a staged structural test that requires:

```powershell
@(
    "updater\__init__.py",
    "updater\cli.py",
    "updater\runtime.py",
    "updater\windows_runtime.py",
    "updater\state.py",
    "UpdaterBootstrap.ps1"
)
```

No test may require contents to match source after the copy.

- [ ] **Step 3: Run focused tests and verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "updater_bootstrap_deployment and (repository or staging or reparse or elevation or hash)"
```

Expected: fail because the production validation and staging adapter are not implemented.

- [ ] **Step 4: Implement the production context and staging adapter**

Implement these functions and wire them into `Get-ProductionUpdaterBootstrapAdapter`:

```powershell
function Assert-TrustedUpdaterBootstrapRepository {
    param([string]$RepositoryRoot, [string]$ExpectedCommit)
    $Canonical = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    if (-not $Canonical.Equals("D:\code\ai-drawing", [StringComparison]::OrdinalIgnoreCase)) {
        throw "UPDATER_BOOTSTRAP_REPOSITORY_INVALID"
    }
    & git.exe -C $Canonical fetch --prune origin main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "UPDATER_BOOTSTRAP_FETCH_FAILED" }
    $Branch = (& git.exe -C $Canonical branch --show-current).Trim()
    $Head = (& git.exe -C $Canonical rev-parse HEAD).Trim()
    $OriginMain = (& git.exe -C $Canonical rev-parse origin/main).Trim()
    $Remote = (& git.exe -C $Canonical remote get-url origin).Trim().TrimEnd("/")
    $Dirty = @(& git.exe -C $Canonical status --porcelain --untracked-files=no)
    if ($Branch -ne "main") { throw "UPDATER_BOOTSTRAP_BRANCH_INVALID" }
    if ($Remote -ne "https://github.com/tf00185077/ai-drawing.git") { throw "UPDATER_BOOTSTRAP_REMOTE_INVALID" }
    if ($Head -ne $OriginMain) { throw "UPDATER_BOOTSTRAP_SOURCE_STALE" }
    if ($Head -ne $ExpectedCommit) { throw "UPDATER_BOOTSTRAP_COMMIT_MISMATCH" }
    if ($Dirty.Count -ne 0) { throw "UPDATER_BOOTSTRAP_SOURCE_DIRTY" }
}
```

Validate `ExpectedCommit` with `^[0-9a-f]{40}$`, dot-source the repository's `WorkerSecurity.ps1`, call `Assert-ExistingWorkerRoot`, and call `Assert-SecureUpdaterTree` for installed updater and ProgramData.

Create staging under `$WorkerRoot\updater-deployment-owned\staging-<ExpectedCommit>` using `New-SecureUpdaterDirectory`. Copy only the tracked updater directory and bootstrap with literal paths, reject all reparse components, and call `Protect-UpdaterTree`. Structural validation uses `Test-Path -PathType Leaf` only.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass and the static no-hash test passes.

- [ ] **Step 6: Commit Task 2**

```powershell
git add worker/windows/Deploy-UpdaterBootstrap.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): stage trusted updater bootstrap"
```

### Task 3: Implement task quiescence, switch, smoke, and rollback

**Files:**
- Modify: `worker/windows/Deploy-UpdaterBootstrap.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Add failing task-isolation tests**

Add tests proving the production adapter references only `AI-Drawing Worker Updater` for stop/poll operations and never passes these names to `Stop-ScheduledTask`, `Start-ScheduledTask`, or `Stop-Process`:

```python
for forbidden in ("AI-Drawing NVIDIA Worker", "AI-Drawing NVIDIA Worker Restart"):
    assert forbidden not in stop_block
assert "Stop-Process" not in stop_block
assert "Start-ScheduledTask" not in script_text
```

Use a mocked task that transitions `Running -> Running -> Ready` and assert condition polling completes. Add timeout coverage returning `UPDATER_BOOTSTRAP_TASK_BUSY` without beginning backup.

- [ ] **Step 2: Add failing switch/smoke/rollback tests**

Create real temporary directory trees with distinct marker text for old and new updater packages. Through a filesystem adapter, assert:

- success leaves the new marker installed and the old marker in backup;
- activation failure restores old updater and bootstrap;
- smoke failure restores old updater and bootstrap;
- rollback-smoke failure returns `UPDATER_BOOTSTRAP_RECOVERY_REQUIRED`;
- staging is removed after success but the previous backup is retained;
- no models, shared paths, current junction, or release paths are enumerated or modified.

- [ ] **Step 3: Run focused tests and verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "updater_bootstrap_deployment and (task or switch or smoke or rollback)"
```

Expected: fail because task polling, directory switching, smoke, and rollback are not implemented.

- [ ] **Step 4: Implement the production switch and smoke**

Implement updater-task quiescence with a deadline rather than a fixed sleep:

```powershell
$Deadline = [DateTime]::UtcNow.AddSeconds(30)
$Task = Get-ScheduledTask -TaskName "AI-Drawing Worker Updater" -ErrorAction Stop
if ($Task.State -eq "Running") {
    Stop-ScheduledTask -TaskName "AI-Drawing Worker Updater" -ErrorAction Stop
}
do {
    $State = (Get-ScheduledTask -TaskName "AI-Drawing Worker Updater" -ErrorAction Stop).State
    if ($State -ne "Running") { break }
    Start-Sleep -Milliseconds 200
} while ([DateTime]::UtcNow -lt $Deadline)
if ($State -eq "Running") { throw "UPDATER_BOOTSTRAP_TASK_BUSY" }
```

Backup and switch whole paths using fixed paths and `Move-Item -LiteralPath`; keep updater backup on the Worker volume and bootstrap backup under ProgramData. After activation call `Protect-UpdaterTree` and `Assert-SecureUpdaterTree`.

Smoke from `$WorkerRoot` with updater-owned Python:

```powershell
& $UpdaterPython -B -c "from updater.cli import ProductionUpdaterServices; ProductionUpdaterServices.from_program_data(); import updater.runtime, updater.windows_runtime, updater.state"
if ($LASTEXITCODE -ne 0) { throw "UPDATER_BOOTSTRAP_IMPORT_FAILED" }
& $UpdaterPython -B -m updater.recovery
if ($LASTEXITCODE -ne 0) { throw "UPDATER_BOOTSTRAP_RECOVERY_FAILED" }
```

Validate the scheduled action's executable and arguments against the fixed Windows PowerShell and ProgramData bootstrap. Do not run the updater task.

Rollback removes only transaction-owned new paths, restores both backups, reapplies ACLs, and reruns import/config smoke against the restored updater.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add worker/windows/Deploy-UpdaterBootstrap.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): activate updater bootstrap safely"
```

### Task 4: Add the elevated operator entrypoint and documentation

**Files:**
- Modify: `worker/windows/Deploy-UpdaterBootstrap.ps1`
- Modify: `worker/windows/README.md`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Add failing entrypoint/output tests**

Add PowerShell 5.1 tests for:

- mandatory `-ExpectedCommit`;
- rejection outside an elevated Administrator session;
- exact success output containing `UPDATER_BOOTSTRAP_READY` and no environment contents;
- fixed terminal errors for `failed_before_switch`, `rolled_back`, and `recovery_required`;
- no raw injected secret from a fake adapter in stdout/stderr;
- direct execution invokes `Invoke-UpdaterBootstrapMain`, while dot-sourcing does not.

- [ ] **Step 2: Run entrypoint tests and verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "updater_bootstrap_deployment and (entrypoint or output or secret or elevated)"
```

Expected: fail because the production main function and safe result rendering do not exist.

- [ ] **Step 3: Implement the production main function**

Add the parameter declaration at the top and direct-execution guard at the bottom:

```powershell
param([Parameter(Mandatory = $true)][string]$ExpectedCommit)

function Invoke-UpdaterBootstrapMain {
    param([string]$ExpectedCommit)
    $Principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "UPDATER_BOOTSTRAP_ADMIN_REQUIRED"
    }
    if ($PSVersionTable.PSEdition -ne "Desktop" -or $PSVersionTable.PSVersion.Major -ne 5) {
        throw "UPDATER_BOOTSTRAP_POWERSHELL_51_REQUIRED"
    }
    $Adapter = Get-ProductionUpdaterBootstrapAdapter
    $Result = Invoke-UpdaterBootstrapTransaction `
        -RepositoryRoot "D:\code\ai-drawing" `
        -WorkerRoot "D:\code\AI-Drawing-Worker" `
        -ProgramDataRoot (Join-Path $env:ProgramData "AI-Drawing-Worker") `
        -ExpectedCommit $ExpectedCommit `
        -Adapter $Adapter
    if ($Result.status -ne "ready") { throw [string]$Result.error_code }
    Write-Output "UPDATER_BOOTSTRAP_READY"
    return $Result
}

if ($MyInvocation.InvocationName -ne ".") {
    Invoke-UpdaterBootstrapMain -ExpectedCommit $ExpectedCommit | ConvertTo-Json -Compress
}
```

Ensure public catches emit only fixed codes. Do not serialize adapter exceptions.

- [ ] **Step 4: Document the exact operator command**

Add this Windows PowerShell 5.1 administrator command to `worker/windows/README.md`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$ExpectedCommit = (& git.exe -C "D:\code\ai-drawing" rev-parse HEAD).Trim()
& "D:\code\ai-drawing\worker\windows\Deploy-UpdaterBootstrap.ps1" `
    -ExpectedCommit $ExpectedCommit
```

Document that the operator must wait for `UPDATER_BOOTSTRAP_READY`, must not rerun a failed request ID, and must keep `NVIDIA_WORKER_AUTO_UPDATE=false`. If the result is `UPDATER_BOOTSTRAP_RECOVERY_REQUIRED`, do not delete backup/staging paths and do not submit an update.

- [ ] **Step 5: Run entrypoint and PowerShell tests**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "updater_bootstrap or powershell_51"
```

Expected: all selected tests pass under Windows PowerShell Desktop 5.1.

- [ ] **Step 6: Commit Task 4**

```powershell
git add worker/windows/Deploy-UpdaterBootstrap.ps1 worker/windows/README.md backend/tests/test_worker_all_entrypoints.py
git commit -m "docs(worker): add updater bootstrap runbook"
```

### Task 5: Rebuild, verify, document, and publish

**Files:**
- Modify: `docs/PROGRESS.md`
- Rebuild: `dist/AI-Drawing-NVIDIA-Worker/`
- Rebuild: `dist/AI-Drawing-NVIDIA-Worker.zip`

- [ ] **Step 1: Rebuild the package**

```powershell
py -3.11 scripts/build-windows-worker.py
```

Expected: the package and ZIP include `Deploy-UpdaterBootstrap.ps1` automatically because the builder copies package files under `worker/windows` except Python bytecode caches. Verify that no user-owned untracked file exists below that package source before rebuilding.

- [ ] **Step 2: Run the complete focused gate**

```powershell
py -3.11 -m pytest `
  backend/tests/test_worker_all_entrypoints.py `
  backend/tests/test_worker_runtime.py `
  backend/tests/test_worker_updater_runtime.py `
  backend/tests/test_worker_updater_cli.py `
  backend/tests/test_worker_operational_recovery.py `
  backend/tests/test_nvidia_worker_update.py `
  backend/tests/test_worker_resources.py `
  backend/tests/test_worker_pairing.py -q
```

Expected: all applicable tests pass; no live services are operated.

- [ ] **Step 3: Verify distribution parity and the no-hash contract**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "distribution or archive or updater_bootstrap_deployment"
git diff --check
```

Expected: source, directory distribution, and ZIP parity pass. The deployment-script prohibition test confirms no file-content hash gate was added. Computing the final ZIP SHA-256 for publication metadata is permitted because it is not a deployment acceptance gate.

- [ ] **Step 4: Update project progress**

Add a `docs/PROGRESS.md` entry recording:

- confirmed installed-updater bootstrap boundary;
- transactional deployment script and rollback behavior;
- retained Git commit boundary and explicit absence of per-file content hash checks;
- PowerShell 5.1 and focused test counts;
- published ZIP SHA-256 as download metadata only;
- pending administrator bootstrap execution and one new live remote-update smoke;
- `NVIDIA_WORKER_AUTO_UPDATE=false` and the prohibition on reusing request IDs.

- [ ] **Step 5: Commit generated artifacts and documentation**

```powershell
git add docs/PROGRESS.md dist/AI-Drawing-NVIDIA-Worker dist/AI-Drawing-NVIDIA-Worker.zip
git commit -m "build(worker): publish updater bootstrap deployment"
```

- [ ] **Step 6: Run fresh verification and push main**

```powershell
py -3.11 -m pytest `
  backend/tests/test_worker_all_entrypoints.py `
  backend/tests/test_worker_runtime.py `
  backend/tests/test_worker_updater_runtime.py `
  backend/tests/test_worker_updater_cli.py `
  backend/tests/test_worker_operational_recovery.py `
  backend/tests/test_nvidia_worker_update.py `
  backend/tests/test_worker_resources.py `
  backend/tests/test_worker_pairing.py -q
git diff --check
$ZipHash = (Get-FileHash -LiteralPath "dist\AI-Drawing-NVIDIA-Worker.zip" -Algorithm SHA256).Hash
git status --short
git push origin main
git rev-parse HEAD
git rev-parse origin/main
$ZipHash
```

Expected: only the two user-owned untracked files remain; push succeeds; `HEAD == origin/main`; record the ZIP SHA-256 only as package download metadata.

## Live operator gate

Implementation and publication do not authorize operating the installed updater. After publication, run the deployment script once in an elevated Windows PowerShell 5.1 session with the exact published commit. Require `UPDATER_BOOTSTRAP_READY`, confirm the production Worker remains ready, and then submit exactly one new remote update request ID from the Mac. Never reuse `b49f9c07-272c-4f19-aa16-25415997f8ed` or earlier failed IDs. Keep `NVIDIA_WORKER_AUTO_UPDATE=false` until the new update, restart, discovery, and reconnection smoke all pass.

## Final review fix wave

- [x] Add behavior-level RED tests for process death after each backup and
  activation move, preserved rollback backups, untracked file/junction
  non-enumeration, exact-origin-before-fetch ordering, and nonfatal lock release
  failure after both success and rollback.
- [x] Add the fixed ProgramData `transaction-journal.json` with the exact
  secret-free schema `schema_version`, `expected_commit`, and closed `stage`.
  Write it atomically before the first destructive move and after every move.
- [x] Under the exclusive lock and before normal installed-updater preflight,
  recover an existing unsmoked journal using only fixed derived paths. Keep the
  journal and existing evidence on any unproven recovery.
- [x] Restore by copying the whole updater backup and bootstrap backup; validate
  the restored installation before removing the journal and never consume the
  backups.
- [x] Obtain `git ls-files` before inspecting tracked source paths, and validate
  the exact configured origin before any fetch/contact.
- [x] Keep lock-file cleanup failures nonfatal, always dispose the exclusive
  handle, and expose only `UPDATER_BOOTSTRAP_LOCK_CLEANUP_WARNING`.
- [x] Keep pre-recovery validation limited to the ProgramData root and exact
  recovery-control paths; run whole-tree ProgramData validation only on the
  no-journal installed-preflight path.
- [x] Run focused GREEN, rebuild directory/ZIP artifacts, run full focused and
  parity gates, update `docs/PROGRESS.md` and the final-fix report, then commit
  and push `main` without operating live state.
