# p2-02 independent delivery review

Verdict: FAIL
Review round: 8
Issue: [QA AID-202](/AID/issues/AID-202)
Coding: [AID-201](/AID/issues/AID-201)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-27

Reviewed ACTUAL NEW FINAL: **1d5e63afee426ebd6f0f1f58ea03fe08b823e23d**.
Reviewed tree: **74c70f55c707085783561889e002e38d7ef23899**.
Coding product/tests/replay freeze: **4436943033b70f838646f12d51b25e71167e5f62**.
Fixed implementation base: **5388e08dee72af39b38d766db40823d77ed80322**.

I read the official [correction7 manifest](manifest-correction-7.md), verified its
24,094 bytes and SHA256 `e0f4981455fa9b66b5794a58de077fda1131ad6ea09620d74ac10418b97119ba`
against FINAL, and pinned the full FINAL/tree on this card before substantive review.
[Pin receipt](review-round-8-evidence/pin-receipt.json). Neither the freeze ancestor
nor the moving Coding worktree was the target. Own report commit/tree and official
QA delivery receipts follow the report commit on the card, avoiding circular hashes.

**The supplied review7 examples are corrected. Original R1/P1 remains incomplete:**
preceding prose quotes can still disable a supported JSON-unit label representation,
and ordinary quoted raw base labels leak through acquisition's new notes and legacy
admission/status responses. R2–R4 and checked R5 bounds pass. Current full suites pass;
the independent complete-value failures block acceptance. All values are synthetic.
No actual owner key was read or disclosed. QA made no product repair, existing-test
change, assertion relaxation, deletion, new skip, registry addition, feature push or merge.

## Finding: original R1 / P1 remains incomplete

### Supported representation candidates still depend on enclosing prose quotes

`resource_records.py:109–141` retains disjoint quote pairing in `_json_string_view`.
A preceding double prose quote consumes the opening quote of an intended JSON string
unit. The corrected local assignment scanner never receives the decoded unit needed
to recognize the complete identifier. Its literal/escape-aware passes cannot recover
that omitted representation candidate.

Coding explicitly added `test_json_unit_*` publication/provider/all-field guards and
plain controls to preserve this view's distinct meaning. The supported plain control
`HTTP_AUTH"\u004f"RIZATION = "synthetic value"` is recognized after one JSON-unit
decode. Adding ordinary `ordinary "unfinished; ` disables recognition of the otherwise
unchanged control. Equivalent `CIVITAI_API_"\u004b"EY` and `vendor.api."\u006b"ey`
cases also fail. No nested serialization, recursive decoding or arbitrary unlabelled
secret discovery is required by these adverse inputs. This applies X1's harmless
context invariant to the implementation's own supported representation.

Independent exact-FINAL evidence, initially and in confirmation:

- [Context/nested cases](review-round-8-evidence/independent_unit_contexts_final.py):
  **54 feature failures /54 passing controls** per run. Real shared publication,
  provider/registered inspect/select/acquire/background, edited install and all12
  old-field/key classes are exercised. All12 classes fail for each of three adverse
  inputs; their36 plain-control counterparts pass. Screen and writer failures are
  separate cases. The initial simpler helper has the same54/54 outcome.
- [Complete phase traces](review-round-8-evidence/independent_unit_boundary.py):
  **nine feature failures /nine passing controls** per run. The full synthetic value
  appears in successful inspect/select, install's committed metadata/new-row notes,
  acquisition admission/background metadata and detail/list/local-ledger.
- All72 enhanced old-field traces collect detail/list/ledger and canonical family
  count/page observations before secrecy assertions. Safe IDs/hashes/triggers remain;
  normalization idempotence is checked. SQL writes/provider/publication/backfill/model
  body access are denied, and exact `metadata_json`/notes are checked in finally even
  on failure. Complete phase traces retain `STORAGE_EXACT=true` observations.
- [12 new safe unit neighbors](review-round-8-evidence/independent_safe_units.py) and
  all24 immutable QA7 useful originals pass, retaining their original representations.

Settings, environment-selected synthetic-file resolver, ProviderOperation machinery,
strict descriptors, registered HTTP, domain writers and ORM commit/reload are real.
Only external HTTP and deterministic thread scheduling substitute behavior. The
[progress analysis](review-round-8-evidence/source-progress-analysis.md) distinguishes
bounded traversal from complete candidate coverage.

### Raw provider labels bypass complete-value normalization in new notes/status

The [raw-label trace](review-round-8-evidence/independent_raw_label_notes.py) supplies
an ordinary quoted `CIVITAI_API_KEY` assignment as the selected provider baseModel,
in plain, once-serialized and preceding-prose forms. **Three feature failures** repeat
in confirmation. This is an explicit labelled value, without the unit-fragment form.

At `civitai_resource_acquire.py:363–370`, `common_notes` keeps the raw base label.
Admission and `_run_one` persist those new notes through `redact_secrets`; the legacy
summary at `:282–317` applies that same narrower redactor to `notes.base_model`.
All three complete traces show the full synthetic value in **admission response,
admitted new-row notes, completed new-row notes and status**. In the same traces,
typed admitted/completed metadata and detail/list/ledger are safely normalized.
Every phase is collected before the final secrecy assertion, including family reads.
This directly checks the required raw labels, new-row notes and retained responses.
Retained-row note preservation remains a separate passing obligation; QA did not
rewrite old notes to repair this new-row/public-response gap.

Both locations are the unresolved original R1, not new finding numbers or a new R5
bounds regression. P1 remains appropriate because complete recognizable credential
values persist or appear in successful public operations. Producer owns reassessment,
correction and acceptance; this report proposes no product patch.

## D/C/S/T/U/V/W/X assessment

All levels remain P1. PASS below states the checked component meaning at this exact
candidate; combined acceptance gates fail where R1 contradicts their contract.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | FAIL | Identity/map/typed and declared/measured facts pass; complete snapshot secrecy fails. |
| D2 | FAIL | Real registered writers/background/ORM run; both writers persist adverse unit values and acquire exposes raw labels. |
| D3 | PASS, isolated | Complete old-schema/value/notes/alias/history/file/startup/backfill audit; no production migration. |
| D4 | FAIL | Routes/OpenAPI/bounds/filter/count/page/read-only checks pass; public reads expose adverse unit values. |
| D5 | FAIL, acceptance | Exact review/fault/restoration/full/package evidence exists; secrecy remains violated. |
| C1 | FAIL | Prior cases pass; new nested recognized-value representations persist and are public. |
| C2 | PASS | Canonical validity/filter/count/page agreement; raw-JSON fault fails9 assertions. |
| C3 | PASS | Known identity/AIR/ID/hash/measured facts survive omission/augmentation; conflicts refused; clearing fault fails2. |
| C4 | PASS | Retained notes stay exact on success/refusal/exception; current recovery truthful; overwrite/error faults fail12/8. |
| C5 | FAIL, combined | Current full/standing GREEN does not override R1. |
| S1 | FAIL | Complete adverse values survive successful publication/descriptors. |
| S2 | FAIL | Useful read-only old resources expose complete adverse values across all12 fields/keys. |
| S3 | PASS | Partial-value mutation fails20 writer/36 reader assertions; exact restoration. |
| S4 | FAIL, combined | Original complete-value obligation remains violated. |
| S5 | PASS, reviewability | Official manifest/bytes/fingerprints and independent restorations checked. |
| T1 | FAIL, complete classes | Old prefixed forms pass; supported prefixed representations/raw labels remain unsafe in demonstrated paths. |
| T2 | FAIL | Both value/key contexts fail complete exclusion; useful immutable reads remain. |
| T3 | PASS | Word-boundary fault fails40 writer/provider and195 reader assertions. |
| T4 | FAIL, combined | Fresh contracts/schema/source evidence cannot establish complete secrecy. |
| T5 | PASS, reviewability | Actual FINAL pinned before review; immutable history/prerequisites verified. |
| U1 | FAIL, complete boundaries | Quoted label suites pass, but raw quoted labels leak through acquire notes/admission/status. |
| U2 | FAIL | Relevant old nested/key/raw-label contexts expose complete values without storage mutation. |
| U3 | PASS | Quoted-parser fault fails70 writer/provider,318 reader and12 key/text assertions. |
| U4 | FAIL, combined | Description bounds/recovery guidance pass; R1 remains incomplete. |
| U5 | PASS, reviewability | Frozen source/helpers and complete official package verified. |
| V1 | PASS, checked bounds | Real92001-character raw/serialized/dense provider/publication/HTTP/ledger features meet unchanged3s marks. |
| V2 | FAIL, complete secrecy | Earlier probes and R2–R4 pass; new observations disprove complete exclusion. |
| V3 | PASS | Exact old scanner yields8 provider/publication and12 old-read3s timeout failures; exact restoration then3808 passes. |
| V4 | FAIL, combined | Fresh full/standing/schema/22 contracts pass; R1 blocks acceptance. |
| V5 | PASS, reviewability | Ordinary inventories/official bytes/bundle and aggregate/per-commit/raw-commit restorations/fsck checked. |
| W1 | FAIL, complete boundaries | Supplied serialized cases pass; supported unit contexts and raw once-serialized labels remain unsafe. |
| W2 | FAIL | All12 old fields/keys run, with canonical phases and exact finally storage; complete values leak. |
| W3 | PASS | All-view omission fails14/36 writer-reader assertions; JSON-unit-only omission fails6/36; plain controls retain meaning. |
| W4 | FAIL, combined | All requested current old suites pass; original R1 still fails. |
| W5 | PASS, reviewability | Exact FINAL/manifest, failures/fingerprints and official restoration access verified. |
| X1 | FAIL | Unrelated preceding quotes disable supported unit controls at real writer/provider boundaries; raw new notes also leak. |
| X2 | FAIL | All12 field/key contexts leak; useful IDs/hashes/triggers, canonical pages and exact storage remain. |
| X3 | PASS | Reviewed candidate omission fails68 writer/provider and135 old-read assertions; literal-boundary omission fails16/72. |
| X4 | FAIL, combined | Frozen full/affected/immutable/standing/schema/bounds checks pass; complete original secrecy remains violated. |
| X5 | PASS, reviewability | Full FINAL/tree pinned, all attempts/history preserved, official bytes and two independent restorations checked. |

## Commands and actual results

Persistent worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-202-qa`,
branch `aid-202-exact-review`. New evidence is only in
[review-round-8-evidence/](review-round-8-evidence/). The [replay guide](review-round-8-evidence/verification-commands.md)
and [verification index](review-round-8-evidence/verification.json) retain argv/cwd,
allowlisted environment, roots, imports, durations, exits and readable/raw-gzip hashes.
Expected adverse exit1 is a failing feature observation, not product GREEN.

| Check | Actual result |
|---|---|
| Exact rejected42775d8 archived QA7 screen/nested/complete traces |38 failed/212 controls;44 failed/40;12 failed/6 |
| Current immutable original/QA2/QA3 prefix/QA3 initial |4/14/20/28 passed |
| Current QA4 labels/real key controls/QA5 lexical |78/3/130 passed |
| Current QA5 trailing/registered latency |4/6 passed; unchanged3s marks |
| Current QA6 terminal/serialized/complete traces |360/42/3 passed |
| Current immutable QA7 screen/nested/traces/safe originals |250/84/18/24 passed |
| New context/nested guard, initial and confirmation | Each54 failed/54 controls; all12 old fields/keys |
| New complete phase traces, initial and confirmation | Each9 failed/9 controls |
| New raw-label traces, initial and confirmation | Each3 feature failures |
| New safe unit neighbors |12 passed |
| Restored affected suite |**3808 passed**,100.78s |
| Full Backend |**5786 passed/124 existing skips**,76 warnings,142.65s |
| Full MCP |**666 passed/4 existing skips**,73.09s |
| Fresh producers/separate readers |**93/73 passed**,19 JSON exports retained; repeated only for scratch-loss recovery |
| Standing MCP/PNG/stdio/content/smoke |**412 passed**,71.98s |
| Fresh wait/retained provider guards |**12/19 passed** |
| Whole/prior-schema audit |**Two passed**, complete synthetic payload retained |
| Increasing-size progress |**Seven passed**,72 observations, three samples each |
| Registry rebuild |All22 prior rows exact; no additions/deletions/supersessions |
| Coding frozen/FINAL inventories |5984/6193 ordinary fingerprints;492 protected source/test/replay/topic bodies exact |

The QA executable sequence was frozen at **c57bd13c65026b43b59145e2a94980d0e51d6525**
before fresh full qualification. The earlier mutation runner/helper freeze is recorded
in attempts.json; later QA commits add helpers/reporting only. Delivered product/tests
and Coding replay bodies remain exact. All33 fault identities match Coding's current
production mutations, but QA executed and inspected them independently.

Before tests, actual private/.env/non-scratch DB/model/write/DNS denials activated
without opening private inputs; all six were reactivated on resume. Python and child
interpreters are3.11.15. The ignored venv references three existing dependency sites
read-only; no canonical installation/repair. **176 ordinary guard receipts across73
runner records** have zero blocked events and intended current/archived imports pinned.
Long suites retain --timeout=60; ordinary-description features retain3s. Exact raw
logs accompany readable logs whose only normalization removes trailing whitespace.

[Fault audit](review-round-8-evidence/fault-audit.json): **24 distinct production
mutations/33 invocations/1176 feature assertion failures plus20 actual3s timeout
failures**. All22 prior/29 invocation meanings remain. Mutations run sequentially;
exact bytes restore in finally before affected/full qualification. Setup/import/SQL/
fingerprint/audit errors and adverse baseline failures are excluded from sensitivity.
No test or fingerprint audit ran concurrently with active mutations. The unchanged
old serialization assertions now overlap with literal-boundary recognition; retained
unit-specific cases preserve each omitted view's independent meaning. Counts match
Coding's explained current1176/20 without deleting or relaxing old assertions.

The [progress data](review-round-8-evidence/progress-measurements.json) and source
analysis support constant forward passes, terminal EOF handling and bounded independent
views, without proving candidate completeness. Terminal raw92001/184001 medians are
0.03141/0.06243s for double quotes and0.02832/0.05656s for single quotes; serialized
medians are0.04733/0.09419s and0.04577/0.09176s. Dense contexts also retain full useful
output across six sizes/both quotes/three representations. These are local observations,
not universal performance guarantees. No timeout increase/truncation/format restriction.

## Preservation, restoration and attempts

D3 covers all16 tables including sqlite_sequence, eight resource rows, five populated
alias/history tables, every old column/value/note/ID/count and synthetic file body.
Startup adds nullable metadata_json only; explicit backfill changes only that field,
remains idempotent and diagnoses malformed/conflicting/duplicate/unsupported/missing/
offline cases. Retry-note/current-error checks separately exercise real background
branches. Legacy/First-check inventories establish usage/dependencies, not removal
permission. No new cancellation/accounting or live artifact claim follows from them.

[Preservation](review-round-8-evidence/preservation.json) verifies3145 prior task bodies,
244 existing test/MCP/registry bodies, all four authorized imports from fc9cce5b, and
unchanged task/repairs1–6. Task SHA256 remains
`c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`;
repair7 remains `97e18e11b0d36628455546133160fc9cca8274bae3e8dbc09c00be5111d8b7b6`.
All6193 candidate bodies were exact after restoration; only the current review is
intentionally replaced with this actual verdict. Its previous body remains exact as
review-round-7.md. All31 MCP intents/risks,22 registry contracts and frozen recipe/AIR/
Anima/alias behavior remain unchanged. FAIL adds no new certification.

This run independently pinned14 shared-main memory bodies/statuses, which matched
its completed preservation observation. Final concurrency receipt records the actual
later workspace observation separately. QA never staged/stashed/reset/restored/edited
or copied those bodies. Review7's distinct initial13-body pin, external change and
fourteenth-path history remains immutable, separate from Producer's14-body baseline.

[Official Coding integrity](review-round-8-evidence/coding-integrity.json) independently
verifies all15 uploads,6193 ordinary fingerprints,469 indexed payloads/470 members/
457 exact Git bodies and five binary/full-index patch/raw-commit pairs. Nine official
base parts combine to**70,813,780 bytes**, SHA256
`2dbe1848f008f5885622911a758ff48c464a1b1e6e1c03f5e36038ab8fbc1da6`.
Two fresh bare stores seed only those official bytes, with declared shallow boundary
`b4e71d18ba4600ad7e053274b90b45ffdfbce87b` written before fetch --update-shallow
and explicit base ref `refs/heads/aid-199-exact-review`. Bundle restoration and the
independent aggregate/per-commit-patch/raw-commit chain reproduce every intermediate
identity and exact FINAL/tree; both fsck --full exit0, no alternates/local candidate
seeding. This is usable declared-shallow restoration, not pre-boundary history backup.
Git bundle/update-shallow/binary apply and Python standard-library orchestration are
prerequisites. Own QA official artifacts/restoration receipts follow the report commit.

[Attempts](review-round-8-evidence/attempts.json) retain the initial generic adverse
expected0/actual1 wrapper mismatch, nonexistent new audit-helper read, and enhanced
helper's sibling-import collection failure. The corrected helper executes all108
cases without collection errors. A reporting parser initially missed pytest-dot-prefixed
progress markers; its72-observation audit failed, then the exact-marker correction
passed without changing logs/assertions. No sensitivity is attributed to these errors.
Coding's failed internal expectations/freezes/scope corrections and all historical
interrupted/failed audits remain unchanged in their original directories.

The heartbeat was interrupted after all tests and final confirmation records had
completed. No matching test process or active mutant remained; all33 mutations had
restored. Old scratch was removed. [Recovery](review-round-8-evidence/interruption-recovery.json)
reactivates six guards and recreates only fresh producer/reader exports and official
base prerequisites needed for delivery. Completed full/fault/standing/confirmation
checks were preserved, not rerun. Recovered93/73 exports pass and all19 JSON files
are retained; prerequisite size/hash readback is independently repeated. This interruption
adds no feature result and does not erase review7's separately attributed interruption.

## Limits and disposition

**Offline:** exact-source synthetic Settings/resolver/provider/strict-schema/
registered HTTP/background/ORM, historical/adverse/fault/restored/full/standing/schema
checks and official artifacts. **Running service:** no production probe/start/restart/
deployment/backfill. **Provider/generation:** no actual owner-key read, live provider
request, real acquisition/registration or generation. **Retrieval:** synthetic installed
bytes and Paperclip artifacts only; no live model/Gallery bytes. Frontend/native
Windows unrun;124 Backend platform skips and four optional MCP-export skips remain
unchanged. Private settings/key/runtime/DB/snapshots/backups/canonical environments,
retained worktrees and model/dataset/output/Gallery data are outside QA mutations.

History: kickoff1 CLEAR; seven earlier delivery FAILs; **this review8 FAIL**, with
original R1 incomplete and five distinct historical P1 findings. No new kickoff
ambiguity or routine owner gate. QA completes only AID-202 with this actual verdict.
Producer AID-146 owns findings/reassessment/correction/acceptance. Changed code needs
another exact FINAL review; no feature merge/push before independent PASS. No parent/
owner mutation, Phase2 jobs/budgets/hash/search/MCP/defaults/removal acceptance, three
different zero-fix sentences, fresh checkpoint+LoRA/CTY demo/exit or aesthetic judgment.
