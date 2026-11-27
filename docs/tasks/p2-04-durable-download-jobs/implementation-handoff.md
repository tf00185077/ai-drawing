# p2-04 cleared implementation handoff

Independent [QA AID-214](/AID/issues/AID-214) returned **kickoff round 1 CLEAR** at
fixed source **f87b6ce44815e118202fcf5f44fc5198dd82e1d7**, tree
**cec7472536c5b64b5ff9affb0fe7370781cfb3a9**. The unchanged [task](task.md) is
11,573 bytes, SHA-256 `49a73639bc1eef1655ef8e07f5b1add5e9199abdeedfddea30498c2b4e35b565`.
Actual [report](kickoff-review.md) and evidence FINAL
**8622d2617ee879a86872785c50a45eb5dd643993**, tree
**68063955e6b7f3f8f1f1a6adac124cb2ce116bce**, follow the native pre-review pin
`5b616b63-6090-459f-8ab6-ee6d2135440a`. No blocking ambiguity or owner-boundary
question was found. This clears the specification; no D1–D5 implementation or
independent delivery PASS is implied.

## Adopted application of the unchanged contract

Use the smallest additive operation/component/claim representation in the existing
Backend/SQLite. Preserve the single resource authority and integer resource IDs.
A job is an operation with execution history, not another model record or a
replacement for generation's in-memory queue. Aggregate quota/reservations remain
the next separate increment after operation identity.

- Audit all real callers: registered acquisition, retained synchronous install,
  and `civitai_easy.generate_like` calling `start_acquisition`. The latter is still
  supported in this increment. No early removal or frozen-feature bypass.
- Commit durable admission and resource ownership before launching a body. Exercise
  independent connections and simultaneous requests; an RLock alone is insufficient.
  Keep idempotent terminal/restart replay, active deduplication, conflicting-key
  refusal and a new explicit terminal retry's separate history. Bound database
  contention by the applicable existing deadline rather than resetting its budget.
- Fence partial, progress, success and exception callbacks at their actual database
  writes. Old workers cannot overwrite a newer owner or regress a terminal job.
  Measure progress during execution; package success requires every selected
  component. Preserve genuine completed components, existing bytes, notes and
  present-operation adoption without inventing a historical network download.
- Prove a previous worker cannot still execute before reconciling it as interrupted.
  A PID or startup event alone is insufficient. Use the smallest supported
  single-Backend lifecycle/fencing mechanism; safe refusal of live or uncertain
  concurrent ownership is allowed. No automatic restart replay/resume or inference
  of completion from a file. Run actual isolated process-death/restart cases at
  admission-before-launch and publication-before-finalization, alongside live-owner
  controls and complete two-pass schema/old-value preservation.
- Current `acquisition_status` and `project_resource` perform filesystem reads.
  New download-job/resource status must use persisted measurements and timestamps,
  not those filesystem-observing projections. Canonical resource reads keep their
  prior contract. Whole public job/error projections share the complete-value
  policy; internal raw selected identity/destination inputs remain usable.
- Route namespaced download IDs directly to the authoritative Backend read in
  existing `wait_for_job`. Known download errors do not fall through generation/
  training or Gallery enrichment. Return verified resource results without fake
  media, retain the overall default/max 50-second budget through reads and result
  preparation, and advise only reading the same job after timeout. Preserve all
  31 names/risks/envelopes and generation/training behavior. Update the existing
  catalog endpoint inventory when adding the read route.

These are applications of D1–D5 already reviewed CLEAR, not new task requirements
or a schema/error-prefix/design approval gate. Coding chooses concrete table/index
names, ID prefix, conflict-code spelling, progress cadence and fencing primitive,
then documents and demonstrates them. Existing p2-03 D/C/E execution limits and
all 87 prior registry items remain binding. Full-package policy/refusal and DB
commit failure must precede any unrecorded body.

## Evidence and qualification limits

QA's unchanged-source baseline checks: Backend 94 passed with one existing warning;
MCP 85 passed, with 12 fresh-export consumers explicitly deselected. Diagnostic
repeats pass 94/85. These are small baseline observations, not complete delivery
qualification. No new full suite, fresh export, stdio, frontend/native Windows or
p2-04 runtime/process-death behavior was tested at kickoff.

The strict guard recorded three Backend and one MCP/source-observation denied
filesystem requests. A system-version read was identified; two Backend requests
remain unlocalized. Preserve the raw diagnostic attempts and this limitation.
Changed-source delivery must record actual guard behavior and account for denied
requests; do not claim zero denials from these baseline runs or silently relax
isolation. Current full Backend/MCP, affected checks, fresh Backend exporters before
independent MCP/stdio readers and the standing 87 contracts are still required.
Use pinned Python/import/settings/root/fixture identities, isolated roots and
per-test 60-second bounds for long suites. Real production-fault assertions,
serialized mutation, exact restoration and complete current GREEN precede delivery.

Initial guessed source paths, ignored-log staging correction and Apple Python
3.9.6 archive-filter failure remain in the exact report/raw evidence. Packaging
with the explicit 3.11.15 interpreter and official restore succeeded; no product,
test assertion or skip was changed. Do not recast those attempts as product tests.

Producer integrity verifies all ten official
uploads, 29 exact evidence payloads, all 8,891 source/report body-mode identities,
8,862 unchanged base paths and their ordinary fingerprints, unchanged 87-row
registry and the self-contained official snapshot plus independent full-index patch
restore. Five ordered parts reconstruct 36,372,480 bytes with SHA-256
`de84342c75963644434a8f994e231470f6f888cae88ccda6b56ea4a98dc3eb6c`.
History explicitly stops at the fixed source. The independent patch store receives
only a base-reachable pack from official bytes; the report candidate is absent
before import. Both fsck checks exit 0, no alternates. No external cache or Git
prerequisite is needed. Original report/evidence remain exact.

## Role handoff and acceptance

Producer publishes this report-only handoff and opens separate Coding and
independent exact-final-commit delivery-QA cards. Their complete native initial
plans pin the actual published full source/tree and include the verbatim task,
actual CLEAR and accepted inputs. New persistent isolated recipient worktrees;
shared main and its 14 concurrent memory edits are not implementation workspaces.
Coding freezes its actual product/tests/helpers before current qualification and
delivers the actual NEW FINAL full SHA/tree, complete ordinary fingerprints,
manifest and usable official exact-restorable evidence. No self-PASS/feature push.

QA waits natively on Coding, reads the actual manifest, pins the actual NEW FINAL
before substantive review, independently checks every D item/adverse boundary/
fault/current qualification and completes its own verdict even adverse. Producer
handles findings and acceptance. Changed code needs a new exact review; feature
merge only after independent PASS. Native Coding → QA → Producer carries
continuation, not comments or send receipts alone.

This increment uses offline fixtures and official artifact retrieval only. Preserve
private key/runtime/settings/schema/data/snapshots/backups/environments/worktrees,
models/datasets/outputs/Gallery. No live provider/model action, production migration,
restart/deployment or generation. Source publication is not deployment. Remaining
aggregate accounting/search/hash/new MCP/defaults/removals and the three different
zero-fix sentences/new checkpoint plus LoRA/CTY demo/Phase 2 exit stay pending.
Owner artistic judgment, approved scope/order/Not now and roadmap delegation remain;
no routine owner confirmation is needed.
