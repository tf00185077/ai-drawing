# Windows Worker Minimal Health Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove redundant object-catalog and resource-plan gates from Worker updates and normal submissions while retaining the minimum CUDA, authenticated version, and required-node checks needed for safe activation.

**Architecture:** Mac-side connection discovery remains in `backend/app/services/nvidia_worker.py`; the Windows Worker remains a passive authenticated listener. Update health validation will use ComfyUI `/system_stats`, authenticated Worker `/status`, and one Worker required-node preflight. Resource synchronization remains available only through explicit APIs and is no longer an implicit submission gate.

**Tech Stack:** Python 3.11, FastAPI/httpx/urllib, pytest, Windows PowerShell 5.1 packaging scripts.

---

## File Map

- Modify `worker/windows/updater/runtime.py`: reduce typed update evidence to required activation fields and map incomplete evidence to stable narrow errors.
- Modify `worker/windows/updater/windows_runtime.py`: remove direct `/object_info` and `/v1/resources/plan` calls; perform phase-aware minimal health polling.
- Modify `backend/app/services/nvidia_worker.py`: stop implicit resource planning/transfers before ordinary prompt submission; retain discovery, auth, node preflight, and direct submission.
- Modify `backend/tests/test_worker_updater_runtime.py`: define the minimal typed evidence contract and activation rejection cases.
- Modify `backend/tests/test_worker_updater_cli.py`: assert the concrete updater calls only status/system-stats/preflight.
- Modify `backend/tests/test_worker_resources.py`: assert Worker submission performs no implicit resource discovery, hashing, planning, or transfer and still surfaces ComfyUI errors.
- Modify `backend/tests/test_nvidia_worker_update.py`: retain exact-once submission behavior around the optional update coordinator.
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

### Task 3: Remove implicit resource planning from ordinary submission

**Files:**
- Modify: `backend/tests/test_worker_resources.py`
- Modify: `backend/app/services/nvidia_worker.py`

- [ ] **Step 1: Write a failing submission-sequence test**

Replace the resource hashing/synchronization tests with a client submission test so `_submit_prompt_once()` records requests and asserts:

```python
assert calls == [
    ("POST", "/v1/workflows/preflight"),
    ("POST", "/prompt"),
]
assert all(path != "/v1/resources/plan" for _, path in calls)
assert all(path != "/v1/resources/content" for _, path in calls)
```

The `/prompt` response must still return the exact Worker prompt ID. Keep the node preflight because it is an approved minimal compatibility gate.

- [ ] **Step 2: Run the submission test and verify RED**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_nvidia_worker_update.py -q -k "submission"
```

Expected: FAIL because `_submit_prompt_once()` still invokes `_synchronize()` and `/v1/resources/plan`.

- [ ] **Step 3: Remove the implicit synchronization gate**

Change `_submit_prompt_once()` to:

```python
self._preflight(prompt)
payload: dict[str, Any] = {"prompt": prompt}
```

Remove the private `_synchronize()` method and the now-unused Mac-side resource discovery/synchronization implementation: `ResourceRef`, `_NODE_RESOURCES`, `_roots`, `_safe_name`, `_resolve`, `_digest_cache`, `_digest_lock`, `_read_and_hash`, `_digest`, and `workflow_resources`. Remove their unused imports (`hashlib`, `dataclass`, `Path`, and `Iterable` as applicable). Do not delete the Windows Worker's explicit `/v1/resources/plan` or `/v1/resources/content` APIs; they remain available for explicit operator/informational use.

- [ ] **Step 4: Verify ComfyUI errors remain the execution authority**

Add a test where `/prompt` returns an HTTP error and assert the existing `httpx`/Worker error propagates without being replaced by a resource-plan error. Do not add fallback, retry, or local execution.

- [ ] **Step 5: Run Backend Worker client tests**

Run:

```powershell
py -3.11 -m pytest backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py backend/tests/test_worker_pairing.py -q
```

Expected: all tests pass; discovery and authenticated runtime URL caching remain unchanged.

- [ ] **Step 6: Commit Task 3**

```powershell
git add backend/app/services/nvidia_worker.py backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py
git commit -m "refactor(worker): submit without resource planning"
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

### Task 5: Rebuild, verify, document, and publish

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
- ordinary submission no longer performs implicit resource planning;
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
