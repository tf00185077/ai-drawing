# Imported historical source

Source: `autonomous-staged-change-delivery/references/runtime-preflight-and-existing-artifact-recovery.md`. Original SHA-256: `0658ad31498f55e85b225f573a10f564365940c15eb04f37d37b7188f8a31455`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Runtime Preflight and Existing-Artifact Recovery

Use when a frozen live-acceptance stage fails before submission because the deployed service is from the wrong worktree, required routes are absent, or the correct deployment has no authoritative identity record for a file already present locally.

## Classification sequence

1. Preserve the blocked attempt and its zero-side-effect evidence.
2. Distinguish two independent signatures:
   - **runtime deployment defect**: healthy process, wrong worktree/build, missing route;
   - **product integration gap**: correct service is live, but an existing verified artifact cannot enter the backend-owned identity ledger without redundant acquisition.
3. Start or reload the correct worktree service on a separate free port; do not kill unrelated user services merely to reuse their port.
4. Verify health **and exact required routes** from OpenAPI or equivalent registration evidence. Health alone is insufficient.
5. Exercise the formal client/MCP boundary against that service and inspect the authoritative ledger before allowing any irreversible submission.

## Existing artifact identity

A filename, short hash, or public API lookup alone is not ledger identity. If a local file's full digest resolves to immutable public model/version/file IDs but the formal install service rejects it only because the destination already exists, classify this as a contract/product gap rather than manually inserting a database row.

A bounded recovery may add **verified existing-file adoption** only if all of these remain enforced:

- canonical inspect/select descriptor;
- immutable provider model/version/file IDs;
- streamed full-file SHA-256 and exact byte size;
- regular file, root containment, and no symlink traversal;
- scan, license, availability, and usage gates;
- zero transport/download and zero file mutation;
- transactional, redacted, idempotent ledger persistence;
- mismatch and unsafe paths produce zero ledger mutation.

Write RED tests for exact adoption and an adverse matrix (hash/size mismatch, symlink, non-file, unsafe root/metadata, identity conflict, secret sentinel). Keep the ordinary absent-target safe-download path green.

## Live schema/build staleness

A process may have the correct worktree CWD and all required routes yet still be stale because it imported production schemas before an Owner repair landed. Treat this as a distinct **runtime deployment staleness** signature, not a recurrence of the repaired product defect. Compare the process start time with the repair commit time: a process that predates the commit is stale even when current HEAD, CWD, health, and route registration all look correct. After restart, read back the exact repaired semantic field through the public live boundary; health or OpenAPI presence alone is insufficient.

1. Preserve the blocked attempt and prove zero submission/side effects.
2. Compare the live OpenAPI (or equivalent public schema) at the exact failed producer-consumer boundary with the repaired source contract. Route presence alone is insufficient; assert the exact required identity fields and strictness behavior.
3. Identify the listener and its launch context. Restart only the intended worktree service, preserving required environment variables and avoiding unrelated listeners.
4. Poll readiness, then independently read back the live schema and assert the repaired fields before opening recovery. A new PID or healthy endpoint is not enough.
5. Re-run the formal client preflight from zero; never reuse the prior compatibility response or treat reload as permission to submit.

If reload changes the failure signature from product/integration to deployment staleness, append a fresh bounded recovery stage. Do not generic-resume the blocked attempt or overwrite its result.

## Recovery structure

Do not blindly resume the live stage after correcting only the deployment. If the authoritative ledger is still empty, create an append-only preparation/recovery stage with the new combined signature. Its scope should repair and prove identity establishment only; generation remains forbidden until a later formal transition.

Adopt an existing dirty documentation/evidence scope only after exact allowed-file comparison. Persist the new recovery under the dispatcher lock, set the goal active, invoke the dispatcher entrypoint, and verify the fresh run identity plus durable RUNNING/legitimate reconciled state. The recovery contract should record the independently verified live schema/build prerequisite and require the executor to repeat all preflight checks from zero. A running backend PID is supporting evidence, not the pipeline transition.
