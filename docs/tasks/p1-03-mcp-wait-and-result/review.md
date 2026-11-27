Verdict: PASS
Review round: 1

Reviewed FINAL candidate: **`10d45934191b5f86590aa6408feae170ee3bb9df`**.
Candidate tree: `157863e18d212a2c93d06a32b4322609ff00e60b`.
Base: `faad28dc339b8b5d14aceea91d1fcfaad0a79ddd`.
Task SHA-256: `0d25f752ed4f17b28a01109c10c163e57532ae4b7e11832b8361f63a67af6688`.
Decision SHA-256: `7e91e4392ccab45af01c16db6781a36345e711e0722b9c1260cdb3df6a76e065`.
Date: 2026-11-24 UTC. Independent QA: [AID-164](/AID/issues/AID-164).
Coding: [AID-163](/AID/issues/AID-163). Producer: [AID-144](/AID/issues/AID-144).

All five cleared items pass at this exact candidate. No candidate product,
test, specification, dependency or author-manifest fix was made by QA.
Producer owns acceptance, integration/publication and subsequent task release.
Any later product change requires another exact-commit review.

## Findings

No blocking defect or specification ambiguity demonstrated. The implementation
adds only the approved `wait_for_job` read intent. It preserves the common
envelope, existing 29 risks/capabilities, distinct job and media namespaces,
canonical provenance and the existing safe public training projection.

The actual calling-client enforced limit remains **unverified**. Inspection of
tracked launcher/client/settings/server sources and the preserved kickoff search
establishes no such limit. The **50-second overall maximum is the approved
fallback policy**, not a measured client limit. The implementation uses one
monotonic deadline and cancellable async HTTP reads; the unchanged 60-second
per-request default cannot extend it. Short real-time tests establish the
control behavior, rather than a live 50-second client/session measurement.

## Exact identity and preserved inputs

I read the actual official manifest and external integrity receipt before
substantive review, resolved the full final SHA above, and pinned it plus the
task digest on this recipient card in
[comment 17b875eb](/AID/issues/AID-164#comment-17b875eb-a234-4eff-9eaa-0f26a07db353).
The independent worktree is
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-164-qa`, branch
`aid-164-exact-review`, created at that SHA. Neither the Coding directory nor a
moving branch supplied the reviewed source.

- All five official downloads match attachment byte counts and SHA-256 values.
  The official manifest equals the candidate's committed manifest.
- All **203 indexed payloads / 205 ZIP members** reconcile; indexed file hashes,
  sizes, Git blob IDs and candidate bytes match independently.
- The official patch equals `git diff --binary --full-index <base> <candidate>`.
  Applied with an index in a scratch repository at the exact base, it produces
  the exact candidate tree. The bundle verifies against its prerequisite and
  fetches the full named candidate in that scratch repository.
- All 40 audited inherited p1-03 task/kickoff/evidence and decision/registry
  paths audited against the base remain unchanged. The task and full decision
  have the approved hashes above. Accepted p1-01/02 feature `ef8302c`, actual QA
  `1ad2836` and kickoff report `c5d85f6` are ancestors. I read the actual accepted
  manifests, reports, acceptance, cleared kickoff and normative decision.
- The independent literal policy retains every previous label and adds only
  `wait_for_job: read`. Existing ComfyUI admin stays admin. Exactly 30 names are
  discovered, with one label each; ping remains and health/workers stay absent.

See candidate integrity,
source/policy audit and the
official upload metadata.
Shared main, the active AID-151 runtime/private configuration, real data and
canonical component environments were untouched.

## Done when assessment

| Item | Level | Result | Independent evidence and boundary |
|---|---|---|---|
| D1 — complete generation and truthful media locators | P1 | PASS | Real registered MCP through wrappers/client under mocked HTTP: ordered mixed image/video, 106 results without a cap, distinct canonical/image IDs, revision/source-node metadata, nested/Unicode/encoded paths, relative Backend URL and proven absolute containment. Legacy image-only success keeps artifacts empty. Missing/unsafe/outside/container paths, traversal, symlink escape, remote/credential URLs, mismatched identities and mixed unavailable results retain completed state and the whole known identity set. Available locators survive; no fabricated ID, basename mapping or file operation. Fresh real-route/SQLite responses are also consumed independently. |
| D2 — failed/cancelled jobs and recovery | P1 | PASS | Both domains preserve failed/cancelled state, target ID/domain, generation reason/code/node/recording/revision context and safe public training failure/output/registration fields. Successful training status-read flags do not imply training success. HTTP/connection/enrichment errors retain safe recovery and last-known state. Only actual initial 404 permits lookup in the other UUID domain; later 404 does not reinterpret an identified domain. |
| D3 — overall timeout, clamp and repeatability | P1 | PASS | First read, incremental body, fallback lookup, enrichment and sleep all consume one budget. Body close/abortion is observed. High requests clamp; status is unknown before a completed read and last-known thereafter, including completed during enrichment. Same-ID queued/running recovery executes in both domains. Non-yielding status work and response preparation are checked before success. Additional partial enrichment timeout keeps all three identities and its first available locator. Every recorded wait request is GET; no job cancellation/submission occurs. Manual source/configuration and fallback review agrees with docs. |
| D4 — training output and independent smoke | P1 | PASS | Completed/failed/cancelled/queued/running training, no-media output and absent/real/legacy/queued/running/failed/cancelled/unavailable smoke pass. Safetensors is not Gallery media; artifacts/images stay empty. Real smoke job/image/nullable canonical IDs, locators and safe diagnostics survive. Fresh Backend route fixtures replay through wait; nine independent comparisons against the existing registered training-status tool confirm its complete public projection is preserved. Training completion does not await or request the smoke job. |
| D5 — documentation/current flow | P2 | PASS | Read docs/mcp.md's table, bounded-wait section, examples, current/staged flows and errors against source, discovery and structured/text results. Default/max/fallback, timeout unknown/last-known semantics, locator error/completed state, host/URL mapping, legacy namespace and training/smoke independence agree. Team flow updates agree. No deployed-source, byte-retrieval, health/worker or phase-exit claim is added. |

The public output/error choices (`images`, `job_cancelled`, timeout as an error
envelope) are documented consistently and meet the cleared contract. Gallery
locator construction is metadata proof only; no file existence or consumption
claim follows from it.

## Commands and independent results

Full argv, cwd, selected non-secret environment, UTC start, process duration,
exit and complete raw output are retained for each command in
QA evidence. Pytest uses isolated scratch
roots and `--timeout=60`. Canonical interpreters are used unchanged; only
`pytest-timeout==2.4.0` was installed into run-owned scratch. Explicit
PYTHONPATH/pytest binding and import-origin assertions resolve this QA worktree,
including the separate-interpreter cross-layer helper.

| Check | Result | Evidence |
|---|---|---|
| Full Backend: `-m pytest -c pytest.ini backend/tests -q --timeout=60 -ra` | Exit 0; **1900 passed, 124 Windows-only skips, 76 warnings in 44.39s** | qa-backend.log/json |
| Initial targeted wait: `-m pytest -c pytest.ini mcp-server/tests/test_wait_for_job.py -q --timeout=60 -s` | Exit 0; **77 passed in 1.29s** | qa-wait-baseline.log/json |
| Fresh shape producer: committed `delivery-1-evidence/backend-shape-export.py.txt` | Exit 0; 0.626s process; actual HTTP routes/SQLite in memory, mocked queue, synthetic fixture PNGs, no lifespan/product service | qa-fresh-shapes.log/json |
| Additional independent registered cases: scratch `test_qa_wait.py` | Exit 0; **28 passed in 0.39s** | qa-additional-registered-corrected.log/json; reproducer .py.txt |
| Final restored full MCP: `-m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra` | Exit 0; **540 passed, 2 unchanged optional skips in 2.80s** | qa-mcp-restored.log/json |
| Import binding and policy/source preservation | Exit 0; exact candidate bytes restored; all prior 29 literal labels retained plus wait=read | qa-imports.log/json; source-policy-audit.json |

Fresh Backend revision, multi-LoRA and lifecycle/admission exports from this run
feed the meaningful registered MCP consumers. No older exported fixture or
Backend result substitutes for that proof. The complete Backend suite also
executes the five cross-layer LoRA contract-parity cases and the two broad
historical registry guards. Full MCP executes the remaining seven standing
items, shared client/error/stdio/capability tests and the new wait cases.

The five 70 ms deadline stages measured **71.5–73.7 ms**, including SDK/setup
overhead, with one or two reads per call. The independent 45 ms partial
enrichment check measured **47.4 ms**, three GETs, no fourth lookup and no
mutation. Reads configured to take 300–400 ms were aborted. These are short
mocked-transport elapsed-time observations, not a measured calling-client limit
or production timing guarantee. Repeated same-ID tests use only reads.

The two MCP skips require optional `SMOKE_HTTP_FIXTURE_OUT` and
`SMOKE_IMAGE_HTTP_FIXTURE_OUT` exports. They are unchanged; new smoke-shape tests
and fresh wait readers execute. All 124 Backend skips require Windows. Existing
warnings are retained. Frontend/build and native-Windows execution were not
run: no Frontend, worker, launcher, bot, dependency or related input changes;
this review ran on macOS. Backend was run once, not repeated after restored
MCP-only faults or QA report/helper edits.

## Fault, restore and GREEN

For each automated acceptance item I independently changed production in the
pinned QA worktree, ran the related real registered tests, and restored exact
original bytes in `finally`. No test oracle or tool callable was substituted.
Exact deltas, argv, failures and restoration hashes are retained in
fault-restoration.json and paired
fault patch/log/receipt files.

| Deliberate fault | Observed RED |
|---|---|
| D1: corrupt canonical artifact identity | 1 failed; required media lookup/result cannot succeed |
| D1: hide unavailable-locator disposition | 20 failed; unsafe/missing metadata incorrectly becomes success |
| D2: report failed/cancelled jobs as success | 4 failed |
| D3: remove overall cancellation deadline | 4 failed, 1 passed; slow read/body/fallback/enrichment exceeds elapsed bound; sleep-only case remains guarded separately |
| D4: discard the independent smoke job reference | 7 failed, 1 passed; absent-smoke case remains valid |
| Existing admin risk falsely read | 2 failed, independent catalog and discovery guards |
| New wait risk falsely admin | 2 failed, independent catalog and discovery guards |

All faults exit 1 as expected. Original/restored hashes agree. Final full MCP
GREEN occurs after all mutations are restored. All nine earlier standing guards
remain active; the QA registry is regenerated with the four new automated
acceptance items and no supersession. D5 is a manual task item with supporting
catalog tests, not an extra automated certification.

## QA setup corrections and notes

Two QA-helper issues were diagnosed without changing the candidate. The first
full MCP attempt had one missing fresh lifecycle export (539 passed, one failed,
two optional skips): a preceding integrity helper had exited before copying it.
Copying the actual fresh Backend-produced export made the full suite pass; that
failed run is preserved. Integrity helper corrections used full-index patch
comparison, NUL-delimited Unicode Git names and `--update-shallow` only in its
scratch prerequisite repository. The completed audit verifies exact bytes/tree.

The first additional QA probe compared raw Backend smoke diagnostic display
strings literally and failed three cases. Inspection showed that the unchanged,
accepted MCP public projection deliberately uses closed safe diagnostic copy.
The corrected QA oracle preserves exact identities/status/output/code, and
compares every public training field against the actual existing registered
training-status tool on the same fresh HTTP response. All nine comparisons pass.
Initial helper source/logs and corrected source/logs are retained separately.
This is not a candidate defect, weakened product test or specification change.

## Limits and history

- **Offline software:** independent suites, real SDK registration/wrappers and
  client with mocked HTTP, test-only stdio checks, fresh HTTP-route/SQLite
  fixtures, controlled faults, hashes and document inspection.
- **Running product service:** no probe, restart, replacement, deployment or
  loaded-runtime identity claim.
- **Real generation/training/download/worker dispatch:** none.
- **Generated-artifact retrieval:** no live Gallery-byte read or remote URL
  consumption. Synthetic smoke-reader PNG validation and downloaded review
  packets are separate evidence.

The 23-intervention/eight-incident baseline and historical cached-original /
revision pair with canonical lineage and colocated decoded host paths keep
their original limits. Live timeout/cancel/dedup recovery, remote consumption,
aesthetics, three zero-intervention runs and phase close remain unaccepted.
No main merge/push or p1-04 release is performed by this review.

Accounting remains p1-03 kickoff ambiguity / clarification 1 / kickoff review 2
CLEAR, followed by **implementation delivery review 1 PASS, zero implementation
rejections**. Separate p1-02 and p1-00a rejection/correction histories, original
round-1 task/report/evidence and existing registry entries are preserved.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | mcp-server/tests/test_wait_for_job.py::test_mixed_media_all_identities_order_lineage_and_nested_unicode; mcp-server/tests/test_wait_for_job.py::test_unsafe_or_unavailable_locator_keeps_completed_and_entire_identity_set; mcp-server/tests/test_wait_for_job.py::test_legacy_image_only_has_separate_namespace_and_no_artifact; mcp-server/tests/test_wait_for_job.py::test_no_arbitrary_result_cap | active |
| D2 | P1 | mcp-server/tests/test_wait_for_job.py::test_terminal_failure_cancellation_and_safe_training_projection; mcp-server/tests/test_wait_for_job.py::test_read_failure_is_not_not_found_or_domain_fallback | active |
| D3 | P1 | mcp-server/tests/test_wait_for_job.py::test_overall_deadline_aborts_reads_and_reports_last_known_truth; mcp-server/tests/test_wait_for_job.py::test_pending_timeout_then_same_id_recovery_without_mutations; mcp-server/tests/test_wait_for_job.py::test_high_timeout_is_clamped_to_overall_policy; mcp-server/tests/test_wait_for_job.py::test_deadline_includes_response_preparation | active |
| D4 | P1 | mcp-server/tests/test_wait_for_job.py::test_training_output_and_independent_smoke_never_wait_or_submit; mcp-server/tests/test_wait_for_job.py::test_fresh_real_backend_route_exports_through_registered_wait | active |
