# Windows Worker Minimal Health Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove redundant object-catalog and resource-plan gates from Worker updates, preserve efficient first-transfer resource verification and eviction consistency for normal submissions, and retain the minimum checks needed for safe activation.

**Architecture:** Mac-side connection discovery remains in `backend/app/services/nvidia_worker.py`; the Windows Worker remains a passive authenticated listener. Update health validation will use ComfyUI `/system_stats`, authenticated Worker `/status`, and one Worker required-node preflight. Normal submission retains resource scan/plan/transfer, while Worker verification sidecars are created only after transfer digest verification and removed with evicted resources.

**Tech Stack:** Python 3.11, FastAPI/httpx/urllib, pytest, Windows PowerShell 5.1 packaging scripts.

---

## File Map

- Modify `worker/windows/updater/runtime.py`: reduce typed update evidence to required activation fields and map incomplete evidence to stable narrow errors.
- Modify `worker/windows/updater/windows_runtime.py`: remove direct `/object_info` and `/v1/resources/plan` calls; perform phase-aware minimal health polling.
- Modify `backend/app/services/nvidia_worker.py`: retain resource scanning/planning/transfers and cached Mac digests; do not change discovery, auth, or submission ordering.
- Modify `worker/windows/worker.py`: make verification sidecars authoritative without self-healing hashes and remove them with missing/evicted resources.
- Modify `backend/tests/test_worker_updater_runtime.py`: define the minimal typed evidence contract and activation rejection cases.
- Modify `backend/tests/test_worker_updater_cli.py`: assert the concrete updater calls only status/system-stats/preflight.
- Modify `backend/tests/test_worker_resources.py`: retain Mac resource scan/cache/transfer coverage and ComfyUI error propagation.
- Test `backend/tests/test_nvidia_worker_update.py`: retain exact-once submission behavior around the optional update coordinator.
- Modify `backend/tests/test_worker_runtime.py`: retain explicit resource API coverage without treating it as an implicit gate.
- Modify `docs/PROGRESS.md`: record implementation, verification, package hash, and pending live retry.
- Rebuild `dist/AI-Drawing-NVIDIA-Worker/` and `dist/AI-Drawing-NVIDIA-Worker.zip` from source.

### Task 1: Reduce the typed update-health contract

**Files:**
- Modify: `backend/tests/test_worker_updater_runtime.py`
- Modify: `worker/windows/updater/runtime.py`

- [ ] **Step 1: Write failing evidence-contract tests**

Update `HealthEvidence.complete()` assertions and validator cases so evidence contains only:

```python
HealthEvidence(
    cuda_available=True,
    gpu_name="NVIDIA Test GPU",
    system_stats_ok=True,
    authenticated_status_ok=True,
    preflight_ok=True,
    source_commit=COMMIT_A,
)
```

Delete test mutations for `object_info_ok` and `resource_plan_ok`. Keep independent rejection tests for missing CUDA, invalid system stats, invalid authenticated status, failed preflight, and wrong source commit.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_runtime.py -q -k "validator_requires or complete_health"
```

Expected: FAIL because production `HealthEvidence` still requires `object_info_ok` and `resource_plan_ok`.

- [ ] **Step 3: Implement the minimal typed evidence**

Change `HealthEvidence` and `HealthEvidence.complete()` in `worker/windows/updater/runtime.py` to remove both redundant fields. Change `_require_complete_health()` to require:

```python
if not evidence.cuda_available or not evidence.gpu_name.strip():
    raise UpdateError("CUDA_VALIDATION_FAILED", "staged runtime did not report a CUDA GPU")
if not evidence.system_stats_ok:
    raise UpdateError("COMFYUI_START_TIMEOUT", "ComfyUI system stats are unavailable")
if not evidence.authenticated_status_ok or evidence.source_commit != expected_commit:
    raise UpdateError("WORKER_STATUS_INVALID", "Worker status or source commit is invalid")
if not evidence.preflight_ok:
    raise UpdateError("WORKER_PREFLIGHT_FAILED", "Worker required-node preflight failed")
```

Do not change activation, rollback, recovery, Git trust, or request correlation.

- [ ] **Step 4: Run the focused runtime tests**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add worker/windows/updater/runtime.py backend/tests/test_worker_updater_runtime.py
git commit -m "refactor(worker): minimize update health evidence"
```

### Task 2: Remove redundant updater HTTP checks

**Files:**
- Modify: `backend/tests/test_worker_updater_cli.py`
- Modify: `worker/windows/updater/windows_runtime.py`

- [ ] **Step 1: Write failing transport-sequence tests**

Change the staged and production health fixtures to provide only:

```python
responses = {
    ("GET", f"{comfy_url}/system_stats"): system_stats,
    ("GET", f"{worker_url}/v1/worker/status"): status,
    ("POST", f"{worker_url}/v1/workflows/preflight"): {
        "ready": True,
        "missing_node_types": [],
    },
}
```

Assert the recorded calls are exactly those three endpoints. Add explicit negative assertions that neither URL suffix appears:

```python
assert not any(url.endswith("/object_info") for _, url in transport.calls)
assert not any(url.endswith("/v1/resources/plan") for _, url in transport.calls)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_cli.py -q -k "health or staged"
```

Expected: FAIL because `HttpHealthProbe` still calls both removed endpoints.

- [ ] **Step 3: Implement the three-call probe**

In `HttpHealthProbe._read_evidence()`:

- request ComfyUI `/system_stats`;
- read the token from `WorkerTokenProvider` without logging it;
- request authenticated Worker `/v1/worker/status`;
- request authenticated Worker `/v1/workflows/preflight` once with `REQUIRED_COMFY_NODE_TYPES`;
- construct the reduced `HealthEvidence`.

Delete the direct `/object_info` request, the empty resource-plan request, and their response parsing. Keep every URL loopback-only and every individual request bounded.

- [ ] **Step 4: Make retry failures stage-specific without secrets**

Track the current stage using a fixed internal label (`comfyui`, `worker_status`, `worker_preflight`). After bounded retries, raise only one of:

```python
{
    "comfyui": "COMFYUI_START_TIMEOUT",
    "worker_status": "WORKER_START_TIMEOUT",
    "worker_preflight": "WORKER_PREFLIGHT_FAILED",
}
```

Never persist URLs with credentials, headers, response bodies, token values, or exception strings from HTTP libraries.

- [ ] **Step 5: Run updater transport and runtime tests**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_cli.py backend/tests/test_worker_updater_runtime.py -q
```

Expected: all tests pass; call sequence contains no `/object_info` or `/v1/resources/plan`.

- [ ] **Step 6: Commit Task 2**

```powershell
git add worker/windows/updater/windows_runtime.py backend/tests/test_worker_updater_cli.py
git commit -m "fix(worker): remove redundant update probes"
```

### Task 3: Make first-transfer verification and eviction consistent

**Files:**
- Modify: `backend/tests/test_worker_resources.py`
- Modify: `backend/tests/test_worker_runtime.py`
- Modify: `worker/windows/worker.py`

- [ ] **Step 1: Write failing resource lifecycle tests while preserving Mac behavior**

Keep the existing resource discovery and digest-cache tests. Add a submission sequence assertion:

```python
assert calls == [
    ("POST", "/v1/workflows/preflight"),
    ("POST", "/v1/resources/plan"),
    # zero or more PUT /v1/resources/content calls for resources reported missing
    ("POST", "/prompt"),
]
```

The `/prompt` response must still return the exact Worker prompt ID. Keep the existing tests confirming an unchanged local resource reuses `_digest_cache`, while changed size/mtime invalidates the Mac cache.

Add these Worker tests in `backend/tests/test_worker_runtime.py`:

```python
def test_plan_does_not_self_heal_missing_verification_sidecar(...): ...
def test_plan_removes_stale_sidecar_when_destination_is_missing(...): ...
def test_plan_requires_retransfer_when_size_or_mtime_changes(...): ...
def test_cache_eviction_removes_destination_verification_sidecar(...): ...
def test_digest_mismatch_leaves_no_destination_or_sidecar(...): ...
```

- [ ] **Step 2: Run the submission test and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_resources.py backend/tests/test_worker_runtime.py -q -k "resource or verification or eviction or digest"
```

Expected: FAIL because `_verified_sha()` currently hashes an existing destination and creates a sidecar, and `_enforce_cache()` currently unlinks a destination without removing its sidecar.

- [ ] **Step 3: Implement authoritative sidecar lookup and removal**

Replace self-healing `_verified_sha()` with a lookup that returns an empty value when the sidecar is missing, malformed, or does not match size/mtime. Add:

```python
def _remove_verification(destination: Path) -> None:
    _sidecar_path(destination).unlink(missing_ok=True)
```

When resource planning sees a missing destination, remove its stale sidecar. When `_enforce_cache()` evicts a destination, remove the sidecar immediately after unlinking the destination. Keep `_sha256(partial)` only at completed upload verification, and keep `_record_verified()` only after successful atomic promotion.

- [ ] **Step 4: Verify ComfyUI errors remain the execution authority**

Add a test where `/prompt` returns an HTTP error and assert the existing `httpx`/Worker error propagates without being replaced by a resource-plan error. Do not add fallback, retry, or local execution.

- [ ] **Step 5: Run resource lifecycle and client tests**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_resources.py backend/tests/test_worker_runtime.py backend/tests/test_nvidia_worker_update.py backend/tests/test_worker_pairing.py -q
```

Expected: all tests pass; discovery and authenticated runtime URL caching remain unchanged.

- [ ] **Step 6: Commit Task 3**

```powershell
git add worker/windows/worker.py backend/tests/test_worker_resources.py backend/tests/test_worker_runtime.py
git commit -m "fix(worker): expire verification with cached resources"
```

### Task 4: Verify connection ownership remains unchanged

**Files:**
- Test: `backend/tests/test_worker_pairing.py`
- Inspect: `backend/app/services/nvidia_worker.py`
- Inspect: `worker/windows/worker.py`

- [ ] **Step 1: Run the existing discovery/auth suite**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_pairing.py backend/tests/test_worker_runtime.py -q -k "discovery or auth or status"
```

Expected: all selected tests pass.

- [ ] **Step 2: Verify the responsibility boundary**

Confirm by code inspection and tests:

- Mac Backend owns configured URL failure handling, authenticated `/24` discovery, hostname/protocol matching, and runtime URL caching in `backend/app/services/nvidia_worker.py`.
- Windows Worker owns the authenticated listening APIs and hostname/status advertisement in `worker/windows/worker.py`.
- Windows Worker does not scan for or initiate a connection to the Mac.

No production code change is expected in this task. If a test reveals an actual regression, stop and diagnose it separately rather than combining a connection rewrite with validation simplification.

### Task 5: Audit Windows PowerShell 5.1 compatibility

**Files:**
- Modify: `backend/tests/test_worker_all_entrypoints.py`
- Inspect: `worker/windows/*.ps1`
- Inspect: `worker/windows/*.cmd`
- Inspect: `worker/windows/README.md`

- [ ] **Step 1: Add a real Windows PowerShell 5.1 compatibility harness**

Run shipped script parser checks through the system Windows PowerShell executable, not the current host shell:

```python
subprocess.run(
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
)
```

The harness must exercise environment parsing with `-split '=', 2`, paths containing spaces and `新增資料夾`, scheduled-task command construction, `Start-Process` argument quoting, and listener selection using `Get-NetTCPConnection`.

- [ ] **Step 2: Run the harness and verify RED for every incompatible construct**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "powershell_51"
```

Expected: any remaining PowerShell 7-only or overload-ambiguous construct fails with its exact script/line; if no incompatible construct remains, the new coverage passes without requiring a production edit.

- [ ] **Step 3: Fix only evidenced incompatibilities**

Use Windows PowerShell 5.1 syntax documented by Microsoft. In particular:

```powershell
$Parts = $Line -split '=', 2
```

For `Start-Process`, use a single fully quoted `-ArgumentList` string when an argument can contain spaces. Treat `Start-ScheduledTask` as asynchronous and verify completion with task state/result plus service health rather than a fixed sleep.

- [ ] **Step 4: Re-run real powershell.exe smoke tests**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "powershell_51"
```

Expected: all selected tests pass under `powershell.exe` 5.1 Desktop.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/tests/test_worker_all_entrypoints.py worker/windows
git commit -m "test(worker): enforce Windows PowerShell 5.1 commands"
```

### Task 6: Rebuild, verify, document, and publish

**Files:**
- Modify: `docs/PROGRESS.md`
- Rebuild: `dist/AI-Drawing-NVIDIA-Worker/`
- Rebuild: `dist/AI-Drawing-NVIDIA-Worker.zip`

- [ ] **Step 1: Rebuild the Windows package**

Run:

```powershell
py -3.11 scripts/build-windows-worker.py
```

Expected: package and ZIP build successfully.

- [ ] **Step 2: Run the complete focused gate**

Run:

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

Expected: all applicable tests pass; Windows-only tests may skip on non-Windows hosts.

- [ ] **Step 3: Verify distribution parity and formatting**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q -k "distribution or archive"
git diff --check
Get-FileHash dist\AI-Drawing-NVIDIA-Worker.zip -Algorithm SHA256
```

Expected: parity tests and `git diff --check` pass; record the new SHA-256.

- [ ] **Step 4: Update progress**

Add a `docs/PROGRESS.md` entry recording:

- redundant `/object_info` and resource-plan gates removed;
- ordinary submission retains resource scan/plan/transfer and avoids repeated hashes through valid sidecars;
- LRU eviction and missing destinations remove stale verification sidecars;
- minimal safety gates retained;
- discovery/auth ownership unchanged;
- focused test count and ZIP SHA-256;
- live update retry remains pending and `NVIDIA_WORKER_AUTO_UPDATE=false`.

- [ ] **Step 5: Commit final generated artifacts and documentation**

```powershell
git add docs/PROGRESS.md dist/AI-Drawing-NVIDIA-Worker.zip dist/AI-Drawing-NVIDIA-Worker
git commit -m "build(worker): publish minimal validation package"
```

- [ ] **Step 6: Push only after fresh verification**

Run:

```powershell
git status --short
git push origin main
git rev-parse HEAD
git rev-parse origin/main
```

Expected: only the user's pre-existing untracked files remain, push succeeds, and both revisions are identical.

## Live Retry Gate

Do not retry request `8b7f3f84-1880-40d7-9937-4791669c0309`. After the new package/updater code is deployed and Mac has fast-forwarded to the new `origin/main`, submit exactly one new request ID with `NVIDIA_WORKER_AUTO_UPDATE=false`, monitor it to a terminal state, and verify protocol 2, exact source commit, CUDA/ComfyUI readiness, restart, discovery, and reconnection before enabling automatic updates.
