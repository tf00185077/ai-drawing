# p2-04 independent specification kickoff

Verdict: CLEAR
Review round: 1

[QA AID-214](/AID/issues/AID-214) finds the fixed task aligned with CTY's current
Phase 2 request and implementable within the existing Backend/SQLite/MCP stack.
No demonstrated P0/P1 contradiction or undefined requirement blocks Coding.
This is specification clearance, not delivery PASS, deployed behavior or Phase 2 exit.
[Producer AID-146](/AID/issues/AID-146) owns dispatch, findings and acceptance.

## Exact reviewed identity

| Input | Identity |
|---|---|
| Published source | `11b4326d78a47939b3844d27ef07266f112eef7c` |
| Source tree | `cec7472536c5b64b5ff9affb0fe7370781cfb3a9` |
| Task SHA-256 / bytes | `49a73639bc1eef1655ef8e07f5b1add5e9199abdeedfddea30498c2b4e35b565` / 11573 |
| Native pre-review pin | `5b616b63-6090-459f-8ab6-ee6d2135440a` |
| Persistent QA worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-214-kickoff` |
| QA branch | `qa/aid214-p204-kickoff` |
| Manifest at source | Absent; no Coding delivery exists for this task |

The pin receipt precedes substantive review.
The native plan, owner words, source handoff, adopted decision, p2-01/p2-02
acceptances and actual p2-03 review3 PASS were read with their limits. Accepted
p2-03 is Coding `0508ac4391ae3587cf4dd0db2ed8de91ca918510`, independent report
`1e69e9c67c121d45528a8de22743f23309ad8d6f`. Its earlier rejections remain evidence.
The 14 dirty shared-main memory files are excluded; this worktree uses committed
memory at the fixed source. No existing tracked source, test, registry or historical
evidence file is changed by this review.

## Owner alignment

My reading: CTY directs continued executable Phase 2 work inside the accepted
boundary without routine start/design approvals. The roadmap explicitly requires
large downloads to be Backend jobs followed through status/wait, one Backend
resource authority, verified safe files, private credentials and preserved data.
The independent reading was recorded before
opening task.md in this worktree; the native assignment already supplied the task
verbatim, so this was not a blinded review.

Difference: none material. Operation identity and ownership precede aggregate
accounting under the recorded in-phase sequence. The remaining total-budget,
search/hash/new-intent/default/removal work remains required later. Generation
queue durability remains Phase 3. The First check's temporary 10 GiB guard is
historical; current 8 GiB/file and observed 20 GiB floor remain mandatory. Neither
this sequencing nor CLEAR supplies artistic acceptance or the three real-run exit.
No owner question or project-boundary change is demonstrated.

## Source audit and falsification

The observation records current import
paths/hashes, all 15 registered ORM tables, effective policy, the 31-tool catalog,
87 active registry rows and function line ranges. SQLite's implicit sequence table
is outside that count. Source review covered these actual boundaries:

| Boundary | Current source and implication for the task |
|---|---|
| Registered acquisition | `backend/app/api/civitai_easy.py:41,92` and `mcp-server/mcp_server/tools/civitai.py:95` currently pass only a locator/source. Optional validated idempotency and a durable job ID can be added while existing integer acquisition/resource fields retain their values. |
| Selection and package admission | `civitai_resource_acquire.py:340` resolves selected files and validates the full package, then uses deadline-aware process-local admission. Resource rows commit at 492; thread launch is at 530. Durable database admission must replace the ownership assumption before that launch boundary, including independent sessions and commit/launch failure. |
| Other real acquisition caller | `backend/app/services/civitai_easy.py:394` calls start_acquisition from retained generate-like. It observes legacy `already_installed`/acquiring responses. It must receive the same durable ownership protection; freezing/removing its features is not a shortcut. |
| Retained synchronous execution | `civitai_resource_install.py:367,380,406` refreshes active ownership and commits admission; `:315` publishes verified identity. Registered `/api/civitai-recipes/resource-install` creates its existing ProviderOperation at `civitai_recipes.py:335`. This caller must share durable claims, keep synchronous timing/results and preserve the repaired post-commit failure reason/known ID. |
| Execution and callbacks | Acquisition `_run_one` at `:564`, retained partial/failure callbacks at `:470,481`, and shared `publish_download_state` at `resource_records.py:451` currently mutate resource state without an attempt fence. New callbacks need current-job/owner checks at the database write boundary, including exception/failure callbacks and terminal immutability. |
| File boundary | `civitai_safe_download.py:159,204` already enforces associated prefix proof, measured writes, space, range, hash and atomic link-if-absent publication. Execution callbacks can persist measured progress; status must not re-run this helper. Package completion must reflect every selected component; genuine successful components survive another component's failure. |
| Lifecycle/schema | `db/database.py:65` uses create_all plus explicit additive nullable columns; `db/models.py:354` is the resource authority. `main.py:42` owns startup/drain and currently has no download producer in that lifecycle. The task explicitly requires real proof of dead previous execution, safe refusal of live/uncertain ownership and no replay. A PID or startup event alone cannot meet that proof. |
| Status and public projection | `civitai_resource_acquire.py:297,629` currently stats partial files; canonical `resource_records.project_resource:396` also stats model paths. New DB-only job/resource status cannot simply delegate to those filesystem-observing projections. Persisted measurements plus update times must be distinguishable from current file availability. Existing canonical resource reads retain their prior contract. Complete-value normalization must cover whole outgoing jobs/errors; raw selected identities/destinations must remain usable internally. |
| Shared wait | `mcp_server/tools/wait_for_job.py:57` currently probes generation then training on actual 404 and enriches only generation with Gallery locators. Namespaced downloads can route directly to the authoritative new read. Known download failures must not enter fallback or Gallery enrichment. Existing generation/training behavior and the total deadline through preparation remain required. |
| Catalog and generation separation | `tool_catalog.py:37–41` registers the existing acquire/status/wait boundaries. Its endpoint inventory must gain the download read without changing names/risks/envelopes. `core/queue.py:236` is generation's in-memory queue with separate batch metadata; none of it needs to become a download scheduler. |

These are implementation obligations already present in the task, not new design
approval gates. A small additive operation/component/claim representation can
retain the sole resource registry. SQLite transactions/constraints can make a
claim atomic; the existing RLock cannot supply cross-process durability. Exact
schema/index names, ID prefix, conflict-code spelling, progress persistence cadence
and the supported single-process fencing primitive are delegated choices. Coding
must document and demonstrate them, including deadlines during any database wait.

Same-key replay is bound to the canonical selected operation and destination;
terminal replay must keep its original identity/history. A new explicit terminal
retry is a new operation using the same resource authority, never an overwrite of
the old attempt. Active replay/conflict must not mutate the owner. Verified ready
adoption records present verification without asserting a past network event.
Startup reconciliation preserves partial proofs and all terminal history; an old
unowned downloading row stays explicitly legacy. The schema/init preservation
clause applies to migration/startup, while authorized current execution may still
publish its current resource outcome. This avoids a false conflict with D2.

## Done when assessment

All items retain P1. CLEAR means the specified checks are falsifiable and in scope;
none is marked implemented or certified by these baseline observations.

| Item | Assessment and decisive later evidence |
|---|---|
| D1 | CLEAR. Independent-connection/simultaneous admission and body/row counters distinguish true atomic ownership from an RLock-only implementation. Same-key terminal/restart replay, selected/destination conflict, key validation and distinct terminal retry preserve identity/history. Full-package refusal and commit failure must precede body launch. |
| D2 | CLEAR. Both registered execution paths must retain original D/C/E checks and positive reuse controls. Real stale-owner/progress/terminal-publication faults distinguish fenced writes from status-only labeling. Success, partial package failure and writable/unavailable DB controls must retain truthful bytes, files, notes and known IDs. |
| D3 | CLEAR. Isolated actual process death/restart at admission-before-launch and publication-before-finalization is required, plus live-owner refusal, interrupted-once behavior, no replay and two-pass complete schema/old-value audit. Monkeypatching a status field alone cannot meet it. |
| D4 | CLEAR. Fresh Backend exports must precede independent registered MCP/stdio reads of actual download IDs. No-submit/body/hash/stat counters and domain/identity/budget faults test DB-only status, complete-value secrecy, terminal resource results without fake media, same-job timeout and preservation of generation/training/31-tool contracts. |
| D5 | CLEAR. Exact final source/freeze/import/root fingerprints, production fault REDs, exact restoration, complete current GREEN, full Backend/MCP/affected/fresh/standing qualification, all 87 prior items and official exact-restorable handoff are explicit. This kickoff does not replace any delivery gate. |

## Commands and actual results

Runner uses Python 3.11.15 with `-I -S -B`, the
fixed source's `tools/offline_pytest.py`, read-only dependency sites, allowlisted
environment and run-owned scratch/test roots. Both pytest commands use
`-p pytest_timeout --timeout=60 -q`, disabled plugin autoload and a 180-second
outer limit. Exact argv, environments, all ordinary source hashes, raw logs,
exit codes and guard receipts are retained.

| Command selectors | Result |
|---|---|
| `backend/tests/test_civitai_download_bounds.py backend/tests/test_civitai_download_correction.py backend/tests/test_civitai_admission_deadline.py` | 94 passed, one existing deprecation warning, 1.75 s, exit 0 |
| `mcp-server/tests/test_wait_for_job.py mcp-server/tests/test_tool_catalog.py mcp-server/tests/test_civitai_tools.py -k 'not fresh_real_backend_route_exports'` | 85 passed, 12 explicitly deselected fresh-export consumers, 1.32 s, exit 0 |
| Same selectors under guard-diagnostic observer | 94 / 85 passed again; no test assertion changed |
| Guarded `source_observation.py` | Exit 0; current imports, 31 catalog entries, 87 registry entries, policy 8589934592/21474836480 bytes; no DB connection |
| Source/tree/task and preservation audit | Exact fixed identities; all base tracked bodies/modes and registry remain unchanged |

The 12 omitted consumers need newly produced Backend exports and belong to delivery
qualification. No fresh exporter/stdio/full suite/complete 87-guard run is claimed.
Existing tests' synthetic HTTP/time/space use is not a running service or provider
result. These small checks confirm the baseline interfaces under discussion; they
do not prove a future durable implementation or substitute for fault sensitivity.

## Attempts, limitations and disposition

All command outputs and receipts remain in kickoff-evidence. Two guessed read
paths (`review-3-evidence/bootstrap.py`, `mcp-server/tests/conftest.py`) were absent;
source discovery used the actual offline runner and Backend conftest instead.
No tests failed or hung, no feature assertion was changed and no new skip was added.
The first local commit omitted five ignored .log files; explicit force-staging
corrected it before publication. The first archive extraction then failed because
default python3 was Apple 3.9.6, whose tarfile API lacks filter. The actual 3.11.15
interpreter supports it; the repeat uses that interpreter without changing product
or test code. The full captured error and incomplete archive fingerprint are in
package attempt 1.

The strict runner records three denied filesystem requests during the Backend
run and one during MCP/source observation. A read-only observer identified the
system version plist as one dependency/platform request; its comparison also
listed resolved dependency paths, so its request list is not an exact denied-event
list. Two Backend denials remain unlocalized. The initial tracing attempt recorded
no paths; the later observer did not relax the guard. Both attempts/raw outputs
are retained. These bounded baseline results are reported with that limitation;
there is no claim of zero guard denials or full delivery qualification.

Offline: source/specification review and the listed isolated checks only.
Running service: none started, restarted, migrated or deployed. Real generation,
live Civitai/model download and live Gallery/model-byte retrieval: none. Artifact
retrieval: official review handoff only when recorded in its external publication
index. Frontend/native Windows and p2-04 process-death/runtime behavior are unrun.
No private key, production database/settings, model/dataset/output/Gallery record,
other worktree or environment is altered.

Only new kickoff report/evidence files are delivered. The external post-commit
index binds their actual report FINAL/tree and SHA-256 values without a circular
self-hash. Its source snapshot has an explicit shallow cutoff at the fixed source,
contains both exact commits/trees and all their file objects, and needs no external
Git store. Exact restore steps and verified results accompany that index. It is
an inspection artifact, not a product merge/push or deployment.

This card completes with actual CLEAR. Producer can dispatch separate Coding and
exact-final-commit delivery QA under the existing workflow. No routine owner gate,
parent status write or implementation self-certification is requested.
