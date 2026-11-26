# p2-02 independent delivery review

Verdict: FAIL
Review round: 5
Issue: [QA AID-195](/AID/issues/AID-195)
Coding: [AID-194](/AID/issues/AID-194)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed ACTUAL NEW FINAL: **690d5ab04a3d864e9d36decbb4748f05045845a5**.
Reviewed tree: **160ca4a667a32a7e1f05d4b709187d866d40e4b0**.
Software/tests/replay freeze: **3caeebd68461422b71086eba7715b375f57205ed**.
Fixed correction base: **5d6542607cd2384bb6b86f2e2126512836bba46c**.

I read Coding194's actual official [correction4 manifest](manifest-correction-4.md),
verified its bytes against FINAL, and pinned this full FINAL/tree on this card
before substantive review: [pin receipt](review-round-5-evidence/pin-receipt.json).
This report's commit/tree and official artifacts are recorded in its post-commit
receipt. The review target is FINAL, not the freeze ancestor or a moving branch.

The demonstrated original R1 quoted-label disclosures now pass, as do the earlier
R1 probes and R2-R4 regressions. No current credential disclosure was demonstrated
by this review. **New R5/P1 blocks acceptance:** the added quoted-label scanner
has quadratic behavior on ordinary descriptions ending in a single backslash.
Actual registered provider/read paths exceed the existing three-second feature
bound. Green full suites do not override that adverse result. QA made no product
repair, assertion relaxation, test deletion, new skip, registry addition or merge.

## Finding

### R5 / P1 / D2,D4,U4: terminal backslash defeats bounded quoted-tail scanning

`backend/app/services/resource_records.py:33-36` adds two `_QUOTED_LABELS`
patterns. Their repeated content branch consumes a non-quote/non-backslash
character or a backslash followed by another character. A final solitary
backslash fits neither branch. Consequently the unmatched-tail `\Z` alternative
cannot be reached. At `:67`, `finditer` retries the failed long suffix at each
later quote, including quotes preceded by backslashes. This defeats the stated
one-time unmatched-tail consumption. Both quote kinds exhibit the defect.

Reproducer, with entirely ordinary synthetic metadata:

```python
text = ('\\' + quote + 'ordinary description ') * 4000 + '\\'
# quote is either a single or double quote; len(text) == 92001
```

This is a valid JSON string value after normal serialization. It has no credential
label or secret. The useful value should remain readable within the established
bounded-description contract. A safe input ending in `tail` is the positive
neighbor; only the final suffix changes.

Independent evidence:

- [Trailing-escape feature checks](review-round-5-evidence/independent_trailing_escape.py)
  run the existing real provider-snapshot/shared-publication/ORM/detail feature
  helper with the new input. Initial and final runs each give **two timeout
  failures / two passing controls**, exit 1. Failures occur in actual
  `_QUOTED_LABELS.finditer`, before publication; they are feature timeouts rather
  than collection/import failures. [Initial log](review-round-5-evidence/independent-trailing-escape.log),
  [final log](review-round-5-evidence/independent-trailing-escape-final.log).
- [Registered latency checks](review-round-5-evidence/independent_read_latency.py)
  place the value directly into a real ORM old snapshot, then call actual HTTP
  detail for both quotes, list and local-ledger. They also call registered
  provider inspect with real Settings/file resolver/provider machinery and
  synthetic external HTTP. **Five feature timeout failures / one passing scaling
  observation**, exit 1, 64.71 seconds total. Each failed test has the existing
  three-second bound. The provider and old-read failures reach production parsing;
  no domain parser is stubbed. [Log](review-round-5-evidence/independent-registered-latency.log).
- The old-read checks deny SQL writes, provider operations, publication/backfill
  and model-body access, retain the visible resource's useful metadata assertions,
  and check byte-exact original notes/metadata in `finally`. The input does not
  depend on a write-on-read or a private database.
- Actual `safe_text` timings at 5,751 / 11,501 / 23,001 / 46,001 characters are
  **0.022 / 0.088 / 0.339 / 1.398 seconds** for double quotes and
  **0.023 / 0.092 / 0.357 / 1.383 seconds** for single quotes. Doubling input
  produces approximately four times the work. The same exact-input source checks
  on rejected FINAL **bff2fb127d4ab5de69fe2124e9efc54cad0fd59a** give four
  feature passes in 0.88 seconds and six registered/scaling passes in 0.74 seconds;
  its 46,001-character scans take about 0.0026 seconds. These comparisons isolate
  the newly added scanner. They do not certify the older source's secrecy.
  [Previous feature log](review-round-5-evidence/previous-source-trailing-escape.log),
  [previous registered log](review-round-5-evidence/previous-source-registered-latency.log).

P1 is retained because bounded ordinary-description scanning is an explicit U4/P1
requirement, and an untrusted provider or persisted description can stall real
provider and resource-read paths with a 92 KB value. The measured scaling also
shows that SQL pagination cannot bound parsing cost per returned record. This is
a new regression in correction4, distinct from claiming that the old quoted-label
secrecy demonstrations still leak. Producer owns the correction and acceptance;
QA has not altered the production parser.

## Acceptance items

All assigned levels remain P1. PASS entries describe the checked feature meaning
at this exact source; combined acceptance gates remain FAIL because of R5.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | PASS for checked semantics | Typed ORM, exact four-label map, unknown/malformed metadata, selected provenance and measured-versus-declared evidence; snapshot secrecy probes now pass. |
| D2 | FAIL | Registered writers, same-row identity, resolver/provider/background and retries pass ordinary guards; R5 stalls actual provider inspect on valid ordinary metadata. |
| D3 | PASS in isolated fixtures | Complete old-schema/value/notes/alias-history/file/startup/backfill audit plus previous-schema authority; no production migration. |
| D4 | FAIL | HTTP/OpenAPI/validation/filter/pagination/read-only semantics pass; R5 stalls detail/list/local-ledger normalization. |
| D5 | FAIL as acceptance gate | Exact review, meaningful faults/restoration/full/standing/packages reproduced; adverse feature failures remain. |
| C1 | PASS for tested secrecy | Original four/review2 fourteen/review3 twenty plus twenty-eight/review4 seventy-eight plus three key controls; new quoted and independent lexical cases pass. |
| C2 | PASS | Canonical validation/filter/count/page agreement; raw-JSON filter mutation fails nine feature assertions. |
| C3 | PASS | Omitted/same/augmenting/conflicting AIR keeps same ID/hash/measured facts; clearing mutation fails two assertions. |
| C4 | PASS | Exact old notes across success/refusal/exception with truthful same-ID errors; overwrite/error faults fail twelve/eight assertions. |
| C5 | FAIL as acceptance gate | Current full/standing/preservation checks pass; R5 blocks the corrected whole-task contract. |
| S1 | PASS for tested complete values | Basic/proxy/cookie/quoted/Digest/access-token and current label classes pass real provider/writer/ORM guards. |
| S2 | PASS for tested secrecy/read semantics | All nested unsafe old snapshot values are safely projected without repair writes or hiding resources; R5 bounds are assessed separately. |
| S3 | PASS for sensitivity | Actual one-token production defect fails twenty writer and thirty-six stored-reader assertions. |
| S4 | FAIL as combined gate | Full/standing/schema checks pass, but bounded actual provider/read operation is violated. |
| S5 | PASS for reviewability | Official bytes, complete fingerprints, exact source and two independent restorations verified. |
| T1 | PASS for tested label classes | Current immutable prefixed probes and full new quoted guards pass registered/provider/shared/ORM boundaries. |
| T2 | PASS for tested secrecy/read semantics | Key/text policy, nested fields/keys, old-storage identity and useful neighbors pass; R5 remains a separate bounds defect. |
| T3 | PASS for sensitivity | Reviewed word-boundary mutation fails forty writer/provider and 195 old-read assertions; all prior fault meanings retained. |
| T4 | FAIL as combined gate | Current contracts and preservation pass; the new bounded-scanning regression blocks the combined requirement. |
| T5 | PASS for reviewability | Actual FINAL pinned before review; immutable histories and complete official restoration prerequisites usable. |
| U1 | PASS for tested quoted secrecy | Exact previous 33 RED/45 controls and three key passes reproduced; current immutable 78+3 and new 706 guards pass; independent 130 lexical/boundary cases pass. |
| U2 | PASS for tested quoted secrecy/read semantics | All nested fields/keys, actual detail/list/ledger, canonical counts/pages, immutable old storage and useful neighbors pass; ordinary-description bounds fail under U4. |
| U3 | PASS for sensitivity | Reviewed quoted-extractor mutation fails 86 writer/provider, 411 old-read and twelve key/text assertions; exact restoration. |
| U4 | FAIL | R5: valid ordinary descriptions with a terminal backslash cause quadratic scanning and registered provider/read timeouts. |
| U5 | PASS for reviewability | Exact frozen software and FINAL/evidence/official bytes, full inventories and independent bundle/patch-history restoration verified. |

## Independent verification

Persistent isolated worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-195-qa`,
branch `aid-195-exact-review`. New evidence is exclusively in
[review-round-5-evidence/](review-round-5-evidence/). The
[replay guide](review-round-5-evidence/verification-commands.md) and
[verification index](review-round-5-evidence/verification.json) record exact
argv/cwd/environment, roots/imports, timing, exits and raw/saved log hashes.
Expected exit 1 remains an actual failed feature observation, not product PASS.

| Scope | Actual result |
|---|---|
| Rejected exact bff2fb12, immutable QA4 helpers | 33 feature failures /45 controls; three real key controls pass |
| Current unchanged old QA probes | 4 /14 /20 /28 /78 /3 passed; complete helpers, no deselection |
| Independent quoted lexical/boundary cases | 130 passed, including Unicode/escaped labels, literal backslashes, nested opposite quotes, both delimiters and useful safe neighbors |
| Trailing-escape adverse, initial and final | Each two timeout failures /two controls passed |
| Registered latency adverse | Five timeout failures /one scaling observation passed |
| Previous-source latency controls | Four feature and six registered/scaling cases pass; performance comparison only |
| qa5-restored-feature | **1,424 passed** after exact restoration of all required faults |
| qa5-backend-full | **3,402 passed /124 existing skips**, 76 warnings, 77.06 seconds |
| qa5-mcp-full | **666 passed /four existing skips**, 72.97 seconds |
| Fresh Backend producers /separate MCP readers | **93 /73 passed**, 19 fresh JSON exports retained |
| Standing MCP/PNG/stdio/content/smoke | **412 passed** |
| Fresh wait /retained provider guards | **12 /19 passed** |
| Full old-schema audit /baseline authority | **Two passed**; full before/startup/backfill schema/value payload retained |
| Registry | All **22** previous rows exact; no additions/deletions/supersession |
| Source | **4,399** complete ordinary FINAL fingerprints; 449 protected source/test/helpers exact |

The ignored Python3.11.15 venv references only three existing dependency sites
read-only; no canonical installation. Before new tests the guard actually denied
six private-file/.env/non-scratch DB/model/write/DNS actions without opening private
inputs. All **148** ordinary guard receipts across **46** runner records have zero
blocked events and imports pinned to intended resolved current/archived roots.
Nested isolated children retain the established repository guard. Each command
has unique Paperclip-owned scratch, no cache/bytecode and pinned Backend/MCP child
interpreters. All long suites use `--timeout=60`; description features use the
existing stricter three-second bound. Raw logs are retained byte-exact in
`.raw.log.gz`; readable logs trim trailing whitespace only. No canonical model,
private file, production database or runtime source was opened by the tests.

### Fault sensitivity and exact restoration

QA inspected and executed the production mutations sequentially with no overlapping
suite or source-fingerprint reader. Files restore exact bytes in `finally` before
1,424 feature GREEN and fresh full/standing qualification. The
[fault audit](review-round-5-evidence/fault-audit.json) records **19 distinct
production mutations /23 invocations /902 feature assertion failures**. All
previous 18 distinct faults/20 invocations retain their feature meaning. Counted
failures are observable assertions, never setup/import/SQL/fingerprint failures.

| Mutation | Feature assertion failures |
|---|---:|
| Wrong map /fabricated verification | 1 /2 |
| Split acquire /install writer | 1 /1 |
| Destructive backfill /unbounded list /writing list | 1 /2 /1 |
| Complete normalization /stored projection bypass | 1 /1 |
| Raw-JSON filter /clear omitted identity | 9 /2 |
| Overwrite retained notes /lose current error | 12 /8 |
| One-token redaction, writer /old reader | 20 /36 |
| Inspect descriptor /supplied descriptor /legacy-license bypass | 20 /20 /20 |
| Reviewed word-boundary recognition, writer-provider /old reader | 40 /195 |
| Reviewed quoted extractor, writer-provider /old reader /key-text | 86 /411 /12 |

The separate seven current latency failures are not counted among these 902
mutation assertions. Exact restoration does not remove the actual FINAL defect.
No full-suite result is presented as overriding it.

## Preservation and delivery integrity

The real fixtures use Settings/environment-selected synthetic key file resolver,
provider request machinery, selected non-first version/file, strict schemas,
shared typed publication/projection, real SQLite/ORM, registered HTTP/OpenAPI and
actual background targets with measured tiny synthetic files. Only external HTTP
and scheduling substitute production behavior. Retained duplicate/same-ID retry,
truthful errors/recovery, wait/interruption, PNG bytes and stdio contracts pass.
No new cancellation or persistent download-job API is inferred.

D3 audits all 16 tables including sqlite_sequence, eight resource rows and five
populated alias/history tables. Startup adds nullable metadata_json only; explicit
backfill changes only that field and is idempotent. Every preexisting column/value,
notes, ID/count, alias/history row and synthetic file body remains exact. Malformed,
conflicting, duplicate, unsupported and missing/offline cases retain diagnostics.
The pre-task schema authority does not load Settings. Retry-note preservation is
checked separately from migration. Legacy/alias inventories remain evidence of
callers, not permission or proof to remove them.

[Preservation](review-round-5-evidence/preservation.json) verifies four exact
authorized imports from fixed860f99aa, task/repairs1-4 hashes, 241 existing
Backend-test/MCP/registry bodies, 1,490 historical task bodies plus the previous
current report preserved verbatim as review-round-4.md, and all 4,398 candidate
bodies other than the intentionally replaced current review. The original task
hash remains c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda;
repair4 remains6306d155719910649cf4fc54392ece138fed4f6821a399b314458579528b0155.
No original task/repair/probe/raw log/mirror is rewritten. One application service,
one new test and the topic differ from the correction base. The 31 MCP names/risks,
frozen recipe/AIR/Anima/alias behavior and all22 contracts remain exact. All13
shared-main memory bodies retain their hashes; no staging/stashing/reset/copying
of those edits, private inputs or runtime data occurred.

QA independently downloaded all **15 Coding uploads** and checked every indexed
size/SHA256 and manifest equality. [Coding integrity](review-round-5-evidence/coding-integrity.json)
verifies 4,399 ordinary fingerprints, 329 indexed payloads/330 archive members/
321 exact Git bodies and all three raw commit/per-commit patch pairs. Nine official
base parts combine to **68,272,163 bytes**, SHA256
c6f82ae8886ec77ca662867bfdc73516bd2caf122c87e2da43b115cf4e7d1e94.
Two fresh stores seeded only from those official bytes reproduce exact FINAL/tree
and `git fsck --full` exit0. The patch store imports no candidate/local objects.
Both write declared shallow boundary b4e71d18ba4600ad7e053274b90b45ffdfbce87b before
fetching with `--update-shallow` and explicit prerequisite ref
`refs/heads/aid-193-exact-review`. The patch store independently applies the gzip
aggregate patch and every binary/full-index history patch, reconstructing exact
intermediate trees and raw commit identities. This is usable declared-shallow
restoration, not a pre-boundary history backup.

All this QA run's failed feature observations are retained, including both latency
runs and historical expected failures. The immutable QA4 historical helpers missing
from the older source are copied byte-exact into its scratch archive at their
original relative paths; no historical product body changes. No orchestration or
setup failure is used as sensitivity. The current registry builder runs against
scratch copies of the actual review files and compares all22 rows without changing
the canonical registry after FAIL. Official QA report/bundle/evidence/index and
integrity uploads, byte readback and both report restorations follow the report
commit and are recorded on this card.

## Limits and disposition

**Offline:** exact source, guarded real synthetic provider/resolver/HTTP/background/
ORM, historical/adverse/fault/restored/full/standing/schema checks and official
attachments. **Running service:** no production probe/start/restart/deploy/backfill.
**Provider/generation:** no actual owner-key read, live provider request, real model
acquisition/registration or generation. **Retrieval:** synthetic installed bytes
and Paperclip attachments only; no live model/Gallery bytes. Frontend and native
Windows are unrun. The124 Backend skips remain Windows-only; the four optional
MCP exports are independently covered by fresh current producers/readers.

History remains kickoff1 CLEAR and four prior rejected deliveries, followed by
**this review5 FAIL**. The earlier R1 demonstrations now pass; new R5/P1 prevents
accepting the quoted-parser correction. This is the fifth rejected delivery, not
a new kickoff ambiguity or routine owner gate. Producer owns findings, further
reassessment/reporting and acceptance. QA completes only this card with its actual
verdict. Changed software needs a new exact FINAL review; no feature merge/push or
parent/owner mutation occurs here. No new registry item is certified. No Phase2
full automation, three zero-fix sentences, fresh checkpoint-plus-LoRA qualification,
CTY demo, phase exit or aesthetic acceptance is claimed.
