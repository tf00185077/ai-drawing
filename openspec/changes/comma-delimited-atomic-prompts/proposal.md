## Why

Prompt Library entries and Workbench fragments currently mix comma-delimited prompt lists with single selectable items: 146 of the 297 shipped entries contain ASCII commas, while the editor either normalizes delimiters away or collapses a direct edit into one literal. This makes card identity, source references, caret behavior, saved combinations, and generation payloads disagree about what one prompt is.

## What Changes

- **BREAKING**: define every ASCII comma U+002C as an unconditional prompt boundary. Parentheses, weight syntax, and quotes do not protect commas; there is no escaping or CSV-style exception.
- Preserve editor segments with `raw.split(",")`, including original whitespace and leading, trailing, or consecutive empty slots, and reconstruct visible text from the original segment strings with `join(",")`.
- Keep the final Positive and Negative textareas directly editable and update atomic cards immediately without replacing the controlled value in a way that moves the caret.
- Define one weighted segment model: `snapshotRaw` is the exact unweighted Backend snapshot, `weight` is structured metadata, `renderedRaw=render(snapshotRaw, weight)`, and final text is `renderedAtoms.join(",")`. Textarea reconciliation compares exact `renderedRaw`; editing a rendered atom demotes it to a weight-1 literal whose `snapshotRaw` is the exact edited segment.
- Keep Backend validation strict: persisted or composed fragments whose snapshots are blank or whitespace-only remain invalid.
- Add client-side preflight for Save, Update, Save As, and Generate. It blocks before any network request when temporary empty or whitespace-only slots exist, reports polarity and 1-based positions, and explains that every comma creates a prompt which must be filled or removed.
- Define deterministic, non-persisted display labels without inventing provenance: referenced entries and directly typed tokens with one unique exact catalog match use `name_zh`, then trimmed English; unresolved, ambiguous, or empty tokens display the fixed fallback `自訂文字`. Users edit prompt content, not a custom label, and labels are recomputed on load. A direct text match may borrow only the display label and never creates a source ref.
- Deploy a migration-compatible Backend gate before touching data. It reports readiness false and, whenever migration is required/in progress/incomplete, blocks all ordinary Prompt Library API/MCP reads and writes, including catalog/list/search/category/entry reads, combination load, and compose. Only privileged migration audit/dry-run/apply/resume/rollback operations may access staged state under the migration lock.
- **BREAKING**: migrate the Prompt Library before enabling the new editor. Split every comma-containing source prompt into comma-free atomic entries, preserve raw token text, curate per-token Chinese labels where meanings differ, and emit unresolved reports instead of using runtime LLM translation.
- Preserve source history and operability through stable derived IDs, collision rules, revisions, etags, archive state, aliases, keywords, ordering, idempotent reruns, dry-run reports, rollback artifacts, and fail-closed rollout gates.
- Repair old saved combinations and one-to-many source references without silently losing provenance. An unresolved legacy ref is a blocking document diagnostic: Update and Save As remain rejected until reviewed mapping, explicit replacement-source selection, or an explicit Backend-issued acknowledge-convert-to-literals token resolves it. Ordinary edit/save is not acknowledgment.
- Cover empty-card UX, pagination, reorder/delete, dirty guards, load/save/update/save-as round trips, generation request construction, focused/full tests, production build, and real browser round-trip acceptance. This change does not require a service restart or live image generation during proposal work.

## Capabilities

### New Capabilities

- `comma-atomic-composition`: ASCII-comma segmentation, lossless editor state, labels, card interactions, preflight blocking, document flows, and generation-request behavior.
- `atomic-prompt-library-catalog`: comma-free source-entry invariants and deterministic, curated, reversible catalog import/migration.
- `atomic-prompt-combination-persistence`: Backend fragment validation, atomic compose/load/save semantics, source-reference expansion and repair, warnings, and round-trip persistence.

### Modified Capabilities

None. Prompt Library and Workbench behavior is currently authoritative in project design documents and product contracts but has no corresponding main OpenSpec capability under `openspec/specs/`.

## Rollout

1. Deploy the migration-compatible Backend gate first. It creates/recognizes a migration-required marker, reports readiness false, blocks all ordinary catalog-dependent API/MCP operations, and exposes only the privileged locked migration path.
2. Through that privileged path, audit and dry-run the current 297-entry catalog and four combinations; require exactly 146 comma-containing entries, 683 projected atoms, and zero blank atoms.
3. Review exactly 532 curated records for atoms newly derived from the 146 multi-token entries. Validate, but do not remap or rewrite metadata for, the 151 retained atomic entries. Resolve every blocking ambiguity, collision, and legacy ref.
4. Back up affected documents, then apply/resume the catalog and combination migration under the marker and lock. Keep readiness false and keep all ordinary reads/writes blocked.
5. Run comma-free, referential-integrity, idempotency, revision/etag, weighted round-trip, and rollback gates while the marker remains.
6. Activate and verify atomic Backend enforcement, including comma-free entry writes and canonical weighted compose/repair. Only then may one guarded finalize transition remove the marker and set readiness true.
7. Enable the frontend comma-atomic editor and its client preflight only after the Backend reports both readiness true and atomic enforcement active.

## Risks

- A naive split can attach a misleading shared Chinese label to semantically different tokens, especially clothing and anatomy terms; curated per-token mappings and unresolved blocking reports mitigate this.
- Stable-ID derivation can collide when different source entries yield the same normalized token; deterministic namespace and suffix rules must prevent nondeterministic IDs.
- One legacy source ref can become several refs, so order, weight, source revision, warnings, and later source updates require explicit one-to-many semantics.
- Unconditional comma splitting is intentionally incompatible with comma-bearing weighted expressions or quoted phrases. The simplicity is deliberate and must be visible in UI help and acceptance tests.
- The fail-closed migration window temporarily makes Prompt Library catalog-dependent reads and writes unavailable. A dedicated status response and privileged resume/rollback path make that outage explicit and recoverable.
- Removing the marker before atomic Backend enforcement would reopen mixed behavior. Finalization therefore binds enforcement-active, marker removal, and readiness true in one guarded transition.

## Non-goals

- No comma escaping, backslash syntax, CSV quoting, quote-aware parsing, or parenthesis-aware parsing.
- No runtime LLM translation, probabilistic token matching, or automatic provenance inference from directly typed text.
- No change to Backend acceptance of blank or whitespace-only fragments; temporary empty slots are an editor-only state and are never sent.
- No change to ComfyUI prompt grammar, weight syntax, generation engines, model selection, or workflow defaults.
- No live generation in acceptance for this change; browser verification stops after confirming the constructed generation request.
- No product-code modification, archive operation, service restart, commit, or `docs/PROGRESS.md` update as part of authoring this proposal.

## Impact

- Frontend: `compositionState`, `PromptWorkbench`, `PromptComposerPanel`, entry-label resolution, saved-combination toolbar, generation preflight, and their tests.
- Backend: migration readiness gate, privileged migration path, fail-closed API/MCP access, Prompt Library models/schemas, composer, writer/repair path, blocking diagnostics/resolution tokens, and focused tests while retaining strict blank-fragment rejection.
- Data/tooling: all `prompt_library/positive`, `prompt_library/negative`, and `prompt_library/combinations` documents plus a deterministic LTJ/catalog migration command and fixtures.
- Operations: migration inventory, dry-run and rollback artifacts, curated mapping ownership, unresolved report review, fail-closed rollout gates, production build, and browser round-trip evidence.
