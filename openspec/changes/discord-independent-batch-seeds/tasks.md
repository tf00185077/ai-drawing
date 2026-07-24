## 1. Request contract and validation

- [x] 1.1 Add RED API tests for omitted/shared mode, independent random mode, and every incompatible seed/workflow combination
- [x] 1.2 Add the additive `batch_seed_mode` request contract and validation without changing legacy shared callers
- [x] 1.3 Forward independent mode to the queue while preserving shared queue defaults and pass focused generate API tests

## 2. Parent and child queue execution

- [x] 2.1 Add RED queue tests for one public parent, unique private execution IDs/seeds, and `batch_size=1` children
- [x] 2.2 Implement pure bounded unique seed allocation and distinct parent/child queue identities
- [x] 2.3 Add RED tests for atomic all-child capacity reservation and zero partial enqueue on rejection
- [x] 2.4 Implement locked atomic independent admission while preserving one-job shared admission
- [x] 2.5 Add aggregate queue/status tests and implement monotonic queued-to-running parent projection
- [x] 2.6 Add cancellation race tests and implement atomic queued-parent cancellation with existing running-parent conflict behavior

## 3. Durable outcomes and deterministic artifacts

- [x] 3.1 Add RED model/recording tests for durable parent/member rows, actual member seeds, and sanitized failures
- [x] 3.2 Add generation batch parent/member SQLAlchemy models and one Alembic migration
- [x] 3.3 Add RED artifact tests for repeated source names, parent identity, metadata, and ordinal ordering
- [x] 3.4 Implement collision-free parent/ordinal filenames and propagate `batch_index`, seed, and `source_node_type`
- [x] 3.5 Add RED fresh-session tests for persisted 3-success/1-failure status and restart reconciliation
- [x] 3.6 Implement durable aggregate status lookup and startup `backend_restarted` reconciliation

## 4. Mixed completion and queue safety

- [x] 4.1 Add RED tests proving one child failure does not cancel later siblings
- [x] 4.2 Centralize member terminal accounting and derive completed-mixed versus all-failed parent status
- [x] 4.3 Add RED API tests for deterministic successful artifacts, aggregate counts, and sanitized failed members
- [x] 4.4 Return persisted aggregate outcomes from the job API ahead of naive artifact-presence inference
- [x] 4.5 Add and pass regressions for malformed submit responses, recording failures, queue-slot release, and sibling continuation
- [x] 4.6 Repair aggregate all-failed summaries, SaveImage-only independent success, and bounded queue/history uncertainty with RED regressions

## 5. Discord compatibility

- [x] 5.1 Add RED Discord client tests for preserved compose batch size and independent generation payload
- [x] 5.2 Opt Discord generation into independent mode without changing commands, controls, acknowledgement, or parent lookup
- [x] 5.3 Add and pass result tests for all parent `SaveImage` files, preview exclusion, and mixed-outcome warnings

## 6. Non-live verification and documentation

- [x] 6.1 Pass all focused backend queue, recording, artifact, and generate API tests
- [x] 6.2 Pass the full backend suite, documenting any unchanged baseline failure separately
- [x] 6.3 Pass the full Discord Bot suite
- [x] 6.4 Pass repository type/static checks, strict target/all OpenSpec validation, and `git diff --check`
- [x] 6.5 Complete scoped review for identity/status, durability, sibling continuation, collisions, uniqueness, cancellation/capacity races, slot leaks, secret persistence, and shared compatibility; add RED regressions for every blocker
- [x] 6.6 Update `docs/PROGRESS.md` with exact non-live evidence and remaining live gates

## 7. Controlled live gates and delivery

- [ ] 7.1 After separate CTY approval, deploy/restart only while Backend and ComfyUI queues are idle and run the approved real four-image Discord E2E
- [ ] 7.2 After all approved live gates pass, archive the OpenSpec change and revalidate authoritative specs
- [ ] 7.3 After separate delivery approval, integrate and push while preserving the live main worktree
