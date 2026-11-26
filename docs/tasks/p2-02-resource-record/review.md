# p2-02 independent delivery review

Verdict: FAIL
Review round: 7
Issue: [QA AID-199](/AID/issues/AID-199)
Coding: [AID-198](/AID/issues/AID-198)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-27

Reviewed ACTUAL NEW FINAL: **42775d8fdf488011198267077634ca951b8885b7**.
Reviewed tree: **2dd783dfef0bcc52c1f3a1b6af61178167908dce**.
Coding software/tests/replay freeze: **4a9fa13e63cf2449d9149a36b48c2afb8be6ce96**.
Fixed implementation base: **ae24638a8538a932d0f797de518e01808685eb00**.

I read the actual official [correction6 manifest](manifest-correction-6.md), matched
its complete bytes/SHA256 to FINAL, and pinned this full FINAL/tree on this card
before substantive review. [Pin receipt](review-round-7-evidence/pin-receipt.json).
The freeze ancestor and moving Coding directory were not the review target.
QA report commit/tree and official restoration receipts follow this report's
commit on the card, avoiding circular self-hashing.

**The supplied QA6 serialized assignment cases are corrected, and R5's checked
bounds remain resolved. Original R1/P1 is still incomplete for quoted assignments
preceded by a same-kind prose quote.** Complete synthetic values persist through
both registered writers and appear in public reads. This blocks acceptance
despite current full suites passing. R2-R4 continue to pass their guards. No
actual owner key was read or disclosed. QA made no product repair, assertion
relaxation, test deletion, new skip, registry addition, feature push or merge.

## Finding

### R1 / P1: preceding prose quotes hide complete explicit assignments

The disjoint quote cursor at `backend/app/services/resource_records.py:61-89`
pairs a preceding same-kind quote with the intended label's opening quote. It
then advances beyond that opening quote, so it never considers the complete
credential label and its actual delimiter together. The unquoted fallback at
lines90-92 cannot recover a delimiter separated by the closing quote and inner
whitespace. The wrapper at lines95-110 can reproduce the same pairing problem
in its decoded views. With no backslash it immediately returns the raw result.

Minimal ordinary metadata string (all values synthetic):

```text
ordinary "unfinished; " CIVITAI_API_KEY " = "QA7 complete synthetic value; retained suffix"; useful suffix
```

The explicit `" CIVITAI_API_KEY " = "..."` unit is unchanged from a safely redacted
plain control. The earlier prose quote changes recognition. The entire labelled
value remains visible, including its suffix. Single-quoted HTTP_AUTHORIZATION,
colon/tab/newline delimiters and applicable once-serialized contexts also fail.
This is recognizable labelled free text within the existing metadata boundary;
there is no required valid-document format, new configuration loader, recursive
decoding requirement or arbitrary unlabelled-secret discovery. The task/repairs
require relevant quote/representation/neighbor classes and complete-value
exclusion. Progress and a shared key recognizer do not prove that exclusion.

Independent exact-FINAL evidence, reproduced before and after fault restoration:

- [250 representation/context cases](review-round-7-evidence/independent_representations.py):
  **38 feature failures /212 passing cases**, initially and in confirmation.
  They cover four identifier classes, both quote kinds, whitespace/delimiters,
  raw/once-serialized/bare escaped text, preceding quoted prose and Unicode escape
  spellings. These are assertion failures, with no collection/import/SQL errors.
- [Actual nested boundaries](review-round-7-evidence/independent_quote_context_fields.py):
  **44 feature failures /40 passing controls**, initially and in confirmation.
  Direct publication/ORM commit/reload and registered edited-install fail complete
  exclusion. All12 current old-field/key classes run; nine value classes fail for
  each of four adverse contexts while key controls pass. Raw source labels,
  licenses, diagnostics, triggers, recommendations/origins and opaque evidence
  are covered. Passing plain controls retain their prior meaning.
- [Complete registered/old-read phase traces](review-round-7-evidence/independent_quote_context_boundary.py):
  **12 feature failures /six passing controls**, initially and in confirmation.
  All observations are collected before secrecy assertions. The complete value
  appears in successful inspect/select, install's committed metadata and new-row
  notes, acquisition admission and actual background completion, detail/list/
  local-ledger. Settings, environment-selected synthetic key-file resolver,
  strict descriptors, provider machinery, registered HTTP, domain logic and ORM
  are real. Only external HTTP and deterministic scheduling substitute behavior.
- Each old-read trace still returns the useful resource ID, safe hash and trigger,
  checks the canonical family-filter total, denies SQL writes/provider/publication/
  backfill/model-body access, and checks exact metadata_json/notes **in finally
  even on adverse failure**. Logs retain `STORAGE_EXACT=true` and full observations.
- [24 independent useful neighbors](review-round-7-evidence/independent_safe_representations.py)
  pass through real publication/read guards, retaining original literal/serialized
  representations. Existing safe and bounded ordinary descriptions also pass.

P1 remains appropriate: explicitly credential-labelled provider or stored metadata
is persisted and returned by successful public operations. This is the unresolved
original R1, not a new finding number or a new R5 bounds regression. Producer
owns findings, reassessment, corrections and acceptance; QA has not repaired it.

## D/C/S/T/U/V/W assessment

All levels remain P1. PASS states the checked meaning at this exact candidate;
combined gates fail where the adverse R1 observation contradicts their contract.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | FAIL | Identity/map/typed and declared-versus-measured facts pass; complete snapshot secrecy fails. |
| D2 | FAIL | Real Settings/provider/registered writers/background/ORM and same-ID guards pass; both writers persist adverse values. |
| D3 | PASS, isolated fixtures | Full old-schema/value/notes/alias/history/file/startup/backfill audit; no production migration. |
| D4 | FAIL | Bounded registered routes/OpenAPI/filters/counts/pages/read-only semantics pass; public reads expose complete adverse values. |
| D5 | FAIL as acceptance gate | Exact review/fault/restoration/full/standing/package evidence exists; secrecy remains violated. |
| C1 | FAIL | Prior nested locator/value cases pass; analogous quote-context values persist and appear publicly. |
| C2 | PASS | Canonical typed validity/filter/count/page agreement; raw-JSON fault fails nine assertions. |
| C3 | PASS | Known identity/AIR/ID/hash/measured facts retained on omission/same/augmentation; real conflicts refused; clearing fault fails two. |
| C4 | PASS | Exact retained notes and truthful current errors on success/refusal/exception; overwrite/error faults fail12/eight. |
| C5 | FAIL, combined gate | Current full/standing checks do not override the incomplete secrecy contract. |
| S1 | FAIL | Earlier Basic/cookie/quoted/Digest/access-token cases pass; new explicit values survive actual publication. |
| S2 | FAIL | Old storage stays exact and useful while complete adverse values leak through projection. |
| S3 | PASS | Reviewed partial-value mutation fails20 writer/36 reader assertions; exact restoration. |
| S4 | FAIL, combined gate | Current original secrecy obligation remains violated. |
| S5 | PASS, reviewability | Exact official manifest/bytes/fingerprints and two independent restorations verified. |
| T1 | FAIL, complete coverage | Immutable prefixed cases pass; explicit prefixed labels in adverse quote contexts evade recognition. |
| T2 | FAIL | Relevant key controls pass while equivalent value text leaks; old reads remain useful/read-only. |
| T3 | PASS | Word-boundary mutation fails40 writer/provider and195 reader assertions; previous meanings retained. |
| T4 | FAIL, combined gate | Full/current/standing/schema results cannot establish complete secrecy. |
| T5 | PASS, reviewability | Actual FINAL pinned before review; immutable history and official prerequisites verified. |
| U1 | FAIL, complete classes | Old78+3/706/130 cases pass; preceding quote contexts expose full values. |
| U2 | FAIL | Public old-row values leak; exact storage, safe neighbors and visible resources retained. |
| U3 | PASS | Quoted-parser regression fails70 writer/provider,318 reader,12 key/text assertions; exact restoration. |
| U4 | FAIL, combined gate | Bounds and actionable guidance pass; complete secrecy remains incomplete. |
| U5 | PASS, reviewability | Frozen Coding product/tests/helpers, exact FINAL and complete official restoration checked. |
| V1 | PASS, checked bounds | Current real92001-character provider/publication/ORM/detail/list/ledger and parity/neighborhood features meet unchanged3s marks; increasing-size progress retained. |
| V2 | FAIL, complete secrecy | All unchanged older probes pass; new quote contexts disprove complete labelled-value exclusion. R2-R4 pass. |
| V3 | PASS | Exact rejected scanner yields eight provider/publication and12 old-read timeout failures; exact restoration then1886 feature passes. |
| V4 | FAIL, combined gate | Current full/standing/schema/22 contracts pass, original secrecy remains incomplete. |
| V5 | PASS, reviewability | All ordinary inventories, official bytes and independent exact bundle/aggregate/per-commit/raw-commit restorations/fsck checked. |
| W1 | FAIL, complete classes | Exact old22/20 and three trace failures reproduce; supplied current42+3 pass; independent quote/serialization neighbors still leak through real writers. |
| W2 | FAIL | All12 fields/keys run; nine value classes leak in four adverse contexts. Exact finally storage, useful IDs/hashes and canonical read behavior remain. |
| W3 | PASS | Complete-view omission fails50 writer/provider and45 reader assertions; independent JSON-unit-only omission fails28/36. Plain controls pass; all prior fault meanings retained. |
| W4 | FAIL, combined gate | Fresh full/standing/immutable/schema/bounds checks pass; complete original R1 still fails. |
| W5 | PASS, reviewability | Actual FINAL/manifest, complete attempts/fingerprints/official history and two independent restorations verified. |

## Commands and results

Persistent worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-199-qa`,
branch `aid-199-exact-review`. All new evidence is in
[review-round-7-evidence/](review-round-7-evidence/).
[Replay guide](review-round-7-evidence/verification-commands.md) and
[verification index](review-round-7-evidence/verification.json) preserve actual
argv/cwd/environments/roots/imports, durations, exits and raw/saved log hashes.
Expected exit1 remains a failing feature observation, not product GREEN.

| Check | Actual result |
|---|---|
| Exact rejected QA6 archived source, complete immutable assignments/phase traces | 22 failed/20 controls; three failed, as previously reported |
| Current immutable original /QA2 /QA3 prefix /QA3 initial | 4 /14 /20 /28 passed |
| Current immutable QA4 labels /real key controls /QA5 lexical | 78 /3 /130 passed |
| Current immutable QA5 trailing /registered | 4 /6 passed, unchanged3s marks |
| Current independent QA6 terminal /serialized /complete traces | 360 /42 /3 passed |
| New250-case screen, initial and confirmation | Each38 failed/212 passed |
| New nested boundaries, initial and confirmation | Each44 failed/40 passed |
| New complete phase traces, initial and confirmation | Each12 failed/six passed |
| New independent safe originals | 24 passed |
| Restored affected suite | **1886 passed**,43.40s, exact restoration |
| Current full Backend | **3864 passed /124 existing skips**,76 warnings,89.67s |
| Current full MCP | **666 passed /four existing skips**,72.21s |
| Fresh producers /separate readers | **93 /73 passed**,19 fresh JSON exports retained |
| Standing MCP/PNG/stdio/content/smoke | **412 passed**,71.02s |
| Fresh wait /retained provider guards | **12 /19 passed** |
| Whole schema audit /prior-schema authority | **Two passed**, complete synthetic before/startup/backfill payload retained |
| Registry rebuild | All22 prior rows exact; no additions/deletions/supersessions |
| Frozen source /complete FINAL inventory | 5142 ordinary frozen fingerprints;478 protected application/test/replay/topic bodies exact;5484 ordinary FINAL fingerprints verified |

Before new tests, the guard actually denied private-file/.env/non-scratch DB/model/
write/DNS actions without opening private inputs; reactivation repeats all six
on resume. **163 ordinary guard receipts across61 runner records** have zero
blocked events and pinned intended current/archived imports. Python and child
interpreters are3.11.15. The ignored venv references three existing dependency
sites read-only; no canonical install/repair. Long suites use --timeout=60;
ordinary description features retain3s. Exact raw gzip logs accompany readable
logs whose only normalization is trailing whitespace removal.

The core QA replay helpers were committed at **549f75b82c7c9a994ea2cc07bd70db8870ea76ee**
before current full qualification. Later additions are reporting/concurrency
audits and the separately recorded safe/confirmation checks. Product/tests and
Coding replay helpers remain the exact delivered source throughout qualification.

### Bounds and mutation sensitivity

[Source analysis](review-round-7-evidence/source-progress-analysis.md) confirms
monotonic quote/escape cursors, explicit terminal EOF, disjoint JSON string-unit
decoding and two nonrecursive views of the original input. At most three scanner
calls occur. This preserves the demonstrated R5 progress mechanism without proving
complete secrecy. No timeout increase, truncation, hidden resource or size/format
exclusion was introduced.

[Measurements](review-round-7-evidence/progress-measurements.json) retain three
samples at six increasing sizes for each quote and literal/serialized/bare escaped
representation. For92001 raw characters, literal medians are0.01574/0.01295s
(double/single quote); serialized medians0.02434/0.02768s. Doubling raw size gives
literal0.03150/0.02572s and serialized0.04912/0.05564s. Full useful text is asserted.
These are local observations, not a universal performance guarantee.

[Fault audit](review-round-7-evidence/fault-audit.json): **22 distinct production
mutations /29 invocations /952 assertion failures plus20 actual3s timeout
failures**. All20 prior distinct/25 invocation meanings remain; Coding's current
serialization-view omission is independently executed, and QA adds a narrower
JSON-unit-only omission. No other suite/source fingerprint reader runs during
mutation. Exact bytes restore in finally before current qualification. Counts
exclude setup/import/SQL/fingerprint/recorder errors and the interrupted partial
invocation. Current adverse secrecy failures are separate from mutation counts.

| Mutation | Observable failures |
|---|---:|
| Wrong map /fabricated verification | 1 /2 assertions |
| Split acquire /install publication | 1 /1 |
| Destructive backfill /unbounded list /writing list | 1 /2 /1 |
| Complete normalization /stored projection bypass | 1 /1 |
| Raw-JSON filter /clear omitted identity | 9 /2 |
| Overwrite retained notes /lose current error | 12 /8 |
| One-token redaction writer /reader | 20 /36 |
| Inspect descriptor /supplied descriptor /legacy-license bypass | 20 /20 /20 |
| Word-boundary writer-provider /reader | 40 /195 |
| Quoted extraction writer-provider /reader /key-text | 70 /318 /12 |
| Exact rejected terminal scanner provider-publication /old reads | Eight /12 timeout failures |
| Omit all serialized views writer-provider /old reads | 50 /45 assertions |
| QA omit only JSON-unit view writer-provider /old reads | 28 /36 |

## Preservation, delivery and failed attempts

D3 audits all16 tables including sqlite_sequence, eight resource rows and five
populated alias/history tables. Startup adds nullable metadata_json only;
backfill changes only that field, remains idempotent and preserves every old
column/value/note/ID/count/alias/history/synthetic body. Malformed/conflicting/
duplicate/unsupported/missing/offline cases retain diagnostics. Retry notes and
truthful recovery are checked separately. Source/First-check inventories prove
usage/dependencies, not permission for removal. No new cancellation/accounting
API or live retrieval is inferred from retained duplicate/failure/wait/fixture
artifact checks.

[Preservation](review-round-7-evidence/preservation.json) verifies the four exact
authorized imports from4d40e83e, original task/repairs1-5 hashes,2499 prior task
bodies plus the previous current report preserved exactly as review-round-6,
and243 existing test/MCP/registry bodies. All5483 candidate bodies other than the
intentionally replaced current report remain exact. Task remains
`c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`;
repair6 remains`7e9bc6ed521ef189a25e65067eeb0a38a9ed1f4c5481d71a88cc48aebee1639d`. All31 MCP names/risks, frozen recipe/AIR/Anima/alias
behavior and22 registry contracts remain unchanged. A FAIL adds no certification.

Shared main's initial13 memory body hashes and modified statuses are pinned
before review. During the resumed run, one body (`model-family-loader-compatibility.md`)
changed externally and `explicit-lora-list-semantics.md` became a fourteenth
modified path. The harness names concurrent AID-200; QA does not infer a writer
identity from content. Twelve initial bodies remain exact and all13 initial
modified statuses persist. [Concurrency receipt](review-round-7-evidence/concurrent-memory-change.json)
and [final observation](review-round-7-evidence/shared-main-preservation.json)
retain both observations without replacing the initial pin. QA did not stage,
stash, reset, restore or edit any shared-main memory body. Unchanged13-body
preservation is therefore not claimed for the final external workspace state.

[Official Coding integrity](review-round-7-evidence/coding-integrity.json)
independently reads all15 uploads, checks every official size/SHA256 and exact
manifest,5484 ordinary fingerprints,403 payloads/404 members/395 exact Git bodies,
and all three binary/full-index patch/raw-commit pairs. Nine official base parts
combine to**69920931 bytes**, SHA256
`450bc7d43e4423f7206366f837ca2b8781bbb84f386b2363baee17591c12a2be`.
Two new bare stores use only these official bytes, writing shallow boundary
b4e71d18ba4600ad7e053274b90b45ffdfbce87b before fetch with --update-shallow and
explicit refs/heads/aid-197-exact-review. One restores the official bundle; the
other independently applies gzip aggregate and per-commit patches/raw commits,
without local/candidate objects or alternates. Every intermediate tree/commit,
exact FINAL/tree and both fsck exit0 results match. This is usable declared-shallow
restoration, not pre-boundary backup. Official QA report/evidence/index/bundle/
patch/restoration receipts follow this report's commit on the card.

[All attempts](review-round-7-evidence/attempts.json) retain the initial generic
screen expected0 versus actual feature exit1, a tail of a not-yet-created log,
and a new-helper trailing-whitespace check failure corrected before helper freeze.
The subsequent stat command had masked that whitespace subcommand's wrapper exit;
the actual failed check is recorded separately. No feature sensitivity is
attributed to those audit/setup mistakes. The frozen preservation helper fails
on the real concurrent memory body change; a supplemental audit records it, then
its first status check fails on the additional modified memory path. The final
supplement records all initial statuses and additions, rather than resetting
shared state or falsely declaring13 unchanged bodies.

The previous heartbeat was interrupted externally during an old-read terminal
fault. No matching QA process remained on resume. The exact partial mutant/log
were preserved, the product file was restored byte-for-byte from pinned FINAL,
and actual-denial guards were reactivated in fresh Paperclip scratch. Only the
three unfinished invocations resumed. The incomplete log counts as no completed
feature result. [Recovery receipt](review-round-7-evidence/interruption-recovery.json).
All completed prior results and Coding failed attempts remain immutable.

## Limits and disposition

**Offline:** exact-source synthetic Settings/resolver/provider/strict-schema/
registered HTTP/background/ORM, complete historical/adverse/fault/restored/full/
standing/schema checks and official artifacts. **Running service:** no production
probe/start/restart/deployment/backfill. **Provider/generation:** no actual owner-key
read, live provider request, real acquisition/registration or generation.
**Retrieval:** synthetic installed bytes and Paperclip artifacts only; no live
model/Gallery bytes. Frontend/native Windows unrun;124 Backend platform skips and
four optional MCP-export skips remain unchanged, with applicable fresh producers/
readers separately exercised.

History: kickoff1 CLEAR, six earlier delivery FAILs, **this review7 FAIL**. The
supplied serialized case is corrected, R5 remains resolved for checked bounds,
and original R1 remains incomplete for preceding-quote contexts. This is the
seventh rejected delivery with five distinct historical P1 findings, not a new
kickoff ambiguity or routine owner gate. QA completes only this card with its
actual verdict. Producer owns reassessment/corrections/acceptance; changed code
requires another exact FINAL review. No parent/owner mutation, new registry
certification, feature merge/push, Phase2 automation/three zero-fix sentences/
fresh checkpoint+LoRA/CTY demo/phase exit or aesthetic acceptance is claimed.
