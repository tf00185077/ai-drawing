# p2-03 implementation and exact delivery-review handoff

Producer accepts actual [QA AID-207](/AID/issues/AID-207) **kickoff1 CLEAR** at
published source `86837c724d0887d03c24e7d0c94c3b62d803ba9f`, tree
`8513654d554bab9a0626ba7ed21c1944642b4c6b`. The [task](task.md) remains byte-exact,
SHA-256 `285af6d1419f70e9c5e3b4a7d86f64f5913e6dfebb24e0897d3a67fb21ca32f0`.
Actual report/evidence FINAL `9dfdf9f175a1ea130bdb66c2aa561caebf8d4c42`, tree
`5065490af6b16fefa97438cd2dd5acbb1f1a6c8d`; [report](kickoff-review.md),
[official manifest](kickoff-delivery-manifest.json), [integrity](producer-kickoff-integrity.json).
No P0/P1 ambiguity, clarification or owner question; no p2-03 delivery rejection
or implemented feature is inferred. p2-02's nine earlier rejections/five historical
P1 findings and actual review10 acceptance remain a separate task history.

## Fixed scope and production boundaries

Deliver the cleared D1–D5 through shared stock download execution, acquisition
and retained inspect/install, registered HTTP/MCP/status and existing resource
identity. Adopted settings remain configurable 8 GiB/file and 20 GiB observed
destination free-space floor, selected safetensors checkpoint/LoRA policy, exact
stream/prefix bytes, valid resume and verified atomic no-overwrite publication.
The source findings below describe where the existing contract must apply; they
neither revise the task nor approve a new architecture or future schema.

- Apply effective policy and selected-size/hash/type gates before body/partial/row
  side effects in both callers. Actual acquisition rounds sizeKB while inspect
  truncates; choose and document one strict selected-size interpretation shared
  with typed metadata. Preserve safe exact-file adoption, failed-row retry and
  frozen other-kind/Anima package routing. Validate the complete selected package
  before row publication; a helper-only or blanket `_normalize_file` format edit
  cannot satisfy both requirements. Document environment Settings loading and
  rejected direct fixtures, rather than only injecting a helper policy.
- The helper receives only URL/hash/size today. Establish or verify resume
  association to existing provider/version/file/resource authority; filename and
  prefix length are insufficient. Unknown legacy/foreign/linked/changed partials
  survive refusal. Count the prefix, verify Content-Range before append, and
  retain valid associated resume and safe owned 200 restart. Space observations
  use the actual destination filesystem before admission/every write, without
  claiming cross-process reservations or total-budget enforcement.
- Treat retained install's admission/current-failure record as part of the same-ID
  contract too. Current install only persists completion, so a failed download
  can leave an old row planned. Pre-admission refusals create no new row; admitted
  failures publish truthful current failure on the existing row and keep old
  notes/identity. No second attempt table or durable job is introduced here.
- Verify ownership through open/write/hash/publication/cleanup, including races.
  Preflight target absence cannot justify replacing a later target. Retained
  install currently unlinks the final unconditionally after commit failure;
  compensation may remove only a still-owned publication. A replacement final
  or foreign partial must survive. Old rows, aliases/history and measured facts
  stay exact; no masked public locator becomes an executable internal lock.
- Keep the real ProviderOperation/ProviderDownloadTransport path, configured-file
  precedence, prepared-request credential isolation, redirect/origin policy,
  absolute deadline and closure. New disk/hash/publication work uses that same
  deadline. Isolated external HTTP fixtures are allowed; manual key/transport
  injection cannot certify production caller wiring or configured-file loading.

These observations are confirmed in the [source inventory](kickoff-evidence/reviewed-source-inventory.json)
and [nine bounded stock cases](kickoff-evidence/stock-observations.log). The stock
observer intentionally asserts the old defects. Keep its exact historical inputs
and results; do not run it as a future passing safety guard on changed source.
New positive/negative feature guards and meaningful production faults establish
correct behavior, with raw RED/finally restoration/GREEN recorded separately.

## Feature assertions that need explicit replacement

QA identified current unassociated-part success fixtures in
`test_206_resumes_from_part_offset_and_atomically_publishes_only_after_hash_and_size`
and `test_200_ignoring_range_overwrites_part_safely_instead_of_concatenating`.
Replace their obsolete fixture assumptions with associated-part positive cases
plus retained/refused legacy/foreign negatives; keep their byte/hash checks.
`test_http_size_sha_failures_leave_no_final_or_ledger`'s zero-row assertion after
admission becomes truthful failed same-ID evidence, retaining final-file/hash
checks. Review `test_ledger_commit_failure_removes_only_new_publication_and_row`
and linked-part cases for ownership/admission semantics. Safe exact reuse may need
explicit verification/adoption when tests retain a final but change row status.
Read-only old-note/status tests must not repair their seeded legacy parts.
No silent test deletion/new skip or registry supersession. Preserve all 72 existing
certified contracts and the 31 MCP names/risks; QA certifies any new registry rows.

## Execution, evidence and recipient ownership

Coding uses a new persistent isolated worktree from the published handoff commit,
reads actual CLEAR, implements the smallest coherent change and freezes the
actual code/tests/feature helpers before current qualification. Deliver a complete
D1–D5 manifest with actual FINAL full SHA/tree, exact ordinary source hashes,
effective settings and error contract, caller/dependency inventory, every failed
attempt/intervention, bounded byte/space/range/ownership/same-ID/closure traces,
meaningful five named production faults with exact restoration, current affected/
full Backend/MCP and fresh exports/standing consumers. Pin imports/roots, use
60-second per-test long-suite bounds and read-only canonical dependency sites.
Use synthetic credentials/files and isolated DBs; no production key/provider/model/
runtime/backfill action is required. Preserve all current shared edits, private
configuration/runtime/jobs, environments/worktrees and models/datasets/outputs/
Gallery records. No feature merge/push or self-PASS by Coding.

Independent delivery QA has a separate recipient-owned card natively blocked on
Coding. It reads the actual manifest, pins ACTUAL NEW FINAL full SHA/tree before
substantive review, checks all D1–D5 and the actual production boundaries above,
independently reproduces effective faults/restoration and current qualification,
then publishes its actual verdict and completes its own card even if adverse.
No product fix, parent/owner mutation or acceptance substitution by QA. Producer
handles findings/acceptance; any changed code needs another exact review and
feature merge only follows actual independent PASS.

Producer AID-146 retains ownership and the native prerequisite on delivery QA;
Coding → independent delivery QA → Producer carries continuation without polling,
self-delegation or duplicate wakes. Initial plans include the verbatim task/CLEAR/
handoff/decision/owner source at creation and are read back exactly.

## Baseline and phase limits

Kickoff fresh offline baseline: Backend 7043 passed/124 existing skips (190.68 s),
MCP 666/four existing skips (83.45 s), additional standing document guards 25 passed.
This is unchanged-source baseline, not qualification of future p2-03 code. No
fresh cross-layer exports/Frontend/native Windows were run at kickoff. Guard
activation has six deliberate denials and zero later blocked events. QA's initial
raw-log packaging omission and unchanged-log correction remain documented.
Producer's first bundle fetch guessed the worktree branch; the official bundle
exports HEAD. Reading its actual head fixed restoration without changing bytes.

All three official uploads, 46 archive members/42 Git bodies and 8128 complete
original source fingerprints agree. Official incremental bundle restores exact QA
FINAL/tree from only the published prerequisite; full-index patch independently
reproduces that tree; both fsck checks exit 0. All 72 registry rows and 14 current
shared dirty memory bodies/statuses remain exact. No product/test/task/registry
change or full suite repeat by Producer in this handoff. Producer checks 190 authored
local targets, English/whitespace and five Done items; two existing catalog/doc
guards pass in 0.20 s with an outer 60-second bound. Those two document guards
use the read-only canonical MCP Python 3.10.20; QA's full baseline uses its isolated
Python 3.11.15. Neither is qualification of future p2-03 source. Publication is not
runtime deployment. Firstcheck's one bridged chain/20 interventions/77 overlapping
units/five missing historical hashes and p2-01/p2-02 acceptances remain separate.
Durable attempts/jobs/aggregate reservations, search/hash lookup/new MCP/defaults/
removals and real three different zero-fix sentences/fresh checkpoint+LoRA/CTY
demo/Phase2 exit remain pending. Owner phase order/scope/architecture/Not now and
artistic authority are unchanged; no routine owner question is needed.
