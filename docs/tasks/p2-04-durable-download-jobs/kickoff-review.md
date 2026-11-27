# p2-04 revised specification — fresh independent kickoff

Verdict: CLEAR
Reviewed: 2026-11-27 · [QA AID-223](/AID/issues/AID-223)
Producer: [AID-217](/AID/issues/AID-217)
Pinned source: **`6b82a91ea0974b8f069a7429530086c2997125ae`**
Report branch: `qa/aid223-p204-revised-kickoff`

This reviews the complete revised [task](task.md), after accepted p2-02a.
It supersedes the original AID-214 kickoff CLEAR for dispatch. The original verdict
remains in Git/native history. Existing WIP and cancelled AID-215/AID-216 carry no
p2-04 delivery acceptance; this kickoff supplies none.

## Independent reading and source boundary

My reading: CTY wants useful Phase 2 progress from revised main, with routine
in-boundary choices delegated and the three-rejection stop gate preserved. The
roadmap requires large Civitai downloads to be persisted Backend jobs agents can
follow through existing acquire/status/wait intents. Preserve file safety, resource
identity, held secrets and old data; establish truthful restart failure before
subsequent disk-budget and agent-facing work.

Difference: none material. I recorded this reading in run scratch before opening
the repository task; the assignment already contained its full text.
No owner question or reserved project-boundary decision is needed.

CTY's direct quote is in [fresh continuation](../../requests/2026-11-27-fresh-producer-continuation.md).
The source distinguishes that quote from inherited versioned authority and Hermes's
operator procedure. I applied [verification scope](../../decisions/verification-scope.md)
first, then AGENTS, memory/INDEX, README, CURRENT, ROADMAP, team/QA instructions and
bound review/handoff skills. I read the current source-handoff section before its
historical discovery, the owner WIP checkpoint, download decision/topic, p2-03
acceptance, additive-schema memory, resource topic and p2-02a acceptance/manifest/PASS.
There is no current p2-04 delivery manifest; this is explicitly a kickoff.

## Five product checks

| Item | Assessment and decisive delivery boundary |
|---|---|
| D1 / P1 | CLEAR. Registered `/api/civitai/resources/acquire` and catalog-driven `civitai_resource_acquire` reach `start_acquisition`. Commit job/resource linkage before launch; return explicit `resource_ids` beside legacy fields. Validate keys, bind replay to selection, reject conflicting keys, and use simultaneous registered calls plus a model-body counter to prove one download. |
| D2 / P1 | CLEAR. Acquisition `_run_one` and registered `/api/civitai-recipes/resource-install` reach the real safe-download helper. Persist bytes/time and per-file outcomes; preserve successful components when another fails. Both callers must share operation ownership, with existing bounded contention and same-ID diagnostics. |
| D3 / P1 | CLEAR. Models, `init_db` and Backend lifespan provide additive persistence/startup hooks. One actual isolated subprocess kill/restart test can prove interrupted-once failure, no replay, files retained and completed history unchanged. One supported Backend process and a boot identifier suffice. |
| D4 / P1 | CLEAR. Existing catalog registration routes `dl_` IDs to `/api/civitai/download-jobs/{job_id}`. Exercise the real Backend read through registered MCP for completed/failed/interrupted/timeout results, verified size/hash and no image locators. Preserve the single 50-second total budget and generation/training semantics. |
| D5 / P2 | CLEAR. `backend/tests/fixtures/resources/previous-schema.sql` and `test_resource_record_migration.py` provide the old-schema fixture/audit. Check startup additions separately from exact old values/notes, repeat startup and show old rows have no fabricated job ID. |

These checks are bounded and implementable; none is certified implemented here.
The WIP response currently lacks top-level `resource_ids`, and its process harness
uses service reconciliation with queued/published boundaries. Those are starting
inputs to complete against D1/D3, not evidence that the revised requirements pass.
Likewise mocked status payloads alone cannot establish D4's Backend-route boundary.

## Compatibility and implementation guidance

- D2's terminal assertions concern admitted operations. Preserve p2-03's existing
  pre-admission policy/type/space refusals and no-new-resource-row behavior; test
  post-admission size/space/hash failures without weakening those refusal guards.
- Partial-package coverage uses the existing acquisition package path; synchronous
  install keeps its single-descriptor API and exercises the same component outcomes.
- The synchronous caller may refuse an active resource and identify its existing
  job; participation in shared ownership does not authorize a competing download.
  Retained `civitai_easy.generate_like` also calls `start_acquisition` and still
  consumes legacy response fields. Preserve that caller while completing D1.
- `download_jobs.status` and resource status linkage already use persisted rows.
  Keep download status/progress DB-only; canonical resource detail's existing stat
  contract is separate. Persist measurements in execution callbacks, never reads.
- Reuse accepted p2-02a `safe_evidence`/typed projection. Actual held raw/encoded key,
  received signed URL/query and auth transport are the secret boundary; public
  credential-looking creator prose is at most P3. No recognizer or new framework.
- Old-row preservation is the startup/schema contract. Explicit current execution
  still publishes current state on its existing resource ID while retaining notes.
  An operation table is execution history, not another model registry.
- The current WIP's sidecar/fencing mechanics and historical handoff's live-owner,
  inventory, lease and restoration demands do not add requirements to this respec.
  Keep the supported single-process boundary; no multiprocess/lease-service claim.
- Preserve 8 GiB/file, 20 GiB observed free floor, safetensors/hash/no-overwrite,
  associated-part and bounded absolute-deadline protections. Aggregate disk budget
  is the subsequent task; no cancel API, automatic replay/resume or live downloads.

Both known immediate-expiry install quarantines are real retained inputs:

1. `backend/tests/test_civitai_admission_deadline.py::test_registered_contender_times_out_before_original_owner_releases[-0.01-install]`
2. `docs/tasks/p2-03-bounded-download/review-3-evidence/deadline_checks.py::test_real_callers_return_before_held_owner_releases[-0.01-install]`

The accepted p2-02a first FAIL/correction handoff attributes the missing
`resource_id` before lookup to starting WIP; its correction PASS preserves all other
parameters and active p2-03 guards. Source inspection confirms install calls
`owner_for(..., operation)` before `_install_row`, so immediate expiry can precede
known-ID capture. Fix that diagnostic and remove both skips without changing other
guards/assertions or extending the deadline. This is compatibility, not a sixth
Done-when item. No material p2-03 admission-contract mismatch was found.

## Verification and limits

Offline inspection: exact-source caller/model/startup/status/wait review and a
Python AST/input check: **31 catalog intents**, `wait_for_job` read risk, old-schema
fixture and both task-linked quarantine guards present. Exit 0. Before report
editing, `git diff --exit-code <pinned-source> --` passed in the fresh worktree.
Report checks: `git diff --check`; report <=150 lines; only this report changed;
task directory below 2 MB and no new evidence files. Results recorded on publication.

Product tests/full suites/fault injection: **not run for kickoff**, as assigned.
Prior p2-02a counts remain attributed to its exact sources; they do not qualify this
WIP. Delivery must run final-candidate full suites once; corrections run affected
tests plus active REGISTRY guards in one invocation under the settled scope.
Running service: not probed, started, restarted, deployed or migrated.
Real generation: not run. Artifact retrieval: no live model/Gallery retrieval.
No owner key, production data, model, output, other worktree or role setting changed.
Memory reviewed; no new durable fact requires an entry and no receipt/log is added.

Producer may integrate this actual CLEAR report and dispatch new recipient-owned
Coding and exact-commit delivery QA. Publish/read back the report's full SHA on
AID-223; child completion is the native continuation path. Rejection history is
unchanged: no p2-04 delivery rejection/acceptance found; p2-02a retains 1 and historical
p2-02/p2-03 retain 9/2. Another same-class finding after rejection 2 is AMBIGUITY;
at rejection 3 Producer pauses for CTY before another correction. ROADMAP Thresholds,
CTY's artistic gates and the three-real-zero-fix Phase 2 exit remain unchanged.
