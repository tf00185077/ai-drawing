# p2-02 independent delivery review

Verdict: FAIL
Review round: 4
Issue: [QA AID-193](/AID/issues/AID-193)
Coding: [AID-192](/AID/issues/AID-192)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed ACTUAL NEW FINAL: **bff2fb127d4ab5de69fe2124e9efc54cad0fd59a**.
Reviewed tree: **47e415fead18dedeb7c50caa0c931a01994ad1c8**.
Software/tests/test-replay freeze: **affcd94714b61b96326d11ac80c39c2aadd52462**.
Fixed implementation base: **8d7e5c5182d200a24b103f660f082f5844469739**.
The actual correction3 [manifest](manifest-correction-3.md) and Coding native
receipt were read before the FINAL was pinned on this card, before substantive
review: [pin receipt](review-round-4-evidence/pin-receipt.json). The official
manifest equals its FINAL Git body. This report's commit/tree and official
artifacts are published in the post-commit receipt.

**Original R1/P1 remains incomplete.** The two demonstrated prefixed assignments
and earlier complete-value forms now pass. Matching quoted credential labels
with whitespace inside their quotes still disclose their complete values through
writers and old reads, despite being recognized as dictionary credential keys.
R2–R4 remain passing. This is the existing shared-recognition/secrecy obligation,
not arbitrary unlabelled secret discovery or a new owner decision. No product
repair, merge, assertion relaxation, test deletion, new skip or registry addition
was made. Ordinary green suites do not override the observed disclosures.

## Finding

### R1 remains / P1 / D1,D2,D4,C1,S1,S2,T1,T2: quoted-label parsing disagrees with keys

In `backend/app/services/resource_records.py:26–28`, `_ASSIGNMENT_LABEL` requires
its captured label to start with a word/dot/hyphen and the closing quote to follow
the last such character immediately. It cannot consume whitespace just inside
the enclosing quotes. Its unquoted fallback matches the inner identifier without
an assignment delimiter, so `safe_text` at line 66 does not call the common
recognizer for that assignment. Conversely, `credential_label` at line 45 trims
outer whitespace, and dictionary normalization recognizes/removes those keys.
The Basic fallback does not repair recognition for a labelled opaque auth value.

These synthetic free-text values survive byte-for-byte, including the secret:

| Supplied text | Persisted/public observation |
|---|---|
| `" CIVITAI_API_KEY " = "QA4 unique complete value"` | Complete assignment retained |
| `' HTTP_AUTHORIZATION ' : Basic b3BhcXVlUUEx` | Complete header/value retained |
| `"provider\tapi\tkey " : "QA4 unique complete value"` (literal tabs) | Complete assignment retained |

The labels have the documented prefix/separator/case meaning, matching quotes,
and explicit colon/equal delimiters. The labels inside the quotes are also actual
credential keys under this candidate's own policy. Surrounding label whitespace
does not make the explicit value unlabelled. No claim is made that the app loads
these environment variables. No actual owner key was read or disclosed.

[Independent probe](review-round-4-evidence/independent_label_classes.py), initial
[log](review-round-4-evidence/independent-label-classes.log) and final
[log](review-round-4-evidence/independent-label-classes-final.log): both runs exit 1,
**33 failed / 45 passed**, all failures on feature assertions, no setup/import
errors. Thirty failures cover three inputs across these real boundaries:

- Shared typed publication commits/reloads the complete unsafe string with ORM;
  repeated normalization is idempotent but unsafe. Ordinary hash/trigger neighbors
  remain present.
- Registered inspect/select followed by edited typed install returns 200, keeps
  the measured hash and same row, persists the string, then detail/list/local-ledger
  return it. This is an unsafe success, not an allowed refusal.
- Synthetic external HTTP supplies each value through real Settings/file resolver,
  provider machinery, registered inspect/select and actual acquire/background.
  Acquisition succeeds and persists the value.
- Twenty-one old-storage cases span license, diagnostic field, trigger,
  recommendation value/origin, opaque evidence and raw base label. Registered
  detail/list/local-ledger disclose it. SQL writes, provider operations,
  publication/backfill and model-body reads are denied. Before the final secrecy
  assertion, old metadata_json/notes are verified byte-exact and the visible
  resource retains its safe hash/license data. No whole-resource hiding occurs.

The remaining three failures directly contrast recognized credential keys with
unchanged quoted assignment text. Separate [real ORM/HTTP key controls](review-round-4-evidence/independent_key_controls.py)
pass **three** cases: those exact literal keys are removed from nested license,
recommendation and evidence dictionaries at publication and all three public reads,
while safe neighbors remain. These controls isolate parsing inconsistency from
missing writer wiring. The 45 positive cases cover additional numeric/camel/dot/
Unicode/header classes plus safe near-neighbors; they do not certify the failing
quoted forms.

Expected under the unchanged complete-value/shared-recognition contract: exclude
the complete recognizable credential-bearing value, or safely refuse before
publication; old reads exclude it without writes or hiding the resource. Observed:
successful publication and read-only projection retain it. Producer owns findings
and any subsequent correction. QA has not repaired product or product tests.

## Acceptance items

All items retain their assigned P1 level.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | FAIL | Typed ORM/mapping/verification distinctions pass; complete secrecy fails. |
| D2 | FAIL | Real registered/provider/resolver/background/ORM and same-ID behavior pass; unsafe strings still publish. |
| D3 | PASS in isolated fixtures | Full old-schema/value/notes/alias-history/file/startup/backfill audit and exact previous-schema authority pass. |
| D4 | FAIL | HTTP/OpenAPI/filters/pagination/errors/read-only guards pass; old snapshots still disclose explicit credential values. |
| D5 | FAIL as acceptance gate | Exact independent review, faults/restoration/full/standing/packages reproduced; feature failures remain. |
| C1 | FAIL | Original signed-URL and old credential probes pass; quoted prefixed assignments remain unsafe. |
| C2 | PASS | Nine canonical validity/filter/count/page cases; raw-JSON filter mutation causes nine feature failures. |
| C3 | PASS | Omitted/same/augmenting/conflicting AIR on registered writers preserves ID/hash/measured facts; clearing mutation fails two cases. |
| C4 | PASS | Original notes exact across success/refusal/exception, truthful same-ID errors/recovery and new-row behavior; overwrite/error mutations fail 12/eight. |
| C5 | FAIL as acceptance gate | Current full/standing/preservation succeed; C1 remains unmet. |
| S1 | FAIL | Earlier complete Basic/cookie/quoted/Digest/access-token forms pass; new explicit labelled strings persist. |
| S2 | FAIL | Delivered all-nested stored-read cases pass; independent old reads disclose padded quoted labels without writes. |
| S3 | PASS for tested sensitivity | Actual one-token production defect fails 20 writer/36 stored-reader assertions; original fault meanings retained. |
| S4 | FAIL as combined acceptance | Current full/standing/schema checks pass; D1/D2/D4/C1 remain violated. |
| S5 | PASS for reviewability | Exact source/official bytes/fingerprints and both independent restorations usable; no correctness certification. |
| T1 | FAIL | Exact old 20 REDs reproduced and now pass; independent quoted-label provider/writer/ORM cases fail. |
| T2 | FAIL | Dictionary keys and quoted assignment text disagree; read-only old resources expose complete values. |
| T3 | PASS for tested sensitivity | Reviewed word-boundary production mutation fails 40 writer/provider and 195 old-read assertions, with exact restoration. |
| T4 | FAIL as combined acceptance | New source passes current full/standing/22-contract/preservation checks; original secrecy obligations remain unmet. |
| T5 | PASS for reviewability | FINAL pinned, immutable history, complete evidence and official shallow-aware bundle/patch prerequisites verified independently. |

## Independent commands and results

Persistent isolated worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-193-qa`,
branch `aid-193-exact-review`. Evidence is exclusively in
[review-round-4-evidence/](review-round-4-evidence/).
[Replay guide](review-round-4-evidence/verification-commands.md) and
[verification.json](review-round-4-evidence/verification.json) record 38 pytest
command records with exact argv/cwd/allowlisted environment/roots/imports, timing,
exit and saved/raw log hashes. Expected historical/adverse exit 1 remains actual
pytest failure, not product PASS.

| Scope / label | Actual result |
|---|---|
| rejected-review3-prefixed, exact21d273fe | 20 expected-feature failures, unchanged historical helper |
| rejected-review3-initial, exact21d273fe | Four expected-feature failures / 24 positive passes |
| current-original-probes / current-review2-probes | Four / 14 passed, unchanged helpers |
| current-review3-prefixed / current-review3-initial | 20 / 28 passed, unchanged complete helpers; no deselection |
| independent-label-classes / independent-label-classes-final | Both 33 failed / 45 passed |
| independent-key-controls | Three passed on actual shared ORM/HTTP paths |
| qa4-restored-feature | 718 passed after exact fault restoration |
| qa4-backend-full | **2,696 passed / 124 existing skips**, 76 warnings, 59.13s |
| qa4-mcp-full | **666 passed / four existing skips**, 73.06s |
| export-qa4 / cross-layer-qa4 | Fresh 93 Backend producers / 73 separate MCP readers |
| registry-mcp-qa4 | 412 standing MCP/PNG/stdio/smoke/content cases passed |
| fresh-wait-qa4 / retained-provider-guards-qa4 | 12 / 19 passed |
| schema-audit-qa4 | Two passed; full synthetic before/startup/backfill audit retained |
| source/restoration | 3,917 ordinary FINAL fingerprints; 437 selected protected source/test/helpers exact; every candidate body except the replaced current review remains exact |
| registry | All 22 previous rows exact; no additions/deletions/supersession |

The ignored Python3.11.15 venv references three existing dependency sites read-only;
no installation in canonical environments. Before tests the guard actually denied
six private-file/.env/non-scratch DB/model/write/DNS actions without opening private
inputs. All 140 ordinary pytest guard receipts have zero blocked events and imports
pinned to intended resolved current/archived roots. Nested isolated children retain
the established repository guard. Long suites use `--timeout=60`, unique run-owned
scratch, no cache/bytecode and pinned Backend/MCP child interpreters. Stat remains
allowed; feature guards separately deny model-body access. The long ordinary-text
feature also passes with its stricter three-second bound. Raw logs are retained
byte-exact in deterministic gzip; readable logs trim trailing whitespace only.

### Fault sensitivity

QA inspected and ran the production mutations sequentially, without an overlapping
suite or source-fingerprint reader. Files restore exact bytes in finally before
718 feature GREEN and fresh full/standing suites. [Fault audit](review-round-4-evidence/fault-audit.json):
**20 invocations / 18 distinct production mutations / 393 feature assertion failures**.
Every counted failure is an observable assertion, never collection/import/SQL/
fingerprint setup failure. The previous 17 distinct/18 invocation meanings remain.

| Mutation | Feature failures |
|---|---:|
| Wrong map / fabricated verification | 1 / 2 |
| Split acquire / install publication | 1 / 1 |
| Destructive backfill / unbounded list / writing list | 1 / 2 / 1 |
| Complete normalization / stored projection bypass | 1 / 1 |
| Raw-JSON filter / clear omitted identity | 9 / 2 |
| Overwrite retained notes / lose current error | 12 / 8 |
| One-token redaction: writer / old reader | 20 / 36 |
| Inspect descriptor / supplied descriptor / legacy-license bypass | 20 / 20 / 20 |
| Reviewed word-boundary recognition: writer-provider / old reader | 40 / 195 |

These sensitivity results do not negate the separate current RED inputs.

## Preservation and delivery integrity

The real synthetic boundaries include Settings/environment-selected file resolver,
provider request machinery, selected version/file, strict schemas, shared typed
publication/projection, SQLite/ORM, registered HTTP/OpenAPI and actual background
targets with measured tiny files. Only external HTTP and scheduling substitute
production behavior. No Settings/resolver/domain injection is presented as proof
of loading. Current provider guards retain prepared-header/origin/cookie/deadline
protections. Retained duplicate/retry/same-ID error recovery, wait/interruption,
PNG bytes and stdio contracts pass; no new cancellation or job API is introduced.

D3 audits 16 tables including sqlite_sequence, eight resource rows and five
populated alias/history tables. Startup adds nullable metadata_json only; explicit
backfill changes that field only and remains idempotent. Old columns/values/notes,
IDs/counts, aliases/history and synthetic file bytes remain exact. Duplicate,
conflicting, malformed, unsupported and offline cases have diagnostics. The
pre-task schema authority does not load Settings. Retry-note preservation is
separately tested; an isolated migration result alone does not establish it.
Legacy caller/alias inventories remain source evidence, not removability proof.

[Preservation](review-round-4-evidence/preservation.json) verifies the four exact
authorized supplement imports, task/repair hashes, 240 existing Backend-test/MCP/
registry bodies, 952 old task bodies at their original paths and the previous
current report preserved verbatim in review-round-3.md. All 3,916 candidate bodies
other than this intentionally replaced review.md remain exact. The original task
SHA256 is `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`;
repairs1/2/3 retain their authorized hashes. Two application services, one new test
and the technical topic differ from the fixed correction base; old product tests
are unchanged. No Backend/MCP change follows the affcd94 software freeze. All 31
MCP names/risks, frozen recipe/AIR/Anima/alias behavior and 22 prior contracts remain.
All 13 shared-main memory bodies match preserved hashes. No staging/stashing/reset
or copying of those edits, private settings or runtime data occurred.

QA independently downloaded **all 15 Coding uploads**. All sizes/SHA256 match
both official indexes/receipts. [Coding integrity](review-round-4-evidence/coding-integrity.json)
checks 3,917 ordinary fingerprints, 390 indexed payloads/391 archive members/
380 exact Git bodies and four raw commit/per-commit patch pairs. The nine official
base parts combine to **67,480,250 bytes**, SHA256
`5776e99dfa619adb6bb3363196a80d01f8b4ce5ea2555eb8dbcc31524d8a5a92`.
Separate fresh bundle and patch/history stores reproduce exact FINAL/tree and
both `git fsck --full` exit 0 using only official bytes. The patch store imports
no candidate/local objects. Both write declared shallow boundary
`b4e71d18ba4600ad7e053274b90b45ffdfbce87b` before fetching with `--update-shallow`
and explicit prerequisite ref `refs/heads/aid-191-exact-review`. This is a usable
declared-shallow restoration, not a pre-boundary history backup.

The first adverse command expected exit 0 and therefore also reported an
orchestration mismatch after its 33 actual feature failures; both the original
record and later explicit expected-exit-1 replay are preserved. An administrative
integrity summary called getmembers after closing a tar file; the failed helper
and attempt record remain. A corrected helper repeats official-byte verification
and both restorations in fresh stores. Neither checker failure counts as feature
sensitivity. One guessed evidence-decision filename was absent and resolved to
tracked decisions/evidence.md. No failed attempt is hidden by a product change.

QA's report commit/tree, uploaded artifacts, exact readback and independent bundle/
patch report restorations are published on this card after commit. The report-only
delta declares the verified official Coding FINAL prerequisite and its complete
access paths. QA completes its own card with this FAIL; Producer handles findings,
threshold reporting and acceptance. Any changed software requires another exact
FINAL review. No feature push/merge, parent/owner write or routine owner gate.

## Limits and disposition

**Offline:** pinned source, guarded real synthetic provider/ORM/HTTP/background,
adverse/fault/restored/full/standing/schema tests and official attachments.
**Running service:** no production probe/start/restart/deploy/backfill.
**Provider/generation:** no actual owner key read, live provider request, real model
acquisition/registration or generation. **Retrieval:** synthetic installed bytes
and Paperclip attachments only; no live Gallery/model bytes. Frontend and native
Windows unrun. The 124 Backend skips require Windows; four optional MCP exports
are separately covered by fresh producers/readers.

History remains kickoff1 CLEAR, delivery1 FAIL/four P1s, review2 FAIL/R1 incomplete,
review3 FAIL/R1 incomplete, then **this review4 FAIL/R1 incomplete**: four rejected
deliveries, one unresolved original finding. Producer's already-recorded
three-rejection threshold reassessment/adopted shared-recognition option stays
attributed; this result is not acceptance of that implementation. R2–R4 pass at
this exact source. No Phase2 automated flow, three zero-fix sentences, fresh
checkpoint-plus-LoRA qualification, phase exit or CTY aesthetic verdict is claimed.
