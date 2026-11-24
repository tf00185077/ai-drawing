# Bounded wait implementation plan

Goal: deliver the cleared D1–D5 in [task.md](task.md), based on
`a88b84a50ef46ff34a89cd1f85c7911963ced379`. Execution is authorized inline by
AID-163; independent delivery QA is AID-164. No routine approval is pending.

Architecture: one async read intent, real existing Backend HTTP readers, and
one monotonic deadline. Add an async GET to the existing client without changing
its synchronous callers. Keep locator validation in a focused MCP module and
reuse the existing public training projection. No Backend or dependency change.

Constraints: preserve immutable task/decision/kickoff inputs and registry; keep
generation/training and image/artifact namespaces distinct. Client timeout is
unverified; use the approved 50-second overall fallback. No submission,
cancellation, migration, file copying, runtime replacement or main publication.

Review focus: encoded traversal and symlink escape; mixed available/unavailable
identities; successful training reads of failed jobs; independent legacy smoke;
slow first read, fallback and streamed body consuming the same deadline.

1. Pin source/imports and establish baseline using scratch-only test tooling
   and fresh cross-layer exports. Preserve command receipts.
2. Write registered transport tests in `test_wait_for_job.py`; observe RED for
   missing discovery. Cover complete/failed/cancelled/pending jobs, all locator
   classes, identity/provenance, public training/smoke and bounded slow reads.
3. Add `HttpBackendClient.get_async`, `media_locators.py`, and
   `tools/wait_for_job.py`; register only wait=read. Run targeted GREEN.
4. Extend independent literal risk assertions from 29 to 30, adapt the existing
   generic transport fixture for async reads, and update current MCP flow docs.
5. Run full MCP and affected Backend/contract checks with isolated roots and
   per-test timeout. Verify P1 assertions with deliberate production faults,
   restore source and run final GREEN. Preserve all nine registry guards.
6. Commit source/tests/docs/manifest/evidence, then build external final-SHA
   receipt, indexed packet, binary patch and verified Git bundle. Upload to
   AID-163 and mark Coding done to release native dependent QA. No QA PASS claim.
