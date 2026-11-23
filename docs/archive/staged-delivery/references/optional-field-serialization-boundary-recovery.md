# Imported historical source

Source: `autonomous-staged-change-delivery/references/optional-field-serialization-boundary-recovery.md`. Original SHA-256: `881a7db1ffb8b62edae96d9e0a23df790bc359ebc00eae0b00429a5c3f28faa8`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Optional-field Serialization Boundary Recovery

Use when a strict backend distinguishes an **omitted field** from an explicit JSON `null`, but an MCP/Pydantic wrapper silently turns an omitted optional value into `null`.

## Failure shape

- Client input validates locally because an optional model field defaults to `None`.
- The wrapper calls ordinary `model_dump()` on the model or a parent model.
- JSON sent to the backend contains `"value": null` even though the caller omitted `value`.
- The strict backend correctly rejects the request before durable creation or side effects.

This is an integration/serialization defect, not a reason to weaken the backend contract.

## Owner repair recipe

1. Preserve the blocked executor result and verify the failed call created no durable object or external side effect.
2. Trace the exact representation across: formal MCP input → Pydantic model → wrapper dump → HTTP JSON → backend request schema.
3. Add a RED wrapper-boundary regression that captures the exact posted body. Include both:
   - a directive whose explicit value must survive; and
   - a preserve/absence directive whose key must be absent, not `null`.
4. Fix the narrow serializer, for example with a directive-specific `model_dump(exclude_none=True)` helper. Avoid applying `exclude_none` globally to unrelated models because explicit null semantics may differ elsewhere.
5. Reuse the narrow serializer at every wrapper that transports that same contract (for example single-child and variation-set facades).
6. Run focused wrapper tests, the complete separately packaged client suite, and `git diff --check`.
7. Commit only Owner production/regression scope. Preserve executor evidence/fixture/PROGRESS dirty scope untouched.
8. Append a bounded recovery stage under the dispatcher lock. Give it a new failure signature, fresh attempt identity, exact adopted dirty baseline, and explicit one-call side-effect budget.
9. Dispatch through the formal control-plane entrypoint and verify durable `ACTIVE/RUNNING`, fresh run ID, prompt/log/result paths, and unchanged historical attempts.

## Evidence assertions

- Posted JSON contains explicit replacement values unchanged.
- Posted JSON omits absent preserve values entirely.
- Backend strict validation remains unchanged and fail-closed.
- Prior attempt records retain their original zero-side-effect facts.
- Recovery stage does not use free-form owner text to override the failed contract.

## Pitfalls

- Treating `None`, omitted, and JSON `null` as interchangeable.
- Fixing the strict backend to accept `null` when its contract intentionally requires absence.
- Calling `exclude_none=True` on an entire heterogeneous request without checking fields where explicit null is meaningful.
- Repairing only the wrapper that exposed the bug while leaving another facade on the same serializer path.
- Committing preserved executor evidence together with the Owner repair merely to clean the worktree.
