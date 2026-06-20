## Context

`FileStylePresetProvider` (backend/app/core/style_presets.py) loads a single `catalog.json` into an in-memory list (`from_file` / `from_data`) and serves `list_presets` / `get_preset` / `validate_presets` / `compose`. The API list endpoint calls `list_presets()` and builds `StylePresetSummary` objects. Unit tests construct providers via `from_data` (in-memory) and rely on this interface. The recently chosen layout is per-preset files + a lightweight index (mirrors the workflow-template sidecar idea, but with an explicit shared index file rather than globbing).

## Goals / Non-Goals

**Goals:**
- `list` reads only `index.json` (no full-body scan).
- `get`/`compose` load a single `presets/<id>.json`.
- Keep the in-memory provider + its `from_data` tests working unchanged.
- Keep API routes and compose-then-generate semantics unchanged.
- Index stays in sync via an explicit reindex; read path self-heals if the index is missing.

**Non-Goals:**
- Multiple top-level catalogs (rejected option).
- Programmatic preset authoring (presets are still authored by hand for now).
- Per-request caching of detail bodies (out of scope; the index already removes the hot-path scan).

## Decisions

### Decision 1: Two providers behind one interface
Keep `FileStylePresetProvider` (in-memory, `from_data`/`from_file`) for tests and small in-memory use. Add `DirStylePresetProvider(agent_dir)` for production. Both expose `list_summaries()`, `get_preset(id)`, `validate_presets(inv)`, `compose(...)`. The API list path calls `list_summaries()`.
- *Why:* the in-memory provider's 28 existing tests keep passing; production gets the lazy dir-backed behavior.

### Decision 2: `list_summaries()` is the cheap list method
Add `list_summaries() -> list[dict]` returning index-shaped entries (id, name, profiles, note_path, template, checkpoint, lora, diffusion_model). Dir provider reads `index.json`; in-memory provider derives from its presets. The API builds `StylePresetSummary` from these.
- *Why:* the API summary needs more than id/name; the index carries exactly those summary fields (still far lighter than full bodies).

### Decision 3: Index shape and reindex
`index.json` = `{"presets": [ <summary entry>, ... ]}`. `reindex(agent_dir)` scans `presets/*.json`, parses each (reuse `_parse_preset`), and writes the summary entries. The dir provider's read path: if `index.json` is missing, call reindex first (self-heal), then read.
- *Alternative:* glob per-preset `*.meta.json` sidecars (no index file, like workflow templates) — rejected per the chosen option (explicit index requested); the self-heal + validate-drift mitigate the sync risk.

### Decision 4: Compose logic extracted to a free function
Extract `compose_preset(preset, content_prompt, profile, overrides) -> ComposeResult` so both providers share it.

### Decision 5: Validation reports drift
`validate_presets` (dir) cross-checks index ids vs `presets/*.json` filenames and reports missing-either-side entries, alongside the existing resource/note checks.

## Risks / Trade-offs

- **[Index drift]** index out of sync with detail files → Mitigation: explicit reindex, self-heal on missing index, and validate reports drift. (Accepted residual: a stale-but-present index isn't auto-detected on the hot path; validate surfaces it.)
- **[Two providers]** small duplication → Mitigation: shared free functions (`_parse_preset`, `compose_preset`, summary builder).
- **[Migration]** existing single `catalog.json` must be split → one-time migration of `creator-a`; remove `catalog.json`.

## Migration Plan

1. Create `style_presets/agent/presets/creator-a.json` (the existing recipe) and `style_presets/agent/index.json`; delete `catalog.json`.
2. Land the dir-backed provider + API/MCP wiring; `get_default_provider` → dir provider.
3. Reindex tool/endpoint available for future preset edits.
Rollback: revert code and restore `catalog.json` (kept in git history).

## Open Questions

- Whether to also expose an even-more-minimal "ids only" listing — deferred; current summary index is already cheap.
- Whether to auto-reindex on detail-file mtime change — deferred; explicit reindex + self-heal is enough for hand-authored presets.
