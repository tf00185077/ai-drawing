# Imported historical source

Source: `autonomous-staged-change-delivery/references/authoritative-external-metadata-recovery.md`. Original SHA-256: `ea4ea9b00c19c804fd0c1298cbc3e8a64b6c4beb495d0b63ed54793c61d58cb4`.

Historical and version-sensitive; not current project policy, status, or authorization. Revalidate against this project's current entrypoint and authoritative records before any separately authorized execution. Original language is preserved below.

---

# Authoritative External Metadata Recovery

Use when a frozen live acceptance is blocked because a real provider payload does not match the fields assumed by an offline fixture, even though the external artifact identity is independently verified.

## Classification

Treat this as a **product/integration normalization defect**, not automatically as a human-only authorization gate, when:

- the provider exposes authoritative public metadata through another canonical endpoint or payload level;
- existing safety policy can be derived without guessing or weakening gates;
- the local artifact has an independently verified full digest and size;
- recovery can preserve zero-download and zero-generation side-effect budgets.

Escalate only if policy metadata truly requires unavailable authentication, payment/legal consent, or a new product decision.

## Recovery procedure

1. Preserve the blocked stage, result, review, and dirty scope unchanged.
2. Capture the exact live provider payload from the canonical public endpoint and compare it with the test fixture field-by-field.
3. Add a RED regression using the provider's real payload shape. Prefer a minimal synthetic fixture that retains exact field names, nesting, and types.
4. Normalize only explicit authoritative fields:
   - require complete expected fields and strict types;
   - keep absent or malformed policy fail closed;
   - produce a deterministic canonical representation;
   - retain legacy canonical inputs only when they remain valid contract inputs.
5. Run focused tests, full validators, and a direct normalization probe against the captured real payload.
6. Exercise the formal client boundary end-to-end. For existing-artifact adoption, prove inspect → select → install/adopt → ledger read-back, including full digest, byte size, canonical IDs, and zero transport.
7. If runtime configuration selects the wrong storage root or deployment, restart the correct worktree process with explicit non-secret path configuration and verify process/route provenance before retrying the formal boundary.
8. Create an append-only bounded recovery stage with a new failure signature, exact safe dirty scope, and acceptance IDs for both normalization and real-path read-back. Dispatch only through the formal dispatcher and verify the durable run identity.

## Evidence gates

- RED failure demonstrates the fixture/provider disagreement.
- Missing/malformed policy remains rejected.
- Real canonical payload normalizes and selects successfully.
- Existing artifact is streamed for full digest and exact size before ledger adoption.
- Read-back returns exactly one immutable identity.
- No download, overwrite, file mutation, raw database write, generation, or failed-history rewrite occurred.

## Pitfalls

- Do not treat a fixture-only `license` or `usage` field as proof that the provider emits it at that nesting level.
- Do not invent a license label. Canonically preserve the provider's explicit permission fields and identify their source.
- Do not infer availability merely from a filename or digest; use explicit provider availability/status evidence.
- Do not call a version endpoint when the required policy is authoritative only on the model endpoint unless the route explicitly and safely joins those canonical identities.
- A healthy backend is not enough: verify its configured storage roots before concluding an existing file is absent.
