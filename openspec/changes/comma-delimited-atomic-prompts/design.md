## Context

The current system has three incompatible notions of a fragment:

- `compositionState.rebuild()` trims card text, filters blank cards, and inserts `", "` between rendered cards.
- Direct editing of a final textarea preserves its visible value but replaces all cards with one literal, so commas no longer represent card boundaries.
- Backend `PromptFragment` correctly rejects blank snapshots, while `PromptComposer` additionally strips commas/outer whitespace and filters empty rendered values.

The shipped Prompt Library is not atomic. A repository audit found:

| Inventory | Current value | Comma-atomic projection |
|---|---:|---:|
| Source entries | 297 | 683 raw `split(",")` atoms |
| Entries containing ASCII comma | 146 | 0 after migration |
| Blank/whitespace atoms in source entries | 0 | 0 |
| Saved combinations | 4 | 4 |

The four combinations are `character` (2 positive atoms), `niji基礎瑟瑟` (10 positive and 15 negative atoms), `portrait-detail` (5 positive atoms), and `portrait` (4 positive atoms). They currently store comma-bearing literal fragments and project to 36 atomic fragments in total with no blank atoms.

The removed one-time LTJ importer preserved each LTJ prompt string as one entry, generated IDs with traversal-order numeric suffixes, and supplied a shared source label. That approach created the current multi-token entries and cannot provide stable reruns, curated per-token labels, one-to-many reference repair, or rollback. The new migration operates on the self-contained Prompt Library; LTJ is not a runtime dependency.

The latest product decision keeps Backend blank validation strict. Empty slots created while typing are valid transient editor state only. They cannot be saved, composed through the API, or generated.

## Goals / Non-Goals

**Goals:**

- Make U+002C the only and unconditional prompt boundary everywhere in the Workbench and Prompt Library.
- Preserve the exact raw segment strings and delimiter count through edit, card operations, load, save, update, Save As, compose, and reload.
- Keep final textareas continuously editable while cards update immediately and caret/selection remain stable.
- Preserve real source provenance, but never infer a source ref from typed text.
- Migrate all current source entries and combinations before enabling the editor.
- Make the migration deterministic, curated, idempotent, reversible, concurrency-safe, and fail closed.
- Keep Backend rejection of blank/whitespace fragments and block invalid editor actions before network requests.

**Non-Goals:**

- Escaping commas, quote-aware parsing, parenthesis-aware parsing, CSV rules, or an alternate delimiter.
- Runtime translation, fuzzy provenance inference, LLM-assisted labels, or automatic semantic merging.
- Supporting a comma-bearing atomic source entry after rollout.
- Changing ComfyUI syntax, workflow defaults, model selection, queue behavior, or generation semantics beyond the submitted prompt strings.
- Running a service restart or live image generation while creating this OpenSpec change.

## Decisions

### 1. Deploy a fail-closed Backend gate before migration

The first production change is a migration-compatible Backend gate, not the data migration or frontend editor. On deployment it creates or recognizes a durable migration control marker with `state=required`, reports `comma_atomic_ready=false`, and exposes a catalog-independent status response.

While the marker is in `required`, `applying`, `incomplete`, `validating`, or `rolled_back_required`, every ordinary Prompt Library catalog-dependent operation fails closed with a structured service-unavailable error. The blocked surface includes catalog/list/search, category and entry reads, combination list/load, compose, category/entry/combination save, archive/restore, and their API/MCP equivalents. No ordinary request can observe a mixed old/staged/new catalog.

Only a local/operator-privileged migration capability may invoke audit/dry-run, apply, resume, rollback, validate, or finalize. Each privileged operation acquires the migration lock before reading live or staged Prompt Library state; it is not exposed as a general Workbench or MCP tool. The ordinary health endpoint remains available, and the migration status endpoint returns state/readiness only, never catalog contents.

The same deployed Backend contains the atomic enforcement mode, but readiness cannot become true merely because data files were migrated. After post-write validation, the Backend activates and self-tests comma-free entry-write enforcement plus canonical atomic compose/repair while the marker and ordinary-operation block remain. One guarded finalize transition may remove the marker and set `comma_atomic_ready=true` only if `atomic_enforcement_active=true` and all data gates still pass. Rollback restores pre-images but leaves a `rolled_back_required` marker and readiness false.

Alternative considered: migrate files first and deploy Backend enforcement afterward. It was rejected because an old Backend could write comma-bearing entries between migration and deployment or serve mixed data during an interrupted apply.

### 2. U+002C defines the grammar

For a non-empty lane, the editor derives segments only with JavaScript `raw.split(",")`. It does not scan nesting, quotes, escapes, weights, or balanced syntax. It reconstructs the lane only with `segments.map(segment => segment.raw).join(",")`.

Examples:

| Raw text | Segments |
|---|---|
| `a,,b,` | `["a", "", "b", ""]` |
| `,a` | `["", "a"]` |
| `"a,b"` | `["\"a", "b\""]` |
| `(a,b:1.2)` | `["(a", "b:1.2)"]` |

An entirely empty lane is represented as no prompts (`raw=""`, `segments=[]`) so an unused Negative lane remains valid. Any non-empty value, including whitespace-only text, has at least one segment and is validated normally. A single comma has two empty segments.

Full-width comma U+FF0C and other punctuation are ordinary characters. No escape syntax is introduced.

Alternative considered: top-level parsing that protects parentheses or quotes. It was rejected because the approved product model values a visible, universal delimiter over prompt-language interpretation.

### 3. Weighted segments and raw text have one authoritative model

Each lane keeps:

```text
rawText: exact textarea value
segments[]:
  uiId
  kind: entry | literal
  sourceRef/sourceRevision when genuine
  snapshotRaw: exact unweighted Backend snapshot
  weight: structured numeric weight
  renderedRaw: render(snapshotRaw, weight)
  displayLabel: derived presentation only
```

The Backend wire field `snapshot` is `snapshotRaw`. Rendering is defined exactly once: when `weight == 1`, `renderedRaw = snapshotRaw`; otherwise `renderedRaw = "(" + snapshotRaw + ":" + formatWeight(weight) + ")"`. The final textarea value is always `segments.map(segment => segment.renderedRaw).join(",")`.

On every final-textarea `onChange`:

1. Store `event.currentTarget.value` exactly as `rawText`.
2. Split that exact value into edited rendered atoms without trimming or filtering.
3. Reconcile cards after the raw value has been accepted; never feed a normalized string back into the same input event.
4. Compare edited atoms to the previous segments' exact `renderedRaw`, not to `snapshotRaw`, labels, or parsed weight syntax.
5. Preserve `snapshotRaw`, `weight`, UI identity, and genuine source metadata only for non-overlapping exact common-prefix and common-suffix `renderedRaw` matches.
6. Treat every changed middle rendered atom as a weight-1 literal whose `snapshotRaw` is the exact edited atom and whose `renderedRaw` therefore remains byte-for-byte identical. Do not parse apparent parentheses or weights from textarea text.
7. A one-to-one edited literal may retain its `uiId`, but an edited entry immediately loses its source ref.
8. Give new or ambiguous segments stable UI-local IDs and deterministic display labels.

Prefix/suffix matches consume each old card at most once. Duplicate text inside the changed region never preserves a ref by position. This prevents insertion or deletion from shifting a source identity onto unrelated text.

The textarea records `selectionStart`, `selectionEnd`, and `selectionDirection`. A layout effect restores the clamped selection only if React or a derived render moved it. IME composition keeps accepting the exact browser value; card derivation never rewrites it.

Card content edits update `snapshotRaw`; editing the content of an entry card demotes it to literal, while changing only weight preserves the entry ref and snapshot. Card edits, reorder, delete, entry insertion, and weight changes recompute `renderedRaw` and rebuild the lane with exact `renderedAtoms.join(",")`. Because those operations originate outside final-textarea typing, they do not participate in textarea caret restoration.

For example, loading `{snapshotRaw:"detail", weight:1.2, ref:...}` displays `(detail:1.2)`. Saving without a textarea change preserves all three structured fields. Editing the textarea atom to `(detail:1.3)` produces `{kind:"literal", snapshotRaw:"(detail:1.3)", weight:1}` with no ref; its visible value stays exactly `(detail:1.3)`.

Alternative considered: parse only on blur or require an Apply button. It was rejected because cards must reflect every comma immediately.

### 4. Empty cards are preserved editor state

Empty or whitespace-only raw segments render as ordinary paginated cards with:

- label `自訂文字`;
- an editable content field containing the exact raw value;
- an invalid/empty status;
- reorder and delete actions;
- its real position among all cards.

Pagination counts empty cards. Reorder moves the exact raw segment. Delete removes that segment and the one separator needed to join the remaining list; deleting the only segment returns the lane to `raw=""` and `segments=[]`. No card operation calls `filter(Boolean)`, `trim()`, or a delimiter-normalizing join.

### 5. Client preflight is the only path from transient blanks to actions

One shared preflight inspects both lanes before Save, Update, Save As, and Generate. It computes invalid positions with `segment.raw.trim() === ""`, using 1-based positions in each polarity.

If any invalid segment exists:

- the operation returns before `fetch`, compose, or generation helpers are called;
- no fragment is silently dropped, trimmed, or canonicalized;
- the error lists every affected polarity and position, for example `正向第 2、4 段；負向第 1 段`;
- the message states: `每個 ASCII 逗號都會建立一個 prompt；請填入內容或移除該空白段。`;
- the first invalid card is focused and its page is opened.

`raw=""`/`segments=[]` is an absent lane, not a blank fragment. A non-empty whitespace-only lane is invalid. Existing requirements such as a non-empty Positive prompt for generation remain separate.

Backend remains a second line of defense and MUST reject blank/whitespace fragment snapshots from any client.

### 6. Provenance and display labels are separate

A source ref exists only when:

- the user adds an entry from the Prompt Library;
- a saved combination contains a valid entry ref; or
- the migration registry deterministically expands a known legacy ref.

Directly typed text remains `kind=literal`, even when its normalized token uniquely equals a source entry. Catalog matching may choose a display label but never changes `kind`, `ref`, or `source_revision`.

Display lookup uses the raw token only for presentation:

1. A valid referenced entry uses non-empty trimmed `name_zh`.
2. A valid referenced entry without Chinese uses its trimmed English `prompt`.
3. A literal whose token has exactly one full normalized prompt match across all polarities, categories, and archive states uses that entry's `name_zh`, or its trimmed English prompt when Chinese is absent.
4. Empty, unresolved, or ambiguous tokens display the fixed fallback `自訂文字`.

Labels are presentation state only: they are neither editable nor serialized in a combination. Users edit the prompt content field. Every load recomputes labels from the current ref/catalog and exact normalized-match rules. Normalization for matching is Unicode NFKC, trim, whitespace collapse, and Unicode case folding. It never changes stored text. Substring, fuzzy, alias-only, or keyword-only matches cannot establish the label hierarchy. Duplicate English tokens or cross-category/cross-polarity candidates fail safe to `自訂文字`.

### 7. Backend stores and returns atomic fragments

Backend keeps the existing invariant `snapshotRaw.strip() != ""` (the wire field remains `snapshot`). It adds the comma-atomic invariant to canonical fragments and saved combinations: one `snapshotRaw` cannot contain U+002C.

Compatibility behavior is deterministic:

- New or existing Prompt Entry writes containing U+002C are rejected with an actionable `comma_not_atomic` error because Backend cannot curate names or metadata.
- Compose/save inputs containing a comma-bearing literal are split with Python `raw.split(",")` before resolution. If any resulting segment is blank/whitespace-only, the entire request is rejected; no partial result is returned.
- A legacy comma-bearing entry ref is expanded through the reviewed migration registry.
- A legacy comma-bearing literal is expanded into ordered literals.
- Every atom inherited from one weighted legacy fragment receives the original structured weight. Its `renderedRaw` is then derived independently, and the expansion emits a structured warning.
- Canonical responses and saved combination files contain only nonblank, comma-free fragments.

For `weight == 1`, rendering returns `snapshotRaw` byte-for-byte. For another weight, rendering wraps exact `snapshotRaw` as `(<snapshotRaw>:<weight>)`. Lanes are rendered with literal `",".join(renderedRaw_atoms)` and never strip or filter atoms. Exact source whitespace therefore round-trips.

The Backend response remains the canonical state installed after save. Frontend computes every returned fragment's `renderedRaw` from its returned `snapshot` and `weight`, then verifies that joining those rendered atoms reproduces the visible lane. Comparing or joining unweighted snapshots is incorrect. A mismatch is an error and does not clear dirty state.

Alternative considered: accept comma-bearing source entries and split only in the UI. It was rejected because MCP, external API clients, saved combinations, and lazy repair would still disagree.

### 8. Catalog migration uses exactly 532 reviewed per-token records

The migration command reads the current Prompt Library JSON without executing LTJ code. It creates curation records only for new atoms produced by exact `prompt.split(",")` of the 146 multi-token entries. Each multi-token source entry is removed only after its ordered derived entries and legacy-ref mapping are staged.

The current audited projection is exactly:

- 151 already-atomic entries retained;
- 532 atoms derived from 146 multi-token entries;
- 683 final entries;
- zero blank/whitespace atoms.

The curation worksheet MUST contain exactly 532 records—one for every newly derived atom and none for the 151 retained entries. The 151 already-atomic entries undergo invariant validation only (nonblank and comma-free) and retain their existing ID, prompt bytes, `name_zh`, `description_zh`, aliases, keywords, order, revision, and archive state.

Each of the 532 versioned curation records is keyed by:

```text
polarity/category_id/source_entry_id/source_prompt_sha256/segment_index
```

Each derived-atom record fixes the raw segment, `name_zh`, `description_zh`, aliases, keywords, and optional explicit canonical mapping. Runtime code does not call an LLM or guess a translation. Curators may deliberately reuse one `name_zh` for semantically equivalent tokens. Tokens with meaning differences, including distinct shirt types, require separate per-token Chinese names.

Any missing or extra worksheet record, raw/hash mismatch, blank atom, non-Chinese required label, retained-entry invariant failure, or unresolved semantic decision appears in the unresolved report and blocks apply.

### 9. Derived IDs and metadata are deterministic

Every new atom ID is based on the source locator and raw token, not traversal order:

```text
<bounded-source-id>-<bounded-token-slug>-<digest>
digest = SHA-256(polarity/category/source-id/source-prompt-hash/segment-index/raw-segment)
```

The lowercase ASCII token slug is presentation only; the digest carries identity. Generation starts with 8 hex characters. If an ID is occupied by the same recorded provenance and content, it is reused. If occupied by different provenance, the digest expands deterministically to 12, 16, then 64 characters. A collision at full digest or a collision with an unrelated pre-existing ID fails closed. Numeric `-2` suffixes based on iteration order are prohibited.

Metadata rules:

- Exact `prompt` is the untrimmed raw segment.
- Derived atoms receive curated aliases/keywords appended to inherited values and deduplicated by normalized comparison while preserving first lexical occurrence.
- Source archive state propagates to every derived atom.
- New derived atoms start at revision 1; every retained single-token entry keeps all existing metadata, including `order` and revision.
- Each affected category revision increments once per successful migration, regardless of atom count.
- Derived entries receive deterministic ordering based on the removed source entry position and segment index without changing any retained entry's `order`; equal order values use a stable source-position/segment-index tie-break.
- Category metadata, polarity, archive state, and unrelated fields remain unchanged.
- Combination metadata and archive state remain unchanged; each changed combination revision increments once.
- Etag remains the SHA-256 of final JSON bytes and changes only when bytes change.

An idempotent rerun against the migrated manifest plans zero writes, does not increment revisions, and leaves etags byte-identical.

### 10. One legacy ref expands to ordered derived refs

The migration registry records:

```text
legacy source locator -> [derived source locators in segment order]
```

When a saved combination references a migrated multi-token source entry:

- migration/repair replaces the one fragment with one `kind=entry` fragment per derived locator;
- every atom receives the derived source revision and exact source prompt;
- the original weight is copied to every atom;
- atoms occupy the original fragment's position before subsequent fragments;
- order values are deterministically renumbered;
- Backend returns `legacy_reference_expanded` with old ref, new refs, count, and weight policy.

The first expansion repairs the persisted combination and increments its revision/etag once. Later loads are idempotent and warning-free unless another source revision changed.

If the registry has no unique expansion:

- migration apply fails closed for repository-owned combinations;
- runtime load of an externally introduced legacy combination keeps the snapshot available, splits it into literals only when all atoms are nonblank, and returns `legacy_reference_unresolved`;
- the diagnostic includes the old ref, fallback atom hashes, combination revision/etag, and states that provenance was not transferred;
- the diagnostic remains blocking across ordinary content edits; it is not cleared by Save, Update, or Save As;
- Update and Save As fail unless the diagnostic is resolved by a newly reviewed mapping, explicit replacement source-entry selection, or an explicit acknowledge-convert-to-literals action;
- the acknowledge action obtains an opaque Backend token bound to combination ID, source revision/etag, diagnostic IDs, and fallback atom hashes. Backend requires and validates that token on conversion persistence; ordinary edit/save cannot mint or substitute it;
- automatic lazy persistence is disabled until one of those explicit resolution paths succeeds.

No fragment is silently discarded. Duplicate derived refs are not collapsed during migration; if normal compose duplicate-ref policy would remove one, migration reports it as blocking instead.

### 11. Migration is staged, guarded, and reversible

The command has `audit`, `dry-run`, `apply`, and `rollback <run-id>` modes.

`audit` and `dry-run` are read-only. The machine-readable report includes:

- source and post-migration counts;
- all 146 source locators and 532 derived atoms;
- all four combination IDs and their 36 projected fragments;
- document etags and revisions;
- ID allocations and collision decisions;
- curated mapping coverage;
- legacy ref expansions and warnings;
- unresolved items;
- planned creates, replacements, and removals;
- expected post-write hashes.

Apply is allowed only when the report matches the reviewed repository baseline (297, 146, 683, zero blanks, four named combinations), has zero unresolved/collisions, and all source etags still match. It acquires the Prompt Library write lock, writes exact pre-image bytes plus checksums to a run-specific rollback directory, stages and validates every destination document, then uses atomic replacements.

The Backend gate's marker exists before audit begins and remains throughout apply and validation. While it exists, every ordinary catalog-dependent read and write fails closed; only the privileged migration path under its lock can read live/staged state. If the process stops mid-apply, startup/readiness reports `comma_atomic_migration_incomplete`; operators must use privileged resume or rollback. Ordinary list/search/read/load/compose/write traffic never receives partial or mixed data.

Post-write gates re-read from disk and require:

- manifest atomic version active;
- zero comma-bearing or blank source entries;
- exactly 683 entries for this baseline;
- all combinations atomized and nonblank;
- all repository refs resolvable with zero blocking document diagnostics;
- revisions/etags matching the plan;
- a second dry-run with zero changes.

Passing data gates does not remove the marker or set readiness true. The Backend must next activate atomic enforcement and prove that comma-bearing/blank entry writes are rejected and canonical weighted compose/repair uses `snapshotRaw`, `weight`, and `renderedRaw` correctly. Only the privileged finalize operation may then remove the marker and publish readiness true in one guarded transition.

Rollback restores exact pre-image bytes only when current etags equal the recorded post-image etags. A later edit causes rollback to fail rather than overwrite it. Rollback also uses staged validation, atomic replace, and the write lock. Successful rollback moves the marker to `rolled_back_required`; it does not remove the marker, reopen ordinary operations, or publish readiness true.

### 12. Editor enablement follows Backend-finalized readiness

The catalog-independent migration status exposes readiness and `atomic_enforcement_active`. The frontend does not call catalog endpoints or render the Prompt Workbench while readiness is false. The new editor behavior is enabled only when the Backend reports readiness true, atomic enforcement active, no marker, and no blocking migration diagnostics.

Deployment order is fixed:

1. Deploy the migration-compatible Backend gate; create/recognize the marker, publish readiness false, and verify every ordinary API/MCP catalog operation fails closed.
2. Use only the privileged locked path to audit/dry-run and review exactly 532 curated derived-atom records plus retained-entry invariants.
3. Back up, apply/resume, validate, and prove idempotency while keeping the marker and ordinary-operation block.
4. Activate and test atomic Backend entry-write enforcement and canonical weighted compose/repair while the marker remains.
5. Run privileged finalize, which rechecks data/enforcement and atomically removes the marker plus publishes readiness true.
6. Enable the frontend editor and preflight only after observing the finalized status.

There is no supported mixed mode where any ordinary API/MCP client reads old, staged, partially migrated, or migrated-but-not-enforced catalog data.

### 13. Verification strategy

Focused tests cover pure split/join, prefix/suffix identity reconciliation, caret selection, labels, duplicate ambiguity, empty-card operations, preflight, Backend validation/rendering, deterministic IDs, collision expansion, mapping coverage, ref expansion, revisions/etags, idempotency, interruption, and rollback.

Full verification includes:

- complete Backend tests;
- complete Frontend tests and TypeScript typecheck;
- complete MCP tests where Prompt Library contracts are exposed;
- Vite production build;
- migration dry-run against a fixture matching the audited repository inventory;
- real browser round trip: type, reorder, delete, save, load, update, Save As, and inspect generation request construction.

Browser acceptance must exercise `a,,b,`, leading comma, quotes, parentheses, weighted comma text, a non-1-weight referenced fragment through load/save/reload, textarea demotion of a changed weighted atom, source insertion, direct typed catalog-equivalent text, duplicate English tokens, blocking unresolved diagnostics/resolution actions, and all preflight actions. It must not restart services or submit live image generation as part of this change's acceptance run.

## Risks / Trade-offs

- **[Comma inside prompt syntax is always destructive to grouping]** → Document the rule beside the editor and test quotes, parentheses, and weights explicitly; do not add hidden exceptions.
- **[Curated mapping volume is large]** → Require exactly 532 derived-atom records, reject extras/missing records, and invariant-check the 151 retained entries without remapping them.
- **[Whitespace-preserving atoms can look unusual when selected alone]** → Keep exact prompt content for round-trip; use trimmed text only for labels/search and allow later explicit catalog edits with normal revision semantics.
- **[One-to-many refs change weight scope]** → Copy weight to every atom and emit a structured expansion warning; never pretend the old group weight survived unchanged.
- **[Multi-file apply can be interrupted]** → Stage all files, keep exact pre-images, use a marker and lock, and require resume/rollback before readiness.
- **[Duplicate English tokens can mislabel literals]** → Require a unique exact normalized match across the complete catalog or show fixed `自訂文字`; recompute rather than persist labels.
- **[Fail-closed migration blocks normal Prompt Library use]** → Deploy the status/privileged recovery gate first, make the outage explicit, and keep resume/rollback available under the lock.
- **[Unresolved fallback can launder lost provenance through Save As]** → Keep a Backend-enforced blocking diagnostic and require mapping, replacement refs, or an opaque explicit conversion token.
- **[Frontend validation could be bypassed]** → Retain Backend blank rejection and canonical atomic validation.
- **[Rollback could overwrite post-migration edits]** → Require recorded post-image etags before restoring any file.

## Migration Plan

1. Implement and deploy the migration-compatible Backend gate, privileged locked path, durable marker, readiness=false status, and fail-closed ordinary API/MCP behavior.
2. Implement audit/dry-run, deterministic IDs, collision handling, exactly-532-record curation validation, retained-entry invariant checks, ref expansion, staging, rollback, and idempotency tests.
3. Produce and manually review the 532 derived-atom Chinese records and unresolved report; run dry-run until clean and stable.
4. Apply/resume under the marker and lock with pre-image backups; keep all ordinary operations blocked.
5. Run post-write gates and a zero-diff second dry-run without removing the marker.
6. Activate and test Backend atomic entry-write and canonical weighted compose/load/save/repair enforcement.
7. Privileged-finalize only after data and enforcement gates pass; atomically remove the marker and publish readiness true.
8. Enable frontend segmentation, weighted reconciliation, fixed labels, blocking-diagnostic resolution, blank preflight, and document flows.
9. Run focused/full suites, production build, and browser request-only round trip.

Rollback uses the migration command and recorded run ID. It is permitted only before any affected document diverges from its recorded post-image etag.

## Open Questions

None. The curated Chinese text is implementation data that must pass the review gate, not a runtime or design decision.
