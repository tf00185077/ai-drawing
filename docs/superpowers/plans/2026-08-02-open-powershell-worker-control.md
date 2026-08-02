# Open PowerShell Worker Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace paired, validation-heavy Worker management with unauthenticated arbitrary Windows PowerShell control on the existing Worker port 8791, while sending ordinary ComfyUI prompts without update, preflight, resource-plan, or digest gates.

**Architecture:** The Windows Worker keeps its existing FastAPI/Uvicorn listener and gains a small process manager responsible only for starting, observing, and cancelling Windows PowerShell 5.1 processes. The Mac Backend stops attaching Bearer credentials and exposes the command manager through its existing Worker client and `/api/workers` router; ordinary generation goes directly to `/prompt`. A one-time local administrator script copies the changed runtime files into the installed D-drive Worker and restarts its existing scheduled task without managed-updater, ACL, owner, hash, release-contract, or health validation.

**Tech Stack:** Python 3.11/3.12, FastAPI, Pydantic, httpx, subprocess/threading, Windows PowerShell 5.1, pytest, PowerShell Pester-free static tests.

---

## File map

- Create `worker/windows/powershell_control.py`: thread-safe, in-memory lifecycle manager for arbitrary PowerShell processes.
- Modify `worker/windows/worker.py`: remove endpoint authentication and add submit/status/cancel PowerShell routes.
- Create `backend/tests/test_worker_powershell_control.py`: isolated process-manager and Worker route tests with fake processes; tests never execute real PowerShell.
- Modify `backend/app/services/nvidia_worker.py`: remove token headers and submission gates; add PowerShell client methods.
- Modify `backend/app/api/workers.py`: treat a URL as configured and expose Mac-side command submit/status/cancel routes.
- Modify `backend/app/config.py`: retain the legacy token setting for configuration compatibility but document it as ignored.
- Modify `backend/tests/test_worker_pairing.py`: convert discovery/client expectations from paired auth to URL-only access.
- Modify `backend/tests/test_worker_resources.py`: prove prompt submission skips resource planning, digest synchronization, and node preflight.
- Modify `backend/tests/test_worker_runtime.py`: prove existing Worker routes accept requests without Authorization.
- Create `backend/tests/test_nvidia_worker_powershell.py`: test the Mac Backend command routes and raw script forwarding.
- Create `worker/windows/Enable-Open-PowerShell-Control.ps1`: one-time direct deployment to the installed D-drive Worker.
- Create `backend/tests/test_enable_open_powershell_control.py`: static PowerShell 5.1 and no-validation/no-extra-port checks.
- Modify `worker/windows/README.txt`: document the open-control security model and exact enablement command.
- Modify `.env.example`: make clear that `NVIDIA_WORKER_TOKEN` is legacy and ignored.
- Modify `docs/PROGRESS.md`: record the final architecture, operator action, tests, and security implications.

### Task 1: In-memory PowerShell command lifecycle

**Files:**
- Create: `worker/windows/powershell_control.py`
- Create: `backend/tests/test_worker_powershell_control.py`

- [ ] **Step 1: Write failing manager tests using an injected fake process**

Add tests that construct `PowerShellCommandManager(process_factory=factory, max_terminal_records=2)`. The fake factory must capture the exact executable, argument list, `cwd`, and script passed to `communicate(input=...)`, and provide controllable `returncode`, `stdout`, `stderr`, `terminate()`, and `kill()` behavior. Cover these exact assertions:

```python
command = manager.submit(
    script="Get-ChildItem C:\\\nWrite-Output '完成'",
    working_directory=r"D:\code\ai-drawing",
)
assert command["state"] == "running"
factory.release(returncode=0, stdout="完成\n", stderr="")
terminal = wait_for_terminal(manager, command["command_id"])
assert terminal["state"] == "completed"
assert terminal["exit_code"] == 0
assert factory.script == "Get-ChildItem C:\\\nWrite-Output '完成'"
assert factory.cwd == r"D:\code\ai-drawing"
assert factory.argv == [
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "-",
]
```

Also assert nonzero exit becomes `failed`, `cancel()` terminates a running process and yields `cancelled`, an unknown ID raises `PowerShellCommandNotFound`, timestamps are nonempty UTC ISO strings, and adding a third terminal command evicts only the oldest terminal record while never evicting a running record.

- [ ] **Step 2: Run the new tests and verify the module is absent**

Run: `pytest backend/tests/test_worker_powershell_control.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'powershell_control'`.

- [ ] **Step 3: Implement the minimal manager**

Create these public types and signatures in `worker/windows/powershell_control.py`:

```python
class PowerShellCommandNotFound(KeyError):
    pass


class PowerShellCommandManager:
    def __init__(
        self,
        *,
        process_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        max_terminal_records: int = 100,
        powershell_executable: str | None = None,
    ) -> None: ...

    def submit(self, *, script: str, working_directory: str | None) -> dict[str, Any]: ...
    def get(self, command_id: str) -> dict[str, Any]: ...
    def cancel(self, command_id: str) -> dict[str, Any]: ...
```

Use `uuid.uuid4()` for `command_id`, `datetime.now(timezone.utc).isoformat()` for timestamps, a `threading.RLock` for records/process maps, and one daemon thread per command. Start the process with `stdin/stdout/stderr=subprocess.PIPE`, `text=True`, `encoding="utf-8"`, `errors="replace"`, `shell=False`, `creationflags=subprocess.CREATE_NO_WINDOW`, and the exact PowerShell argument vector from Step 1. Feed `script` unchanged through `process.communicate(input=script)`; do not parse commands or paths and do not set a timeout. Return copied public dictionaries so callers cannot mutate manager state.

Each record must contain:

```python
{
    "command_id": str,
    "state": "running" | "completed" | "failed" | "cancelled",
    "exit_code": int | None,
    "stdout": str,
    "stderr": str,
    "created_at": str,
    "started_at": str,
    "finished_at": str | None,
}
```

On cancellation, call `terminate()`, wait at most five seconds inside the background worker, then call `kill()` only if the process still has not exited. A cancellation race must remain terminal and must never be overwritten as `completed` or `failed`. Retention applies only after a record becomes terminal and keeps the newest `max_terminal_records` terminal records.

- [ ] **Step 4: Run the manager tests**

Run: `pytest backend/tests/test_worker_powershell_control.py -q`

Expected: all manager tests pass and no real `powershell.exe` process is started.

- [ ] **Step 5: Commit the isolated manager**

```powershell
git add worker/windows/powershell_control.py backend/tests/test_worker_powershell_control.py
git commit -m "feat(worker): manage open PowerShell commands"
```

### Task 2: Open Worker routes and remove Worker authentication

**Files:**
- Modify: `worker/windows/worker.py`
- Modify: `backend/tests/test_worker_powershell_control.py`
- Modify: `backend/tests/test_worker_runtime.py`

- [ ] **Step 1: Write failing HTTP route tests**

Extend `backend/tests/test_worker_powershell_control.py` with a fake manager injected into the Worker module and FastAPI `TestClient` assertions for:

```python
response = client.post(
    "/v1/powershell/commands",
    json={
        "script": "$x = '任意內容'; Write-Output $x",
        "working_directory": r"C:\Windows\System32",
    },
)
assert response.status_code == 202
assert fake_manager.submitted == {
    "script": "$x = '任意內容'; Write-Output $x",
    "working_directory": r"C:\Windows\System32",
}
assert "Authorization" not in response.request.headers
```

Assert `GET /v1/powershell/commands/cmd-1` returns the manager record, `POST /v1/powershell/commands/cmd-1/cancel` returns the cancelled record, unknown IDs return 404 with `detail.code == "powershell_command_not_found"`, malformed JSON/wrong field types return FastAPI 422, and strings are not rejected based on command text or working-directory location.

In `backend/tests/test_worker_runtime.py`, replace authenticated requests with requests that omit `Authorization` and assert representative existing routes (`/v1/worker/status`, `/v1/admin/update/status`, `/v1/admin/restart/status`, `/v1/resources/plan`, `/v1/workflows/preflight`, `/prompt`, `/queue`) do not return 401.

- [ ] **Step 2: Run focused route tests and verify they fail**

Run: `pytest backend/tests/test_worker_powershell_control.py backend/tests/test_worker_runtime.py -q`

Expected: PowerShell routes return 404 and existing unauthenticated routes return 401.

- [ ] **Step 3: Remove auth dependencies and add the three routes**

In `worker/windows/worker.py`:

- remove `Depends` and `Header` imports;
- delete `_auth`;
- remove every `dependencies=[Depends(_auth)]` argument from Worker, admin, resource, preflight, prompt, history, queue, view, and upload routes;
- import `PowerShellCommandManager` and `PowerShellCommandNotFound`;
- instantiate one module-level `_powershell_commands = PowerShellCommandManager()`;
- define a Pydantic request model containing only `script: str` and `working_directory: str | None = None`;
- add the following handlers without any dependency or authorization check:

```python
@app.post("/v1/powershell/commands", status_code=202)
def submit_powershell_command(request: PowerShellCommandRequest) -> dict[str, Any]:
    return _powershell_commands.submit(
        script=request.script,
        working_directory=request.working_directory,
    )


@app.get("/v1/powershell/commands/{command_id}")
def powershell_command_status(command_id: str) -> dict[str, Any]:
    try:
        return _powershell_commands.get(command_id)
    except PowerShellCommandNotFound as error:
        raise HTTPException(
            404, detail={"code": "powershell_command_not_found"}
        ) from error


@app.post("/v1/powershell/commands/{command_id}/cancel")
def cancel_powershell_command(command_id: str) -> dict[str, Any]:
    try:
        return _powershell_commands.cancel(command_id)
    except PowerShellCommandNotFound as error:
        raise HTTPException(
            404, detail={"code": "powershell_command_not_found"}
        ) from error
```

Do not add empty-script checks, command allowlists, path existence checks, path-root checks, token fallbacks, hash checks, or confirmation flags.

- [ ] **Step 4: Run focused Worker tests**

Run: `pytest backend/tests/test_worker_powershell_control.py backend/tests/test_worker_runtime.py -q`

Expected: all tests pass; no endpoint test needs an Authorization header.

- [ ] **Step 5: Commit the open Worker API**

```powershell
git add worker/windows/worker.py backend/tests/test_worker_powershell_control.py backend/tests/test_worker_runtime.py
git commit -m "feat(worker): expose unauthenticated PowerShell control"
```

### Task 3: Make the Mac Worker client URL-only and add PowerShell operations

**Files:**
- Modify: `backend/app/services/nvidia_worker.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_worker_pairing.py`
- Create: `backend/tests/test_nvidia_worker_powershell.py`

- [ ] **Step 1: Write failing URL-only discovery and client tests**

Update `backend/tests/test_worker_pairing.py` so `_probe_worker_status`, `discover_worker_url`, `NvidiaWorkerClient`, and `get_worker_client` are exercised without a token. Capture outgoing requests and assert `Authorization` is absent. Configure only `nvidia_worker_url` and assert `get_worker_client()` succeeds. Configure discovery with an unreachable remembered URL and assert the retry scans the configured CIDR and adopts a reachable protocol-2 Worker without credentials.

Create `backend/tests/test_nvidia_worker_powershell.py` and assert these client methods use the exact paths and payloads:

```python
accepted = client.submit_powershell(
    "$env:TEST='任意'; Get-ChildItem D:\\",
    working_directory=r"D:\code",
)
status = client.powershell_status(accepted["command_id"])
cancelled = client.cancel_powershell(accepted["command_id"])
```

Expected requests:

```text
POST /v1/powershell/commands
GET  /v1/powershell/commands/{command_id}
POST /v1/powershell/commands/{command_id}/cancel
```

The POST JSON must preserve the script and working-directory strings exactly.

- [ ] **Step 2: Run the client tests and verify the old token contract fails**

Run: `pytest backend/tests/test_worker_pairing.py backend/tests/test_nvidia_worker_powershell.py -q`

Expected: failures show a required `token` constructor argument, Authorization headers, or missing PowerShell client methods.

- [ ] **Step 3: Remove client authentication and add command methods**

In `backend/app/services/nvidia_worker.py`:

- remove the `token` parameter from `_probe_worker_status`, `discover_worker_url`, and `NvidiaWorkerClient.__init__`;
- remove `_headers`, `_token`, and all Authorization merging;
- let explicitly supplied non-auth headers such as upload `Content-Type` pass through unchanged;
- call `discover_worker_url` without a token after connect failures;
- change `get_worker_client()` to require only `settings.nvidia_worker_url`;
- keep hostname/protocol matching and the runtime URL cache because those select the intended Worker, but do not use them as request authorization;
- add these methods:

```python
def submit_powershell(
    self,
    script: str,
    *,
    working_directory: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    return self._request(
        "POST",
        "/v1/powershell/commands",
        json={"script": script, "working_directory": working_directory},
        **({} if timeout is None else {"timeout": timeout}),
    ).json()

def powershell_status(
    self, command_id: str, *, timeout: float | None = None
) -> dict[str, Any]: ...

def cancel_powershell(
    self, command_id: str, *, timeout: float | None = None
) -> dict[str, Any]: ...
```

The latter methods use the GET and cancel paths from Step 1. Do not validate command IDs beyond placing them in the URL.

In `backend/app/config.py`, retain `nvidia_worker_token: str = ""` so old `.env` files continue loading, but add a comment that open-control mode ignores it. Do not make it a configuration gate.

- [ ] **Step 4: Run URL-only and command client tests**

Run: `pytest backend/tests/test_worker_pairing.py backend/tests/test_nvidia_worker_powershell.py -q`

Expected: all tests pass and captured headers contain no Authorization value.

- [ ] **Step 5: Commit the Mac client changes**

```powershell
git add backend/app/services/nvidia_worker.py backend/app/config.py backend/tests/test_worker_pairing.py backend/tests/test_nvidia_worker_powershell.py
git commit -m "feat(backend): control Worker without pairing auth"
```

### Task 4: Remove prompt-time update, preflight, and resource validation

**Files:**
- Modify: `backend/app/services/nvidia_worker.py`
- Modify: `backend/tests/test_worker_resources.py`
- Modify: `backend/tests/test_nvidia_worker_update.py`

- [ ] **Step 1: Write failing direct-submission tests**

In `backend/tests/test_worker_resources.py`, add a transport spy and submit a prompt containing checkpoint, LoRA, and image resource references. Assert the only prompt-submission request is:

```python
assert requests == [
    ("POST", "/prompt", {"prompt": prompt}),
]
```

Assert `/v1/resources/plan`, `/v1/resources/content`, and `/v1/workflows/preflight` are never requested and no file digest helper is called. Preserve the existing assertion that a non-2xx ComfyUI body is surfaced as `ComfyUIError` with its `node_errors` unchanged.

In `backend/tests/test_nvidia_worker_update.py`, replace the old prompt-time auto-update expectation with a test that sets `nvidia_worker_auto_update=True`, makes `ensure_worker_compatible` raise if called, and still observes exactly one `/prompt` request. This proves the legacy setting cannot reintroduce the managed validation path.

- [ ] **Step 2: Run the direct-submission tests and verify the gates still run**

Run: `pytest backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py -q`

Expected: the new assertions fail because `_preflight`, `_synchronize`, or `ensure_worker_compatible` is invoked.

- [ ] **Step 3: Reduce submission to a direct `/prompt` request**

In `backend/app/services/nvidia_worker.py`:

- remove the `ensure_worker_compatible` import;
- delete the auto-update branch from `submit_prompt`;
- remove `_preflight()` and `_synchronize()` calls from `_submit_prompt_once`;
- delete the now-unused `_preflight` and `_synchronize` methods;
- remove imports used only by resource scanning/digest planning, while retaining `upload_image()` for explicit file transfer;
- keep ComfyUI error-body parsing so errors originate from ComfyUI and remain actionable.

Do not replace these gates with node inspection, file existence checks, capacity checks, hashes, manifests, or a different pre-submit validation.

- [ ] **Step 4: Run prompt and update tests**

Run: `pytest backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py -q`

Expected: all tests pass; the direct-submission test records one `/prompt` call and zero validation/resource calls.

- [ ] **Step 5: Commit direct ComfyUI submission**

```powershell
git add backend/app/services/nvidia_worker.py backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py
git commit -m "refactor(worker): submit prompts without validation gates"
```

### Task 5: Expose PowerShell control through the existing Mac Backend API

**Files:**
- Modify: `backend/app/api/workers.py`
- Modify: `backend/tests/test_nvidia_worker_powershell.py`

- [ ] **Step 1: Write failing Mac API tests**

Use FastAPI `TestClient`, replace `get_worker_client()` with a fake, and test:

```python
response = client.post(
    "/api/workers/powershell/commands",
    json={
        "script": "Restart-Service Spooler",
        "working_directory": r"C:\",
    },
)
assert response.status_code == 202
assert fake.submitted == ("Restart-Service Spooler", r"C:\")
```

Also test GET status and POST cancel routes, exact `command_id` forwarding, unknown Worker/unreachable errors mapped to HTTP 503, and `/api/workers/status` reports `configured=True` when only `NVIDIA_WORKER_URL` is set. Do not test for a token or command allowlist.

- [ ] **Step 2: Run the API tests and verify the routes are absent**

Run: `pytest backend/tests/test_nvidia_worker_powershell.py -q`

Expected: the three Mac API routes return 404 and URL-only status reports not configured.

- [ ] **Step 3: Add Pydantic request and three API handlers**

In `backend/app/api/workers.py`, add a request model containing `script: str` and `working_directory: str | None = None`, then add:

```python
@router.post("/powershell/commands", status_code=202)
def submit_powershell_command(request: PowerShellCommandRequest) -> dict:
    try:
        return get_worker_client().submit_powershell(
            request.script,
            working_directory=request.working_directory,
        )
    except Exception as error:
        raise HTTPException(
            503, detail={"code": "worker_powershell_submit_failed"}
        ) from error
```

Add corresponding GET `/{command_id}` status and POST `/{command_id}/cancel` handlers using `powershell_status()` and `cancel_powershell()`. Do not constrain `command_id` length/content and do not inspect response state. Change `configured` in `worker_status()` to `bool(settings.nvidia_worker_url)`.

- [ ] **Step 4: Run the Mac API tests**

Run: `pytest backend/tests/test_nvidia_worker_powershell.py -q`

Expected: all tests pass and scripts are forwarded unchanged.

- [ ] **Step 5: Commit the Mac API surface**

```powershell
git add backend/app/api/workers.py backend/tests/test_nvidia_worker_powershell.py
git commit -m "feat(backend): proxy open Worker PowerShell control"
```

### Task 6: Add the one-time direct D-drive deployment script

**Files:**
- Create: `worker/windows/Enable-Open-PowerShell-Control.ps1`
- Create: `backend/tests/test_enable_open_powershell_control.py`

- [ ] **Step 1: Write failing static deployment tests**

Create tests that read the script as text and assert it:

- requires an elevated process using the current principal's Administrator role;
- sets `$SourceWindowsRoot = "D:\code\ai-drawing\worker\windows"` and `$InstalledWorkerRoot = "D:\code\AI-Drawing-Worker"`;
- retains `-ExpectedCommit` and executes both `git rev-parse HEAD` and `git rev-parse origin/main`, requiring each to equal the supplied commit;
- stops and starts only scheduled task `AI-Drawing NVIDIA Worker`;
- copies `worker.py` and `powershell_control.py` directly into `current\worker\windows`;
- stops only the process listening on port 8791 and never targets 8188;
- waits for a port-8791 listener and prints `OPEN_POWERSHELL_CONTROL_READY`;
- contains none of these strings: `Get-FileHash`, `SHA256`, `Assert-Secure`, `Set-Secure`, `Get-Acl`, `Set-Acl`, `Owner`, `releases`, `resources/plan`, `workflows/preflight`, `worker/status`, `Deploy-UpdaterBootstrap`, `Migrate-Worker`;
- parses under Windows PowerShell 5.1 with `[scriptblock]::Create()`.

- [ ] **Step 2: Run the deployment tests and verify the script is absent**

Run: `pytest backend/tests/test_enable_open_powershell_control.py -q`

Expected: failure because `worker/windows/Enable-Open-PowerShell-Control.ps1` does not exist.

- [ ] **Step 3: Implement the direct deployment script**

Define this parameter and boundary:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$ExpectedCommit
)
```

The script must:

1. fail with `ADMINISTRATOR_REQUIRED` when not elevated;
2. run `git.exe -C D:\code\ai-drawing fetch origin main`;
3. read `HEAD` and `origin/main`, require equality, then require both equal `$ExpectedCommit`;
4. require `D:\code\AI-Drawing-Worker\current\worker\windows` to exist;
5. stop scheduled task `AI-Drawing NVIDIA Worker` if running;
6. find `Get-NetTCPConnection -State Listen -LocalPort 8791` and stop only those owning processes;
7. copy the two runtime files with `Copy-Item -LiteralPath ... -Force`;
8. start the same scheduled task;
9. poll `Get-NetTCPConnection -State Listen -LocalPort 8791` for up to 60 seconds;
10. print `OPEN_POWERSHELL_CONTROL_READY` and exit 0 when the listener appears, otherwise throw `WORKER_8791_NOT_LISTENING`.

Do not call an HTTP health endpoint, inspect owner/ACL, hash files, compare deployed bytes, invoke updater/recovery/migration, modify the firewall, create another listener, or delete any Worker data.

- [ ] **Step 4: Run the deployment script tests**

Run: `pytest backend/tests/test_enable_open_powershell_control.py -q`

Expected: all tests pass, including a real Windows PowerShell 5.1 parser invocation that does not execute the script body.

- [ ] **Step 5: Commit the direct deployment path**

```powershell
git add worker/windows/Enable-Open-PowerShell-Control.ps1 backend/tests/test_enable_open_powershell_control.py
git commit -m "feat(worker): deploy open control directly to D drive"
```

### Task 7: Update operator documentation and compatibility configuration

**Files:**
- Modify: `worker/windows/README.txt`
- Modify: `.env.example`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Document the exact operational and security contract**

In `worker/windows/README.txt`, state plainly that:

- port 8791 accepts unauthenticated arbitrary PowerShell from any host that can reach it;
- commands run as the Windows account used by the existing Worker scheduled task, not automatically as SYSTEM;
- pairing/token files are legacy and ignored;
- no WinRM, SSH, SMB, RDP, VNC, or additional Windows listener is enabled;
- command state is in memory and is lost when the Worker restarts;
- ordinary generation goes directly to ComfyUI and ComfyUI returns missing-resource/node/capacity errors;
- the one-time administrator command is exactly:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& "D:\code\ai-drawing\worker\windows\Enable-Open-PowerShell-Control.ps1" `
    -ExpectedCommit "<40-character commit shown after the final push>"
```

The angle-bracket value is documentation notation, not executable code; the final handoff must replace it with the actual pushed commit in the user-facing command.

- [ ] **Step 2: Mark the legacy environment setting as ignored**

In `.env.example`, retain `NVIDIA_WORKER_TOKEN=` for backward-compatible parsing but add an adjacent comment:

```dotenv
# Legacy compatibility only; open-control Worker requests do not use this value.
NVIDIA_WORKER_TOKEN=
```

Keep `NVIDIA_WORKER_AUTO_UPDATE=false` and explain that managed updater coordination is not part of prompt submission or open PowerShell control.

- [ ] **Step 3: Record completion criteria in progress documentation**

Add a dated `2026-08-02` entry to `docs/PROGRESS.md` containing the three Worker routes, three Mac routes, URL-only discovery, direct `/prompt` behavior, direct deployment script, current-account execution boundary, in-memory retention boundary, and explicit no-extra-port/no-auth security consequence. Record that `HEAD == origin/main` and `-ExpectedCommit` are the only retained deployment version checks.

- [ ] **Step 4: Review documentation for forbidden legacy guidance**

Run:

```powershell
rg -n "Bearer|paired|pairing|required token|resources/plan|workflows/preflight|managed updater" worker/windows/README.txt .env.example docs/PROGRESS.md
```

Expected: matches appear only in historical context or explicit statements that pairing, token auth, preflight, resource planning, and managed-updater gating are disabled; no instruction tells the operator to use them for the open-control path.

- [ ] **Step 5: Commit documentation**

```powershell
git add worker/windows/README.txt .env.example docs/PROGRESS.md
git commit -m "docs: describe open Worker PowerShell control"
```

### Task 8: Full verification, package build, and publication

**Files:**
- Modify if mechanically generated: Windows Worker ZIP output selected by `scripts/build-windows-worker.py`
- Verify: all files changed in Tasks 1-7

- [ ] **Step 1: Run focused Worker and Backend tests**

Run:

```powershell
pytest backend/tests/test_worker_powershell_control.py backend/tests/test_worker_runtime.py backend/tests/test_worker_pairing.py backend/tests/test_nvidia_worker_powershell.py backend/tests/test_worker_resources.py backend/tests/test_nvidia_worker_update.py backend/tests/test_enable_open_powershell_control.py -q
```

Expected: all selected tests pass; Windows-only tests may skip only when their prerequisite is unavailable, and the PowerShell parser test must run on this Windows host.

- [ ] **Step 2: Run the complete Backend and MCP suite and classify only known unrelated baselines**

Run:

```powershell
pytest backend/tests/ mcp-server/tests/ -q
```

Expected: all relevant Worker/control tests pass. If the previously documented Prompt Library/multi-LoRA baseline failures remain, record their exact count and names in `docs/PROGRESS.md`; do not weaken or delete unrelated tests to obtain a green result.

- [ ] **Step 3: Verify no Worker route retains an auth dependency and no prompt gate remains**

Run:

```powershell
rg -n "Depends\(_auth\)|Authorization|Bearer|_preflight\(|_synchronize\(|ensure_worker_compatible\(" worker/windows/worker.py worker/windows/powershell_control.py backend/app/services/nvidia_worker.py backend/app/api/workers.py
```

Expected: no matches for Worker authentication, prompt preflight/synchronization, or prompt-time update coordination. Any occurrence in comments must be removed or rewritten to avoid misleading future maintenance.

- [ ] **Step 4: Build the Windows distribution and verify required files are included**

Run:

```powershell
python scripts/build-windows-worker.py
```

Expected: build succeeds and the produced archive contains `worker.py`, `powershell_control.py`, `Enable-Open-PowerShell-Control.ps1`, and the updated `README.txt`. The archive SHA-256 may be reported as publication metadata, but must not be used by runtime, deployment, or command execution.

- [ ] **Step 5: Confirm repository cleanliness without touching user-owned files**

Run:

```powershell
git status --short
git diff --check
```

Expected: no whitespace errors. Preserve `.codex/config.toml` and `scripts/Run-Live-Worker-Migration.ps1` exactly as user-owned untracked files; do not stage or delete them.

- [ ] **Step 6: Commit any generated package/progress metadata**

Stage only the archive/build metadata and `docs/PROGRESS.md` changes produced by verification, then commit:

```powershell
git commit -m "build: publish open-control Windows Worker"
```

If the build output is intentionally ignored and no tracked files changed, skip this commit rather than creating an empty commit.

- [ ] **Step 7: Push main and verify the two retained Git checks**

Run:

```powershell
git push origin main
$Head = (git rev-parse HEAD).Trim()
$OriginMain = (git rev-parse origin/main).Trim()
if ($Head -ne $OriginMain) { throw "HEAD_ORIGIN_MAIN_MISMATCH" }
$Head
```

Expected: push succeeds and one 40-character commit is printed with `HEAD == origin/main`.

- [ ] **Step 8: Hand off the single local Windows enablement command**

Use the exact printed commit from Step 7:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& "D:\code\ai-drawing\worker\windows\Enable-Open-PowerShell-Control.ps1" `
    -ExpectedCommit "PRINTED_COMMIT_FROM_STEP_7"
```

Expected local output: `OPEN_POWERSHELL_CONTROL_READY`. This is the only remaining local administrator action. Do not run managed updater/bootstrap/migration and do not remove models, cache, input, output, shared data, or releases.

## Self-review result

- Spec coverage: all approved requirements map to Tasks 1-8, including unauthenticated 8791-only control, current-account execution, arbitrary script/cwd, lifecycle/cancel, no prompt/resource/update validation, URL-only discovery, direct deployment, and retained `HEAD == origin/main` plus `-ExpectedCommit` checks.
- Placeholder scan: the implementation steps contain exact paths, signatures, commands, and expected results. The documentation-only `<40-character commit shown after the final push>` is explicitly identified as notation and the final handoff step requires replacing it with the actual commit.
- Type consistency: Worker and Mac use the same `command_id`, `script`, `working_directory`, state names, and submit/status/cancel paths throughout the plan.
