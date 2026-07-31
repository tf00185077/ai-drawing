# Task 5: Privileged Orchestrator and Distribution

## Status

DONE

## RED

- State/activation contract first failed during collection because `ActiveUpdateRequest` did not exist. Follow-up RED tests required locked typed active-request reads, terminal rollback persistence with private-message redaction, and an Activator callback after production start but before health. The initial focused run reported one collection error; after exposing the state type, the behavioral callback tests failed until the callback contract was implemented.
- Production adapter tests first failed during collection because `worker.windows.updater.windows_runtime` did not exist. They cover argv-only bounded subprocesses, detached no-window starts, stdout/stderr redaction, fixed scheduled-task start/stop, canonical secret-provider reads, all five health endpoints, CUDA/GPU evidence, exact commit propagation, and exception-token suppression.
- CLI/state claim tests produced **5 failed / 25 passed** for the missing typed request claim and one CLI collection error for the missing module. The behavior suite covers argument rejection without echo, the complete durable success path, stable pre/post-activation failure mapping, proven rollback, and forward-only resume from staging/installing/validating/activating/restarting.
- Bootstrap/installer/distribution RED produced **5 failed / 9 passed** for missing assets, ACL/task/shared contracts, and stale directory/ZIP payloads. A real temporary ProgramData test proves an unknown env key is rejected without echoing its value.
- Self-review RED caught three additional production issues: an unknown token-like error code remained in private state, the bootstrap used a .NET Core-only path helper, and Windows PowerShell 5.1 `Set-Content -Encoding UTF8` would add a BOM to Python-consumed files. PowerShell AST verification then caught the existing non-ASCII no-BOM installer text as invalid under Windows PowerShell decoding.

## GREEN

- `updater.cli` accepts no options or positional values. It loads only fixed ProgramData configuration, claims a strict request through `UpdateStateStore`, acquires a non-blocking global run lock, composes Task 1-4 contracts, and persists `fetching -> staging -> installing -> validating -> activating -> restarting -> ready`.
- Crash retries never move state backward. Pre-activation retries re-fetch only when the immutable candidate is absent, reuse a published candidate when present, revalidate before activation, and invoke the recovery-aware Activator from `activating` or `restarting`.
- `UpdateStateStore` now returns `ActiveUpdateRequest`, validates the fixed three-field Worker request, records typed terminal failures, canonicalizes unknown private/public error codes to `UPDATE_FAILED`, and redacts URL credentials, bearer values, named secrets, CR/LF, and oversized diagnostics.
- `Activator.activate(..., on_restarting=...)` invokes the callback only after production start and before production health. Callback failure enters the existing rollback path. Same-target crash retry announces restarting before health.
- `windows_runtime.py` supplies production `SubprocessCommandRunner`, `ScheduledTaskController`, `WorkerTokenProvider`, and `HttpHealthProbe`. Commands remain argv lists with positive timeouts, `shell=False`, `CREATE_NO_WINDOW`, detached staged output, and redacted captured output. The token is read only from canonical `config/worker.json`, never stored in repr/log/env/request/status/arguments.
- The probe checks ComfyUI `/system_stats` and `/object_info`, authenticated Worker status, empty resource plan, and empty-node workflow preflight, returning complete typed evidence for Task 4's strict validator.
- `UpdaterBootstrap.ps1` parses exactly four allowlisted keys without evaluation, validates the owned local Worker root, locates only `updater-runtime\Scripts\python.exe`, and invokes only `-m updater.cli` with no caller arguments or value output.
- The installer preserves an existing token, creates but never removes shared data, installs a dedicated updater venv/package, writes Python-consumed files as UTF-8 without BOM, applies fail-closed restricted ProgramData ACLs, and registers the fixed no-trigger SYSTEM/highest `AI-Drawing Worker Updater` task with `IgnoreNew` concurrency policy. Its action contains only the fixed ProgramData bootstrap path.
- Task 5 remains migration-ready only. A missing `current` junction returns `recovery_required`, does not start/stop production, does not create a guessed junction, and preserves the legacy runtime. Task 7 owns transactional C-to-D migration and the first release/current creation.
- The build excludes Python bytecode and rebuilds directory plus ZIP assets. Tests compare source, directory distribution, and ZIP updater bytes.

## Verification

- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1` -- passed and rebuilt the directory/ZIP distribution.
- `py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py backend/tests/test_worker_updater_git.py backend/tests/test_worker_updater_runtime.py backend/tests/test_worker_updater_cli.py backend/tests/test_worker_all_entrypoints.py -q` -- **206 passed, 2 pre-existing warnings**.
- `py -3.11 -m compileall -q worker\windows\updater worker\windows\worker.py` -- passed.
- Windows PowerShell AST parsing -- `UpdaterBootstrap.ps1`, `Install-Worker.ps1`, `Start-Worker.ps1`, and `build-windows-worker.ps1` all parsed without errors.
- `git diff --check` -- passed; only the repository's expected LF-to-CRLF checkout notices were printed.
- No production Worker, ComfyUI, port, repository, ProgramData directory, ACL, installer, or Scheduled Task was contacted or mutated. All PowerShell behavior used temporary ProgramData or source/AST contracts; all task/health/process boundaries used fakes except a harmless local Python subprocess.

## Self-review

- Confirmed no request-selected path, URL, branch, remote, task, executable, module, or command reaches production adapters.
- Confirmed activation state changes to `restarting` before health and callback persistence failure cannot leave an untracked candidate reported ready.
- Confirmed unknown error codes and arbitrary exception text cannot reach public state, private error-code fields, subprocess output, or bootstrap output with token material.
- Confirmed missing migration state fails closed and legacy/shared/token data is not deleted.
- Confirmed the updater task has no trigger and receives neither token nor updater.env values in its action.

## Commit

- `feat(worker): install privileged update orchestrator`

---

## Fix Round 1

### RED

- The ACL review suite first reported **2 failed / 1 skipped**: the installer had no SID-based, read-back-verifying ACL helper and accepted an ownership marker on an insecure pre-existing root. A subsequent real temporary junction test failed because the required no-follow traversal did not exist.
- The hardened health suite first reported **7 failed / 24 passed**: the probe inherited the process-global proxy opener, sent an empty node list, and accepted partial status, object-info, and resource-plan responses.
- Request-consumption tests first reported **3 failures**: replaying a terminal request queued it again, and an active request could be claimed with an inconsistent ID or commit.
- Timeout tests first reported **2 failures**: `subprocess.run` leaked `TimeoutExpired` directly and process cleanup chained the exception carrying captured/argv data.

### GREEN

- `WorkerSecurity.ps1` now uses the well-known SYSTEM (`S-1-5-18`) and Administrators (`S-1-5-32-544`) SIDs, sets SYSTEM ownership, disables inherited ACLs at roots, installs only two inheritable allow/full-control rules, and fails closed after re-reading owner, protection, principal, access type, and rights for every ACE.
- Worker and ProgramData roots reject reparse points. Pre-existing Worker roots require the exact ownership marker plus verified secure ACLs across existing updater executable trees; pre-existing insecure layouts point to Task 7 migration. Fresh roots are secured before executable content is written, and updater runtime/package plus bootstrap/environment descendants are inherited and re-verified.
- Tree traversal uses an iterative no-follow walk. It detects any reparse point before ACL mutation, and a real temporary junction test proves an external target is rejected rather than traversed.
- `UrllibJsonTransport` owns a dedicated `ProxyHandler({})` opener. A malicious local proxy integration proves the Authorization header reaches only the loopback target.
- Health evidence now requires protocol 2, update capability 1, the exact source commit, ready ComfyUI status, a CUDA device with a non-empty GPU name, all six base workflow node types, `missing == []`, and exact ready/empty-missing preflight flags.
- Request claim is one locked state transaction. Active state requires the request-file ID and commit to match private state exactly; a terminal record with the same ID is a durable no-op acknowledgement, the atomically replaced request file remains crash-replay safe, and only a new request ID can queue new work. A terminal no-op exits successfully.
- Command and process-wait timeouts translate to fixed `TimeoutError` messages with `from None`, never retaining captured stdout/stderr or sensitive argv in the visible exception chain.

### Verification

- ACL integration: **2 passed / 1 skipped**. The mandatory temporary insecure-root and junction tests passed; the exact-owner/only-two-ACE mutation test requires an elevated Windows pytest process and was skipped in this non-elevated session.
- `py -3.11 -m pytest backend/tests/test_worker_updater_cli.py backend/tests/test_worker_updater_state.py -q` -- **67 passed**.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-windows-worker.ps1` -- passed and rebuilt directory plus ZIP assets.
- Focused Task 1-5 suite -- **225 passed / 1 skipped / 2 pre-existing warnings**.
- Python compileall, Windows PowerShell AST parsing for all changed/entry scripts, and `git diff --check` -- passed.
- No production Worker, ComfyUI, ProgramData root, ACL, installer, or Scheduled Task was contacted or mutated.
