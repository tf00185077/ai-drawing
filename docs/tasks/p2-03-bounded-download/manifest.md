# p2-03 correction2 Coding delivery

[Coding AID-212](/AID/issues/AID-212) delivers the admission-deadline repair for
independent QA3. [Producer AID-146](/AID/issues/AID-146) owns findings and acceptance.
Original task/kickoff1 CLEAR/correction1 are unchanged. History remains two rejected
deliveries and three distinct P1 findings; this is a new candidate, not independent
PASS, accepted main, a feature push/merge, deployment or Phase2 exit.

## Exact identity and preservation

| Input | Identity |
|---|---|
| Fixed report-only QA base | `7b37b8c87e222eaadcb42d22286951c19e9e6ecc` |
| Base tree | `5042d00d491b7348071aa6dfb1ebcb02f0dcde3d` |
| Authorized five-path supplement | `2624d13da93fbcbeb4d0a37bf4f80be0e3fa2d11` |
| Unchanged task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Product/tests/helpers/topic freeze | `3209a712330b8beb948199dfeca75ae9f8f71b7d` |
| Freeze tree | `9eddd0fb7149234eb7f2d8ef22def3290b3d655b` |
| Persistent branch | `aid-212-p203-correction2` |
| Persistent isolated worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-212-download-correction` |

The official post-commit index and final card comment bind this manifest's exact
body/hash to the actual NEW FINAL full SHA/tree. A commit cannot contain its own
hash; the actual final in that index is the review target, with the freeze as its
ancestor. Only reporting/evidence changes follow the freeze.

Only repair-round-2.md, manifest-correction-1.md, review-round-2.md,
download-topic-correction-1.md and the current download decision were imported
from the supplement. Main was not merged over rejected software. The prior
manifest is preserved in its authorized immutable mirror. All original raw
implementation/review/correction1/review2 bodies and reports remain exact.
New evidence is solely [correction-2-evidence](correction-2-evidence/).

[Preservation](correction-2-evidence/integrity-preservation.json) confirms all
7,394 original task bodies/modes and all 7,835 fixed-base task paths remain exact
at freeze; final reporting changes only the current Coding manifest and new
correction2 evidence. Registry remains the same72, SHA-256
`b71084a95126e99ff3261541baa125ab9b29e13188358598e915781d0608adca`; read-only rebuild
is exact with zero warnings. The 31 MCP names/risks, sole family map, frozen
recipe/Anima/other-kind behavior and all 14 shared dirty memory bodies/statuses
remain. No new registry certification or supersession is claimed.

## Repair and actual boundary

Both callers retain the shared process-local RLock. The new context manager
acquires it with the applicable operation's existing remaining time, checks the
same deadline after entry, and releases exactly one successfully acquired level
in finally. Failed/expired acquisition never releases another owner's level.
Acquisition creates its existing admission ProviderOperation before waiting;
retained install passes its already-started registered route operation. Waiting,
entry and subsequent preflight/hash checks consume that same budget. No budget
reset, larger timeout, second lock or synchronization removal is used.

A timed-out retained contender returns blocked/current `civitai_timeout`, actual
hint and already-known resource ID without changing the row, status, metadata,
notes, files, partials or body count. Expiration during existing-file preflight
keeps the actual timeout rather than incorrectly becoming `already_exists`.
Original pending/running ownership, useful inactive reuse/retry and same-ID
post-commit failure publication remain. Legacy direct service calls lacking an
operation can acquire an available lock immediately; they cannot wait without
an applicable deadline. Model bodies still execute after admission release.
The existing background operation lifecycle is unchanged. This is neither a
cross-process reservation nor a durable download attempt/job architecture.

See the [admission-site inventory](correction-2-evidence/admission-inventory.md)
and [original caller inventory](implementation-evidence/caller-inventory.md).
Production changes are limited to resource_records.py and the two existing
callers. The [download topic](../../civitai-downloads.md) documents the contract.
No schema/table/queue/dependency/MCP/UI/worker/default/removal feature was added.

Effective real Settings defaults remain positive integer bytes:
`CIVITAI_DOWNLOAD_MAX_BYTES=8589934592` (8 GiB/file),
`CIVITAI_DOWNLOAD_FREE_SPACE_FLOOR_BYTES=21474836480` (20 GiB observed floor).
[Effective settings/root receipt](correction-2-evidence/final-settings-bootstrap.log)
uses actual Python3.11.15 Settings/bootstrap and emits no credential value.
Actual caller guards use configured synthetic credential files; no manual key
or alternative download transport certifies them. HTTPX replaces external HTTP
only; ProviderOperation, registered HTTP/MCP, ORM commits and temporary files are real.

## D1–D5 / C1–C5 / E1–E5 evidence

All items remain P1. These are Coding checks and delivery evidence; independent
D5/C5/E5 certification belongs to QA3, not this manifest.

| Item | Check / level | Evidence, layer and real boundary |
|---|---|---|
| D1 | test / P1 | Current registered admission matrices in provider/bounds/callers/install/easy/writer tests retain Settings/type/format/exact declared size/hash and package-wide no-side-effect refusal, inactive reuse and frozen Anima/other-kind routing. Selected-size production fault causes2 assertions. Existing compatibility replacements remain explicit in implementation-evidence/compatibility.md. |
| D2 | test / P1 | Actual temporary chunk/prefix files, observed destination space, associated206/owned200 and full-prefix hash; foreign/linked/changed partial preservation. Byte/space/range faults cause1/1/5 assertions before exact restoration. |
| D3 | test / P1 | Registered same-ID acquisition/retained status, old notes/foreign targets, atomic publication/compensation and measured evidence remain. Original independent47 and author correction20 pass in complete249. Publication/verification faults cause1/2 assertions. |
| D4 | test / P1 | Same real configured credentials/ProviderOperation, request-origin/redirect/closure/backoff, disk/hash/publication deadlines. New registered contention has actual budget before waiting; unchanged QA R3 guard passes. Provider19 plus current provider suite/exit guards pass. |
| D5 | test + delivery / P1 | Frozen current full/affected/feature suites, fresh producers/readers/standing consumers, twelve assertion-sensitive faults/restoration, complete ordinary fingerprints, raw attempts, unchanged72/history and official restore artifacts. Independent exact-final verdict remains required. |
| C1 | test / P1 | Original corrected post-commit deadline/replacement cases plus real committed-adoption history/deletion/identical-byte replacement and writable/unavailable-DB controls. Actual reason, ID/hint/status agree without erasing history/notes or deleting foreign bytes. Current-publication/current-reason faults each cause3 assertions. |
| C2 | test / P1 | Pending/running/late target/stale ORM admission, actual partial bytes/metadata, retained-owner overlap, simultaneous retained calls and useful retry/inactive adoption remain. Active-admission bypass causes2 assertions. New timeout does not falsely fail the original owner. |
| C3 | test / P1 | Complete249 includes original bounds/provider/caller features, repaired R1/R2 and R3. Affected492/full Backend7174/MCP666 pass. One explicit access-time fixture repair below; no feature deletion, new skip or defect deselection. |
| C4 | test / P1 | Twelve sequential production faults produce25 intended assertion failures, not setup/hang/timeout substitutions; exact finally restoration followed by complete249 GREEN. Original five boundaries plus publication/reason/ownership/size/post-commit guards remain meaningful. |
| C5 | test + delivery / P1 | Freeze8629 ordinary fingerprints/modes and current per-run inputs match final product/tests/helpers. All old task bodies/modes and registry72 remain. Actual NEW FINAL/tree, exact manifest/index/archive/bundle/patch/prerequisite restore receipts provide QA3's review target. |
| E1 | test / P1 | New test_registered_contender_times_out_before_original_owner_releases covers install/acquire ×0.15s/already-expired. The original registered acquisition owns production admission throughout measurement; return is required before release within0.6s (explicit0.45s scheduling margin). Before/during columns, ID, notes, ownership stat, bytes, body/partial/row counters and original successful completion remain exact. Unchanged QA R3 guard also passes. |
| E2 | test / P1 | All16 new registered cases cover short/expired/available budgets, existing/absent final, real reentrant lock levels, exception release, original completion and following successful admission; a different-thread probe detects leaked levels. Both callsites and legacy no-operation policy are audited. Unbounded wait/budget-reset faults each cause2 assertions. |
| E3 | test / P1 | Complete feature249, affected492 and full suites preserve D1–D4/C1–C3, active same-ID ownership, old notes/measurements, adopted/foreign bytes, size/space/range/no-overwrite, configured credentials/deadline/closure and frozen compatibility. No safe timeout changes the original owner. |
| E4 | test / P1 | correction-2-evidence/fault_replay.py serializes all12 faults; final-fault-audit.json records exact substitutions/hashes, selectors and25 intended RED assertions. Original source restores byte-exact in finally; final-complete-features249 includes R3 without known-defect deselection. |
| E5 | test + delivery / P1 | All current gates apply to the exact freeze and unchanged descendant software, with Python3.11 imports, isolated guarded roots/DBs, per-test60s/outer600s limits, raw failures/recoveries, fresh19 fixture exports, registry/history and official empty-store bundle/patch restoration. Actual independent QA3 remains pending. |

## Current frozen qualification

[Verification](correction-2-evidence/verification.json) retains every actual argv,
allowlisted environment, cwd/root, source hash/mode, child imports/SQLite identities,
timing, exit and raw-log hash. [Qualification identity](correction-2-evidence/qualification-integrity.json)
confirms all current run inputs match freeze. Dependency sites are read-only;
current-worktree Python3.11.15 imports and isolated test roots are pinned. All long
suites use `--timeout=60` per test and600s outer bounds. Guard activation proves
six deliberate denials; current qualification has zero unexpected denials.

| Gate | Actual result |
|---|---|
| Full Backend | 7174 passed,124 existing skips,112 warnings;195.39s |
| Full MCP | 666 passed,four existing skips;85.67s |
| Affected production/compatibility/corrections | 492 passed;15.68s |
| Complete restored features including R3 | 249 passed;4.68s; no known-defect deselection |
| Twelve production faults | 25 intended assertion failures; exact finally restoration |
| Fresh Backend producers / separate MCP readers | 93 /73 passed;19 exact retained exports |
| Standing MCP/PNG/stdio/content/smoke consumers | 412 passed;83.57s |
| Independent configured-provider / fresh wait consumers | 19 /12 passed |
| Registry/history/shared edits | Same72;7394 original task bodies/modes;14 memory entries exact |

The [fault audit](correction-2-evidence/final-fault-audit.json) has failures by fault:
current-publication3, current-reason3, active-admission2, byte1, space1, range5,
no-overwrite1, size/hash2, selected-size2, post-commit deadline1, admission-wait2,
admission-budget-reset2. All are assertion RED with exit1. Setup/collection/timeout
termination never counts as sensitivity. [59 parsed observations](correction-2-evidence/outcome-traces.json)
retain before-release thread stacks/timing and owner/adoption/current-outcome traces;
raw logs remain authoritative.

## Attempts and compatibility

All29 run attempts and29 raw logs are preserved. `rejected-r3` independently
reproduces the fixed rejected product: real0.15s operation still blocked at0.6s
in production lock entry, then original owner completes after release. The old
QA log is retained as input, not substituted for this experiment.

The first expanded TDD run has5 failures/7 passes and a fixture limitation: its
shortening hook also reached the original background operation in negative-budget
cases. Clearing that hook before owner completion corrects only the fixture.
The corrected TDD run again has5 intended failures/7 passes: short retained wait,
late acquisition budget initialization (short/expired), and expired retained
adoption reason in two contexts. Initial repair passes37, pre-freeze affected492;
final results above are fresh at freeze. Early test bodies reconstructed from the
recorded write/single edit are explicitly labelled reconstruction and checked against
contemporaneous recorded SHA-256 in early-inputs.json; no absent hash is inferred.

One legacy feature fixture is explicitly repaired:
`test_acquisition_retains_known_storage_when_configured_root_changes` now observes
preservation before its own byte read. It retains exact old/foreign bytes and
ownership-critical device/inode/mode/link/uid/gid/size/mtime/ctime assertions.
Access time is excluded because reads change it. The actual review2 initial
1FAIL/475PASS, controlled self-read reproduction, unchanged476 repeat and original
raw fixture history remain immutable. No feature is removed, weakened to hide a
product mutation, deselected or newly skipped.

A reporting-only Settings command initially omitted the mandatory test bootstrap;
the production import guard refuses before Settings evaluation. The corrected
command calls real test_support.activate and successfully records effective defaults
and isolated roots. Both raw attempts/argv remain; no production/test/helper changed
and this setup failure is not qualification. See [attempt ledger](correction-2-evidence/attempt-ledger.json).

## Official delivery and limits

[Replay](correction-2-evidence/replay.md) specifies the guarded commands and official
restoration sequence. Ten uploaded/read-back prerequisite-only parts reconstruct
78,887,056 bytes, SHA-256
`f177e368dbe7732ab71c138b5e8169b1c2e027a4c28e7ac6098eb8b882395a61`, with declared
shallow cutoff `b4e71d18ba4600ad7e053274b90b45ffdfbce87b`. Two empty stores are seeded
only from those official bytes, with candidate absence and no alternates before
import. The official post-commit index binds actual FINAL/tree, full ordinary
fingerprints/modes, exact Git payload archive, incremental bundle, independent
full-index binary patch and their exact official readbacks/restores/fsck receipts.
Source publication/send receipts do not establish acceptance.

Offline only: synthetic external HTTP/credentials/time/scheduling/space with real
Settings/ProviderOperation/registered callers/ORM/filesystem. Running service:
none started/restarted/deployed/backfilled. Real generation/live model download:
none. Retrieval: synthetic installed bytes and official task artifacts only;
no live Gallery/model bytes. Frontend/native Windows remain unrun; inherited
open-writer deletion denial is an offline emulation. Private key/configuration,
runtime/jobs/databases/snapshots/backups, canonical environments, other worktrees
and models/datasets/outputs/Gallery are preserved. No artistic acceptance, durable
attempt/job/aggregate-budget feature or Phase2 exit is inferred.

Coding completes its own card with actual FINAL and artifacts. The native independent
QA3 card reads that actual pin before substantive review and publishes its own
verdict even if adverse. Producer owns repair/acceptance; changed software needs
another exact review and feature integration waits for independent PASS.
