# p2-02 independent delivery review

Verdict: FAIL
Review round: 6
Issue: [QA AID-197](/AID/issues/AID-197)
Coding: [AID-196](/AID/issues/AID-196)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-26

Reviewed ACTUAL NEW FINAL: **afe9d694704ca7cada86222baa39aacd59e1af00**.
Reviewed tree: **7f563c8cc246cebc9c6bad6a25734d06a277eb6a**.
Software/tests/replay freeze: **02e21afc3735c0e97fecc088c029f73f7d91d6a5**.
Fixed correction base: **79e709cec49abbbad2ff3a9e944b9278440f8908**.

I read the actual official [correction5 manifest](manifest-correction-5.md),
matched its bytes to FINAL, and pinned this full FINAL/tree on this QA card before
substantive review: [pin receipt](review-round-6-evidence/pin-receipt.json).
The freeze ancestor and moving Coding directory were not the review target.
This report's commit/tree and official upload/restoration receipts are recorded
on this card after commit to avoid circular self-hashing.

**R5's terminal-escape bounds defect is resolved at this candidate.** The exact
old failures reproduce; current provider/publication/ORM/detail/list/ledger
features meet the unchanged three-second bounds with complete useful values.
All previously demonstrated R1 forms and R2-R4 regressions pass. However,
**original R1/P1 remains incomplete for recognizable quoted assignments carried
as JSON-serialized metadata text**. Full synthetic credential values survive
real publication and public reads. This adverse observation blocks acceptance
despite green full suites. QA made no product repair, assertion relaxation,
test deletion, new skip, registry addition, merge or feature push.

## Findings

### R1 / P1 / D1,D2,D4,C1,S1,S2,U1,U2: serialized quoted delimiters evade recognition

The quoted cursor at `backend/app/services/resource_records.py:65-92` treats
escaped quotes as content and applies `_LABEL_ESCAPE` decoding only after it has
found an unescaped closing quote followed by a delimiter. A serialized assignment
can therefore lose its label/delimiter relationship before recognition. The
unquoted fallback at lines 95-96 does not recover that relationship across the
backslashes before closing quotes. Complete-string exclusion never activates.

Minimal synthetic input, as an ordinary metadata string:

```python
plain = '" CIVITAI_API_KEY " = "QA6 complete serialized value; suffix"'
serialized = json.dumps(plain)
# Equivalent serialized content without its outer string quotes:
escaped = serialized[1:-1]
```

`plain` is safely redacted. Both `serialized` and `escaped` retain the entire
label and synthetic value. This is one JSON serialization of explicit labelled
text, not arbitrary unlabelled-secret discovery, a real configuration variable
load, or an actual owner-key disclosure. The task/repairs require recognizable
complete values, relevant quoted/serialized classes, shared key/text meaning and
safe nested provider/publication/old-read boundaries. The same strings used as
metadata dictionary keys are excluded, while their values leak: the key policy
alone does not establish text safety. No new format or size exclusion is assumed.

Independent evidence at exact FINAL:

- [Serialized-assignment cases](review-round-6-evidence/independent_serialized_assignments.py)
  exercise the plain control and both encoded forms through direct publication/
  commit/reload, registered provider inspection, and all 12 existing nested old
  fields/keys. Initial and final runs each give **22 feature assertion failures /
  20 passing controls**, exit 1. Encoded text remains in triggers, license values,
  diagnostics, recommendation values/origins, raw labels and opaque evidence.
  The three key classes pass; raw assignment controls pass. These are feature
  assertions, not collection/import/SQL failures.
  [Initial log](review-round-6-evidence/qa6-serialized-assignment-adverse.log),
  [confirmation](review-round-6-evidence/qa6-serialized-assignment-final.log).
- [Complete boundary trace](review-round-6-evidence/independent_serialized_boundary.py)
  collects all phases before asserting secrecy. Initial and confirmation runs
  each give **three feature failures**, exit 1. The unchanged complete synthetic
  value appears in successful inspect and select descriptors, successful install's
  committed `metadata_json` and new-row notes, registered acquire admission and
  actual background success, and detail/list/local-ledger projections. Settings,
  environment-selected synthetic key file resolver, strict schemas, provider
  machinery, ORM and actual background targets are real; only external HTTP and
  deterministic scheduling substitute production behavior.
  [Initial trace](review-round-6-evidence/qa6-serialized-boundary-final.log),
  [confirmation](review-round-6-evidence/qa6-serialized-boundary-confirmation.log).
- The independent old-row trace calls all three reads plus the canonical family
  filter. It denies SQL writes, provider/publication/backfill and model-body
  access; confirms visible resource IDs, safe hashes/triggers and filtered total;
  and checks exact original `metadata_json` and notes in **finally even when the
  secrecy assertion fails**. Six observed statements are read-only. Its log
  records `STORAGE_EXACT=true` and all three full-value observations.

P1 is retained: untrusted provider or already-stored serialized metadata exposes
an explicitly labelled complete credential value through successful public
responses and persists it through both real writer paths. The correction's
latency success does not satisfy the original complete-value secrecy contract.
Producer owns the finding, any correction and acceptance; QA has not repaired it.

## Terminal-escape correction

The [source analysis](review-round-6-evidence/source-progress-analysis.md) confirms
that each quote pass advances monotonically. Escapes consume their next character
or explicit EOF; unmatched tails end the pass. Gap scans, closed label slices and
whitespace lookahead are disjoint per quote kind. No already-scanned growing suffix
is retried. Both quote kinds and opposite-quote recognition remain. This addresses
the demonstrated R5 mechanism, not exhaustive secrecy for every lexical form.

Both immutable QA5 helpers first ran against exact rejected `690d5ab0` archived
in Paperclip scratch. Only the two immutable helper bodies were added at their
original relative paths: **two trailing timeouts/two controls**, and **five
registered timeouts/one scaling observation**, exit 1. On FINAL the complete
unchanged helpers give **four and six passes**, respectively. All 74 new terminal
product cases and 706 existing quoted cases pass. My additional
[360 parity/neighborhood cases](review-round-6-evidence/independent_terminal_classes.py)
pass both initially and after exact restoration. They cover literal/serialized
ordinary text, both quotes, terminal parity, useful suffixes and standalone or
opposite-quoted synthetic assignments through real writer/provider/old-read guards.
Those passing assignments do not cover the separately failing serialized-delimiter
class above.

[Current production measurements](review-round-6-evidence/progress-measurements.json)
retain three samples at each of six sizes per quote: 5,751 through 184,001
characters. At 92,001 characters the medians are **0.00747 / 0.00740 seconds**
(double/single quote); at 184,001 they are **0.01506 / 0.01500 seconds**. Exact
useful content is asserted. These are observations in this environment, not a
universal performance guarantee. No timeout increase, truncation, hidden resource,
new size/format rule or secrecy bypass was introduced to pass bounds.

## Acceptance assessment

All assigned levels remain P1. PASS entries state the checked meaning at this
exact source; combined gates remain FAIL because of R1 above.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | FAIL | Identity, typed map and declared/measured semantics pass; complete nested snapshot secrecy fails for serialized quoted assignments. |
| D2 | FAIL | Real resolver/provider/registered writers/background/ORM and same-ID regressions pass ordinary guards; both writers persist the new adverse value. |
| D3 | PASS in isolated fixtures | Complete old-schema/value/notes/alias/history/file/startup/backfill audit and prior-schema authority; no production migration. |
| D4 | FAIL | Bounded HTTP/OpenAPI/filter/count/paging/read-only behavior passes; detail/list/ledger expose the adverse complete value. |
| D5 | FAIL as acceptance gate | Exact review, faults/restoration/full/standing/packages reproduced; actual adverse secrecy remains. |
| C1 | FAIL | Prior R1 forms pass; analogous serialized quoted values still persist and appear publicly. |
| C2 | PASS | Canonical typed validation/filter/count/page agreement; wrong raw-JSON filter fails nine assertions. |
| C3 | PASS | Same ID/AIR/hash/measured facts survive omitted/same/augmenting input; real conflicts refused; clearing fault fails two assertions. |
| C4 | PASS | Exact retained notes and truthful current errors across success/refusal/exception; overwrite/error faults fail 12/eight assertions. |
| C5 | FAIL as combined gate | Current full/standing/preservation pass; complete secrecy contract remains violated. |
| S1 | FAIL | Earlier Basic/cookie/quoted/Digest/access-token guards pass; new explicitly labelled serialized values survive publication. |
| S2 | FAIL | Earlier unsafe stored values project safely; the new serialized class leaks without changing storage. |
| S3 | PASS | Actual one-token mutation fails 20 writer/36 old-reader assertions; exact restoration. |
| S4 | FAIL as combined gate | Full/standing/schema evidence cannot override current secrecy failure. |
| S5 | PASS for reviewability | Official manifest/index/bytes/fingerprints and two independent exact restorations verified. |
| T1 | FAIL for complete label coverage | Immutable prefix probes pass; an explicit prefixed label with serialized quoted delimiters evades parsing. |
| T2 | FAIL | Keys exclude the same adverse strings while value projection exposes them; read-only and useful neighbors hold. |
| T3 | PASS | Reviewed word-boundary defect fails 40 writer/provider and 195 reader assertions; earlier fault meanings retained. |
| T4 | FAIL as combined gate | Current original secrecy obligation remains violated. |
| T5 | PASS for reviewability | Actual FINAL pinned before review, immutable history and usable official prerequisites verified. |
| U1 | FAIL for complete quoted classes | All old 78+3/706/130 guards pass; serialized quoted delimiters introduce 22 adverse feature failures. |
| U2 | FAIL | Public old-row reads retain complete adverse values; exact storage and useful resources preserved. |
| U3 | PASS | Quoted-extractor fault fails 86 writer/provider, 411 reader and 12 key/text assertions; exact restoration. |
| U4 | FAIL as combined gate | Ordinary-description bounds/actionable guidance pass; broader complete secrecy still fails. |
| U5 | PASS for reviewability | Frozen product/tests/helpers, exact FINAL and complete official restoration verified. |
| V1 | PASS | Exact old timeouts reproduced; current real 92,001-character boundaries, parity/neighbor guards and increasing-size progress pass at unchanged bounds. |
| V2 | FAIL as complete-secrecy gate | All immutable prior probes remain passing; additional current serialized class disproves complete labelled-value exclusion. R2-R4 remain passing. |
| V3 | PASS | Actual rejected parser mutation yields eight provider/publication and 12 old-read timeouts; exact restoration returns 1,498 feature passes. |
| V4 | FAIL as combined gate | Current full/standing/schema/22 contracts pass, but original secrecy is incomplete. |
| V5 | PASS for reviewability | Complete ordinary inventories, actual FINAL/manifest, official sizes/hashes and independent bundle/aggregate/per-commit/raw-commit restorations/fsck pass. |

## Commands and results

Persistent isolated worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-197-qa`,
branch `aid-197-exact-review`. New evidence is exclusively
[review-round-6-evidence/](review-round-6-evidence/).
The [replay guide](review-round-6-evidence/verification-commands.md) and
[verification index](review-round-6-evidence/verification.json) retain exact
argv/cwd/environments, imports/roots, timing, exits and raw/saved hashes. Expected
exit 1 remains an actual failing feature observation, not product GREEN.

| Scope | Actual result |
|---|---|
| Historical exact QA5 trailing /registered helpers | Two timeouts/two controls; five timeouts/one scaling observation |
| Current immutable original /QA2 /QA3 prefix /QA3 initial | 4 /14 /20 /28 passed, complete helpers |
| Current immutable QA4 labels /real key controls /QA5 lexical | 78 /3 /130 passed, complete helpers |
| Current immutable QA5 trailing /registered | 4 /6 passed, unchanged three-second bounds |
| New independent terminal/neighborhood cases | 360 passed initially; 360 passed after restoration |
| New serialized assignments, initial and confirmation | Each **22 failed /20 passed** |
| New full registered/old-read traces, initial and confirmation | Each **three failed**, complete synthetic value visible at all recorded phases |
| qa6-restored-feature | **1,498 passed**, 32.48 seconds, after exact restoration |
| qa6-backend-full | **3,476 passed /124 existing skips**, 76 warnings, 80.80 seconds |
| qa6-mcp-full | **666 passed /four existing skips**, 73.33 seconds |
| Fresh producers /separate readers | **93 /73 passed**, 19 fresh JSON exports retained |
| Standing MCP/PNG/stdio/content/smoke | **412 passed**, 71.98 seconds |
| Fresh wait /retained provider guards | **12 /19 passed** |
| Complete old-schema audit /prior-schema authority | **Two passed**, full synthetic before/startup/backfill payload retained |
| Registry | All **22** previous rows exact; no additions/deletions/supersessions |
| Source | **4,878** ordinary FINAL fingerprints; **742** frozen product/test/replay/topic bodies exact at FINAL and after restoration |

Before new tests the guard actually denied six private-file/.env/non-scratch
DB/model/write/DNS actions without opening private inputs. **154 ordinary guard
receipts across 52 runner records** have zero blocked events and imports pinned
to intended resolved current/archived roots. Tests and children use the isolated
Python **3.11.15** interpreter. Unguarded orchestration only handles Git/evidence/
Paperclip; the initial generic system `python3` parent was 3.9, with no application
imports there. The ignored venv references three existing dependency sites
read-only; no canonical installation/repair. Long suites use `--timeout=60`, while
description features retain three seconds. Raw `.raw.log.gz` copies are byte-exact;
readable logs trim trailing whitespace only.

### Fault sensitivity

QA inspected and executed all production mutations sequentially, with no other
suite or source-fingerprint reader during mutation. Files restore exact bytes
in finally before the restored/current qualification.
[Fault audit](review-round-6-evidence/fault-audit.json): **20 distinct mutations /
25 invocations /902 assertion failures plus 20 actual three-second timeouts**.
The prior 19 distinct/23 invocation meanings remain. Setup/import/SQL/fingerprint
errors do not count. The separate current adverse secrecy failures are not added
to this mutation count.

| Mutation | Observable failures |
|---|---:|
| Wrong map /fabricated verification | 1 /2 assertions |
| Split acquire /install publication | 1 /1 |
| Destructive backfill /unbounded list /writing list | 1 /2 /1 |
| Complete normalization /stored projection bypass | 1 /1 |
| Raw-JSON filter /clear omitted identity | 9 /2 |
| Overwrite retained notes /lose current error | 12 /8 |
| One-token value redaction, writer /reader | 20 /36 |
| Inspect descriptor /supplied descriptor /legacy-license bypass | 20 /20 /20 |
| Word-boundary recognition, writer-provider /reader | 40 /195 |
| Quoted extraction, writer-provider /reader /key-text | 86 /411 /12 |
| Exact rejected terminal scanner, provider-publication /old reads | Eight /12 actual timeouts |

## Preservation, delivery and notes

D3 audits all **16 tables**, including sqlite_sequence, eight resource rows and
five populated alias/history tables. Startup adds only nullable metadata_json;
backfill changes only that field, is idempotent, and preserves every old column/
value/note/ID/count/alias/history/synthetic body. Malformed/conflicting/duplicate/
unsupported/missing/offline cases retain diagnostics. Retry-note preservation is
checked separately. Static caller and First-check inventories remain evidence of
usage/dependencies, not proof or permission for removal. No new cancellation or
persistent job API is inferred; retained same-ID duplicate, failure/retry, truthful
recovery, wait/interruption and synthetic artifact contracts pass.

[Preservation](review-round-6-evidence/preservation.json) verifies the four exact
authorized imports from fixed a5aef450, original task/repairs1-5 hashes, **1,996**
prior task bodies plus the exact previous current report preserved as review5,
and **242** existing Backend-test/MCP/registry bodies. It checks **4,877** candidate
bodies other than the intentionally replaced current report. Task remains
c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda;
repair5 remains c4bd55052ba6837ae16306d84a2a1d7aaf486820fea5040db48f59f4894ec205.
The 31 MCP names/risks, frozen recipe/AIR/Anima/alias behavior and all 22 contracts
remain exact. All 13 shared-main memory bodies **and modified statuses** match
the independent initial receipt. No staging/stashing/reset/copying of those edits
or access to private/runtime/model data occurred.

[Official Coding integrity](review-round-6-evidence/coding-integrity.json)
independently downloads all **15 uploads**, checks every official size/SHA256,
manifest equality, **4,878** complete ordinary fingerprints, **301 indexed payloads /
302 members /293 exact Git bodies**, and all three history patch/raw-commit pairs.
Nine official base parts combine to **69,164,117 bytes**, SHA256
`dae69547ab2895258e245f40fc8be21c09e8a0eb9a6fedd7bfb8488da065a740`.
Two new bare stores seed only from those official bytes, write declared shallow
boundary b4e71d18ba4600ad7e053274b90b45ffdfbce87b **before fetch**, then use
`--update-shallow` and explicit `refs/heads/aid-195-exact-review` to restore 79e709ce.
One uses the official candidate bundle. The other independently applies the gzip
aggregate and each binary/full-index history patch/raw commit, without importing
local/candidate objects, reproducing every intermediate tree and commit identity.
Both reproduce exact FINAL/tree and `git fsck --full` exit 0. This is usable
restoration with a declared shallow boundary, not pre-boundary backup.
Official QA report/evidence/bundle/index/readback and both report restorations
follow the report commit and are recorded on this QA card.

The only QA audit failure was an incorrect preservation-helper filename. The
initial multi-command wrapper returned 0 because the subsequent independent
registry audit passed; the preservation subcommand itself failed. I reproduced
and captured that failure under Python3.11, then corrected only the new QA helper
to use its actual independent memory pin. Both attempts are retained in
[attempts.json](review-round-6-evidence/attempts.json). No feature execution or
sensitivity is attributed to them. All Coding failed attempts remain immutable.
The adverse probes are retained as adverse evidence, not rewritten current guards.
The registry builder runs on scratch copies and confirms all 22 rows unchanged;
a FAIL review certifies no new item.

## Limits and disposition

**Offline:** exact-source synthetic Settings/resolver/provider/strict-schema/
registered HTTP/background/ORM, historical/adverse/fault/restored/full/standing/
schema checks and official attachments. **Running service:** no production probe,
start/restart/deploy/backfill. **Provider/generation:** no actual owner-key read,
live provider request, real model acquisition/registration or generation.
**Retrieval:** synthetic installed bytes and Paperclip artifacts only; no live
model/Gallery bytes. Frontend and native Windows are unrun; 124 Backend platform
skips and four optional MCP-export skips are unchanged, with fresh applicable
producers/readers separately covered.

History: kickoff1 CLEAR; five earlier delivery FAILs; **this review6 FAIL**.
R5 is resolved for checked bounds, while original R1 is incomplete for the new
serialized quoted-delimiter class. This is a sixth rejected delivery, not a new
kickoff ambiguity or owner approval gate. Producer owns findings, reassessment,
correction and acceptance. QA completes only this card with its actual verdict.
Changed software requires a new exact FINAL review; no feature merge/push or
parent/owner mutation occurs. No new registry item, complete Phase2 automation,
three zero-fix sentences, fresh checkpoint+LoRA qualification, CTY demo, phase
exit or aesthetic acceptance is claimed.
