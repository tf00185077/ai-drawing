# p2-03 independent delivery review

Verdict: FAIL
Review round: 2

[QA AID-211](/AID/issues/AID-211) reviewed actual completed [Coding AID-210](/AID/issues/AID-210)
correction 1. R1/R2 pass in the checked scope. New P1 R3 breaks the retained
operation deadline. [Producer AID-146](/AID/issues/AID-146) owns findings, repairs
and acceptance. QA makes no product repair, merge or Phase2/artistic decision.

## Exact reviewed identity

| Input | Identity |
|---|---|
| Actual Coding FINAL | `33b920fd124540bf8fdf2128f19ceceb6b10ea41` |
| Coding tree | `95f0bfbfd8644c866882358343868f3c976a8331` |
| Coding software/test/helper/topic freeze | `bc5cab04fdf7bbc4641e0502e76a747c30e05cea` |
| Fixed correction base | `3ed5ae8fc5e86e6a74301e45e52013394a41983f` |
| Unchanged task SHA-256 | `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0` |
| Coding manifest SHA-256 / bytes | `02fe6bf5618fd05521e9bf0676e31ef9f60b8e1559c1cbb5dc0d1c4656320132` /15052 |
| Native pre-review pin | comment `076dbd95-61fa-41b1-8c7f-031eb47a6e69` |
| QA positive/fault helper freeze | `9bde589a0c5900b69e4ddfd42c208733f8b7c99d` |
| QA final adverse helper freeze | `3e2ab550b82a99fbaba31a2c68313d2bc03023dd` |
| QA worktree | `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-211-qa` |
| QA branch | `qa/aid211-p203-review2` |

Actual Coding final comment `85a666cc-825d-4195-aa8b-65d5f18942c9`, official index
and exact Git manifest were read. The card pin precedes substantive review/tests.
Original task/kickoff CLEAR and review 1 FAIL remain historical. Official post-commit
QA index/final comment bind this exact report to actual report FINAL/tree, avoiding
a circular self-hash. Only QA report/evidence changes follow helper freezes.

## Findings

### R3 — P1: admission contention can exceed the existing absolute deadline

The correction adds an ordinary process-local `RLock` in
`backend/app/services/resource_records.py`. Retained install enters it at
`civitai_resource_install.py:444` using unbounded `with resource_admission:`.
`operation.remaining()` runs only after acquisition, at line 445. Acquisition holds
that lock from `civitai_resource_acquire.py:389`, including verified-existing
hashing at line 413. A retained call with little time remaining can wait for another
acquisition, or queued admissions, beyond its own absolute deadline.

The independent registered-HTTP guard uses real Settings, configured synthetic
credentials, ProviderOperation, ORM and filesystem. A real acquisition is held at
its verified-existing observation while owning production admission. The competing
retained operation has a deterministic 0.15-second remaining budget. At 0.6 seconds
it has not returned. Its captured actual operation-thread stack is blocked at
`with resource_admission:`, excluding delayed test-thread startup as the explanation.
Only releasing the other caller lets it return HTTP409/`civitai_timeout`. The
original owner then finishes installed; ID and existing bytes survive. No competing
model-body request is needed to expose this failure.

Required outcome: admission contention must honor the existing remaining deadline
while preserving original ownership. Checking expiration after acquiring the lock
returns the right reason too late. No extended deadline or new attempt/job
architecture is required. Scaled synthetic timing proves this blocking path; it
does not measure a naturally slow production disk or live 900-second timeout.

Reproducer: `review-2-evidence/deadline_checks.py::test_registered_admission_wait_obeys_existing_operation_deadline`.
See [final adverse log](review-2-evidence/qa2-admission-wait-final.log), its receipt,
and `QA2_LOCK_DEADLINE` in [traces](review-2-evidence/independent-traces.json).
Complete current independent scope is **1 failed, 232 passed**. This intended
deadline assertion is never deselected or relabelled GREEN.

## D1–D5 and C1–C5

All remain P1. PASS means the checked scope, not Producer acceptance.

| Item | Result | Independent evidence and limits |
|---|---|---|
| D1 | PASS | Both registered callers retain effective Settings, safetensors, strict size/hash and no side effect refusal. Settings/type/package/Anima/other-kind/inactive reuse pass. Disabling declared-size admission fails both caller assertions. Original compatibility replacements remain explicit; correction 1 edits no legacy feature test. |
| D2 | PASS | Actual chunk/prefix files, destination space, invalid ranges, associated 206/owned 200, full hash and foreign/linked/changed preservation pass. Independent byte/space/range faults fail 1/1/5 assertions and restore exactly. |
| D3 | PASS in checked scope | Real committed adoption failures publish actual same-ID reasons. Pending/running callers preserve owner columns/notes, actual partial bytes/stat and late foreign targets. Racing publication, compensation, measured success and useful retry/reuse pass. |
| D4 | FAIL | Configured-file credentials/origins/closure/backoff and original deadline guards pass; R3 adds a blocking wait outside the deadline. Independent removal of post-commit adoption deadline checking also causes intended RED. |
| D5 | FAIL as complete certification | Exact-source fault/current/full/consumer/artifact checks performed; registry 72 exact. Complete independent feature scope is RED on R3. Prior narrower positive 232 GREEN cannot certify the complete requirement. |
| C1 | PASS | Original R1 REDs reproduce rejected source and pass corrected source. New real-commit deadline, identical-byte inode replacement and deletion cases retain ID/notes/download time/history, actual code/hint and truthful current certification. Author new/existing-row and true/unavailable-DB controls independently pass. |
| C2 | PASS in checked scope | Original active-duplicate RED reproduces. Registered MCP acquire/status plus retained HTTP cover pending/running × late target, actual 1 MiB prefix preservation, both competitors, stale preflight/adoption, original completion and inactive retry/reuse. Author simultaneous/retained-owner cases pass. Admission bypass fails both independent stale-boundary cases. |
| C3 | FAIL | Original limits/compatibility pass; R3 breaks the retained absolute deadline during new admission contention. |
| C4 | FAIL as complete GREEN gate | Required repair/original faults are assertion-sensitive and restore exactly. Ten faults cause 21 intended assertions. Complete current scope still has1 failure / 232 passes on R3; no defect exclusion supplies GREEN. |
| C5 | FAIL as delivery certification | Actual FINAL pinned; current qualification, restoration and preservation supplied. R3 prevents corrected task certification. No new registry row is certified. |

Original rejected-source replay has the intended three assertions failing. All 47
original independent cases pass corrected source. New adoption checks preserve
committed historical verification JSON; only unchanged file identity retains
current certification. Identical-byte replacement invalidates it. DB controls
distinguish pre-admission rollback, actual installed commit and permanently
unavailable later persistence. Old notes remain exact. No blanket install refusal
or hidden owner/resource substitutes for useful retry/reuse.

## Verification and sensitivity

The [runner](review-2-evidence/run_checks.py) retains argv/cwd, allowlisted
environment, ordinary input hashes, imports/SQLite paths, timing, exit and raw-log
hashes. Children use QA-owned Python 3.11, read-only installed dependency sites,
isolated scratch roots, disabled plugin autoload, per-test `--timeout=60` and
outer 600-second limits. Guard activation demonstrates six denials; qualification
has no unexpected denials. Full suites use 836 exact inputs at the positive helper
freeze. The later adverse module adds an input without changing product/full-suite
inputs; applicable full-suite evidence remains exact.

| Runner command label | Actual result |
|---|---|
| `qa2-complete-independent` | 1 failed, 232 passed; 4.26 s; R3 assertion |
| `qa2-backend backend/tests` | 7158 passed, 124 existing skips, 112 warnings; 194.36 s |
| `qa2-mcp mcp-server/tests` | 666 passed, four existing skips; 96.13 s |
| `qa2-affected-repeat` (nine production selectors) | 476 passed; 13.23 s |
| `export-qa2` / `cross-layer-qa2` | 93 /73 passed; fresh producers precede separate readers |
| `registry-qa2` | 412 passed; 93.93 s |
| `qa2-provider` / `fresh-wait-qa2` | 19 /12 passed |

All 31 verification attempts/selectors are in [verification.json](review-2-evidence/verification.json).
Nineteen fresh export bodies/hashes are retained in [fresh-exports](review-2-evidence/fresh-exports/).
Existing optional/platform skips remain unchanged. Current helper/provider suites
also check interruption and response/iterator closure; no new cancellation API or
durable recovery is claimed.

Faults execute sequentially against production files with no other tests active.
[Driver](review-2-evidence/independent_faults.py) and [supplement](review-2-evidence/supplemental_faults.py)
retain mutations and exact finally-restored hashes. Setup/collection/timeout errors
never count as sensitivity.

| Production fault | Intended assertion failures |
|---|---:|
| Publish installed rather than failed current adoption | 3 |
| Replace actual adoption reason with generic persistence error | 3 |
| Bypass refreshed active admission | 2 |
| Disable pre-write byte / destination floor | 1 /1 |
| Disable Content-Range association | 5 |
| Replace link-if-absent with overwrite | 1 |
| Disable exact final size/hash | 2 |
| Disable selected-size admission | 2 |
| Remove post-commit adoption deadline check | 1 |

Positive 232 passes after restoration. Subsequent complete scope 233 remains RED
with the new adverse deadline guard. Neither the narrower GREEN nor Coding's 222
GREEN establishes complete acceptance.

## Preservation, artifacts and attempts

All 17 official Coding uploads were downloaded/hash-checked. Two empty stores seed
only the official 77,962,971-byte prerequisite pack and declared shallow cutoff
`b4e71d18ba4600ad7e053274b90b45ffdfbce87b`. Candidate absence/no alternates are
checked before import. Official bundle restores actual FINAL/tree; independent
full-index patch restores that same tree. Both fsck checks exit 0. All 8487 ordinary
fingerprints/modes, 108 archive members, 106 Git payloads and exact manifest agree.
See [readback](review-2-evidence/coding-artifact-readback.json) and
[restoration](review-2-evidence/independent-coding-restore.json).

All 7394 original published task bodies/modes and all 72 registry rows remain exact.
Original p203 reports/raw inputs and round 1 mirrors survive; review.md is the
explicit current QA report update. QA changes no product/test/catalog/recipe/Anima
body. The 31 MCP names/risks and sole family map remain. Registry rebuild adds no
certification on FAIL. Shared main's 14 dirty memory bodies/statuses remain exact.
Complete inventories and official QA report/archive/index/bundle/patch accompany
the handoff; final index binds actual report FINAL/tree.

[Attempt ledger](review-2-evidence/attempt-ledger.json) separates setup/packaging
failures. Initial MCP fixture import order produced 7 failures; importing actual
registration before replacing external HTTP classes resolves it. First adverse
module has a sibling-import collection error; its correction then exposes R3
repeatedly. Exact early input bodies match contemporaneous hashes.

First affected run has 1 failed/475 passed: its foreign-file self-read precedes a
full stat comparison, and only access time differs. A controlled self-read without
production calls reproduces that stat change; [diagnosis](review-2-evidence/atime-fixture-diagnosis.json).
Unchanged full affected repeat 476 and full Backend 7158 pass. This remains a fixture
fragility note; no product/test edit or deselection hides it. Auxiliary-payload
lookup and preservation-count packaging mistakes are retained/corrected separately.

## Evidence limits and disposition

Offline synthetic HTTP/files, real configured credential factory/ProviderOperation,
registered callers/ORM/filesystem, deterministic scheduling and controlled space/
time only. No manual credential/download-transport bridge certifies callers.

Running service: none started/restarted/deployed/backfilled. Real generation/live
model download: none. Retrieval: synthetic installed bytes and official task
attachments; no live Gallery/model bytes. Frontend/native Windows remain unrun;
inherited writer-deletion denial is an offline emulation. Private key/configuration,
runtime/jobs/databases/snapshots/backups, dependencies, other worktrees and
models/datasets/outputs/Gallery remain preserved.

The QA card completes with actual **FAIL**. Producer receives the native wake and
owns the next repair/acceptance action. Changed software requires another exact
review. No feature merge, Phase2 exit or CTY artistic acceptance is inferred.
