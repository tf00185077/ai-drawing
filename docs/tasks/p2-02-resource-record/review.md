# p2-02 independent delivery review

Verdict: FAIL
Review round: 3
Issue: [QA AID-191](/AID/issues/AID-191)
Coding: [AID-190](/AID/issues/AID-190)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed FINAL: **21d273fec6ce8bf00a533634d685edfb42431b05**.
Reviewed tree: **1f4e58600af5d7583522cb37120dbb62153d990c**.
Software/tests/replay freeze: **374c158b58332c9f49164a478961de5e9a7b871e**.
Fixed correction base: **5c6e9b4fcd9e1bf0adff89da8d93a5146e804953**.
The actual FINAL was pinned on this QA card before substantive review:
[pin receipt](review-round-3-evidence/pin-receipt.json). This report's own
commit/tree and official artifacts are in the post-commit delivery.

**Original R1/P1 remains incomplete.** The review2 Basic/cookie/quoted forms now
pass, but recognizable underscore-prefixed credential assignments pass unchanged
through publication, provider snapshots and stored reads. R2–R4 continue to pass.
This is one unresolved original finding, not a new requirement or owner decision.
Green ordinary suites do not override observed disclosure. No product repair or
merge was made.

## Finding

### R1 remains / P1 / D1,D2,D4,C1,S1,S2: prefixed labels escape normalization

In the reviewed `backend/app/services/resource_records.py:26`, `_CREDENTIAL_TEXT`
requires a word boundary immediately before a recognized credential label.
Underscore is a word character, so neither `API_KEY` within `CIVITAI_API_KEY` nor
`AUTHORIZATION` within `HTTP_AUTHORIZATION` matches. Whole-value redaction at :49
is skipped. The Basic fallback at :53 requires decoded `user:password`; it does
not repair missing recognition of an explicit authorization assignment. The final
existing `redact_secrets` call handles keys/query values, not these free-text values.

These synthetic inputs remain **byte-for-byte unchanged**, including their full
value, when supplied in nested metadata descriptions:

| Supplied text | Persisted/public result |
|---|---|
| `CIVITAI_API_KEY="QA3 ENV MULTI WORD VALUE"` | Same complete assignment |
| `HTTP_AUTHORIZATION=Basic UUEzX0VOVl9WQUxVRQ==` | Same complete assignment |

These are explicit credential assignments, not arbitrary unlabelled secrets. No
claim is made that the application loads either variable; the input is provider
or client free text with recognizable credential labels. The Basic token is
synthetic, as were the opaque Basic tokens in review2.

Final reproducer:
[independent_prefixed_credentials.py](review-round-3-evidence/independent_prefixed_credentials.py).
Actual output:
[independent-prefixed-final.log](review-round-3-evidence/independent-prefixed-final.log),
pytest exit1, **20 failed** on feature assertions, with no setup/import error:

- Registered inspect/select supplies a valid descriptor; edited typed metadata
  goes through registered install. Install returns200, retains measured SHA/same
  row and persists the entire assignment. Actual detail/list/local-ledger return
  it while retaining an ordinary hash.
- Fourteen stored-snapshot cases cover both assignments in license, diagnostic
  field, trigger, recommendation value/origin, opaque evidence and raw base label.
  Detail/list/local-ledger disclose the value. SQL writes, provider requests,
  publication/backfill and model-body reads are denied. Original metadata_json
  and notes are verified byte-exact **before** the final secrecy assertion, and
  the resource remains visible. This is disclosure through read-only projection.
- Direct shared typed publication commits/reloads the unsafe value with real ORM.
  Repeated normalization is idempotent but unsafe; safe neighboring trigger/hash
  data remains useful.
- Synthetic external-HTTP provider metadata carries each assignment through real
  Settings/file resolver/provider machinery and registered inspect/select.
  Actual acquire/background succeeds and stores the same unsafe value.

The initial observation is separately preserved in
[independent_complete_values.py](review-round-3-evidence/independent_complete_values.py):
four failed/24 passed. The24 positive cases cover the original four forms plus
JSON quoting, Digest, access-token and Unicode cookie variants through writers,
shared publication and old reads. They pass again under `independent-covered-forms`.
The original failing history is not relabelled as certification.

Expected: remove/redact the complete recognizable credential-bearing value, or
refuse before unsafe publication with a stable safe failure. Old reads must
exclude it without repair writes or hiding the resource. Observed: successful
publication/reads retain the complete value. No actual owner key was read or
disclosed and no live provider disclosure is asserted. Producer owns correction.

## Acceptance items

| Item | Level | Verdict | Independent evidence |
|---|---|---|---|
| D1 | P1 | FAIL | ORM mapping/typed metadata/measured versus declared facts pass; complete secrecy fails. |
| D2 | P1 | FAIL | Registered writers/provider/resolver/ORM/background, selected provenance, same-ID reuse and R3/R4 pass; unsafe metadata still publishes. |
| D3 | P1 | PASS in isolated fixtures | Full old-schema/value/backfill/notes/alias-history/file audit and exact pre-task schema authority pass. |
| D4 | P1 | FAIL | HTTP/OpenAPI/filter/paging/error/read-only guards pass; stored snapshots still disclose credentials. |
| D5 | P1 | FAIL as acceptance gate | Exact review, faults/restoration/full suites/packages reproduced; feature failures remain. |
| C1 | P1 | FAIL | Original URL and complete review2 probes pass; prefixed values remain unsafe. |
| C2 | P1 | PASS | Malformed version/nested/JSON/legacy canonical filter/detail agreement, totals/pages/bounded SQL; raw-JSON fault fails nine cases. |
| C3 | P1 | PASS | Registered omitted/same/augmenting/conflicting AIR preserves ID/hash/measured facts and refuses conflicts; clearing fault fails two cases. |
| C4 | P1 | PASS | Retained notes exact through success/refusal/exception, truthful errors and retry; overwrite/error faults fail12/eight cases. |
| C5 | P1 | FAIL as acceptance gate | Current complete checks/preservation succeed; C1 remains violated. |
| S1 | P1 | FAIL | Rejected review2 RED reproduces and14 probes pass now; independent provider/writer/ORM cases expose values. |
| S2 | P1 | FAIL | Delivered48 stored-read cases pass; independent old-storage projections expose prefixed values without writes. |
| S3 | P1 | PASS for tested sensitivity | Reviewed one-token production defect fails20 writer/36 stored-reader assertions, including cookies/quotes; original13 fault guards retained. |
| S4 | P1 | FAIL as combined acceptance | Current full/standing/migration checks pass, but original D1/D2/D4/C1 remain unmet. |
| S5 | P1 | PASS for reviewability | Exact source/manifest/official bytes/fingerprints, both restorations, attempts and independent evidence usable; not correctness certification. |

## Independent commands and evidence

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-191-qa`,
branch `aid-191-exact-review`. New evidence is exclusively in
[review-round-3-evidence/](review-round-3-evidence/).
[Replay guide](review-round-3-evidence/verification-commands.md) records setup and
reproduction. [verification.json](review-round-3-evidence/verification.json)
indexes34 command records with exact argv/cwd/allowlisted environment/roots/imports,
timing/exit and saved/raw log hashes. Expected RED calls preserve pytest exit1;
orchestration success is not feature success.

| Scope / label | Actual result |
|---|---|
| rejected-original-r1-r4, exact9abe3d1 | Four expected-feature failures; original helper unchanged |
| rejected-review2-probes, exact6fbcb246 |13 expected-feature failures / one passed |
| original-r1-r4-current / current-review2-probes | Four /14 passed on pinned candidate |
| qa3-restored-feature |222 passed after exact fault restoration |
| independent-covered-forms |24 passed, four adverse cases explicitly deselected; bounded positive run only |
| independent-complete-values / independent-prefixed-final | Four failed/24 passed initial;20 failed final |
| backend-full |**2200 passed /124 existing skips**,76 warnings,48.52s |
| mcp-full |**666 passed /four existing skips**,71.69s |
| export-qa3 / cross-layer-qa3 | Fresh93 Backend producers /73 separate MCP readers |
| registry-mcp-qa3 |412 standing MCP/PNG/stdio/smoke/content cases passed |
| fresh-wait-qa3 / retained-provider-guards-qa3 |12 /19 passed |
| schema-audit | Two passed; complete synthetic before/startup/backfill payload retained |
| source/restoration |3390 complete ordinary FINAL fingerprints;427 protected source/test/helper bodies exact |
| registry | All22 prior rows exact; no additions/deletions/supersession |

Fresh ignored Python3.11.15 environment references three existing dependency sites
read-only; no canonical installation. Guard activation preceded new tests and
actually denied private key/.env, non-scratch DB/model reads, repository writes
and remote DNS. All136 ordinary guard receipts have zero blocked events and
imports pinned to intended current/archived roots. The separate activation receipt
contains six intentional denials. Nested isolated children retain the established
repository offline guard. Long suites use `--timeout=60`, unique scratch roots,
no cache/bytecode and pinned child interpreters. Stat is allowed; feature checks
separately deny model-body access. No private input was opened to prove denials.

### Fault sensitivity

QA inspected and ran mutations sequentially without an overlapping suite or
fingerprint user. Files restore exact bytes in finally before222 feature GREEN
and full current suites. Every failure is an observable feature assertion, not
collection/import/fingerprint/SQL failure. [Fault records](review-round-3-evidence/qa3-faults.json)
and [audit](review-round-3-evidence/fault-audit.json):18 invocations,17 distinct
production mutations,158 intended assertion failures.

| Fault | Failures |
|---|---:|
| Wrong map / fabricated verification |1 /2|
| Split acquire / install publication |1 /1|
| Destructive backfill / unbounded list / writing list |1 /2 /1|
| Complete normalization / stored projection bypass |1 /1|
| Raw-JSON filter / clear omitted identity |9 /2|
| Overwrite retained notes / lose current errors |12 /8|
| Reviewed one-token defect: writer / stored reader |20 /36|
| Inspect descriptor / supplied descriptor / legacy license bypass |20 /20 /20|

Sensitivity to these faults does not establish safety against additional RED
inputs. No product/test repair, assertion relaxation, new skip or certification.

## Preservation and delivery integrity

Real boundaries: synthetic Settings/environment-selected file resolver, provider
operation/request machinery, selected version/file, strict schemas, SQLite/ORM,
shared publication/projection, registered HTTP/OpenAPI and actual background
targets with measured tiny files. Only external HTTP and deterministic scheduling
substitute domain execution. No settings/resolver/domain-operation injection is
used as proof of production loading.

Migration audits16 tables including sqlite_sequence, eight resource rows and five
populated alias/history tables, old columns/values/notes, duplicate/conflicting/
malformed/unsupported/offline cases and synthetic file bytes. Startup adds nullable
metadata_json only; explicit backfill changes that field only and is idempotent.
Exact pre-task ORM schema authority loads no application Settings. R4 writer
preservation is separately checked. Legacy inventories are source/caller evidence
for later migration, not proof of removability.

[preservation.json](review-round-3-evidence/preservation.json) verifies469 prior
evidence bodies, original mirrors, four exact authorized imports and original
task/repair bodies. Task SHA256 remains
`c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`;
repair1 remains `b3d649dcd8e60217b6581d1bdf8ca34db5f22ad0c71f5efd31c1449390b06977`.
Three application services and one added test differ from the fixed correction
base; existing product tests are unchanged. All31 MCP names/risks, frozen
recipe/AIR/Anima/alias behavior and22 contracts remain. All13 shared-main memory
bodies match preserved hashes; no staging/stashing/reset/copy of shared edits.

QA independently downloaded **all19 Coding uploads**: six current final artifacts,
eight official base chunks and five superseded report/package artifacts. All
sizes/SHA256 match. [coding-integrity.json](review-round-3-evidence/coding-integrity.json)
compares3390 fingerprints,337 indexed payloads/338 archive members/327 exact Git
bodies, official manifest and five raw commit/per-commit patch bodies. The
66,109,399-byte official base restores exact prerequisite. Separate downloaded
bundle and downloaded patch/history restorations reproduce FINAL/tree and both
`git fsck --full` exit0. The patch store uses only official base bytes, no local
candidate objects. Explicit prerequisite ref, `--update-shallow` and declared
b4e71d18 shallow boundary are required; not a pre-boundary history backup.
Superseded package bytes remain historical, not a current restoration claim.

One QA summary attempt used literal `/var` versus `/private/var` prefixes and
rejected eight correct archived imports. The corrected audit resolves paths,
retains alias records and verifies all imports; audit-attempt.json preserves this
checker failure. An initial report patch was rejected before any write because
it combined delete/add for the same path; the report was then written normally.
Absent guessed source/doc names were resolved through tracked inventory. None
of these administrative attempts is counted as a feature or sensitivity result.

QA report commit/tree, official artifacts, hashes/readback and usable restoration
prerequisites are published on this card after commit. No feature source is
pushed/merged. QA completes its own card with this FAIL; Producer handles findings
and acceptance. Any changed software needs a new exact-final-commit review.

## Limits and disposition

**Offline:** exact source, real synthetic ORM/HTTP/provider machinery, adverse/
fault/restored/full/standing tests, migration and official attachments.
**Running service:** no production probe/start/restart/deploy/backfill.
**Provider/generation:** no actual owner key read, live provider, real model
acquisition/registration or generation. **Retrieval:** synthetic installed bytes
and Paperclip attachments only; no live model/Gallery bytes. Frontend and native
Windows unrun. Existing124 Backend skips are platform-specific; four optional
MCP exports are separately exercised with fresh producers/readers. No cancellation/
job API is added; retained wait/interruption/PNG/stdio contracts pass, while live
cancellation/download accounting remain later work.

History stays kickoff1 CLEAR, delivery1 FAIL/four P1s, correction1, review2 FAIL/R1
incomplete, correction2, **this review3 FAIL/R1 incomplete**. R2–R4 resolution does
not rewrite prior rejection. p2-01 and First check histories remain attributed.
No complete Phase2 automation, three zero-fix sentences, fresh checkpoint+LoRA
qualification, phase exit or CTY aesthetic acceptance is claimed. No parent status/
owner question, routine approval gate, self-delegation or product repair.
