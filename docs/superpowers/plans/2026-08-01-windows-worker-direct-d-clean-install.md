# Windows Worker Direct-to-D Clean Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the C-drive Worker with a destructive clean installation rooted at `D:\code\AI-Drawing-Worker`, using a new token and no preserved Worker data.

**Architecture:** Parameterize installation around one canonical Worker root and add a separate, ownership-checked clean-install entrypoint. Cleanup and installation are distinct phases: cleanup accepts only fixed verified paths, then the existing managed runtime builder installs directly into D and writes ProgramData/task configuration for that root.

**Tech Stack:** Windows PowerShell 5.1, Task Scheduler, Windows ACL APIs, Python 3.11 pytest, uv, FastAPI/Uvicorn, ComfyUI, CUDA PyTorch.

---

## File responsibilities

- `worker/windows/WorkerRoot.ps1`: canonical local-root parsing and containment checks shared by installer scripts.
- `worker/windows/Clean-Install-Worker.ps1`: destructive preflight, exact cleanup, and direct-to-D orchestration.
- `worker/windows/Install-Worker.ps1`: accepts the validated root and derives all runtime/task/config paths from it.
- `worker/windows/WorkerSecurity.ps1`: verifies ownership markers and ACLs before any deletion or reuse.
- `worker/windows/Start-Worker.ps1`: remains root-relative and must work from D without C literals.
- `worker/windows/UpdaterBootstrap.ps1`, `Restart-Worker.ps1`: resolve the Worker root from fixed ProgramData metadata.
- `worker/windows/Setup-D.cmd`: elevated one-click entrypoint for the approved destructive clean install.
- `backend/tests/test_worker_all_entrypoints.py`: Windows integration and distribution contracts.
- `backend/tests/test_worker_operational_recovery.py`: launcher/updater root contracts.
- `scripts/build-windows-worker.py`: distribution generation and parity.
- `docs/PROGRESS.md`: verified implementation and live outcome.

### Task 1: Canonical D-root contract

**Files:**
- Create: `worker/windows/WorkerRoot.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing PowerShell integration tests**

Add a harness test that dot-sources `WorkerRoot.ps1` and asserts:

```powershell
$Root = Resolve-WorkerInstallRoot -Path 'D:\code\AI-Drawing-Worker'
if ($Root -ne 'D:\code\AI-Drawing-Worker') { throw 'wrong root' }
```

Add rejection cases for UNC paths, relative paths, drive roots, `D:\code\ai-drawing`, reparse ancestors, trailing whitespace, and any path other than the fixed approved D root.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k direct_d_root
```

Expected: FAIL because `WorkerRoot.ps1` and `Resolve-WorkerInstallRoot` do not exist.

- [ ] **Step 3: Implement the minimal root resolver**

Implement `Resolve-WorkerInstallRoot` to require a local absolute path, normalize it with `GetFullPath`, reject reparse components without following them, reject the development repository, and accept only `D:\code\AI-Drawing-Worker` case-insensitively.

- [ ] **Step 4: Verify GREEN and commit**

Run the focused tests and commit:

```powershell
git add worker/windows/WorkerRoot.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): define direct D install root"
```

### Task 2: Exact destructive cleanup contract

**Files:**
- Create: `worker/windows/Clean-Install-Worker.ps1`
- Modify: `worker/windows/WorkerSecurity.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing cleanup tests**

Create temporary ownership-marked C root, source checkout, ProgramData root, failed D root, fake scheduled tasks, and Downloads packages. Assert dry-run returns only these exact targets and their byte totals. Add tests proving it rejects:

```text
reparse target
missing/invalid ownership marker
unexpected ACL owner
path outside the fixed allowlist
D:\code\ai-drawing
arbitrary Downloads content
```

Assert apply mode requires an explicit `-Apply` switch and a second exact inventory hash produced by dry-run.

- [ ] **Step 2: Verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k clean_install_cleanup
```

Expected: FAIL because the cleanup entrypoint is missing.

- [ ] **Step 3: Implement cleanup as a two-phase transaction**

Implement:

```powershell
Get-CleanInstallDeletionPlan -DownloadsRoot $DownloadsRoot
Invoke-CleanInstallDeletion -Plan $Plan -ExpectedPlanSha256 $ExpectedPlanSha256
```

The plan records canonical path, ownership evidence, file count, bytes, and SHA-256. Apply revalidates every target, stops only the three fixed tasks and exact 8188/8791 listeners, unregisters those tasks/firewall rule, then deletes each verified root with native PowerShell/.NET operations. Downloads matching is limited to `AI-Drawing-NVIDIA-Worker-fixed-*` files/directories and the canonical old package names.

- [ ] **Step 4: Verify cleanup tests and commit**

```powershell
git add worker/windows/Clean-Install-Worker.ps1 worker/windows/WorkerSecurity.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): add verified clean install cleanup"
```

### Task 3: Parameterize the managed installer

**Files:**
- Modify: `worker/windows/Install-Worker.ps1`
- Modify: `worker/windows/Migrate-Worker.ps1`
- Modify: `worker/windows/Start-Worker.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`
- Modify: `backend/tests/test_worker_operational_recovery.py`

- [ ] **Step 1: Write failing path-derivation tests**

Assert installer accepts `-Root`, defaults only through the direct-D entrypoint, and contains no production `C:\AI-Drawing-Worker` root literal. Assert Worker/updater/restart task actions and ProgramData environment derive from the supplied D root. Keep migration legacy literals isolated to migration-only code and ensure clean install never calls migration.

- [ ] **Step 2: Verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py backend/tests/test_worker_operational_recovery.py -q -k "install_root or direct_d"
```

- [ ] **Step 3: Implement root parameterization**

Add:

```powershell
param([Parameter(Mandatory = $true)][string]$Root)
. (Join-Path $PSScriptRoot 'WorkerRoot.ps1')
$Root = Resolve-WorkerInstallRoot -Path $Root
```

Derive config, releases, shared roots, task actions, updater environment, pairing output, and firewall setup from `$Root`. Do not use `C:\AI-Drawing-Worker-Source` for clean install; the local approved project root supplies the source commit and payload.

- [ ] **Step 4: Verify focused suites and commit**

```powershell
git add worker/windows/Install-Worker.ps1 worker/windows/Migrate-Worker.ps1 worker/windows/Start-Worker.ps1 backend/tests/test_worker_all_entrypoints.py backend/tests/test_worker_operational_recovery.py
git commit -m "refactor(worker): install managed runtime at canonical root"
```

### Task 4: New-token and pairing contract

**Files:**
- Modify: `worker/windows/Install-Worker.ps1`
- Modify: `worker/windows/Clean-Install-Worker.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing token tests**

Seed an old config with a sentinel token and assert clean install neither reads nor copies it. Assert the new config token is generated from 32 random bytes, is non-empty, differs across runs, never appears in stdout/stderr, and is written only to protected config/pairing files.

- [ ] **Step 2: Verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k new_worker_token
```

- [ ] **Step 3: Implement token generation**

Use `Security.Cryptography.RandomNumberGenerator` to fill 32 bytes and encode with base64url. Do not accept or preserve an existing token in clean-install mode. Emit only the pairing filename and instructions.

- [ ] **Step 4: Verify and commit**

```powershell
git add worker/windows/Install-Worker.ps1 worker/windows/Clean-Install-Worker.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): rotate token during clean install"
```

### Task 5: One-click direct-D orchestration and retry behavior

**Files:**
- Create: `worker/windows/Setup-D.cmd`
- Modify: `worker/windows/Clean-Install-Worker.ps1`
- Modify: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing orchestration tests**

Assert `Setup-D.cmd` invokes the clean installer as Administrator, passes the fixed D root, and never invokes `Migrate-Worker.ps1`. Simulate failure after cleanup and assert a retry recognizes only the ownership-marked D root, skips broad C/Downloads deletion, and resumes installation.

- [ ] **Step 2: Verify RED**

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k direct_d_setup
```

- [ ] **Step 3: Implement orchestration**

The first run prints the deletion inventory and requires an explicit plan hash passed to `-Apply`. The live operator wrapper may calculate and immediately pass the displayed hash only after the user has approved the already-reviewed fixed target set. Persist a protected `cleanup-complete.json` marker under the D root so retries cannot repeat broad deletion.

- [ ] **Step 4: Verify and commit**

```powershell
git add worker/windows/Setup-D.cmd worker/windows/Clean-Install-Worker.ps1 backend/tests/test_worker_all_entrypoints.py
git commit -m "feat(worker): add direct D clean setup"
```

### Task 6: Distribution and documentation

**Files:**
- Modify: `scripts/build-windows-worker.py`
- Modify: `worker/windows/README.md`
- Modify: `docs/PROGRESS.md`
- Regenerate: `dist/AI-Drawing-NVIDIA-Worker`
- Regenerate: `dist/AI-Drawing-NVIDIA-Worker.zip`

- [ ] **Step 1: Extend distribution parity tests**

Require `WorkerRoot.ps1`, `Clean-Install-Worker.ps1`, and `Setup-D.cmd` in both dist and ZIP with exact source bytes.

- [ ] **Step 2: Rebuild and verify**

```powershell
py -3.11 scripts/build-windows-worker.py
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_runtime.py backend/tests/test_worker_operational_recovery.py -q
git diff --check
Get-FileHash dist\AI-Drawing-NVIDIA-Worker.zip -Algorithm SHA256
```

Expected: all focused tests pass, source/dist/ZIP parity passes, and a new SHA-256 is reported.

- [ ] **Step 3: Document and commit**

Document the destructive behavior, new pairing requirement, exact D root, and no-rollback semantics. Commit source, tests, docs, and tracked distribution artifacts.

### Task 7: Live destructive clean install

**Files:**
- Use: `worker/windows/Clean-Install-Worker.ps1`
- Use: `worker/windows/Setup-D.cmd`
- Modify after verification: `docs/PROGRESS.md`

- [ ] **Step 1: Run dry-run and record exact sizes**

Run in Administrator PowerShell without `-Apply`. Review that every target is in the approved spec and that `D:\code\ai-drawing` is absent.

- [ ] **Step 2: Apply cleanup**

Pass the exact dry-run plan hash with `-Apply`. Confirm tasks/listeners are stopped and only approved targets are removed. Report bytes released.

- [ ] **Step 3: Install directly to D**

Run `Setup-D.cmd` as Administrator. Do not close the process until installation reports its final status.

- [ ] **Step 4: Run health gate**

Verify task state/result, ports 8188/8791, ComfyUI `/system_stats`, authenticated Worker status, protocol 2, exact commit, CUDA GPU name, update/restart capabilities, D `current` junction, and ProgramData D root.

- [ ] **Step 5: Verify deletion and new pairing**

Confirm C Worker/source roots are absent, no obsolete Worker packages remain in Downloads, the new pairing file exists, and the old token was not reused. Transfer only the new pairing file to Mac.

- [ ] **Step 6: Record live outcome and commit**

Update `docs/PROGRESS.md` with the exact health evidence and released capacity, then commit.

### Task 8: Final verification and remote publication

**Files:**
- Verify: entire intended commit range

- [ ] **Step 1: Run verification-before-completion checklist**

Confirm focused tests, distribution parity, live D health, clean git diff, no secrets, and only the two known user-owned untracked files remain.

- [ ] **Step 2: Audit commits for secrets and scope**

Inspect staged/tracked filenames and diffs for token, pairing, `.env`, local config, generated logs, and machine-specific secrets. Confirm none are committed.

- [ ] **Step 3: Present the exact commit range and request push authorization**

Do not push until the user explicitly approves publishing the verified local `main` commits to `origin/main`.
