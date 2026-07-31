# Mac-Managed Windows Worker Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Mac Backend automatically update the complete Windows Worker to the exact Mac `origin/main` commit with staged activation and rollback.

**Architecture:** The Worker accepts only a full target commit and triggers an independent privileged updater. The updater reads Windows-local `updater.env`, exports the exact configured remote-branch head, builds an immutable release under `D:\code\AI-Drawing-Worker\releases`, validates on staging ports, and atomically switches `current`. The Mac compares exact commits at startup and before submission, waits through the expected restart, revalidates, and retries once.

**Tech Stack:** Python 3.11/3.12, FastAPI, httpx, Pydantic Settings, PowerShell 5.1, Task Scheduler, Git, uv, pytest.

---

## File Map

- Create `worker/windows/update_contract.py`: request schema, atomic request/status files, fixed task trigger.
- Modify `worker/windows/worker.py`: protocol metadata, update endpoints, update exclusion.
- Create `worker/windows/updater/{config,state,git_source,runtime,cli}.py`: independent updater units.
- Create `worker/windows/UpdaterBootstrap.ps1`: stable ProgramData bootstrap.
- Create `backend/app/services/nvidia_worker_update.py`: Mac commit comparison and one-update coordinator.
- Modify `backend/app/services/nvidia_worker.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/api/workers.py`: client, settings, startup and status integration.
- Create `worker/windows/Migrate-Worker.ps1`: transactional C-to-D migration.
- Modify Worker installer/start/uninstall/build scripts for versioned runtime and updater assets.
- Add focused tests under `backend/tests/test_worker_updater_*.py` and `backend/tests/test_nvidia_worker_update.py`.

## Task 1: Worker Version and Update Contract

**Files:**
- Create: `worker/windows/update_contract.py`
- Modify: `worker/windows/worker.py`
- Modify: `worker/windows/worker-manifest.json`
- Test: `backend/tests/test_worker_runtime.py`

- [ ] **Step 1: Write failing status and request tests**

```python
def test_status_advertises_release_and_update_capability(worker_client, worker_module):
    worker_module.SOURCE_COMMIT_PATH.write_text("a" * 40, encoding="utf-8")
    body = worker_client.get("/v1/worker/status", headers=_auth()).json()
    assert body["protocol_version"] == 2
    assert body["worker_version"] == "0.3.0"
    assert body["source_commit"] == "a" * 40
    assert body["update_capability"] == 1
    assert body["update_state"] == "idle"


@pytest.mark.parametrize("value", ["main", "abc", "g" * 40, "a" * 39])
def test_update_rejects_non_full_hex_commit(worker_client, value):
    response = worker_client.post(
        "/v1/admin/update", headers=_auth(), json={"target_commit": value}
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_runtime.py -q`.
Expected: FAIL because protocol metadata and update endpoint are missing.

- [ ] **Step 3: Implement typed update contract**

```python
class UpdateRequest(BaseModel):
    target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)
```

Persist only request ID, target commit and timestamp. Same-target duplicates reuse the active request ID; a different target raises `UpdateAlreadyRunning`.

- [ ] **Step 4: Add fixed update endpoints and task trigger**

```python
@app.post("/v1/admin/update", dependencies=[Depends(_auth)], status_code=202)
def request_update(body: UpdateRequest) -> dict[str, str]:
    request_id = queue_update(body.target_commit)
    subprocess.run(
        ["schtasks.exe", "/Run", "/TN", "AI-Drawing Worker Updater"],
        check=True, timeout=15,
    )
    return {"request_id": request_id, "status": "queued"}


@app.get("/v1/admin/update/status", dependencies=[Depends(_auth)])
def update_status() -> dict[str, Any]:
    return read_public_update_status()
```

The request never supplies a task, command, URL, branch or path.

- [ ] **Step 5: Block mutations while update is active**

Apply `_require_update_idle()` to resource plan/content and prompt. Return structured `409 worker_updating` unless state is `idle`, `ready`, `rolled_back` or `failed_before_activation`.

- [ ] **Step 6: Align manifest and app constants**

Set protocol `2`, Worker `0.3.0`, updater capability `1`; remove hard-coded `0.1.0` status values and read `source-commit.txt`.

- [ ] **Step 7: Verify GREEN and commit**

```powershell
py -3.11 -m pytest backend/tests/test_worker_runtime.py -q
git add worker/windows/update_contract.py worker/windows/worker.py worker/windows/worker-manifest.json backend/tests/test_worker_runtime.py
git commit -m "feat(worker): define automatic update contract"
```

## Task 2: Updater Configuration and State

**Files:**
- Create: `worker/windows/updater/__init__.py`
- Create: `worker/windows/updater/config.py`
- Create: `worker/windows/updater/state.py`
- Test: `backend/tests/test_worker_updater_config.py`
- Test: `backend/tests/test_worker_updater_state.py`

- [ ] **Step 1: Write failing env/path boundary tests**

```python
def test_config_accepts_distinct_local_owned_roots(tmp_path):
    project = _git_repo(tmp_path / "source", remote=EXPECTED_REMOTE)
    worker = _owned_worker_root(tmp_path / "runtime")
    config = load_updater_config(_env_file(tmp_path, project, worker))
    assert config.project_root == project.resolve()
    assert config.worker_root == worker.resolve()


@pytest.mark.parametrize("project,worker", [
    (r"\\server\share\repo", r"D:\worker"),
    (r"D:\code", r"D:\code\worker"),
    (r"D:\same", r"D:\same"),
])
def test_config_rejects_unc_nested_or_equal_roots(tmp_path, project, worker):
    with pytest.raises(UpdaterConfigError):
        load_updater_config(_env_file_values(tmp_path, project, worker))
```

Also test unknown/duplicate env keys, malformed lines, missing ownership marker, wrong remote URL and empty branch.

- [ ] **Step 2: Run config tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_updater_config.py -q`.
Expected: import failure for updater config.

- [ ] **Step 3: Implement strict local env parsing**

```python
ALLOWED_KEYS = {
    "AI_DRAWING_PROJECT_ROOT", "AI_DRAWING_WORKER_ROOT",
    "AI_DRAWING_WORKER_REMOTE", "AI_DRAWING_WORKER_BRANCH",
}

@dataclass(frozen=True)
class UpdaterConfig:
    project_root: Path
    worker_root: Path
    remote: str
    branch: str
    expected_remote_url: str
```

Parse without shell evaluation. Resolve strictly; reject UNC, equality and containment; require `.git`, ownership marker and exact normalized remote URL.

- [ ] **Step 4: Write failing state/idempotency/redaction tests**

```python
def test_state_machine_rejects_skipped_activation(tmp_path):
    store = UpdateStateStore(tmp_path)
    store.queue("req", "a" * 40)
    with pytest.raises(InvalidUpdateTransition):
        store.transition("ready")


def test_public_state_redacts_secret_and_command(tmp_path):
    store = UpdateStateStore(tmp_path)
    store.fail("RUNTIME_INSTALL_FAILED", "safe message")
    text = store.public_path.read_text()
    assert "Bearer" not in text
    assert "TOKEN" not in text
    assert "command" not in text.casefold()
```

- [ ] **Step 5: Implement explicit state graph and atomic stores**

```python
TRANSITIONS = {
    "queued": {"fetching", "rejected"},
    "fetching": {"staging", "failed_before_activation"},
    "staging": {"installing", "failed_before_activation"},
    "installing": {"validating", "failed_before_activation"},
    "validating": {"activating", "failed_before_activation"},
    "activating": {"restarting", "rolled_back", "recovery_required"},
    "restarting": {"ready", "rolled_back", "recovery_required"},
}
```

Keep private request/state separate from public redacted status. Use an exclusive OS lock and atomic replace for each write.

- [ ] **Step 6: Verify and commit**

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py -q
git add worker/windows/updater backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py
git commit -m "feat(worker): add updater config and state machine"
```

## Task 3: Exact Git Source Export

**Files:**
- Create: `worker/windows/updater/git_source.py`
- Test: `backend/tests/test_worker_updater_git.py`

- [ ] **Step 1: Write failing temporary-Git tests**

```python
def test_export_requires_target_equal_fetched_remote_head(git_fixture, tmp_path):
    source = GitSource(git_fixture.checkout, "origin", "main")
    with pytest.raises(UpdateError, match="WINDOWS_REMOTE_HEAD_MISMATCH"):
        source.export_commit("0" * 40, tmp_path / "export")


def test_export_leaves_dirty_checkout_untouched(git_fixture, tmp_path):
    before = git_fixture.snapshot_worktree()
    exported = GitSource(...).export_commit(git_fixture.remote_head, tmp_path / "export")
    assert (exported / "worker/windows/worker.py").is_file()
    assert git_fixture.snapshot_worktree() == before
```

Cover fetch failure, wrong remote, non-commit object, missing Worker source and archive path escape.

- [ ] **Step 2: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q`.
Expected: import failure for `GitSource`.

- [ ] **Step 3: Implement checked Git and safe export**

```python
def _git(self, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(self.root), *args], text=True,
        capture_output=True, timeout=300, check=False,
    )
    if result.returncode:
        raise UpdateError("GIT_COMMAND_FAILED", redact(result.stderr))
    return result.stdout.strip()
```

Fetch only configured remote/branch, resolve `refs/remotes/<remote>/<branch>^{commit}`, require exact SHA equality, export with `git archive`, safely extract canonical relative paths and write `source-commit.txt`. Never checkout/reset the user's worktree.

- [ ] **Step 4: Verify and commit**

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_git.py -q
git add worker/windows/updater/git_source.py backend/tests/test_worker_updater_git.py
git commit -m "feat(worker): export exact trusted Git revision"
```

## Task 4: Versioned Runtime, Activation and Rollback

**Files:**
- Create: `worker/windows/updater/runtime.py`
- Test: `backend/tests/test_worker_updater_runtime.py`

- [ ] **Step 1: Write failing layout and rollback tests**

```python
def test_stage_keeps_mutable_data_outside_release(tmp_path, fake_commands):
    layout = RuntimeLayout.create(tmp_path / "worker")
    release = RuntimeBuilder(layout, fake_commands).stage(EXPORTED, "a" * 40)
    assert release == layout.releases / ("a" * 40)
    assert (release / "ComfyUI/models").resolve() == layout.shared_models.resolve()
    assert not (release / "config/worker.json").exists()


def test_failed_production_health_restores_previous_junction(tmp_path, fake_health):
    layout = _layout_with_current(tmp_path, "a" * 40)
    fake_health.fail_for("b" * 40)
    result = Activator(layout, fake_health).activate("b" * 40)
    assert result.status == "rolled_back"
    assert layout.current.resolve().name == "a" * 40
```

Also test install exit failure, CUDA false, staging-port failures, rollback failure, interrupted staging and retention.

- [ ] **Step 2: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_updater_runtime.py -q`.
Expected: import failure for runtime units.

- [ ] **Step 3: Implement immutable layout and shared links**

```python
@dataclass(frozen=True)
class RuntimeLayout:
    root: Path
    releases: Path
    shared: Path
    config: Path
    current: Path
    staging: Path

    def release(self, commit: str) -> Path:
        if not FULL_SHA.fullmatch(commit):
            raise UpdateError("TARGET_COMMIT_INVALID", "Invalid commit.")
        return self.releases / commit
```

Create Windows junctions for models/input/output/cache/partial. Reject all resolved paths outside Worker root/shared root.

- [ ] **Step 4: Implement checked runtime installation**

Install release-local Python/venv, force CUDA PyTorch from manifest index before other requirements, pin ComfyUI/custom nodes, and check every Git/uv/pip/Python exit code. Never mutate `current` while staging.

- [ ] **Step 5: Implement staged health**

Start staged ComfyUI and Worker on loopback-only reserved ports. Verify CUDA, GPU name, `/system_stats`, `/object_info`, authenticated status/resource plan/preflight and exact commit. Always terminate staging processes in `finally`.

- [ ] **Step 6: Implement atomic activation and rollback**

Record old junction, stop production ports, construct `current.next`, atomically exchange junctions, start stable bootstrap and verify. On failure restore old junction and verify recovery. Do not delete releases/shared data inside this transaction.

- [ ] **Step 7: Implement post-success retention**

Keep current and previous successful release. Delete older known releases only after production validation; preserve unknown and staging directories.

- [ ] **Step 8: Verify and commit**

```powershell
py -3.11 -m pytest backend/tests/test_worker_updater_runtime.py -q
git add worker/windows/updater/runtime.py backend/tests/test_worker_updater_runtime.py
git commit -m "feat(worker): add transactional versioned runtime"
```

## Task 5: Privileged Orchestrator and Distribution

**Files:**
- Create: `worker/windows/updater/cli.py`
- Create: `worker/windows/UpdaterBootstrap.ps1`
- Modify: `worker/windows/Install-Worker.ps1`
- Modify: `scripts/build-windows-worker.ps1`
- Test: `backend/tests/test_worker_updater_cli.py`
- Test: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing orchestration and parity tests**

```python
def test_updater_cli_advances_success_states(fake_updater):
    assert main([], services=fake_updater) == 0
    assert fake_updater.states == [
        "fetching", "staging", "installing", "validating",
        "activating", "restarting", "ready",
    ]


def test_distribution_contains_updater_assets():
    for relative in ("updater/cli.py", "updater/config.py", "UpdaterBootstrap.ps1"):
        assert (DIST / relative).read_bytes() == (SOURCE / relative).read_bytes()
```

Test each stable failure code and token redaction from exception text.

- [ ] **Step 2: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_updater_cli.py backend/tests/test_worker_all_entrypoints.py -q`.
Expected: FAIL because CLI/bootstrap/distribution integration is missing.

- [ ] **Step 3: Implement fixed CLI orchestration**

`main()` accepts no path/URL/branch/remote/command options. Load config, lock, read queued request, transition around each bounded operation, stage/activate and map typed errors to documented terminal states.

- [ ] **Step 4: Implement ProgramData bootstrap**

Parse the allowlisted env file without `Invoke-Expression`, locate updater-owned Python under Worker root, execute only `& $UpdaterPython -m updater.cli`, and return its exit code. Never echo env values.

- [ ] **Step 5: Integrate installer and scheduled task**

Install ProgramData bootstrap/env with restricted ACL, stable updater Python/runtime, and on-demand highest-privilege `AI-Drawing Worker Updater`. Preserve bearer token and shared data.

- [ ] **Step 6: Rebuild, verify and commit**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_updater_cli.py backend/tests/test_worker_all_entrypoints.py -q
git add worker/windows/updater worker/windows/UpdaterBootstrap.ps1 worker/windows/Install-Worker.ps1 scripts/build-windows-worker.ps1 backend/tests/test_worker_updater_cli.py backend/tests/test_worker_all_entrypoints.py dist
git commit -m "feat(worker): install privileged update orchestrator"
```

## Task 6: Mac Automatic Update Coordinator

**Files:**
- Create: `backend/app/services/nvidia_worker_update.py`
- Modify: `backend/app/services/nvidia_worker.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/workers.py`
- Test: `backend/tests/test_nvidia_worker_update.py`

- [ ] **Step 1: Write failing commit trust and no-op tests**

```python
def test_local_commit_requires_head_equal_origin_main(git_repo):
    git_repo.commit_local_only()
    with pytest.raises(WorkerUpdateError, match="MAC_COMMIT_NOT_ORIGIN_MAIN"):
        trusted_local_commit(git_repo.path)


def test_matching_worker_commit_skips_update(fake_client, git_repo):
    fake_client.health_result["source_commit"] = git_repo.origin_main
    ensure_worker_compatible(fake_client, git_repo.path)
    assert fake_client.update_requests == []
```

- [ ] **Step 2: Write failing coordination tests**

Cover mismatch request, same-target reuse, expected outage after accepted request ID, injected-clock 30-minute timeout, post-update commit/preflight validation, one retry, no local fallback and one shared background task.

- [ ] **Step 3: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_nvidia_worker_update.py -q`.
Expected: import failure for coordinator.

- [ ] **Step 4: Implement trusted local commit resolution**

```python
head = git("rev-parse", "HEAD")
origin_main = git("rev-parse", "origin/main^{commit}")
if head != origin_main:
    raise WorkerUpdateError("MAC_COMMIT_NOT_ORIGIN_MAIN", "Local main is not published.")
```

Do not automatically pull Mac source.

- [ ] **Step 5: Extend Worker client**

```python
def request_update(self, target_commit: str) -> dict[str, Any]:
    return self._request("POST", "/v1/admin/update", json={"target_commit": target_commit}).json()

def update_status(self) -> dict[str, Any]:
    return self._request("GET", "/v1/admin/update/status").json()
```

- [ ] **Step 6: Implement one managed coordinator**

Use one lock/condition so startup and submission join the same update. After acceptance, tolerate connection failures until deadline; then require `ready`, exact commit, compatible protocol and preflight. Never loop indefinitely.

- [ ] **Step 7: Gate submission and retry once**

Call coordinator before Worker submission. If update completes, submit once. Avoid recursive submission and never fall back local.

- [ ] **Step 8: Add settings/startup/status**

Add `nvidia_worker_auto_update: bool = False` and `nvidia_worker_update_timeout: float = 1800.0`. Launch a managed background check during FastAPI startup without delaying local Backend/Bot. Expose safe state/error code from `/api/workers/status`.

- [ ] **Step 9: Verify and commit**

```powershell
py -3.11 -m pytest backend/tests/test_nvidia_worker_update.py backend/tests/test_worker_pairing.py backend/tests/test_worker_routing.py -q
git add backend/app/services/nvidia_worker_update.py backend/app/services/nvidia_worker.py backend/app/config.py backend/app/main.py backend/app/api/workers.py backend/tests/test_nvidia_worker_update.py
git commit -m "feat(worker): auto-update from Mac coordinator"
```

## Task 7: Transactional C-to-D Migration

**Files:**
- Create: `worker/windows/Migrate-Worker.ps1`
- Modify: `worker/windows/Start-Worker.ps1`
- Modify: `worker/windows/Uninstall-Worker.cmd`
- Test: `backend/tests/test_worker_all_entrypoints.py`

- [ ] **Step 1: Write failing migration contract tests**

Require source `C:\AI-Drawing-Worker`, target loaded from ProgramData env, copy-before-switch, inventory, token hash redaction, task updates, D `current` validation and C rename only after ready. Assert no recursive removal of source/shared data.

- [ ] **Step 2: Run tests and verify RED**

Run `py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q`.
Expected: FAIL because migration artifact is missing.

- [ ] **Step 3: Implement preflight and inventory**

Validate D free space for temporary copy plus reserve. Record counts, sizes, config hash, canonical paths and token hash only.

- [ ] **Step 4: Implement copy-first layout migration**

Copy runtime to first release and mutable data to shared; verify sizes/digests; create shared links and `current`. Leave C unchanged.

- [ ] **Step 5: Switch launch surfaces and validate**

Update login/updater/one-click tasks, Start script, Python path and markers. Start D `current`; verify authenticated status, preflight, object info, CUDA and token hash.

- [ ] **Step 6: Implement rollback and backup**

On failure restore old task actions and start C. On success rename C to dated backup, restart D and verify again. Never auto-delete backup.

- [ ] **Step 7: Rebuild, verify and commit**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py -q
git add worker/windows/Migrate-Worker.ps1 worker/windows/Start-Worker.ps1 worker/windows/Uninstall-Worker.cmd backend/tests/test_worker_all_entrypoints.py dist
git commit -m "feat(worker): add transactional D-drive migration"
```

## Task 8: Regression and Real-Host Acceptance

**Files:**
- Modify: `docs/PROGRESS.md`
- Deploy: `C:\ProgramData\AI-Drawing-Worker`
- Deploy: `D:\code\AI-Drawing-Worker`

- [ ] **Step 1: Run complete focused suite**

```powershell
py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_routing.py backend/tests/test_worker_resources.py backend/tests/test_worker_pairing.py backend/tests/test_worker_all_entrypoints.py backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py backend/tests/test_worker_updater_git.py backend/tests/test_worker_updater_runtime.py backend/tests/test_worker_updater_cli.py backend/tests/test_nvidia_worker_update.py -q
```

Expected: all PASS with no new warnings.

- [ ] **Step 2: Rebuild and verify distribution parity**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1
py -3.11 -m pytest backend/tests/test_worker_all_entrypoints.py::test_worker_manifest_is_pinned_and_distribution_matches_source -q
```

- [ ] **Step 3: Record protected baseline**

Record token hash only, model/cache/partial counts/sizes, PIDs, CUDA device, commit, status/preflight, task actions and disk free space. Never print token.

- [ ] **Step 4: Run elevated migration**

Execute built `Migrate-Worker.ps1`; verify D layout/current/shared/ProgramData/task actions, ready production health and retained C backup.

- [ ] **Step 5: Exercise failure matrix**

With controlled test commits/releases verify target mismatch, fetch interruption, install failure, staged health failure, production failure+rollback, duplicate reuse and stale staging recovery. Remove only controlled artifacts.

- [ ] **Step 6: Perform real Mac-driven update and generation**

Publish implementation commit to `origin/main`; start Mac Backend with auto-update enabled; verify exact request, expected outage, ready commit/preflight, prompt ID and retrieved Gallery image.

- [ ] **Step 7: Verify preservation and redaction**

Compare token hash/shared inventory to baseline. Search updater/Worker/restart/Backend/task logs for exact token and require zero matches. Confirm current+previous retention.

- [ ] **Step 8: Update progress and commit evidence**

```powershell
git add docs/PROGRESS.md
git commit -m "docs(progress): record unattended Worker updates"
```

- [ ] **Step 9: Final verification**

Repeat focused suite, distribution parity, live status/preflight/CUDA, exact commit equality, task readiness, `current` target, shared inventory and updater `ready`. Report retained C backup path.
