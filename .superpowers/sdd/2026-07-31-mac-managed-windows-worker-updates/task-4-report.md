# Task 4: Versioned Runtime, Activation and Rollback

## Status

DONE_WITH_CONCERNS

## RED

- Added `backend/tests/test_worker_updater_runtime.py` before production runtime code. The first focused run failed during collection with `ModuleNotFoundError` for `worker.windows.updater.runtime`.
- Layout/JunctionOps RED covered full-SHA validation, immutable release publication, mutable shared links, config exclusion, canonical containment, and reparse-source rejection.
- Builder RED produced four expected behavioral failures: no CUDA-first install, ignored nonzero install result, accepted an unpinned custom node, and rejected a recoverable interrupted stage. A later mutation test proved a movable ComfyUI `main` branch was also accepted before the version-tag fix.
- Worker staged-endpoint RED produced ten expected failures: the loopback override was ignored and nine unsafe URL forms did not fail startup.
- Validator RED failed on the missing `RuntimeValidator`; its behavior tests cover distinct reserved loopback ports, bounded argv starts, candidate ComfyUI URL injection, exact commit propagation, second-process start failure, and finally termination/kill fallback. A later typed-health RED failed on missing `HealthEvidence` and then exercised every required CUDA/GPU, ComfyUI, authenticated Worker, resource-plan, preflight, and exact-commit signal.
- Activator RED failed on the missing `Activator`; its tests cover candidate health failure, create and both rename interruption points, stale `current.next`/`current.previous-switch` recovery, rollback verification failure, and post-success retention. A later retention RED demonstrated that a full-SHA operator directory without the updater ownership marker was incorrectly deleted.
- Native Windows JunctionOps RED failed on the missing adapter before the tmp-directory create/read/rename/remove integration test was implemented.

## GREEN

- `RuntimeLayout` creates canonical `releases`, `shared`, `config`, and `staging` roots. Mutable models/input/output/cache/partial storage remains under `shared`; releases contain checked junctions and no copied `config/worker.json`.
- `RuntimeBuilder` copies only a checked exact export into a same-commit staging directory, recovers only that known interrupted staging path, creates a release-local venv, installs manifest-pinned uv, forces CUDA PyTorch from the manifest index before requirements, checks every bounded argv command, pins ComfyUI to a version tag and every custom node to a full SHA, writes an ownership marker, then publishes with `os.replace` without touching `current`.
- `WindowsJunctionOps` uses the Win32 mount-point reparse API directly, not a command shell. It verifies type and resolved target before rename/remove. All higher-level link targets are checked against canonical Worker/shared/release roots.
- `RuntimeValidator` reserves two distinct loopback ports, releases them only at process launch, starts staged ComfyUI and Worker with bounded argv interfaces, passes the staged ComfyUI override without tokens, validates typed complete health and the exact source commit, and always terminates both staged processes in `finally` with bounded kill fallback.
- `worker.py` keeps the exact default `http://127.0.0.1:8188`, accepts only explicit loopback HTTP overrides on ports 1..65535, and fails startup for userinfo, path, query, fragment, non-loopback, HTTPS, or invalid-port values. Status, preflight, and proxy calls share the validated endpoint.
- `Activator` holds an exclusive activation lock, recovers stale switch junctions, journals each phase atomically, performs the recoverable `current.next` -> `current.previous-switch` rename transaction, validates production at the exact target commit, restores and revalidates the previous release on any failure, and returns canonical `ready`, `rolled_back`, or `recovery_required` results/error codes.
- Retention runs only after target production health succeeds. It keeps current and previous, deletes only older full-SHA releases carrying matching source and updater ownership markers, and preserves unknown, unmarked, mismatched, staging, and shared data.

## Verification

- `py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py backend/tests/test_worker_updater_git.py backend/tests/test_worker_updater_runtime.py -q` — **130 passed**.
- `py -3.11 -m compileall -q worker\\windows\\updater worker\\windows\\worker.py` — passed.
- `git diff --check` — passed for tracked changes before staging; a staged diff check is run before commit so new files are included.
- No real ComfyUI, Worker service, production port, scheduler, repository, or Worker root was contacted. Commands and health are fakes; the sole native junction integration uses only a pytest temporary directory.

## Self-review

- Confirmed command inputs are sequences, never shell strings; every run/start receives a positive timeout and nonzero results fail closed without stderr/token exposure.
- Confirmed candidate and previous health both require complete typed evidence and exact commit equality.
- Confirmed rollback never deletes releases/shared data, and retention cannot identify a release as updater-owned from its directory name alone.
- Confirmed stale transaction recovery prefers the previous-switch junction and removes a candidate only after resolving it through JunctionOps.

## Commit

- `feat(worker): add transactional versioned runtime`

## Concerns

- `runtime.py` is intentionally large because the plan requires the public protocols plus Layout/JunctionOps/Builder/Validator/Activator in one focused file. It remains separated into cohesive classes; splitting it would expand the Task 4 file map and can be considered after Task 5 integration.
- Task 5 must provide the concrete `CommandRunner` and authenticated `HealthProbe` transport. The Task 4 contract requires `HealthEvidence`; a probe cannot report success without providing every required signal.
- The focused run emits one pre-existing Pydantic v2 deprecation warning from `backend/app/config.py:54`; Task 4 does not modify that configuration class.

---

## Fix Round 1

### RED

- Added real-module Worker integration coverage for staged status, resource-plan, and preflight requests. The first run exposed production state leakage and showed that the staged validator still used the candidate release as the mutable Worker root.
- Added strict environment-path tests for missing, relative, outside-root, wrong-namespace, wrong-filename, and reparse-point inputs. Five initial failures demonstrated that the Worker accepted unsafe release, config, state, and ComfyUI roots.
- Added activation recovery coverage with an invalid requested release and a valid stale previous-switch. The regression left `current` on the stale candidate because the requested release was validated before recovery acquired the canonical current state.
- Added a real loopback socket test around staged process starts. It demonstrated that both reservations were released before ComfyUI started, leaving the Worker port bindable during the first launch.
- Added cleanup failure tests for terminate, wait, kill, and second-wait failures, including a non-`OSError` adapter mutation. The initial implementation swallowed cleanup failures and stopped cleanup early instead of returning typed evidence.

### GREEN

- Worker startup now treats `AI_DRAWING_WORKER_ROOT` as the mutable deployed root, with explicit release, config, update-state, and ComfyUI roots. Every root is absolute, canonical, existing, correctly typed, contained in its allowed namespace, and free of symlink/reparse components. Backward-compatible defaults remain available for the non-versioned layout.
- Versioned releases must be below `releases/<commit>`, update state is limited to the Worker root or updater-owned state namespaces, config is the exact contained `worker.json`, and ComfyUI is the exact release-local directory. The staged validator passes those coherent roots and an isolated validation-state directory without exposing tokens in environment variables or logs.
- The real imported Worker module now reports the staged commit, staged model plan, staged ComfyUI preflight endpoint, and isolated state while production state remains untouched.
- Activation acquires the lock and recovers stale switch junctions before resolving or validating the requested target release.
- Each reserved loopback socket stays open until immediately before its corresponding process launch; all unreleased reservations are closed in `finally`.
- Cleanup attempts every staged process and every required terminate/wait/kill step. Cleanup-only failures raise `RuntimeValidationError` with `CLEANUP_FAILED`; combined failures preserve the primary code/message, attach the cleanup code and primary exception, and chain the cleanup exception without leaking raw adapter output.

### Verification

- Focused RED/GREEN runs exercised each review finding and the additional reparse/namespace and non-`OSError` cleanup mutations.
- Final full focused suite: `py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py backend/tests/test_worker_updater_git.py backend/tests/test_worker_updater_runtime.py -q` -- **146 passed**.
- `py -3.11 -m compileall -q worker\\windows\\updater worker\\windows\\worker.py` -- passed.
- `git diff --check` -- passed.
- The sole warning remains the pre-existing Pydantic v2 deprecation from `backend/app/config.py:54`; this fix round adds no warnings.

### Commit

- `fix(worker): harden staged runtime activation`

### Remaining Integration Notes

- Task 5's launcher must pass the resolved release directory rather than the mutable `current` junction because Worker startup intentionally rejects reparse components.
- The concrete Task 5 runner/probe remains responsible for carrying the bounded command and authenticated `HealthEvidence` contracts into production.

---

## Fix Round 2

### RED

- A native-junction regression test pointed both `staging` and `staging/validation-state` at an external directory. The old implementation followed the junction, removed the commit child, and destroyed its sentinel before later containment validation failed.
- Staged Worker integration proved partial uploads and resource-plan resume offsets were derived from the isolated update-state root. The validator also omitted an explicit partial-root environment contract, and the Worker accepted missing/outside or wrong-target partial roots.
- Six `BaseException` cases covered ComfyUI start, Worker start, and health-probe interruption with both `KeyboardInterrupt` and `SystemExit`. The old control flow bypassed reservation/process cleanup; a simultaneous cleanup failure also lost typed cleanup metadata.

### GREEN

- Validation state now performs lexical no-follow checks on every existing component of the canonical contained `staging` and `validation-state` parent chain before any commit-child removal or creation. Existing commit children receive the same no-reparse check before removal.
- Worker partial storage is independently selected by `AI_DRAWING_WORKER_PARTIAL_ROOT`. Non-versioned installs retain `ROOT/cache/.partial`; staged managed validation passes the release-local `cache/.partial` junction and verifies that it targets `ROOT/shared/partial`, independent of the isolated update-state root.
- The real Worker integration now demonstrates an incomplete content upload materializing under shared partial storage, a subsequent plan observing the exact resume offset, and no cache data being written below validation state.
- Staged process and socket cleanup runs from an unconditional `finally`. The primary path catches `BaseException`: `KeyboardInterrupt` and `SystemExit` are cleaned and re-raised as the same object when cleanup succeeds, while a simultaneous cleanup failure raises typed aggregation retaining the original primary and cleanup code/failures/cause.
- Cleanup adapters catch `BaseException` per operation so every reservation and every started process still receives its cleanup attempt.

### Verification

- Focused RED produced the expected external-child sentinel deletion, missing partial-root contract, state-coupled partial writes, leaked resources for all six interruption cases, and unaggregated `SystemExit` plus cleanup failure.
- Targeted GREEN: **18 passed**; the strengthened staging and validation-state parent-junction test passes for both parent positions.
- Final full focused suite: `py -3.11 -m pytest backend/tests/test_worker_runtime.py backend/tests/test_worker_updater_config.py backend/tests/test_worker_updater_state.py backend/tests/test_worker_updater_git.py backend/tests/test_worker_updater_runtime.py -q` -- **158 passed**.
- `py -3.11 -m compileall -q worker\\windows\\updater worker\\windows\\worker.py` -- passed.
- `git diff --check` -- passed.
- The sole warning remains the pre-existing Pydantic v2 deprecation from `backend/app/config.py:54`; this fix round adds no warnings.

### Commit

- `fix(worker): secure staged validation resources`
