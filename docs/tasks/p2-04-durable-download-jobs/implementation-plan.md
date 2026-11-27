# Durable download jobs implementation plan

**Goal:** Implement the unchanged cleared [task](task.md) at source
`148d501557d7649f50be24440b856f5d327228de` for independent exact-commit QA.

**Execution:** Native Coding implementation in the isolated
`aid-215-p204-durable-download` branch. The assignment delegates concrete choices
and authorizes implementation; no additional design approval is pending.

**Architecture:** Add operation, ordered component and active claim tables to
existing SQLite. Serialize admission with a deadline-bounded SQLite write
transaction; unique identity/destination claims enforce exclusive ownership.
Persist only a digest of an optional idempotency key and canonical selection.
Hold an OS file lock for the Backend process lifetime, keyed by the actual DB
path. Acquiring that lock proves the preceding supported thread workers cannot
still run; reconcile their nonterminal jobs without replay. Every resource and
component write checks the current claim and operation token under a write
transaction. Read jobs using indexed, bounded DB queries and complete-value
projection. Extend the existing wait intent with direct download routing.

## Constraints and review focus

- Keep existing integer resource identities, all 31 MCP intents/risks/envelopes,
  87 certified contracts and all previous task/evidence bodies.
- Preserve configured-file requests, 8 GiB/file and observed 20 GiB floor,
  associated resume, verified no-overwrite publication and old notes.
- No automatic replay, aggregate quota, generation queue change or production
  provider/key/model/runtime/database action. Synthetic offline fixtures only.
- Review independent DB admission, post-commit failure, stale callbacks,
  live/uncertain process ownership and whole-response secrecy deliberately.
- Status and wait perform no model filesystem observation, provider call or
  submission. Total wait default/max is 50 seconds, including preparation.

## Tasks

- [ ] Admission: registered caller RED; additive operation/component/claim
  models and atomic deadline-aware admission; same-key replay/conflict,
  keyless active reuse and separate terminal retry. Verify real independent
  sessions, full-package refusal and commit-before-launch failure.
- [ ] Execution: acquisition, retained install and generate-like linkage;
  measured progress and fenced partial/success/error publication. Verify
  original stock bounds plus partial package failure and post-commit failure.
- [ ] Lifecycle: exclusive process lock, truthful once-only interruption;
  real isolated process death before launch and after file publication;
  live-owner refusal, stale callbacks and two-pass old-schema/value audit.
- [ ] Status/wait: bounded indexed DB-only job/resource linkage and complete
  projection; existing MCP optional key and direct namespaced wait. Verify
  fresh independent exporters/readers/stdio and all existing domains.
- [ ] Qualification: serial production mutations, intended assertions,
  exact finally restoration and complete GREEN; freeze current product,
  tests/helpers/topics, then current full/affected/fresh/87 standing checks.
- [ ] Delivery: D1–D5 manifest, ordinary fingerprints/raw attempts, actual
  NEW FINAL/tree and official self-contained exact-restorable artifacts.
  Independent QA owns its verdict; no feature merge or push by Coding.

## Progress

Initial source and tree match the assigned pin; shared main's 14 memory edits
are excluded. All implementation and new evidence stay in this worktree.
