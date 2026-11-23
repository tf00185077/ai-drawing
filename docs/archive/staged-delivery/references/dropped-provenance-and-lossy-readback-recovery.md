# Imported historical source

Source: `autonomous-staged-change-delivery/references/dropped-provenance-and-lossy-readback-recovery.md`. Original SHA-256: `65e5445fcf8419b9bd64dbf8ad5ab2ae95d27cd41e9bf1a2efb87eeb34f4bd5a`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Dropped Provenance and Lossy Read-Back Recovery

Use when a live acceptance run completes its irreversible side effect, but the formal client cannot expose a job-bound artifact identity or independently recomputable provenance components.

## Failure classification

Treat these as two related integration/product defects:

1. **Lossy read-back boundary** — the backend owns structured artifact identity, but the formal client returns only a human summary or omits immutable linkage such as `job_id`, artifact ID, and canonical path.
2. **Dropped provenance boundary** — the producer computes canonical component documents and their digests, but persists/exports only digests. A later verifier cannot independently recompute the hashes.

A successful job, gallery row, or aggregate export does not close acceptance if the formal public boundary cannot read back the required identity and component documents.

## Investigation path

1. Preserve the blocked executor result and exact dirty scope.
2. Compare the live backend response with the formal MCP/client response to isolate where structure is lost.
3. Trace every required digest back to the point where its authoritative document is constructed.
4. Check whether each document survives through response schema → durable member/ledger storage → aggregate export → formal client.
5. Distinguish data that still exists authoritatively from data that was never persisted.

## RED matrix

Add explicit regressions proving:

- gallery/list output is machine-readable and includes immutable job-bound identity;
- aggregate export binds each member to artifact ID, job ID, and canonical result path;
- all required canonical component documents are persisted alongside their declared hashes;
- the aggregate self-hash covers gallery identity, component documents, event history, and member lineage;
- mutating any identity, component, or digest fails verification;
- secret redaction occurs before hashing/export.

## Minimal repair pattern

- Expose missing immutable identity at the backend schema and formal client boundary; do not make agents parse display text.
- Return authoritative provenance component documents from the producer that already computed them.
- Persist those documents with the durable member identity before later export.
- Include job-bound gallery identity and validated gallery provenance in the aggregate export.
- Keep old records readable without pretending they contain newly introduced evidence.

## Historical artifact rule

If an old completed artifact predates provenance persistence, do **not** backfill missing canonical documents from filenames, mutable caller assertions, a manually assembled fixture, or direct database edits. Hashes alone cannot reconstruct their preimages.

After the Owner repair:

1. commit only the isolated Owner production/regression scope;
2. preserve the blocked executor evidence unchanged;
3. create a fresh append-only bounded recovery stage;
4. explicitly authorize only the minimum new side effect needed to produce a record under the repaired producer contract;
5. retain the old successful artifact/set as historical evidence and prohibit mutation or disguised rerun of it;
6. prove the next durable dispatcher-created run identity.

## Runtime verification

When the repaired backend process was started before the Owner commit, restart it through the normal runtime path. Then exercise the actual formal client (for example stdio MCP), not just direct HTTP, and read back the exact structured identity fields before dispatching recovery.

## Pitfalls

- Treating a completed image as proof that delivery/provenance acceptance is complete.
- Fixing only the display/list wrapper while component documents are still dropped upstream.
- Adding documents to a transient response but not durable member storage.
- Retroactively claiming old records contain evidence that was never persisted.
- Reusing the original no-retry/no-rerun budget through owner prose; create a bounded recovery stage instead.
- Committing preserved executor fixture/evidence files as part of the Owner production repair.
