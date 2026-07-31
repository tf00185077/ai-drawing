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
