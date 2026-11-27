# Legacy callers and migration boundary

The AST inventory records direct imports/symbols,
line numbers and call sites from every Backend app Python file in this candidate.
It is source evidence, not a live invocation/removal certificate. The accepted
First check's 19-service inventory
records seven touched modules including a value type, and 12 without operational
invocation. Those observations do not establish safe deletion.

- `DownloadedResource` has two application constructor sites: acquisition and
  retained install. Both publish shared typed metadata on the same row. The local
  ledger projects the row through the shared implementation. Its callers remain
  the recipes router, civitai_easy and recipe_variants.
- `civitai_resource_legacy.normalize_model_family` is the frozen historical
  recipe/AIR/Anima adapter. The original import from acquire remains for existing
  callers. Acquisition uses it solely for Anima package routing and old response
  notes. The local ledger uses it solely for historical recipe compatibility
  enums. Canonical metadata and new reads use the single exact Phase 2 table.
- Source-alias schemas require an immutable image/media identity. The independent
  tables `civitai_source_alias_registry_records`, `civitai_source_aliases`,
  `civitai_source_alias_history`, `civitai_source_alias_repoint_transitions`, and
  `civitai_source_alias_backfill_candidates` retain their columns and values.
  They never supply a model resource ID.
- Registry functions are directly used by the recipes router, recipe_pipeline,
  source_alias_parent and source_alias_backfill. Parent materialization is used
  by recipe_variants and recipe_variation_sets; recipe_gallery provides Gallery
  backfill evidence. Renames, archives, repoints, explicit-version resolution,
  discovery and historical hash chains remain frozen and are not migrated.
- Later removal needs contract replacement and caller migration for router,
  recipe pipeline, variants/variation sets, parent and Gallery backfill plus
  their consumers. This task supplies neither a model binding from an image
  alias nor a new alias feature. No alias source/test is removed.

One retained test fixture changes: `test_installed_audited_model_family_reaches_strict_resolution_lock`
now sets the actual provider baseModel to Illustrious before inspect/select,
rather than mutating only the old descriptor model_family afterward. Its original
illustrious lock assertions are unchanged, and the selected provider snapshot is
consistent. The shared `_selected` fixture gains only that optional source input.
This meaningfully preserves the old recipe feature alongside the canonical sdxl
projection; no assertion is deleted, relaxed or skipped.

Synthetic previous-schema fixture: `backend/tests/fixtures/resources/previous-schema.sql`
was emitted by the exact base's `db/models.py` using a separate declarative Base
and in-memory SQLite, without importing Settings or opening a project DB.
The migration guard audits every table (including sqlite_sequence), old column,
constraint/index SQL, and old value. All five source-alias tables contain
synthetic sentinels. The only startup delta is nullable metadata_json on the
resource table. Backfill writes that new field only; notes/aliases/history and
synthetic model bytes are preserved. Audit payloads are synthetic, not private
snapshots. The fixture uses current pre-task full schema; the retained older
partial-schema test separately verifies the established nullable additions.
