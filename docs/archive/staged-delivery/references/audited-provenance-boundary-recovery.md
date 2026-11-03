# Imported historical source

Source: `autonomous-staged-change-delivery/references/audited-provenance-boundary-recovery.md`. Original SHA-256: `fdbe84b652008bd93a81a5315b17a3e229497690751801f3ef46f27887ba4818`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Audited Provenance Boundary Recovery

Use when a frozen worker correctly blocks because an authoritative downstream gate cannot find evidence that was already captured upstream.

## Failure shape

A provider/install path persists an audited attribute, but an intermediate producer drops it before a strict consumer. Typical chain:

`authoritative provider payload → redacted persisted snapshot → backend-owned ledger → resolution actual identity → immutable resource lock → strict API schema → compatibility decision`

The aggregate suites may remain green because tests construct synthetic reports containing the missing field rather than exercising the real producer chain.

## Owner procedure

1. Preserve the blocked executor result and exact dirty evidence scope.
2. Reproduce at the public boundary and confirm the stable fail-closed diagnostic.
3. Locate the authoritative persisted source. Do not infer immutable/audited facts from display names, paths, short hashes, or caller claims.
4. Add one RED integration regression that creates/persists the authoritative metadata and then invokes the real ledger/resolver path. Assert the evidence appears in both the resolution identity and immutable lock and is accepted by the strict consumer.
5. Propagate the field through every typed representation, including strict producer/consumer schemas. A service-only fix can still produce HTTP 422 if the request schema rejects the new authoritative field.
6. Normalize only explicitly supported provider vocabulary. Missing, malformed, or unsupported values remain absent with stable diagnostics so the downstream gate fails closed.
7. Run focused boundary tests, the full backend/client/control-plane suites, and diff checks.
8. If production/test files are separable from preserved executor evidence, commit only Owner scope. Never absorb the executor's evidence files into the Owner commit.
9. Under the dispatcher lock, append a new recovery stage with a new failure signature and exact preserved dirty scope. Preserve the failed stage and attempt unchanged.
10. Invoke the formal dispatcher and reload durable state. Verify goal ACTIVE, recovery stage RUNNING (or another legitimate state), a fresh run ID, and unchanged adopted scope.

## Adverse cases

- malformed persisted JSON does not crash or become trusted evidence;
- non-string or unsupported family/type values do not propagate;
- secrets in persisted snapshots remain redacted;
- no filename/path inference;
- strict schemas permit the exact authoritative field but still forbid unknown extras;
- a missing field retains the original fail-closed behavior;
- no direct database patching or manual identity row insertion.

## Completion evidence

Record the RED failure, repair commit, focused/full test counts, formal recovery event, and fresh dispatcher-created run identity. A PID alone is not sufficient.
