# p2-03 correction1 Coding delivery

Coding [AID-210](/AID/issues/AID-210) delivers a new candidate for independent
[QA AID-211](/AID/issues/AID-211). [Producer AID-146](/AID/issues/AID-146) owns
findings and acceptance. Original task/kickoff1 CLEAR remain unchanged. Review1
was one rejected delivery with two P1 findings, R1/R2. This delivery claims no
independent PASS, feature merge/push, runtime deployment or Phase 2 acceptance.

## Exact identity

| Input | Identity |
|---|---|
| Fixed rejected-product/report base | `3ed5ae8fc5e86e6a74301e45e52013394a41983f` |
| Base tree | `a159b0d5ef8fe93ac9713de673155fb1505bad78` |
| Authorized supplement | `81895a416e3c2e06940fd15b37f4eaa08fa252b2` |
| Unchanged task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Product/tests/feature-helper/topic freeze | `bc5cab04fdf7bbc4641e0502e76a747c30e05cea` |
| Freeze tree | `9ca3c35c4fe43a6c11f3642c7d2472983091e362` |
| Persistent branch | `aid-210-p203-correction1` |
| Persistent isolated worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-210-download-correction` |

The official post-commit delivery index and final AID-210 comment bind the actual
NEW FINAL full SHA/tree to this manifest's exact body/hash, complete ordinary
fingerprints and official attachments. That actual final is the review target;
the software freeze is its ancestor. A commit cannot contain its own hash without
a circular dependency. Only reporting/evidence changes follow the freeze.

Only repair-round-1.md, manifest-round-1.md, review-round-1.md,
download-topic-round-1.md and the current download decision were imported from
the supplement. The whole Producer tree was not merged. Original implementation-
evidence/, review-evidence/, review.md and all immutable mirrors remain byte-exact.
All new attempts are in [correction-1-evidence](correction-1-evidence/).

## Result and boundaries

Retained adoption now verifies the preexisting final, commits admission on the
existing resource authority, retains that known ID and uses the same bounded
failure path as newly downloaded installs. An exception after the actual installed
commit publishes failed/current state with the actual `civitai_timeout` or
`civitai_file_changed` code/hint on the same ID. Original notes, known identity,
download time and genuine historical measurement survive. A changed final loses
current hash certification through the existing projection. Adopted/preexisting
and foreign replacement bytes are never compensation targets. The provider deadline
is not extended to write failure state.

An active `downloading` row owns pending/running work. Retained install refuses
with HTTP409 `civitai_resource_active`, the owner's resource ID and inspect/wait
hint before competing body/state/partial/file mutation. It checks early and again
on refreshed ORM state at admission. Acquisition reuses active rows without
publishing competing metadata. Both claim sections use one process-local reentrant
lock in the existing Backend; model bodies run after release. This is neither a
cross-process reservation nor a durable attempt/job architecture. Failed-row retries
and verified inactive reuse remain useful. No new table/schema/queue/dependency,
MCP intent, worker, UI, default, removal or resource authority is introduced.

A true pre-admission DB failure rolls back without a new row. After admission,
permanently unavailable persistence may prevent recording current failure; the
response still returns failure, the known ID and actual reason when available.
The explicit unavailable-DB control distinguishes that limit from writable-DB R1.

The [download topic](../../civitai-downloads.md) documents policy and the corrected
admission/failure contract. Existing effective defaults remain 8 GiB/file
`CIVITAI_DOWNLOAD_MAX_BYTES=8589934592` and observed 20 GiB destination floor
`CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES=21474836480`, both positive integer bytes.
Exact provider size, safetensors selection, associated resume, chunk/space/range
checks, atomic no-overwrite, size/hash verification, configured-file credentials,
absolute deadline, closure, public normalization and raw internal locators remain.
The original [caller inventory](implementation-evidence/caller-inventory.md) still
applies; the two writers and their current callers/readers are unchanged.

## D1–D5 and C1–C5 evidence

All items remain P1. These are Coding checks; D5/C5's independent verdict belongs
to AID-211. HTTPX substitutes external HTTP only. Settings, configured synthetic
key files, production ProviderOperation/transport, registered HTTP/MCP, ORM commits,
status projections and temporary files are real. Scheduling and disk observations
are deterministic fixtures, not production deployment or reservation evidence.

| Item | Check | Feature evidence, layer and real boundary |
|---|---|---|
| D1 | test | Existing registered admission matrices in `test_civitai_provider.py`, bounds/easy/install/writer tests: policy/settings/type/format/exact size/hash, no body/partial/row effects, package-wide admission, frozen Anima/other-kind and exact inactive reuse. Current affected476/full Backend7158/MCP666 cover both callers and registered adapters. |
| D2 | test | Existing bounds and real-row caller guards plus unchanged independent byte/space/range guards: actual accepted bytes, decreasing/unknown space, valid associated206/owned200, full-prefix hash and foreign/linked/changed-part preservation. All five original production faults cause intended RED again. |
| D3 | test | New `test_civitai_download_correction.py` and all repaired original independent cases: same-ID current outcomes after committed adoption, active pending/running/late-target/stale-boundary refusal, actual partial preservation, registered cross-caller reuse, simultaneous retained calls, original owner completion and genuine measurement. Original collision/compensation/no-overwrite/old-note tests remain. |
| D4 | test | New real installed-commit deadline/replacement traces, writable/permanently unavailable DB controls; unchanged independent configured-file rotation/origin/bad-file and sixteen provider-exit cases, retained p2-01 provider19 and current provider suites. No manual key or alternate download transport is injected to certify callers. |
| D5 | test + delivery | Current frozen full/affected suites, fresh exports/readers/standing consumers, complete fingerprints, all raw attempts, eight assertion-sensitive faults and exact finally restoration. Registry72/history preserved. Official archive/index/bundle/full-index patch and prerequisite-only pack allow exact independent restore; actual AID-211 verdict is pending. |
| C1 | test | `test_adoption_current_failure_keeps_actual_reason_id_and_history` covers new/existing rows × actual deadline/replacement after real commit. Response/status/code/hint/ID agree; notes and adopted/foreign bytes survive; historical measured evidence stays exact and projection invalidates changed bytes. Six DB controls distinguish admission/publication/unavailable persistence. Original two R1 cases now pass unchanged. Current-publication and current-reason faults each fail four intended assertions. |
| C2 | test | `test_active_acquire_refuses_retained_without_mutating_owner` covers pending/running × late-target; stale preflight rechecks actual committed ownership, retained-owner acquire/install overlap preserves all columns, real partial bytes/stat/metadata survive both competitors, simultaneous retained requests produce one owner. Retry/inactive controls stay useful. Original R2 passes unchanged; admission bypass fails the stale-boundary assertion. |
| C3 | test | All original affected456 plus twenty new correction cases pass; full suites and unchanged independent feature47 pass. No old feature test is edited/deleted/skipped. Original compatibility replacements remain explicit in `implementation-evidence/compatibility.md`; the only new public compatibility behavior is active retained refusal and truthful post-adoption failure. |
| C4 | test | `correction-1-evidence/fault_replay.py` serializes eight faults: current publication4, current reason4, active ownership1, byte1, space1, range5, no-overwrite1, size/hash2 assertion failures (19 total). No setup/collection/timeout substitute. Every finally restores exact original bytes; complete restored feature222 passes without known-defect deselection. |
| C5 | test + delivery | Frozen source qualification, 8,415 freeze-body hashes/modes, 828 ordinary software/test/helper inputs per final receipt, 19 fresh exports, same registry72 and 7,394 historical task bodies/modes. Actual final full SHA/tree and official exact-restore readback are bound by the post-commit index; separate exact QA remains required. |

## Current qualification

All rows below execute after the actual freeze with current-worktree imports,
read-only dependency sites, isolated scratch/test/SQLite paths, disabled plugin
autoload and `--timeout=60` per test/600-second outer bounds. Actual argv,
environment, source hashes, import/SQLite receipts, timings and raw-log hashes
are in [verification.json](correction-1-evidence/verification.json). Successful
qualification has zero guard denials; guard activation deliberately denies six
private/write/DNS probes. All original platform/optional skips remain explained.

| Check | Actual result |
|---|---|
| Full Backend | 7158 passed, 124 existing skips, 112 warnings; 193.89 s |
| Full MCP | 666 passed, four existing skips; 88.45 s |
| Affected production/compatibility + correction | 476 passed; 15.35 s |
| Eight production faults | 19 meaningful assertion failures, each expected exit1; exact finally restoration |
| Complete restored features, including all repaired independent cases | 222 passed; 2.98 s; no known-defect deselection |
| Fresh Backend producers / separate MCP readers | 93 / 73 passed; 19 retained exports |
| Standing MCP/PNG/stdio/content/smoke consumers | 412 passed; 87.46 s |
| Retained independent provider / fresh wait consumers | 19 / 12 passed |
| Registry/history | Same72 rows, read-only relative-input rebuild exact; 7394 prior task bodies/modes exact |
| Shared checkout preservation | All14 original dirty memory bodies/statuses preserved; checked again at delivery |

The [fault audit](correction-1-evidence/final-fault-audit.json) records each exact
substitution, source/mutated/restored hashes and feature selector. The unchanged
helper restores SHA-256 `a8413c44f08d7ac2f52744db87aca6ad02362fe9e947dd0db32c86db49f182ee`.
[Sixty parsed observations](correction-1-evidence/outcome-traces.json) bind the
restored source log and include adoption/current-ID/old-note/body/closure/range/
partial/compensation outcomes. Raw logs retain every assertion, not only summaries.

## Attempts, compatibility and limits

Rejected-base `rejected-r1-r2` reproduces exactly three intended assertion failures
(two adoption, one duplicate) before software changes. The expanded pre-fix
correction suite produces ten assertion failures/two passing retry controls.
Initial `correction-tdd-red` was terminated (-15) after an unbounded recursive
running-caller fixture; a single-entry guard fixes that probe. First implementation
`correction-green-initial` passes eight correction cases, then is terminated (-15)
when a deterministic nested acquisition exposes an overbroad retained preflight
lock. Narrowing the retained lock to refresh/claim resolves it. Neither interrupted
attempt is a meaningful fault result or qualification. `correction-green-boundary`
passes59, expanded controls pass20 and pre-freeze affected476 pass. Final results
above are fresh and apply to the frozen source, not those intermediates.

The initial copied runner indexed tracked inputs and omitted then-untracked new
tests/helpers. Early receipts remain unchanged and explicitly limited;
[early-source-inventory-limit.json](correction-1-evidence/early-source-inventory-limit.json)
retains reconstructed new-test bodies from the recorded deterministic write/edit
sequence, labelled as reconstruction rather than contemporaneous hashes. The final
runner includes untracked ordinary source too, and all feature inputs are tracked
at freeze before final qualification. Final complete inventories are authoritative.

One report aggregation guessed7394 after excluding the whole current task. That
selection actually has7365 paths; the original handoff's7394 includes29 current-task
kickoff paths. The corrected preservation check uses the actual published handoff
path set, with exact bodies/modes, and retains this packaging failure. No source or
test outcome changed. Authored files pass whitespace checks; raw pytest logs retain
their original diff whitespace. No generated cache is staged or delivered. Original
cache-removal/intermediate history is retained through the prerequisite/bundle.

No scope/specification deviation, new skip, registry supersession or legacy test
edit. The lock changes indentation of acquisition's existing admission block;
its policy/package/dedupe/commit logic is reused. Retained adoption and download
share the existing completion/failure logic. Rollback-only adoption, an early-only
active check and blanket install refusal were rejected because they cannot meet
same-ID/current-outcome and useful retry/reuse requirements.

Offline only: synthetic external HTTP/credentials, controlled scheduling/space,
real Settings/ORM/filesystem. Running service: not started/restarted/deployed or
backfilled. Real generation and live model download: none. Artifact retrieval:
synthetic installed bytes and official task attachments only, no live Gallery bytes.
Frontend/native Windows remain unrun; inherited open-writer unlink denial is an
offline emulation. Private key/config/runtime/jobs/databases/snapshots/backups,
canonical dependencies, other worktrees and model/dataset/output/Gallery data are
preserved. No artistic verdict, durable-job/aggregate-budget claim or Phase2 exit.

## Exact delivery and continuation

[Replay instructions](correction-1-evidence/replay.md) and the official index provide
actual final pin, manifest hash, archive member/body hashes, complete final ordinary
fingerprints, incremental bundle and full-index binary patch. Ten published/read-back
prerequisite-only pack parts reconstruct77,962,971 bytes with declared shallow
cutoff `b4e71d18ba4600ad7e053274b90b45ffdfbce87b`. Two empty stores are seeded only
from those official prerequisite bytes; candidate absence/no alternates are checked
before final artifact import. The post-commit official receipt records exact bundle
FINAL/tree restoration, independent patch-tree agreement and both fsck results.

AID-210 completes with this delivered candidate. AID-211 is the real independent
review card natively blocked on Coding; its reviewer pins the actual NEW FINAL
before substantive review and publishes its own verdict even if adverse. Producer
handles findings and acceptance. Feature integration waits for actual PASS.
