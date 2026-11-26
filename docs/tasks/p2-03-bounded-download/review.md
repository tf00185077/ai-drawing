# p2-03 independent delivery review

Verdict: FAIL
Review round: 1

Recipient-owned [QA AID-209](/AID/issues/AID-209) reviewed the actual completed
[Coding AID-208](/AID/issues/AID-208) delivery. Two P1 defects prevent acceptance.
[Producer AID-146](/AID/issues/AID-146) owns findings, repairs and acceptance.
This review makes no product repair, merge, deployment or Phase 2/artistic decision.

## Exact reviewed identity

| Input | Identity |
|---|---|
| Coding FINAL | `9db560974e42189a827017c0cc6779e1646dd50c` |
| Coding tree | `bdeec89ce67bda525b9a4f6ba59d8a10d851eb10` |
| Fixed published prerequisite | `aefb8318bcdd7942b5c2be14b1c9fc42b33d7556` |
| Coding software/test/helper freeze | `b5af8b691a677a98786f3f371bda1366cb7418a2` |
| Unchanged task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Coding manifest SHA-256 / bytes | `b0fac2232b7e9dfe9027c1326d31b204a00aa1536c63b1cfb45765c0182e4cd1` / 14732 |
| QA pre-review card pin | comment `7666d22c-b680-4eda-9189-501c6620d432` |
| QA feature/helper freeze | `befdb14a9c590a266c40a7f82151dbff6384f324` |
| Persistent QA worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-209-qa` |
| QA branch | `qa/aid209-p203-delivery` |

Coding's actual final comment `0c98f67a-b364-49cf-a3ec-a619813e1ffc` and official
receipt were read; the actual manifest was read from that commit. The card pin
precedes substantive source review and test execution. This is delivery review,
not another kickoff. The original CLEAR and kickoff observer/report bytes remain
unchanged. The observer asserting obsolete unsafe behavior was not run as GREEN.

All 8302 candidate ordinary file bodies are indexed in
[candidate-inventory.json](review-evidence/candidate-inventory.json). They remain
exact in the QA worktree after all deliberate faults. Only new review/report/helper
files are added by QA. Reporting descendants do not change the frozen independent
feature inputs. The official post-commit QA index binds the report body to QA's
actual final commit/tree, avoiding a circular self-hash inside this file.

## Findings

### R1 — P1: failed retained adoption leaves a committed installed/current-success row

At `backend/app/services/civitai_resource_install.py:355`,
`_persist_ledger_identity` commits installed state and measured evidence, then checks
the deadline and actual final identity. In the existing-file adoption branch at
lines 417–425, either post-commit failure goes to a broad exception handler that
only rolls back and returns `ledger_persistence_failed`. Rollback cannot undo the
already committed state. This branch does not use the same-ID failure publication
used by newly downloaded installations, and discards the actual timeout/file-change
code, recovery hint and resource ID.

Independent registered-HTTP reproductions start with one planned row, exact existing
bytes and immutable old notes. A wrapper performs the real ORM commit and then
either expires the actual configured-file `ProviderOperation` deadline or renames
the verified final and writes a foreign replacement. No production transport or key
is injected. Both calls return HTTP 500; status on the same ID remains `installed`
with no current error. The deadline case reports verified hash evidence; the
replacement case correctly invalidates measured verification but still advertises
`installed`. The foreign replacement and original notes survive.

Required outcome: preserve that data and genuine historical measurements while
publishing the actual failed/current reason on the same row/ID. A truthful failure
must not leave installed/current-success state or replace timeout/file-change with
an unrelated ledger error. This violates D3 and D4. It is not a permanently
unavailable database scenario: the commit succeeded and subsequent writes work.

Reproducer:
`review-evidence/independent_checks.py::test_adoption_failure_after_commit_must_publish_current_failure`
(`deadline`, `replacement`). Both fail the intended same-ID state assertion.
See [raw results](review-evidence/qa-independent-pinned.log) and the two
`QA_ADOPTION_COMMIT` records in [independent traces](review-evidence/independent-traces.json).

### R2 — P1: retained install duplicates an admitted acquisition and corrupts its current outcome

`_admit_install` at `backend/app/services/civitai_resource_install.py:362` reuses
the selected file's row without checking whether that row already has active
download ownership. The retained path reaches it at line 437. Its read-only
preflight and identity-conflict checks do not reject an existing `downloading` row.

An independent registered-HTTP trace submits acquisition and holds its real
background callable pending using the established deterministic scheduling fixture.
Retained install for the same selected file then makes another provider model-body
request, returns HTTP 200 and marks that same resource installed. When the original
admitted callable resumes, its no-overwrite preflight sees the newly installed
target and changes the same row from `installed` to `failed/civitai_target_exists`.
The verified file survives. This is a second submission and a contradictory current
outcome for one resource, rather than safe reuse of the original active operation.

Required outcome: the retained caller must respect the already admitted resource's
active ownership and avoid another body submission. This violates the same-ID,
duplicate-submission and truthful-status contract in D3. It does not require a new
attempt table or job architecture.

Reproducer:
`review-evidence/independent_checks.py::test_acquire_then_retained_install_must_not_duplicate_active_body`.
Its `QA_DUPLICATE` record contains one extra `/api/download/models/21` request,
retained HTTP 200, the single original resource ID, and installed → failed status.
See the same [raw log](review-evidence/qa-independent-pinned.log) and
[parsed trace](review-evidence/independent-traces.json).

## D1–D5 assessment

| Item | Result | Independent evidence and limits |
|---|---|---|
| D1 / P1 | PASS in checked scope | Both registered callers refuse format, cap, fractional size, invalid hash and unavailable/insufficient space without body/partial/row effects. Current production MCP/HTTP admission tests also pass. Settings reject invalid direct types and load explicit positive environment values; defaults are 8589934592 and 21474836480 bytes. Exact provider byte interpretation is shared by acquisition, inspect and typed snapshots. Frozen Anima component/package/other-kind and safe exact-file reuse guards pass. |
| D2 / P1 | PASS in checked scope | Independent actual-file guards observe two accepted bytes before a refused overrun/depleting-space write; observations use the target filesystem. Missing/malformed/wrong-start/wrong-end/wrong-total ranges preserve the associated prefix. Valid 206 and owned 200 restart verify exact final bytes/hash. The candidate's real-row interruption, prefix association and all foreign/linked/nonregular/oversize/changed-part guards pass in the independently run affected suite. |
| D3 / P1 | FAIL | Core atomic no-overwrite, racing-target preservation, ownership compensation, normal same-ID failures and measured success pass. R1 and R2 demonstrate missing current-failure/active-ownership behavior in retained install. No blanket claim of safe caller state is justified. |
| D4 / P1 | FAIL | Configured-file precedence, rotation, bad-file refusal, final origin credentials and cross-origin stripping pass through both real callers. Sixteen additional production exit traces cover cap/space/hash/collision/network/403/final-hash deadline/publication deadline, response closure, same ID and old notes. Existing provider/deadline/backoff/redirect regressions pass. R1 still loses the actual post-commit deadline/file-change outcome on adoption. |
| D5 / P1 | Verification performed; no task certification | Five distinct production faults produce ten meaningful assertion failures, with exact finally restoration and GREEN for the restored guarded scope. Current full/affected suites, fresh exports/readers and standing consumers pass. All 72 prior rows remain exact; no new row is certified for this failed delivery. The independent full feature run remains RED on R1/R2. |

## Fresh verification and fault sensitivity

The [frozen runner](review-evidence/run_checks.py) records actual argv, cwd,
allowlisted environment, loaded-source hashes, elapsed time, exit code and raw-log
hash. Children use the QA-owned Python 3.11 environment, read-only installed
dependency sites, explicit scratch/test roots, disabled plugin autoload, current
worktree Backend/MCP imports and `--timeout=60` per test, with a 600-second outer
bound. The final runner records 821 ordinary software/helper inputs as well as the
complete candidate inventory. Guard receipts include child imports and SQLite
paths. Six explicit containment denials were demonstrated by `qa-guard`; successful
qualification runs have no unexpected guard denials.

| Command through `review-evidence/run_checks.py` | Result |
|---|---|
| `qa-independent-pinned review-evidence/independent_checks.py -s` (full repo-relative path in receipt) | 3 failed, 44 passed; R1 twice and R2 once; 1.61 s |
| `qa-affected` (eight exact production/compatibility selectors in receipt) | 456 passed; 14.17 s |
| `qa-backend-final backend/tests` | 7138 passed, 124 existing skips, 112 warnings; 193.06 s |
| `qa-mcp-final mcp-server/tests` | 666 passed, four existing skips; 89.13 s |
| `export-qa-final` (four Backend producers) | 93 passed; 2.84 s |
| `cross-layer-qa-final` (four separate MCP readers) | 73 passed; 0.49 s |
| `registry-qa-final` (registered MCP/PNG/stdio/content/smoke consumers) | 412 passed; 86.46 s |
| `qa-provider-final` (retained independent configured-file/provider boundary) | 19 passed; 1.24 s |
| `fresh-wait-qa-final` (fresh HTTP wait consumers) | 12 passed; 1.32 s |

The complete argv and raw outputs are retained for every row; see
[verification index](review-evidence/verification.json). The 19 newly produced
export bodies and hashes are under [fresh-exports](review-evidence/fresh-exports/)
and [fresh-export-index.json](review-evidence/fresh-export-index.json). Producers
completed before readers. Both full suites cover the active registry's ordinary
Backend/MCP guards; the additional standing/provider runs cover its document-owned
guards. No candidate feature guard was deleted or skipped by QA.

Independent faults alter the actual production `civitai_safe_download.py`, one
boundary at a time, with no other tests running concurrently. The
[fault driver](review-evidence/independent_faults.py) and
[audit](review-evidence/independent-fault-audit.json) preserve exact substitutions,
original/mutated/restored hashes and related guard names.

| Fault | Feature observation causing RED | Assertion failures |
|---|---|---|
| Disable pre-write byte accounting | Violating bytes are accepted instead of refusal at two bytes | 1 |
| Disable destination floor enforcement | Depleted-space write proceeds instead of stopping at two bytes | 1 |
| Disable Content-Range validation | Invalid responses append/publish instead of preserving the prefix | 5 |
| Replace link-if-absent with `os.replace` | The independent guard observes replaced racing-target bytes | 1 |
| Disable final exact size/hash verification | Short or wrong-hash bytes complete instead of refusal | 2 |

All five exits are assertion-driven exit 1, with no collection/import/setup/timeout
substitute for sensitivity. Every finally block restores SHA-256
`a8413c44f08d7ac2f52744db87aca6ad02362fe9e947dd0db32c86db49f182ee`.
Then `qa-restored-green` passes 125 checks. That GREEN scope explicitly deselects
the three known candidate defects by name; it does not turn the full independent
47-case run into GREEN. The subsequent full independent run again reports the same
three failures. Full Backend/MCP and fresh consumer qualification run after this
restoration and the final independent-helper freeze.

## Compatibility, preservation and delivery integrity

I inspected every modified legacy test body against the published prerequisite.
The [Coding compatibility inventory](implementation-evidence/compatibility.md)
matches the actual diff: raw unassociated-part success fixtures become real
associated-prefix positives; legacy/foreign/link negatives retain bytes; admitted
size/hash failures now require a failed same-ID row; the old incomplete Settings
fixture supplies explicit policy; retained exact-final retry rehashes/adopts rather
than forcing a provider refusal. Original byte/hash/identity/old-note checks remain.
The original ledger pre-admission commit-failure guard remains unchanged. New
post-admission compensation guards pass. No silent deletion/new skip or registry
supersession was found.

All 72 existing registry rows and all 7394 prior task bodies/modes are exact.
The registry builder was run after this FAIL report and produces the unchanged
72-row registry; no p2-03 coverage is certified. The complete 31-name MCP catalog
and risk guards pass. The single Phase 2 family map remains separate from frozen
Anima routing, and public projection does not become an internal executable lock.
Current p2-01/p2-02 regression guards pass, including raw old-note preservation.
Shared main's 14 dirty memory bodies/statuses remain unchanged.

All six Coding official attachments were independently retrieved. Their declared
hashes agree; the 165 archive members, 158 Git payloads, complete 8302 final
fingerprints and exact manifest agree with the pinned Git tree. A prerequisite-only
pack seeds two fresh stores, with candidate absence and no alternates checked.
The downloaded official bundle reconstructs the exact Coding final/tree; the
independent full-index patch reconstructs the same tree. Both `fsck --full` exit 0.
The existing published shallow cutoff is explicitly retained, not guessed.
See [readback](review-evidence/coding-artifact-readback.json),
[restoration commands](review-evidence/independent-coding-restore.json) and
[preservation audit](review-evidence/integrity-preservation.json).

QA's own official report/evidence archive, incremental bundle, full-index patch
and post-commit index provide the reproducible handoff. Raw `.log` bodies are
explicitly included despite ignore rules. The final comment/receipt names QA's
actual commit/tree and artifact hashes; the reviewed product target remains the
Coding FINAL above. Any product change needs a new exact-candidate review.

## Attempts, reproduction and practical limits

All attempts are retained in [verification.json](review-evidence/verification.json).
The initial independent run was 28 passed/three demonstrated failures. Adding sixteen
deadline/closure cases yielded 44 passed/the same three failures. A second helper
freeze strengthens direct racing-byte assertions and pins document-owned Python
inputs; it changes no product code or expected defect outcome. Earlier independent
logs and the first fresh full-suite/export logs remain immutable. These are
pre-final observations, not substituted final qualification. No fixture/setup
failure was needed to obtain the final independent result.

One reporting aggregation guessed 24 run records and asserted against the actual
21. The corrected aggregation retains all 21, with no test rerun/reclassification
or product/input change. This packaging error is recorded in
[packaging-attempts.json](review-evidence/packaging-attempts.json).

The first evidence commit also included one generated guard `.pyc` after the
staged-cache assertion failed; continuing to commit was a QA packaging mistake.
A subsequent report-only commit removes that generated cache without rewriting
history. All raw/source/test/input bodies stay exact. A whole-payload whitespace
check reports 17 original pytest diff lines; those raw bytes are intentionally
retained, and the authored non-log changes pass their separate whitespace check.

Reproduction uses the frozen runner and current isolated scratch root. Prepare the
QA-owned environment with `review-evidence/setup_environment.py`, activate its guard,
then run the full repo-relative independent file using the recorded argv. The
three failures are expected reproductions on this rejected candidate. Run
`review-evidence/independent_faults.py` sequentially with no other tests active;
its five faults restore production bytes in finally. Fresh export labels must
precede separate reader/standing labels. Exact selectors, imports, policy sources,
raw logs and hashes are in the receipts rather than dependent on a running service.

Offline verification: synthetic external-HTTP fixtures, real production request
factories, registered routes/MCP adapters, deterministic background callbacks,
isolated ORM databases, controlled space observations and real temporary files.
No live provider or owner key was needed; HTTPX MockTransport substitutes
external I/O, so these are not live provider proofs. Keyboard interruption and
response closure are checked; no new cancellation API or durable job is claimed.
Open-writer deletion denial is an offline emulation from the delivered guards.

Running service: not started, restarted, deployed or backfilled. Real generation
and live model download: none. Artifact retrieval: synthetic fixture bytes plus
official Coding/QA attachments, with no live model/Gallery bytes. Frontend and
native Windows were not run; no affected UI/worker change exists. Private key/config,
canonical dependencies, runtime/jobs/databases, models/datasets/outputs/Gallery and
other role worktrees were not repaired or cleaned up. Offline success does not
establish runtime deployment, Phase 2 exit or CTY's artistic acceptance.

The QA card completes with this actual adverse verdict. Producer owns the next
repair/acceptance action; no imaginary future FINAL is awaited by this review.
