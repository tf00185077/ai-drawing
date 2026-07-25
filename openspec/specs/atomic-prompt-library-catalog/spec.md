# atomic-prompt-library-catalog Specification

## Purpose
TBD - created by archiving change comma-delimited-atomic-prompts. Update Purpose after archive.
## Requirements
### Requirement: Prompt Library source entries are comma-atomic
Before rollout readiness can become true, Backend atomic enforcement SHALL be active and every Prompt Library entry prompt SHALL contain exactly one nonblank atomic prompt without ASCII comma U+002C. Entry prompt whitespace SHALL be preserved exactly; trim/normalization is allowed only for validation, matching, search, and display. Once atomic enforcement is active, every ordinary category-management, API, MCP, and import entry write containing U+002C MUST be rejected; privileged migration may persist only its separately curated comma-free staged entries.

#### Scenario: Atomic source entry is accepted without trimming
- **WHEN** an entry write contains prompt ` best quality` with no U+002C and has valid metadata
- **THEN** the stored prompt remains exactly ` best quality`
- **AND** it represents one source entry

#### Scenario: Comma-bearing source write is rejected
- **WHEN** a new Prompt Entry write contains `masterpiece, best quality`
- **THEN** the write is rejected with `comma_not_atomic`
- **AND** the error instructs the caller to create one curated entry per comma segment

#### Scenario: Blank source atom is rejected
- **WHEN** an entry prompt is empty or whitespace-only
- **THEN** the Backend rejects it
- **AND** no entry or category revision is changed

#### Scenario: Readiness waits for entry-write enforcement
- **WHEN** migrated files pass data validation but comma-bearing ordinary entry writes are not yet rejected by the active Backend
- **THEN** readiness remains false
- **AND** the migration marker remains

### Requirement: Migration-compatible Backend gate precedes all data migration
The migration-compatible Backend gate SHALL be deployed before audit or migration of live Prompt Library data. On startup with migration required it SHALL create or recognize a durable migration marker, report readiness false through a catalog-independent status surface, and keep atomic enforcement state explicit. Marker removal and readiness true MUST occur only in one privileged finalize transition after atomic Backend enforcement is active and all data gates pass.

#### Scenario: Gate deployment enters migration-required state
- **WHEN** the migration-compatible Backend starts against the reviewed legacy library
- **THEN** it reports readiness false and a migration-required marker
- **AND** it does not expose the legacy catalog through ordinary operations

#### Scenario: Actual predecessor manifest needs no synthetic opt-in
- **WHEN** Backend starts against the predecessor schema-v1 manifest bytes with no comma-atomic fields
- **THEN** it creates the required marker before provider access
- **AND** ordinary catalog operations fail closed

#### Scenario: Migrated data alone cannot remove the marker
- **WHEN** data migration and idempotency checks pass but atomic Backend enforcement is inactive
- **THEN** privileged finalize fails
- **AND** the marker remains and readiness stays false

#### Scenario: Finalize binds enforcement marker removal and readiness
- **WHEN** data gates pass and atomic Backend enforcement is active
- **THEN** privileged finalize revalidates both conditions
- **AND** atomically removes the marker and publishes readiness true

### Requirement: Marker states fail closed every ordinary catalog operation
Whenever the migration marker is `required`, `applying`, `incomplete`, `validating`, or `rolled_back_required`, Backend SHALL reject every ordinary catalog-dependent operation without reading live or staged catalog contents. This includes catalog/list/search, category and entry reads, combination list/load, compose, all ordinary category/entry/combination writes, archive/restore, and all corresponding API and MCP tools. Only catalog-independent health/migration status and the privileged migration path are available. No client SHALL observe mixed old, staged, partial, migrated-but-unenforced, or new state.

#### Scenario: Ordinary reads fail closed during migration
- **WHEN** any migration marker state is present
- **THEN** catalog, list, search, category/entry reads, combination load, and API/MCP read tools return a structured migration-unavailable error
- **AND** none reads or returns catalog documents

#### Scenario: Ordinary writes and compose fail closed during migration
- **WHEN** any migration marker state is present
- **THEN** compose, Save, Update, Save As, archive, restore, category/entry writes, and API/MCP write tools fail before accessing catalog state
- **AND** no document, revision, etag, staged file, or cache changes

#### Scenario: Migrated but unenforced catalog remains unavailable
- **WHEN** post-write data validation has passed but atomic enforcement is not active
- **THEN** ordinary reads and writes remain blocked
- **AND** readiness remains false

### Requirement: Only privileged locked migration operations access staged state
Audit/dry-run, apply, resume, rollback, validate, and finalize SHALL require an operator-privileged migration capability and the migration lock before accessing live or staged Prompt Library data. They MUST NOT be exposed as ordinary Workbench actions or general MCP tools. Audit/dry-run SHALL remain write-free even while holding the lock.

#### Scenario: Privileged audit reads under the lock
- **WHEN** an authorized operator runs audit during migration-required state
- **THEN** the privileged path acquires the migration lock and may inspect the legacy/staged files
- **AND** ordinary callers remain blocked

#### Scenario: Unprivileged staged access is rejected
- **WHEN** an ordinary API/MCP caller attempts to invoke or emulate apply, resume, rollback, or finalize
- **THEN** Backend rejects the request before staged-state access

### Requirement: Migration audit is anchored to the reviewed repository inventory
The migration SHALL audit the current repository before any write and SHALL require the reviewed baseline of 297 source entries, 146 comma-containing entries, 683 projected exact `split(",")` atoms, zero blank/whitespace atoms, and four saved combinations named `character`, `niji基礎瑟瑟`, `portrait-detail`, and `portrait`. The four combinations SHALL project to 36 total atomic fragments: 2, 25, 5, and 4 respectively. A baseline mismatch MUST fail closed and require a new reviewed report.

#### Scenario: Current audited inventory passes
- **WHEN** audit reads the reviewed repository state
- **THEN** it reports 297 entries, 146 comma-containing entries, 683 projected atoms, zero blank atoms, and the four named combinations
- **AND** dry-run is allowed to continue to mapping validation

#### Scenario: Source inventory drift blocks apply
- **WHEN** any audited count, combination ID, source revision, or source etag differs from the reviewed baseline after dry-run
- **THEN** apply stops before acquiring a write plan
- **AND** the report identifies each mismatch for review

### Requirement: Dry-run report is complete and write-free
Audit and dry-run SHALL make no Prompt Library or repository-tree writes. Their cross-process lock SHALL use a stable resolved-library key outside those trees. A caller MAY explicitly request a report output path; that operator-directed report is not a planned product mutation. The machine-readable dry-run report SHALL include source and target counts, every source locator and exact raw atom, revisions/etags, deterministic ID decisions, collisions, mapping coverage, aliases/keywords/order changes, archive propagation, saved-combination repairs, legacy ref expansions, unresolved items, planned file mutations, and expected post-write hashes.

#### Scenario: Dry-run produces a reviewable plan
- **WHEN** the operator runs dry-run against the reviewed baseline
- **THEN** the report enumerates all 146 multi-token source entries and 532 derived atoms
- **AND** it accounts for all 683 final entries and all four combinations
- **AND** no Prompt Library file, revision, etag, or manifest byte changes

#### Scenario: Dry-run lock leaves the product tree byte-stable
- **WHEN** dry-run completes without an explicit in-tree report path
- **THEN** a digest over every Prompt Library file is unchanged
- **AND** no `.prompt-library.lock` file is created inside the Prompt Library or repository tree

#### Scenario: Dry-run exposes unresolved work
- **WHEN** a token lacks a curated mapping or has an ambiguous target
- **THEN** the report records its source locator, segment index, raw token, reason, and required remediation
- **AND** the report marks apply as ineligible

### Requirement: Chinese labels and metadata are deterministic curated data
The curation worksheet SHALL contain exactly 532 required records, one for each new atom derived from the 146 multi-token entries and none for the 151 retained atomic entries. Each derived atom SHALL obtain `name_zh`, `description_zh`, aliases, and keywords from a versioned deterministic mapping keyed by source polarity, category, entry ID, source prompt hash, and segment index. The 151 retained entries SHALL undergo nonblank/comma-free invariant validation only and retain all existing metadata. Runtime and migration code MUST NOT call an LLM or guess a translation. Curators MAY deliberately reuse the same `name_zh` for semantically equivalent tokens, but semantically different tokens, including different shirt types, MUST have per-token curated Chinese names. Missing, extra, stale, blank, or unresolved curation MUST block apply.

#### Scenario: Equivalent tokens share an approved Chinese label
- **WHEN** two atom records are explicitly curated as semantically equivalent with the same `name_zh`
- **THEN** migration preserves that approved shared display label
- **AND** does not infer that equivalence from English text alone

#### Scenario: Distinct clothing tokens require distinct review records
- **WHEN** one source fragment contains different shirt types separated by U+002C
- **THEN** each shirt token has its own segment-indexed curation record and Chinese label decision
- **AND** a shared generic source label alone is insufficient to pass the gate

#### Scenario: Runtime has no translation fallback
- **WHEN** a catalog token has no deterministic curated Chinese mapping
- **THEN** runtime does not invoke an LLM or synthesize a translation
- **AND** migration remains unresolved until a human-corrected mapping is supplied

#### Scenario: Worksheet has exact derived-atom cardinality
- **WHEN** curation validation runs against the reviewed baseline
- **THEN** it requires exactly 532 derived-atom records
- **AND** any missing record, extra record, or record for one of the 151 retained entries blocks apply

### Requirement: Derived entry IDs and collision handling are stable
New atom IDs SHALL be derived from source locator, source prompt hash, segment index, and exact raw segment with a SHA-256-based digest. IDs MUST NOT depend on filesystem traversal order or first-available numeric suffixes. A matching provenance/content record SHALL reuse its ID. A conflicting occupied ID SHALL lengthen the digest deterministically; a conflict at full digest or with unverifiable provenance MUST block apply.

#### Scenario: Rerun derives identical IDs
- **WHEN** the same source documents and curation mapping are audited twice in different traversal orders
- **THEN** every derived atom receives the same ID in both reports

#### Scenario: Short digest collision expands deterministically
- **WHEN** two different provenance records collide at the initial digest length
- **THEN** migration expands the digest length according to the fixed policy
- **AND** both runs choose the same expanded IDs

#### Scenario: Unresolvable collision fails closed
- **WHEN** a candidate conflicts with unrelated existing provenance through the maximum digest
- **THEN** apply is ineligible
- **AND** no sequential `-2` style fallback or overwrite occurs

### Requirement: Migration preserves lifecycle and search metadata
All 151 retained single-token entries SHALL retain IDs, revisions, prompt bytes, archive state, `name_zh`, `description_zh`, aliases, keywords, and order. Derived atoms SHALL preserve exact raw prompt segments, inherit source archive state and common aliases/keywords, add curated token metadata with normalized stable deduplication, and begin at revision 1. Each affected category SHALL increment revision once, retain category metadata/archive state, place derived entries deterministically without changing retained-entry order metadata, and receive a new etag only when final bytes change.

#### Scenario: Archived source expands to archived atoms
- **WHEN** a comma-containing source entry is archived before migration
- **THEN** every derived atom is archived
- **AND** none appears in normal active browsing

#### Scenario: Affected category changes revision once
- **WHEN** one category replaces multiple multi-token entries during one apply
- **THEN** the category revision increments exactly once
- **AND** its etag matches the final serialized bytes

#### Scenario: Single-token entry remains stable
- **WHEN** an existing entry is already comma-free and nonblank
- **THEN** migration retains its ID, revision, prompt bytes, archive state, name, description, aliases, keywords, and order
- **AND** only invariant validation is applied to that entry

#### Scenario: Entry order is deterministic
- **WHEN** a source entry expands into multiple atoms between two existing entries
- **THEN** the derived atoms remain consecutive in source segment order
- **AND** reruns produce the same complete category ordering

### Requirement: Migration apply is staged and fail closed
Apply SHALL require the previously deployed Backend gate, a clean reviewed dry-run, exactly 532 curated derived-atom records, valid retained-entry invariants, zero unresolved mappings, zero blocking collisions, matching source revisions/etags, operator privilege, and the migration lock. It SHALL save exact predecessor pre-image bytes and checksums, stage and validate every destination, and use atomic replacements. The pre-existing marker SHALL remain through apply, post-write validation, and atomic-enforcement activation until finalize. All ordinary catalog-dependent reads and writes and frontend editor readiness MUST remain disabled while the marker exists. Any failed precondition or post-write/enforcement gate MUST prevent finalize.

#### Scenario: Concurrent change blocks apply
- **WHEN** a category etag changes after dry-run and before apply
- **THEN** apply stops without replacing any planned document
- **AND** the report identifies the stale document

#### Scenario: Interrupted apply blocks readiness
- **WHEN** migration stops after replacing only part of the planned documents
- **THEN** the in-progress marker remains
- **AND** Backend readiness reports an incomplete comma-atomic migration
- **AND** every ordinary Prompt Library read/write and editor enablement remains blocked until privileged resume or rollback

#### Scenario: Clean data gates still wait for Backend enforcement
- **WHEN** disk revalidation finds 683 nonblank comma-free entries, four valid atomized combinations, valid refs, planned revisions/etags, and a zero-change second dry-run
- **THEN** data validation passes but the marker remains
- **AND** readiness stays false until atomic Backend enforcement is active and privileged finalize succeeds

### Requirement: Migration reruns are idempotent
After a successful apply, rerunning audit or dry-run with the same catalog and mapping SHALL plan zero mutations. A no-op apply SHALL NOT increment any revision, change any etag, reorder entries, rewrite bytes, or recreate derived IDs.

#### Scenario: Second dry-run is byte-stable
- **WHEN** dry-run is executed immediately after a successful migration
- **THEN** it reports zero creates, updates, removals, repairs, and manifest changes
- **AND** all recorded document hashes match the first apply's post-image hashes

### Requirement: Rollback restores exact pre-images without overwriting later edits
Each apply SHALL create a run-specific rollback manifest containing exact predecessor pre-image bytes/checksums and expected post-image hashes. Privileged rollback SHALL remain available for that run after finalize during the rollout window. It SHALL acquire the migration lock, fail ordinary operations closed before validation, stage and validate restored documents, and restore exact pre-images only when every affected current hash equals its recorded post-image hash. Any divergence MUST fail without replacing a document; a post-finalize divergence SHALL remove the temporary marker and preserve the unchanged finalized ready state. Successful rollback SHALL leave a `rolled_back_required` marker, readiness false, and all ordinary catalog-dependent operations blocked.

#### Scenario: Immediate rollback restores the legacy catalog
- **WHEN** rollback is invoked for a completed run before any affected document changes
- **THEN** all affected documents and manifest are restored byte-for-byte
- **AND** their pre-migration revisions, etags, archive states, entries, and combinations are restored
- **AND** the migration marker remains in rolled-back-required state

#### Scenario: Later edit blocks rollback
- **WHEN** an affected category or combination etag differs from the recorded post-image etag
- **THEN** rollback does not overwrite any affected file
- **AND** it reports the divergent locator and required manual recovery

#### Scenario: Post-finalize rollback remains safe
- **WHEN** finalize removed the migration marker but every affected document still matches the recorded post-image hash
- **THEN** privileged rollback temporarily blocks ordinary operations, restores exact predecessor bytes, and publishes `rolled_back_required`
- **AND** if any post-image diverged it restores the unchanged finalized ready state without replacing files

### Requirement: Import reruns use the same atomic curation contract
Any future import of comma-containing source data, including LTJ-derived data, SHALL split with raw `split(",")`, preserve segment whitespace, require deterministic per-token curation, use the same stable ID/collision policy, and emit the same unresolved and dry-run reports. Runtime SHALL not depend on the LTJ source tree or execute source modules.

#### Scenario: Future LTJ-style source is imported atomically
- **WHEN** a static source record contains `masterpiece, best quality`
- **THEN** import plans two separately curated atomic entries with exact raw prompts `masterpiece` and ` best quality`
- **AND** no shipped runtime reads or imports LTJ code

#### Scenario: Reimport is idempotent
- **WHEN** the same reviewed import source and mapping are rerun
- **THEN** existing matching derived entries are reused
- **AND** no revisions or etags change
