# p2-02 independent delivery review

Verdict: FAIL
Review round: 9
Issue: [QA AID-204](/AID/issues/AID-204)
Coding: [AID-203](/AID/issues/AID-203)
Producer: [AID-146](/AID/issues/AID-146)
Date: 2026-11-27

Reviewed ACTUAL NEW FINAL: **c01730db22cc91d64aa779550313c3125fd66355**.
Reviewed tree: **28c9a63d852c4a4ae179a1f2b45a52757e604ffe**.
Coding product/tests/replay/topic freeze: **5baa7cfa451d6048d1edad1c94663750c33591e2**.
Fixed implementation base: **7ebf45d5a83b8bc0977a1f502b64b79bd35b22c5**.

I read the official [correction8 manifest](manifest-correction-8.md), verified its
18,497 bytes and SHA256 `fdaaf840bd2ac1a29abd34d16f43bc791130dd27140dd8a32bd5b82dd4b75a53`
against FINAL, and pinned the full FINAL/tree on my own card before substantive
review. [Pin receipt](review-round-9-evidence/pin-receipt.json). The freeze ancestor
and moving Coding directory were not the review target. Own report commit/tree and
official artifacts follow the report commit on AID-204, avoiding circular hashes.

**The supplied review8 representation and new-note/status failures are corrected.
Original R1/P1 remains incomplete:** the outer local-ledger DTO still exports raw
provider-derived AIR and local paths through the weaker redactor, although its
nested typed resource record is safe. Eight independent full-trace feature failures
repeat in confirmation; two useful safe controls pass. R2-R4 and checked R5 bounds
pass. Full Backend/MCP pass, but those results do not override this public disclosure.
All values are synthetic. No actual owner key was read or disclosed. QA made no
product repair, existing-test change, assertion relaxation/deletion, new skip,
registry addition, feature push/merge, or parent/owner mutation.

## Finding: original R1 / P1 remains incomplete at the outer local ledger

The [independent probe](review-round-9-evidence/independent_ledger_surfaces.py)
supplies an explicit quoted credential assignment as either the selected provider
file's `air` or a filename ending in `.safetensors`. It covers plain, once-serialized,
preceding-prose and supported JSON-unit-fragment contexts. For example:

```text
" CIVITAI_API_KEY " = "QA9 complete raw-identity synthetic value; retained suffix"
```

The filename case appends `.safetensors`; the AIR case supplies that string as the
provider AIR value. A stable safe refusal before publication is allowed by the
probe, but all eight operations instead return admission 202, run the actual
background target and reach installed state. These are recognizable labelled
values under the existing policy, including a unit representation already supported
by this implementation. No recursive decoding or arbitrary unlabelled-secret
recognition is requested.

The public `GET /api/civitai-recipes/local-ledger` response exposes the complete
synthetic value in **outer `entries[].air` or `entries[].local_path`**, both after
admission and after completed installation. In the same response,
`entries[].diagnostics.resource_record` is safe. Admission, typed admitted/completed
metadata, new notes, acquisition/status, canonical detail/list and family/count/page
responses are also safe. This isolates another public surface that cannot be
certified by checking only the typed record or the repaired acquisition summary.

Exact source trace:

- [Acquisition](../../../backend/app/services/civitai_resource_acquire.py), lines
  394-399 and 434, carries the provider AIR through shared identity publication;
  lines 419-424 retain the selected filename and actual target path on the row.
- [Local ledger](../../../backend/app/services/civitai_local_identity_ledger.py),
  lines 69-91, builds a safe typed diagnostic record while separately copying raw
  `local_path` and `air` into `LocalResourceLedgerEntry`.
- The same file's `ledger_payload`, lines 141-156, copies those outer fields and
  returns `redact_secrets(...)`, rather than the shared complete-value policy.
  [The registered router](../../../backend/app/api/civitai_recipes.py), line 624,
  returns that payload. Repeated use of the weaker redactor does not establish
  complete-value exclusion.
- Coding's [publication inventory](correction-8-evidence/publication-inventory.md)
  identifies local-ledger diagnostics but does not account for these raw outer
  fields. Internal locator/identity use and safe public projection remain separate
  concerns; retaining valid AIRs and real paths does not require exposing affected
  credential-bearing values.

[Phase audit](review-round-9-evidence/ledger-phase-audit.json): **eight failures/two
safe controls**, initially and in final confirmation. Each attack collects all13
phases before the secrecy assertion: **104 observations**, with16 exposed ledger
phases. All eight complete synthetic installations. Settings, environment-selected
synthetic-file resolver, ProviderOperation, selected non-first version/file,
registered HTTP, actual background target, shared publication and ORM commit/reload
are real. Only external HTTP and deterministic scheduling substitute behavior.

Completed reads deny SQL writes, provider/publication/backfill and model-body
access. Every original ORM column, including `metadata_json`, notes, identity,
status and measured facts, is checked byte-exact in finally even on adverse failure.
Safe IDs/hashes/triggers and canonical family pages remain visible. Both controls
retain a valid AIR, original useful path and verified hash in outer and typed views.
The public failure does not require changing old storage or hiding a whole resource.

This is the unresolved original R1, not a sixth distinct historical finding or a
new kickoff ambiguity. Producer owns correction, reassessment and acceptance.

## Y1-Y5 assessment

All levels remain P1. A component PASS describes its checked meaning at this exact
candidate; combined acceptance fails wherever complete public exclusion is required.

| Item | Verdict | Independent evidence |
|---|---|---|
| Y1 | FAIL, complete pipeline | Supplied108 context/18 phase/12 safe-unit cases and495 additional positives pass. Candidate extraction is corrected in checked contexts; supported unit text still appears through outer ledger AIR/path fields. |
| Y2 | FAIL, public-surface coverage | New-note admission/background, refusal/exception, seeded old-note summaries and retained reuse/retry checks pass. The outer legacy DTO retains another weaker public projection; safe typed metadata cannot certify it. |
| Y3 | PASS |29 distinct production mutations/39 invocations,1577 feature assertion failures and20 actual3s timeouts; representation63/252, notes45, summaries60, refusal5 and warnings5; exact restoration. |
| Y4 | FAIL, combined | Current affected/full/standing/immutable/schema/progress checks pass and22 prior rows remain exact; the independent public-value failures block acceptance. |
| Y5 | PASS, reviewability | Actual FINAL/tree pinned first; complete ordinary inventories, attempts, official bytes and two independently seeded declared-shallow restorations verified. |

## Retained D/C/S/T/U/V/W/X assessment

The rows distinguish canonical typed-route checks from the additional unsafe outer
ledger surface. Combined FAIL rows do not count as additional findings.

| Item | Verdict | Independent evidence |
|---|---|---|
| D1 | PASS, typed component | One row/ID authority, exact mapping, selected metadata, unknown/invalid cases and declared/measured facts pass; this does not certify outer DTO copies. |
| D2 | FAIL | Real acquire/install/background/ORM execute, but the retained ledger publishes a weaker representation outside its safe typed diagnostic. |
| D3 | PASS, isolated | Whole16-table/value/notes/alias/history/file/startup/backfill and prior-schema audits pass. |
| D4 | PASS, canonical routes | New list/detail/OpenAPI, bounded SQL filters/counts/pages/errors and no-write/no-provider/no-body checks pass; the failing retained ledger is separately identified. |
| D5 | FAIL, acceptance | Exact review/fault/restoration/package evidence exists; complete public secrecy still fails. |
| C1 | FAIL, complete public R1 | Typed/shared/descriptor normalization passes; the outer ledger still exposes recognizable affected values. |
| C2 | PASS | Canonical validity/filter/count/page agreement; raw-JSON mutation fails9 assertions. |
| C3 | PASS | Omitted/same/augmenting/conflicting AIR preserves ID/hash/measured evidence; clearing mutation fails2. |
| C4 | PASS | Retained notes exact on success/refusal/exception and current recovery truthful; overwrite/error mutations fail12/8. |
| C5 | FAIL, combined | Full GREEN does not override remaining R1. |
| S1 | PASS, typed writers | Complete-value metadata and strict descriptor guards, including original Basic/cookie/quoted forms, pass. |
| S2 | FAIL, whole ledger result | All12 nested snapshot fields/keys pass; successful persisted-row ledger reads can still expose complete values in outer identity/path fields. |
| S3 | PASS | One-token mutation fails20 writer/36 reader assertions; exact restoration. |
| S4 | FAIL, combined | Current standing/full/schema evidence passes; public R1 remains incomplete. |
| S5 | PASS, reviewability | Official manifest/bytes/fingerprints and independent restorations checked. |
| T1 | PASS, tested typed classes | Prefixed assignments and applicable provider/strict descriptor/nested publication classes pass. |
| T2 | FAIL, complete read output | Nested key/text policy and useful immutable reads pass; outer ledger copies remain unsafe. |
| T3 | PASS | Word-boundary mutation fails40 writer/provider and195 reader assertions. |
| T4 | FAIL, combined | Fresh qualification does not establish whole-surface secrecy. |
| T5 | PASS, reviewability | Actual FINAL pinned before review; source/history/prerequisites verified. |
| U1 | FAIL, full public boundary | Quoted-label guards pass, but ordinary quoted assignments in provider AIR/filename appear in successful ledger data. |
| U2 | FAIL | Twelve nested classes pass; outer ledger values remain exposed without storage repair. |
| U3 | PASS | Quoted-parser mutation fails70 writer/provider,318 reader and12 key/text assertions. |
| U4 | FAIL, combined | Bounds and recovery guidance pass; R1 still blocks acceptance. |
| U5 | PASS, reviewability | Frozen helpers/source and complete official package checked. |
| V1 | PASS, checked bounds | Real92001-character raw/serialized/dense provider/publication/HTTP/ledger/notes/summary features retain3s and full useful content. |
| V2 | FAIL, complete secrecy | Earlier forms and R2-R4 pass; unsafe outer ledger values contradict complete exclusion. |
| V3 | PASS | Exact rejected scanner yields8 provider/publication and12 old-read3s timeout failures; restoration then4796 affected passes. |
| V4 | FAIL, combined | Full/standing/schema/registry evidence passes; original R1 persists. |
| V5 | PASS, reviewability | Ordinary inventories, official bytes and both restoration paths/fsck checked. |
| W1 | FAIL, complete boundaries | Supplied serialized writers/descriptors/new notes pass; once-serialized values still reach public outer ledger fields after actual acquisition. |
| W2 | FAIL | All12 nested fields/keys are safe; the whole ledger result is not. Exact storage and canonical reads remain intact. |
| W3 | PASS | All-view omission fails14/36 writer-reader assertions; JSON-unit-only omission6/36; plain controls keep their meaning. |
| W4 | FAIL, combined | All requested current historical/standing checks pass; public R1 is unresolved. |
| W5 | PASS, reviewability | Exact FINAL/manifest, attempts/fingerprints and official restoration access checked. |
| X1 | FAIL, full pipeline | Supplied preceding-quote cases pass; equivalent supported unit/prose values still escape through the unnormalized outer DTO. |
| X2 | FAIL | Nested context classes, counts/pages and storage preservation pass; raw outer ledger fields expose complete values. |
| X3 | PASS | Reviewed assignment omission fails54 writer/provider and135 readers; literal-boundary omission16/72. All prior meanings retained. |
| X4 | FAIL, combined | Frozen current suites/bounds pass; complete public exclusion does not. |
| X5 | PASS, reviewability | Full FINAL/tree pin, complete attempts/concurrency/history and official restorations verified. |

## Commands and actual results

Persistent worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-204-qa`,
branch `aid-204-exact-review`. New evidence is in
[review-round-9-evidence/](review-round-9-evidence/). The
[replay guide](review-round-9-evidence/verification-commands.md),
[verification index](review-round-9-evidence/verification.json) and individual runner
JSON/log/raw-gzip files retain commands, argv/cwd, allowlisted environment, roots,
imports, durations and exits. Expected adverse exit1 is a failing feature observation.

| Check | Actual independent result |
|---|---|
| Exact rejected review8, initial and confirmation | Each54 failures/54 controls; nine/nine phase cases; three raw-label failures;12 safe controls pass |
| Current original /QA2 /QA3 prefix /QA3 initial |4 /14 /20 /28 passed |
| Current QA4 labels /real key controls /QA5 lexical |78 /3 /130 passed |
| Current QA5 trailing /registered latency |4 /6 passed, unchanged3s limits |
| Current QA6 terminal /serialized /full phases |360 /42 /3 passed |
| Current QA7 screen /nested /full phases /safe originals |250 /84 /18 /24 passed |
| Current QA8 contexts /full phases /raw-label notes /safe units |108 /18 /3 /12 passed |
| Additional mixed-context/real-boundary positives |495 passed in final confirmation |
| New outer-ledger adverse, initial and confirmation | Each8 feature failures /two useful safe controls |
| Restored affected |**4796 passed**,110.28s |
| Full Backend |**6774 passed/124 existing skips**,76 warnings,158.52s |
| Full MCP |**666 passed/four existing skips**,73.54s |
| Fresh producers /separate readers |**93 /73 passed**,19 fresh JSON exports retained |
| Standing MCP/PNG/stdio/content/smoke |**412 passed**,71.32s |
| Fresh wait /retained provider guards |**12 /19 passed** |
| Whole /prior-schema audits |**Two passed**, complete synthetic audit payload retained |
| Increasing-size progress |**25 passed**,180 observations with three samples each |
| Registry | All22 prior rows exact; no additions/deletions/supersessions |

The mutation runner/helpers were frozen at **16b02a9487ccbc568177af1ee7c0b31ce05cc92e**.
The added outer-ledger probe and final executable QA sequence were frozen at
**f9ca38b3618bde61827a8358554d64dccb117114** before fresh full/standing/historical
qualification and final confirmations. Product/tests/Coding replay bodies never
changed from reviewed FINAL. Later changes add reporting/evidence only.
[Freeze/restoration receipt](review-round-9-evidence/freeze-and-restoration.json).

Before new tests, six actual private/.env/non-scratch DB/model/write/DNS denials
activated without opening private inputs. Python and children are3.11.15. The ignored
QA venv references three existing dependency sites read-only; no canonical install
or repair. **84 runner records/186 ordinary guard receipts** have zero blocked events
and intended current/archived imports pinned. Long suites retain `--timeout=60`;
description/progress features retain3s. Readable logs trim trailing whitespace only;
exact raw-gzip logs and both hashes are retained.

[Fault audit](review-round-9-evidence/fault-audit.json): **29 distinct production
mutations/39 invocations/1577 feature assertion failures plus20 actual3s timeouts**.
All24/33 retained meanings persist. Representation-candidate omission fails63
writer/provider and252 old-read assertions; new-note bypass45 while typed metadata
and DTO checks pass; legacy-summary bypass60 with exact storage; refusal/warnings5
each. Assignment overlap54 rather than68 and the five selected-provider license
assertions have the same explanation as the delivered manifest: independent new
protection overlaps14 old assignment cases, and downstream summaries protect all20
old license response cases. No old selection/assertion is removed or relaxed.
Mutations run sequentially and restore exact bytes in finally. No test/fingerprint
audit ran concurrently with active mutations. Setup/import/SQL/audit/recorder errors
and the new adverse baseline failures are excluded from sensitivity counts.

The [progress data](review-round-9-evidence/progress-measurements.json) and
[source analysis](review-round-9-evidence/source-progress-analysis.md) cover fixed
views, monotonic escape/EOF traversal, representation candidates and notes/summary
paths. Checked raw/serialized/dense92001-character features retain complete useful
output under3s. Increasing sizes support the documented bounded progress locally;
they do not prove universal timing or complete output-surface coverage. No timeout
increase, truncation or new format/size exclusion is used.

## Preservation, official restoration and attempts

D3 audits all16 tables including sqlite_sequence, eight resource rows, five populated
alias/history tables, every old column/value/note/ID/count and synthetic file body.
Startup adds nullable metadata_json only; backfill changes only that field and is
idempotent, with malformed/conflicting/duplicate/unsupported/missing/offline cases
diagnosed. Retry-note/current-error guards separately exercise actual background
success/refusal/exception. Dependency inventories establish usage, not removal
permission. No new cancellation/job-accounting feature or live retrieval is inferred.

[Preservation](review-round-9-evidence/preservation.json) verifies4366 prior task
bodies and247 candidate Backend-test/MCP bodies exact, plus the four authorized
supplement imports. The original task and repairs1-8 hashes remain exact; task SHA256
is `c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda`, repair8
`abcd8be84dab3444f5e5987b2b942ffef598176b00236da148535202e91ba8d4`.
All6966 candidate bodies were byte-exact after restoration and before replacing the
current report. Its old body remains exact as review-round-8.md. All6713 Coding
freeze fingerprints/509 protected bodies and7090 QA freeze fingerprints/19 QA replay
helpers verified before publication packaging. Feature-check helpers remain exact;
the later packaging-only adjustment is recorded below. Ordinary pathname/hash suppression is empty. All31 intents/risks,
22 prior contracts and frozen recipe/AIR/Anima/alias behavior remain unchanged.
FAIL adds no registry certification.

This run pins14 shared-main memory bodies/statuses. Its completed preservation
observation matches that baseline, with zero observed external changes. Prior
13-body/external-change/fourteenth-path observations, Producer's separate14-body
baseline and QA8's interruption after completed tests/recreated guard/exports/base
prerequisites remain distinct immutable records. QA did not stage, stash, reset,
restore, edit or copy shared memory. Later concurrency observations are separate.

[Official Coding integrity](review-round-9-evidence/coding-integrity.json) verifies
all15 uploads,6966 ordinary fingerprints,503 indexed payloads/504 archive members/
493 exact Git bodies and four per-commit binary/full-index patch/raw-commit pairs.
Nine official base parts combine to **72,061,453 bytes**, SHA256
`9a32f83637e59b1e5d1358b0e079edd98337da458b2c22d53adbdb76f2bf951a`.
Two fresh bare stores seed only those independently downloaded official base bytes,
write declared shallow boundary `b4e71d18ba4600ad7e053274b90b45ffdfbce87b` before
fetch `--update-shallow`, and use explicit base ref `refs/heads/aid-202-exact-review`.
One imports the official candidate bundle; the other independently applies the
aggregate patch then every per-commit patch/raw commit without local/candidate-object
seeding or alternates. Every intermediate identity/tree and FINAL/tree match in both
stores, with both `fsck --full` exits0. The
[history readback](review-round-9-evidence/restoration-history-verification.json)
checks all eight intermediate store observations. This is declared-shallow
restoration, not pre-boundary backup. Git bundle/update-shallow/binary apply and
Python standard-library orchestration are explicit prerequisites. Own official QA
report/evidence/index/bundle/patch/readback receipts follow the report commit on AID-204.

[Attempts](review-round-9-evidence/attempts.json) preserve the first QA screen's
Settings-before-bootstrap collection error, corrected by importing test bootstrap
first. An initial combined writer probe incorrectly shared one fixture database
between independent row-count assertions: three fixture-count failures/486 passes.
Separating those cases with the same assertions gives495 passes. Initial helper
bodies/logs remain. Neither error is a product defect or mutation sensitivity.
The unset Git identity discovery and initial read of the preserved historical
manifest are recorded; the actual correction8 manifest was verified before pinning.
All Coding failed internal expectations and older QA failed/interrupted/recovery
attempts remain immutable. No task-owned interruption or partial fault invocation
occurred in this review.


The first official QA publication at report commit **90d06024ad6ff415e85d895cda49295bf1505cf7** saved and
read back the report, bundle and aggregate patch, then rejected the complete
15,645,283-byte evidence archive with HTTP422. The control-plane source bounds
attachments (default10MiB) and returns422 for LIMIT_FILE_SIZE. This is a reporting
failure, not a product result. [Partial-publication receipt](review-round-9-evidence/partial-publication-attempt.json)
preserves the three completed uploads and the rejected archive's complete bytes
as two official read-back-verified parts; no completed upload was repeated. The
original packaging helper is retained byte-exact as package_review_initial.py.
The corrected reporting-only packager indexes ordered8MiB archive parts, verifies
their combined original size/SHA256 before opening, then performs both independent
restorations. Product/tests/feature-check replay inputs remain unchanged, so their
completed verification still applies. New report/package bytes have a separate
report-only commit and official identity; the earlier partial attempt remains.

## Limits and disposition

**Offline:** exact-source synthetic Settings/resolver/provider/strict-schema/
registered HTTP/background/ORM, adverse/fault/restored/full/standing/schema/bounds
checks and official artifacts. **Running service:** no production probe/start/
restart/deployment/backfill. **Provider/generation:** no actual owner-key read,
live provider request, real model acquisition/registration or generation.
**Retrieval:** synthetic installed bytes and Paperclip artifacts only; no live
model/Gallery bytes. Frontend/native Windows unrun;124 Backend platform skips and
four optional MCP-export skips remain, with fresh applicable exports/readers tested.
Private settings/key/runtime/DB/snapshots/backups/canonical environments/retained
worktrees and all model/dataset/output/Gallery records remain outside QA mutations.

History: kickoff1 CLEAR; eight earlier delivery FAILs; **this review9 FAIL**, with
original R1 incomplete and five distinct historical P1 findings. No new owner
question or kickoff ambiguity. QA completes only AID-204 with this actual verdict.
Producer AID-146 owns findings/reassessment/correction/acceptance. Changed code
requires another exact independent review; no feature merge/push before PASS.
No Phase2 jobs/budgets/hash/search/MCP/default/removal acceptance, automatic chain,
three different zero-fix sentences, fresh checkpoint+LoRA/CTY demo/exit or aesthetic
judgment is claimed. Source availability is not deployment.
