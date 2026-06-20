## Why

The style preset catalog is a single `style_presets/agent/catalog.json` with every preset's full recipe embedded. Listing "which presets exist" today parses the entire file (full bodies, prompts, params, profiles) just to return id/name summaries. As the catalog grows this is wasted work on the hot `list` path, and a single large file is heavier for git diffs and agent writes. We want a lightweight index layer so discovery is cheap and detail is loaded only on demand.

## What Changes

- Split storage into two layers under `style_presets/agent/`:
  - `index.json` — lightweight entries (`id`, `name`, profile names, summary resource refs) read by the `list` path.
  - `presets/<id>.json` — one full recipe per preset, read only by get/compose/validate.
  - Remove the monolithic `catalog.json`.
- `list_style_presets` (API + MCP) reads only `index.json` — no full-catalog scan.
- `get_style_preset` / `compose_style_preset` load a single `presets/<id>.json`.
- Add a **reindex** operation (core + `POST /api/style-presets/reindex` + MCP `reindex_style_presets`) that rebuilds `index.json` from the preset files; the read path self-heals (rebuilds the index if missing).
- `validate_style_presets` additionally reports index↔preset drift (a preset file with no index entry, or vice versa).

## Capabilities

### Modified Capabilities
- `style-preset-catalog`: The catalog is stored as a per-preset detail layer plus a lightweight index; listing reads the index without loading full preset bodies; an explicit reindex keeps the index in sync and the read path self-heals when the index is absent.

## Impact

- Storage: `style_presets/agent/catalog.json` → `style_presets/agent/index.json` + `style_presets/agent/presets/<id>.json` (migrate the existing `creator-a`).
- Backend core: `backend/app/core/style_presets.py` — directory-backed provider (`list_summaries` reads index; `get_preset`/`validate`/`compose` load per-preset files; `reindex`); `DEFAULT_*` path points at the agent dir.
- Backend API: `backend/app/api/style_presets.py` — list uses summaries; add reindex endpoint.
- MCP: `mcp-server/mcp_server/tools/style_presets.py` — `list_style_presets` index-backed; add `reindex_style_presets`.
- Docs: `style_presets/README.md`, `docs/PROGRESS.md`.
- Unchanged: API routes `/api/style-presets`, compose-then-generate semantics, note_path/frontmatter validation, the in-memory provider used by unit tests.
