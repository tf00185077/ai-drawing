# Task 6 implementation report

## Result

Implemented Docker preflight/mount/Compose/readiness operations and the transactional
one-command launcher state machine.

Commit: `b367ddd feat: orchestrate one-command application startup`

## Changed files

- `.env.example`
- `scripts/launcher/docker.py`
- `scripts/launcher/cli.py`
- `scripts/launcher/models.py` (minimal integration: selected application ports)
- `scripts/launcher/configuration.py` (minimal integration: render selected ports and
  external-without-local-path connectivity)
- `scripts/tests/test_docker_launcher.py`
- `scripts/tests/test_cli.py`
- `scripts/tests/test_models.py` (replace obsolete Task 1 no-op CLI expectation with
  parser-contract coverage)
- `scripts/tests/test_configuration.py`

The main checkout and its unrelated root `package-lock.json` were not touched.

## TDD evidence

### Requested RED command and host limitation

Command:

```text
uv run --python 3.12 --with pytest pytest scripts/tests/test_docker_launcher.py scripts/tests/test_cli.py -q
```

Output:

```text
error: Failed to spawn: `pytest`
  Caused by: Application Control policy blocked this file. (os error 4551)
```

This is the same Windows policy limitation recorded by earlier launcher tasks. The
same uv-managed Python 3.12 environment was invoked through the interpreter.

### Valid initial RED

Command:

```text
uv run --python 3.12 --with pytest python -m pytest scripts/tests/test_docker_launcher.py scripts/tests/test_cli.py -q
```

Output:

```text
ERROR scripts/tests/test_docker_launcher.py
ModuleNotFoundError: No module named 'launcher.docker'
1 error in 0.14s
```

### Refinement REDs

The first GREEN exposed one scripted-answer mismatch, corrected to express the actual
single "continue disabled" prompt:

```text
1 failed, 28 passed in 0.20s
```

Task 1 regression then demonstrated that the seven stable commands must remain stable
while `dry-run` is a launcher-only command:

```text
2 failed, 169 passed in 2.22s
```

Transaction/external-readiness tests were added before their fixes:

```text
2 failed, 18 passed in 0.14s
```

They demonstrated that explicit external mode was accepted without a probe and that
`start` did not restore state.json after starting a new managed PID.

DefaultServices identity and structured-port RED:

```text
2 failed, 20 passed in 0.19s
```

These demonstrated an invalid port being accepted and a stale managed PID being
claimed solely because an API answered on the same port.

Duplicate-process safety RED:

```text
1 failed in 0.17s
Expected COMFYUI_MANAGED_NOT_READY, got COMFYUI_NOT_CONTROLLABLE
```

Mount diagnostics RED:

```text
1 failed in 0.09s
FileNotFoundError escaped from Path.resolve(strict=True)
```

Safe example port ownership RED:

```text
1 failed in 0.06s
assert 'BACKEND_PORT=8001' in .env.example
```

### Final focused GREEN

Command:

```text
uv run --python 3.12 --with pytest python -m pytest scripts/tests/test_docker_launcher.py scripts/tests/test_cli.py -q
```

Output:

```text
....................................                                     [100%]
36 passed in 0.16s
```

### Final full launcher GREEN

Command:

```text
uv run --python 3.12 --with pytest python -m pytest scripts/tests -q
```

Output:

```text
........................................................................ [ 40%]
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 2.11s
```

Additional verification:

```text
python -m compileall -q scripts
uv run --python 3.12 --with ruff python -m ruff check scripts/launcher scripts/tests/test_cli.py scripts/tests/test_docker_launcher.py scripts/tests/test_configuration.py scripts/tests/test_models.py
git diff --check
```

All exited 0; Ruff reported `All checks passed!`.

## State-transition analysis

- No command plus no valid state resolves to `setup`; no command plus valid state
  resolves to `start`.
- `setup` and `reconfigure` run Docker preflight, choose unoccupied loopback ports,
  resolve the explicit ComfyUI decision, start only controllable managed ComfyUI,
  probe explicit external APIs, mount-probe resolved paths, stage/validate config,
  atomically publish config, start Compose, then bound-check Backend and Frontend.
- Interactive configuration supports decline, already-running external API, bounded
  discovered roots, existing controllable installation, automatic pinned installation,
  explicit CPU fallback after accelerated smoke failure, and disabled continuation.
- Noninteractive setup requires `--comfyui-mode`; managed additionally requires an
  explicit `--comfyui-path`. It never reads stdin for a missing decision.
- `start` reuses generated ports, never rewrites config unless a newly ready managed
  PID must be recorded, validates current Compose, and uses the same readiness gates.
- `stop` stops Compose and only calls the Task 5 stop boundary for managed state.
  External and disabled modes never receive a termination request.
- `status`, `logs`, `update-comfyui`, and mutation-free `dry-run` are wired. The stable
  command enum remains the approved seven-command contract; `dry-run` is parser-only.

## Rollback analysis

- Setup/reconfigure snapshot `.env`, the local Compose override, and launcher state
  before publication. Task 3 performs staged Compose validation before atomic replace.
- After any process/config/Compose/readiness failure, rollback attempts Compose down,
  atomic config/state restoration, identity-safe stop of only the process started by
  the current transaction, and restart of previously-running Compose.
- All rollback steps are attempted even if one fails. Partial rollback produces the
  stable `ROLLBACK_INCOMPLETE` code without exposing raw exception content.
- `start` uses the same snapshot so a newly recorded managed PID cannot remain stale
  when Backend/Frontend startup subsequently fails.
- An old managed process is not stopped during reconfiguration until the new
  configuration and both application readiness gates succeed.

## Docker and security analysis

- Docker daemon and Compose version are queried with structured lists. Compose must
  parse as v2.24.0 or newer.
- Every Docker/Compose command is an argument list. No shell execution, process-owner
  enumeration, termination command, or interpolated shell string is used.
- Compose always receives explicit absolute env/base/override paths. Validation uses
  the staged env and override paths supplied by Task 3.
- Occupied ports are never terminated; bounded ascending alternatives are selected.
- Mount probes resolve existing directories, require containment in explicit allowed
  project/data/ComfyUI roots, and use the exact `busybox:1.36.1` image tag.
- HTTP readiness uses a monotonic deadline, caps per-request timeout and sleeps to the
  remaining duration, and rejects success observed at/after the deadline.
- A persisted managed PID is trusted only when Task 2 returns the complete recorded
  process identity. A different process serving the same port is downgraded to
  external. A known live managed process whose API is not ready is never started twice.
- Errors are `code + message + hint`. Raw command stderr, install exception text,
  `.env` contents, authorization, tokens, passwords, and secrets are never emitted.
- Selected Backend/Frontend ports are generated into `.env`; `.env.example` contains
  only safe values and the existing placeholder authorization comment.

## Self-review

- Verified daemon/Compose failures, version parsing, staged Compose commands, path
  containment, missing mounts, exact alternate-port behavior, and deadline polling.
- Verified every requested interactive/noninteractive branch, default command routing,
  all commands, old external ownership, stale managed identity, rollback sequencing,
  rollback-step failures, and secret-free unexpected-error output.
- Verified changed/staged names before commit; no unrelated file was staged.
- Secret-pattern audit found only the documented placeholder and tests asserting
  redaction/preservation; no credential value is present.

## Concerns / environment notes

- `.cursor/skills/comfyui-api-client/SKILL.md` is absent in the worktree, so the
  approved design/plan and Tasks 1-5 interfaces were used as the documented fallback.
- The exact `pytest.exe` form is blocked by Windows Application Control; interpreter
  invocation passes in the same uv environment.
- Docker commands, Linux, and macOS are covered through injected boundaries on this
  Windows host. Real Docker/platform smoke remains Task 10 work.
- Task 7 still owns final Compose packaging. Its known gate remains: remove base
  Compose `DATABASE_URL`/`PROMPT_LIBRARY_DIR` overrides that defeat generated `.env`,
  make service env-file behavior compatible with staged/first-run validation, and
  consume generated `BACKEND_PORT`/`FRONTEND_PORT`. Task 6 tests deliberately use
  injected Compose fixtures and do not claim the current pre-Task-7 Compose is final.

---

## Review remediation

Review-fix commit:
`d517c32 fix: complete launcher orchestration contracts`

All Critical, Important, and Minor findings from the Task 6 review were addressed in
coherent TDD waves.

### Review RED evidence

Ownership/provenance/stop-result tests first produced:

```text
7 failed, 37 passed in 0.35s
```

The failures demonstrated missing installation provenance, a discovered root being
allowed to update, same-root reconfigure discarding a verified PID, and a failed Task 5
stop being reported as success.

Relay and exact Compose restoration began with a missing-interface collection RED:

```text
ImportError: cannot import name 'compose_up_services' from 'launcher.docker'
1 error in 0.19s
```

After the first relay implementation, transaction tests showed the remaining relay
replacement gaps:

```text
2 failed, 48 deselected in 0.17s
```

They proved that a new relay was stopped on failure but the exact prior relay was not
restored, and that a successful disabled transition left the old relay running.

Dry-run, ports, and loaded-port validation RED:

```text
8 failed, 29 passed in 0.30s
```

This showed dry-run calling the installer, alternate ports being silently accepted,
and bool/out-of-range persisted ports passing through.

Recovery-choice RED:

```text
4 failed, 37 passed in 0.34s
```

This showed managed start and mount failures lacking retry/CPU/disabled recovery and
noninteractive recovery returning the wrong generic failure rather than a missing
decision.

Status/log contract RED:

```text
4 failed, 40 passed in 0.33s
```

The implementation exposed no per-service/dependency report and emitted no combined
logs. A follow-up log RED proved that masking only the word `Bearer` leaked the rest of
an authorization line.

Additional safety REDs separately proved:

- Task 5 ready state discarded launcher install provenance.
- Compose-down failure prevented relay/Comfy stop attempts.
- documentation-range `192.0.2.1` passed a broad `is_private` relay check.
- pre-setup status attempted Compose with missing config.
- same-root/different-device planning relabelled an existing PID.
- unverified relay ownership was included in a rollback snapshot.

### Review GREEN evidence

Fresh focused review suite:

```text
uv run --python 3.12 --with pytest python -m pytest scripts/tests/test_docker_launcher.py scripts/tests/test_cli.py scripts/tests/test_models.py -q

........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 0.35s
```

Fresh full launcher regression:

```text
uv run --python 3.12 --with pytest python -m pytest scripts/tests -q

........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
.                                                                        [100%]
217 passed in 2.04s
```

Fresh static verification:

```text
python -m compileall -q scripts
uv run --python 3.12 --with ruff python -m ruff check scripts/launcher scripts/tests/test_cli.py scripts/tests/test_docker_launcher.py scripts/tests/test_models.py
git diff --check

All checks passed; each command exited 0.
```

### Safety and transaction table

| Event | State/config | Comfy process | Linux relay | Compose |
|---|---|---|---|---|
| Dry run | read/plan only; no writes or mkdir | never start/stop/install | never start/stop | preflight only; no run/up/down |
| New connected setup | staged validation then atomic publish | record only ready managed identity; external untouched | validated RFC1918 Docker bridge gateway to loopback target; separate state | full up after relay readiness |
| Reconfigure same verified process/root/port/device | preserve full ownership and provenance | reuse exact PID/identity | reuse verified matching relay | replace only after validation |
| Reconfigure replacement | old config/process retained until new app ready | stop old only after Backend+Frontend ready | replace before Compose; rollback stops new and recreates exact old bind/target | exact prior running service set restored with `--no-deps` |
| Transition to disabled | publish disabled env/no Comfy mounts | old managed stopped only after app ready | old launcher relay stopped only after app ready | rollback restores old config/service set/relay |
| Start/mount failure recovery | retry, explicit CPU, disabled, or abort; changed mode/device is atomically written | CPU is never implicit; newly unused managed PID must stop successfully | disabled creates no relay | readiness remains bounded |
| Normal stop | cleared ownership saved only from truthful Task 5 result | external never receives stop; hard failure is nonzero | launcher-owned relay is stopped even for external Comfy; failure is nonzero | down failure is reported but does not skip safe process stops |
| Rollback cleanup failure | old snapshot restoration still attempted | new-process stop false is `ROLLBACK_INCOMPLETE` | new-relay stop/old-relay restore false is `ROLLBACK_INCOMPLETE` | down/precise restore failures are accumulated and nonzero |

### Review-fix implementation notes

- Linux obtains the bridge gateway with structured `docker network inspect bridge`
  arguments. The address must be an IPv4 member of exactly RFC1918 10/8, 172.16/12,
  or 192.168/16; wildcard, loopback, link-local, multicast, documentation, public, and
  invalid addresses are rejected. Task 5 performs the same bind validation again.
- Relay state remains separate in `relay-state.json`. Only complete verified relay
  identities are transaction snapshots. Replacement startup restores a safely stopped
  old relay if the new relay itself cannot start; later transaction rollback stops the
  new relay then recreates the prior bind/target.
- Dry-run now treats an absent managed install target as a plan. Tests spy on every
  install/start/stop/save/write/mount/relay/Compose mutation boundary and observe none.
- `LauncherState` now carries backward-safe `launcher_installed`, `installed_root`, and
  `installed_commit`. Legacy or incomplete provenance loads as user-owned. Task 5
  process results are merged with provenance; a changed root resets it. Only verified
  launcher-installed roots can update.
- Persisted and selected ports require built-in `int` (not `bool`) in range 1..65535.
  Occupied defaults show alternatives; interactive users must confirm, while
  noninteractive callers must pass `--accept-alternate-ports`.
- Noninteractive recovery never reads stdin and requires explicit
  `--on-comfy-failure`/`--on-mount-failure`. Interactive recovery exposes bounded
  retry, explicit CPU, disabled continuation, or abort.
- Status reports Docker availability (after preflight), every Compose service state,
  Backend/Frontend reachability, Comfy reachability plus verified/stale/external
  ownership, relay state, model count, and stable hint. Pre-setup status gracefully
  reports an empty service set.
- Logs combine bootstrap, ComfyUI, relay, and Compose output. Missing files are labeled
  without failing. Authorization/token/secret/password/API-key values are redacted
  through end-of-line; raw command errors and `.env` contents are never emitted.

### Remaining environment notes after review fix

- Real Linux relay and macOS behavior still require Task 10 platform smoke. The relay
  implementation itself is Task 5 code; Task 6 exercises it through injected host,
  process-identity, Docker-inspection, readiness, and rollback boundaries.
- Task 7 must still consume generated application ports and remove Compose environment
  overrides that defeat generated data paths. The Task 6 APIs now expose exact staged
  files and per-service restoration needed for that convergence.

## Second re-review hardening (2026-07-20)

### RED evidence

Focused tests were added before each production change. The ownership and Docker
command-boundary wave first demonstrated the managed/external misclassification and
the commands incorrectly blocked by global preflight. The logging wave then produced
two failures (secret-line leakage and missing bootstrap audit log) while its two
non-mutation/cleanup cases already passed. The D-H wave produced:

```text
CLI: 5 failed, 1 passed
models: 1 failed
```

Those failures covered a stopped non-default ComfyUI root missing from discovery,
no manual-path opportunity, project ports treated as foreign, unknown external model
inventory labelled as empty, existing-state dry-run flags ignored, and forged install
provenance accepted across different roots. A separate RED proved that a reachable
API with an explicitly empty loader inventory returned unknown instead of confirmed
zero.

### GREEN implementation

- A previous managed process is preserved only after exact root, port, device, PID
  identity, and ready-API verification. An identity mismatch is external/unowned.
- Docker preflight blocks only setup/start/reconfigure. Stop still attempts every
  native cleanup, status reports Docker unavailable alongside native truth, logs
  remain locally useful, update is Docker-independent, and dry-run remains read-only.
- Mutating commands write a bounded 256 KiB rotating `bootstrap.log` containing only
  command lifecycle and stable error codes. Any line containing authorization,
  bearer, token, API-key, password, or secret markers is entirely redacted. Logging
  failure is always swallowed; status/logs/dry-run create no audit file merely to log.
- Discovery is finite and de-duplicated: explicit root, prior root, platform default,
  and a small platform-specific common-path list. Interactive users may enter another
  existing root; noninteractive execution never prompts.
- Reconfigure reads running services and persisted ports before selecting ports.
  Verified project-owned ports are reusable while genuinely foreign occupied ports
  still require the existing alternate-port consent contract.
- External ComfyUI model inventory is queried through bounded localhost
  `/object_info` metadata when no root is known. Unknown stays connected/unknown;
  `no_models` is emitted only for confirmed zero.
- Loaded install provenance is accepted only when complete and when canonical
  `installed_root` agrees with canonical `comfyui_root`; mismatch degrades to
  user-owned.
- Existing-state dry-run honors requested mode, path, device, ComfyUI port, and
  application ports and describes them without invoking any mutator.

### Fresh final verification

No real ComfyUI, PyTorch, model, or custom-node installation was executed. All tests
use injected services, simulated runners, and temporary directories.

```text
pytest -q scripts/tests
236 passed in 2.02s

python -m compileall -q scripts
uv run --python 3.12 --with ruff python -m ruff check scripts/launcher scripts/tests/test_cli.py scripts/tests/test_docker_launcher.py scripts/tests/test_models.py
git diff --check

All commands exited 0; Ruff reported "All checks passed!".
```
