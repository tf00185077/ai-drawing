## ADDED Requirements

### Requirement: Backend rejects blank fragments in every contract
Backend persisted models, compose requests, combination writes, repairs, and canonical responses SHALL reject any present fragment whose `snapshotRaw` (wire field `snapshot`) is empty or whitespace-only. It MUST NOT filter, skip, trim into validity, or partially persist such a fragment. An absent polarity list remains valid.

#### Scenario: Literal blank snapshot is rejected
- **WHEN** a compose or combination request contains a literal snapshot of `   `
- **THEN** Backend returns a validation error
- **AND** no compose result or saved document is produced

#### Scenario: Entry blank snapshot is rejected
- **WHEN** an entry fragment has a valid ref but a blank snapshot
- **THEN** Backend rejects the fragment before source repair
- **AND** does not silently replace the blank with current source text

#### Scenario: Absent Negative list is valid
- **WHEN** a request contains valid Positive fragments and `negative=[]`
- **THEN** blank-fragment validation passes for the absent Negative lane

### Requirement: Canonical combinations contain one prompt per fragment
Every canonical PromptFragment returned or persisted after comma-atomic readiness SHALL have nonblank exact unweighted `snapshotRaw` (wire field `snapshot`) containing no ASCII comma, numeric `weight`, and derived `renderedRaw=render(snapshotRaw, weight)`. For weight 1, render SHALL return exact `snapshotRaw`; for another weight it SHALL wrap exact `snapshotRaw` using the supported weight form. Backend SHALL preserve stable fragment order and join `renderedRaw` atoms using exactly U+002C. It SHALL NOT insert separator whitespace, strip snapshots, parse weight syntax out of snapshots, or filter fragments.

#### Scenario: Weight-one composition preserves raw whitespace
- **WHEN** ordered literal snapshots are `a` and ` b ` with weight 1
- **THEN** the composed prompt is exactly `a, b `
- **AND** canonical fragments retain `a` and ` b ` exactly

#### Scenario: Weighted atom is rendered independently
- **WHEN** an atomic `snapshotRaw` is ` detail ` and weight is 1.2
- **THEN** its rendered atom is exactly `( detail :1.2)`
- **AND** its canonical unweighted snapshot remains exactly ` detail `

#### Scenario: Canonical saved file is atomized
- **WHEN** a valid combination is saved
- **THEN** every persisted Positive and Negative fragment is nonblank and comma-free
- **AND** each prompt snapshot equals the exact comma join of `render(snapshot, weight)` for its ordered fragments

#### Scenario: Canonical equality uses rendered atoms
- **WHEN** a response contains fragments `{snapshot:"a", weight:1.2}` and `{snapshot:" b", weight:1}`
- **THEN** canonical response equality compares the visible text to exactly `(a:1.2), b`
- **AND** it does not compare the visible text to unweighted `a, b`

### Requirement: Comma-bearing compatibility inputs atomize deterministically
Backend SHALL atomize comma-bearing literal `snapshotRaw` values received from privileged migration or post-readiness compatibility paths with Python behavior equivalent to `raw.split(",")`. It SHALL preserve all exact nonblank segment strings as unweighted snapshots, inherit the original weight on every atom, derive each resulting `renderedRaw`, and place the atoms consecutively at the original fragment location. If any resulting atom is blank/whitespace-only, Backend SHALL reject the whole request. Canonical responses SHALL expose the expanded fragments and a structured warning.

#### Scenario: Legacy literal expands to exact atoms
- **WHEN** a legacy literal snapshot is `a, b,c` with weight 1
- **THEN** Backend produces ordered literal snapshots `a`, ` b`, and `c`
- **AND** the composed text round-trips exactly as `a, b,c`
- **AND** a `legacy_literal_atomized` warning reports three atoms

#### Scenario: Weighted legacy literal copies weight to every atom
- **WHEN** a legacy literal `a,b` has weight 1.2
- **THEN** Backend produces two independently weighted atoms
- **AND** the warning explains that the original group weight was copied to each atom

#### Scenario: Compatibility atomization refuses empty results
- **WHEN** a compatibility fragment contains `a,,b`
- **THEN** Backend rejects the complete request because atom 2 is blank
- **AND** it does not return or save `a` and `b` as a partial result

### Requirement: Known legacy source refs expand one-to-many
Backend migration and repair SHALL use the reviewed legacy-ref registry to map one old source locator to its complete ordered list of derived entry locators. It SHALL replace the old fragment with one entry fragment per derived locator, preserve exact derived `snapshotRaw`/source revisions, inherit the original structured weight on each atom, derive each `renderedRaw`, retain lane position, and return `legacy_reference_expanded` with old and new refs. It MUST NOT collapse duplicate derived refs or silently keep only the first.

#### Scenario: Multi-token source ref expands during migration
- **WHEN** a saved fragment references a migrated source entry whose registry maps to three derived entries
- **THEN** the repaired combination contains three consecutive `kind=entry` fragments in registry order
- **AND** all three inherit the original weight
- **AND** the warning contains the old ref and all three new refs

#### Scenario: Expanded source updates remain repairable
- **WHEN** one derived source entry later changes revision and prompt
- **THEN** normal snapshot repair updates only the corresponding derived fragment
- **AND** preserves the other expanded refs, order, and snapshots

#### Scenario: Duplicate expansion is a blocking migration issue
- **WHEN** expanding legacy refs would create duplicate refs that ordinary compose policy would discard
- **THEN** migration reports a blocking conflict
- **AND** does not silently apply first-reference-wins behavior

### Requirement: Unresolved legacy provenance is never silently lost
If a legacy source ref has no unique registry expansion, repository migration SHALL fail closed. For an externally introduced legacy combination after finalized readiness, Backend MAY expose nonblank snapshots as ordered literal fallback atoms only with a blocking `legacy_reference_unresolved` document diagnostic containing the original ref, combination revision/etag, diagnostic ID, fallback polarity, 1-based fallback start/count, and fallback atom hashes. The blocking diagnostic SHALL survive ordinary content edits. Backend MUST reject Update and Save As—and any ordinary persistence derived from that loaded document—until the diagnostic is explicitly resolved by a reviewed mapping, diagnostic-specific selection of replacement source entries that occupy its fallback range and remove its fallback atoms, or an explicit acknowledge-convert-to-literals action/token. Ordinary edit or save intent and unrelated existing refs are not acknowledgment.

#### Scenario: Repository combination with unresolved ref blocks apply
- **WHEN** dry-run finds an existing repository combination ref without one unique reviewed expansion
- **THEN** migration apply is ineligible
- **AND** the original combination file remains unchanged

#### Scenario: External unresolved ref loads with explicit fallback warning
- **WHEN** an old external combination contains an unknown ref and a nonblank comma-bearing snapshot
- **THEN** Backend returns exact atomized literal fallback cards and `legacy_reference_unresolved`
- **AND** the warning includes the old ref and states that source provenance was not transferred
- **AND** the document is marked blocked and Backend does not automatically rewrite the file

#### Scenario: Unresolved fallback with blank atom is rejected
- **WHEN** an unknown legacy ref has snapshot `a,,b`
- **THEN** Backend rejects fallback atomization
- **AND** does not discard the old ref or blank atom

#### Scenario: Ordinary edit and Update do not acknowledge provenance loss
- **WHEN** the user edits fallback literal content and invokes Update without an explicit resolution token
- **THEN** Backend rejects Update with the same blocking diagnostic
- **AND** the source combination remains unchanged

#### Scenario: Save As cannot bypass blocking provenance
- **WHEN** a loaded blocked document is submitted through Save As without resolving its diagnostic
- **THEN** Backend rejects Save As even if all fallback atoms are otherwise valid literals
- **AND** no new combination is created

#### Scenario: Reviewed mapping or replacement refs resolve the block
- **WHEN** the diagnostic is resolved by a reviewed legacy mapping or explicit user selection of replacement source entries
- **THEN** Backend validates the resulting refs against the current catalog and document concurrency tokens and verifies them at that diagnostic's fallback location
- **AND** the diagnostic's fallback literals are absent while unrelated equal-text literals may remain
- **AND** a subsequent Update or Save As may proceed without literal-conversion acknowledgment

#### Scenario: Unrelated source ref cannot clear a diagnostic
- **WHEN** a request leaves the diagnostic fallback atoms in place and merely appends another valid source ref
- **THEN** Backend rejects the provenance resolution
- **AND** no combination is written

#### Scenario: Explicit conversion requires a bound token
- **WHEN** the user invokes an explicit acknowledge-convert-to-literals action for all blocking diagnostics
- **THEN** Backend issues an opaque token bound to combination ID, revision, etag, diagnostic IDs, and fallback atom hashes
- **AND** Update or Save As succeeds only when Backend validates that token against the unchanged context
- **AND** an ordinary save request cannot mint, infer, or substitute the token

### Requirement: Current saved combinations migrate before editor enablement
The four repository combinations `character`, `niji基礎瑟瑟`, `portrait-detail`, and `portrait` SHALL be migrated from comma-bearing literals to 36 ordered nonblank comma-free fragments before comma-atomic editor readiness. Their IDs, metadata, aliases, keywords, archive state, and exact rendered prompt text SHALL remain unchanged. Every changed combination SHALL increment revision once and receive an etag for its new bytes.

#### Scenario: Four-combination migration preserves text
- **WHEN** the reviewed migration is applied
- **THEN** `character`, `niji基礎瑟瑟`, `portrait-detail`, and `portrait` contain 2, 25, 5, and 4 atomic fragments respectively
- **AND** each Positive and Negative prompt snapshot is byte-for-byte equal to its pre-migration prompt text

#### Scenario: Combination lifecycle metadata remains stable
- **WHEN** one of the four combinations is migrated
- **THEN** its revision increments exactly once
- **AND** its ID, descriptive metadata, ordering metadata, aliases, keywords, legacy-template flag, and archive state remain unchanged

### Requirement: Load and lazy repair return canonical version tokens
After finalized readiness, combination load SHALL perform deterministic legacy atomization, one-to-many ref expansion, archive/missing-source warnings, and current-source snapshot repair before returning detail. If persisted content changes and no blocking diagnostic exists, Backend SHALL increment the combination revision once and return the new etag, canonical fragments, repaired state, and all warnings. A second load with no source change SHALL be idempotent. During any migration marker state, ordinary combination load SHALL fail before reading the document; equivalent work is available only to the privileged migration path.

#### Scenario: First load persists deterministic repair
- **WHEN** a known legacy combination loads and all mappings are resolved
- **THEN** Backend atomizes/expands it, writes one repaired combination revision, and returns the new revision and etag
- **AND** no fragment is lost

#### Scenario: Second load is idempotent
- **WHEN** the repaired combination loads again without source changes
- **THEN** Backend returns identical fragments, revision, etag, and prompt snapshots
- **AND** does not report another repair

#### Scenario: Archived source keeps atomic snapshot with warning
- **WHEN** an atomic entry ref points to an archived category or entry
- **THEN** load/compose keeps the exact snapshot and ref
- **AND** returns a structured archived-reference warning without dropping the fragment

### Requirement: Save Update and Save As persist only validated canonical atoms
After finalized readiness, Save, Update, and Save As SHALL validate and resolve all fragments before write, persist only canonical atomic fragments, and return the same canonical state. Save/Save As of a new ID SHALL use expected revision zero. Update SHALL require the current repaired detail revision and etag. Save As from a loaded document SHALL include its Backend document-context token so unresolved provenance cannot be dropped by copying. A validation, revision, etag, unresolved-provenance, missing/invalid conversion token, or write failure MUST leave existing and target files unchanged. During any marker state all ordinary persistence and compose SHALL fail before catalog access.

#### Scenario: Valid Save persists and returns the same atoms
- **WHEN** a new combination contains valid ordered atomic fragments
- **THEN** Backend persists those canonical atoms and prompt snapshots
- **AND** the response's atom join equals the saved file's prompt snapshots

#### Scenario: Stale Update fails without partial write
- **WHEN** Update supplies a stale revision or etag
- **THEN** Backend returns the structured concurrency error
- **AND** the existing combination bytes, revision, etag, and fragments remain unchanged

#### Scenario: Save As does not mutate source document
- **WHEN** valid canonical atoms from a loaded combination are saved under a new ID with expected revision zero
- **THEN** Backend creates a distinct combination
- **AND** the loaded source combination is not modified

#### Scenario: Combination metadata survives Update and Save As
- **WHEN** a loaded combination carries its existing name, description, aliases, keywords, order, and `legacy_template`
- **THEN** Update preserves those values
- **AND** Save As copies the intentional loaded values instead of substituting hardcoded defaults

#### Scenario: Non-one weight survives Backend save load round trip
- **WHEN** a referenced fragment with `snapshotRaw=detail`, weight 1.2, and `renderedRaw=(detail:1.2)` is saved
- **THEN** Backend persists unweighted `snapshot=detail`, weight 1.2, and the ref
- **AND** load returns the same fields and composes exactly `(detail:1.2)`

### Requirement: Marker states block ordinary combination contracts
Whenever any migration marker/incomplete state exists, ordinary combination list/load, compose, Save, Update, Save As, repair, and their API/MCP equivalents SHALL fail closed before reading live or staged Prompt Library state. Only privileged migration audit/apply/resume/rollback/validate/finalize under the migration lock may inspect or transform combinations.

#### Scenario: Compose cannot observe partial migration
- **WHEN** a migration marker exists and an ordinary caller invokes compose
- **THEN** Backend returns the structured migration-unavailable error before resolving refs or reading combinations

#### Scenario: MCP combination operations are also blocked
- **WHEN** a migration marker exists
- **THEN** MCP list/load/compose/save operations return the same fail-closed state
- **AND** no MCP operation accesses staged or mixed documents

### Requirement: Compose repair warnings are actionable and complete
Every compatibility or provenance repair warning SHALL include a stable code, message, hint, affected polarity and position or ref, resolution, and resulting refs/count where applicable. Multiple warnings SHALL remain in deterministic lane/order sequence. Compose and save MUST NOT report success while omitting a fragment that was present in valid input.

#### Scenario: Warning order follows fragment order
- **WHEN** a request requires atomizing a literal before expanding a later legacy ref
- **THEN** warnings appear in the same polarity and fragment order as the affected inputs
- **AND** each warning identifies its resolution and atom/ref count

#### Scenario: Valid input count is fully accounted for
- **WHEN** all input fragments are valid and repairable
- **THEN** every input fragment maps to one or more returned canonical fragments
- **AND** any one-to-many mapping is disclosed by a warning
- **AND** no valid fragment disappears silently
