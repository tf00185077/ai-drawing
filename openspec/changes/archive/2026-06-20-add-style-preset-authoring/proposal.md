## Why

Style presets can be listed, fetched, validated, and composed, but there is no way for an agent to **create** one from a user's description — today a human must hand-write both the machine recipe (`style_presets/agent/presets/<id>.json`) and the human note (`style_presets/human/<id>.md`), then reindex. We want an MCP tool so the agent can author a preset on request, writing both layers consistently and keeping the index in sync.

## What Changes

- Add a create operation (core + `POST /api/style-presets/` + MCP `create_style_preset`) that, from the fields the agent supplies, writes:
  - the machine recipe `style_presets/agent/presets/<id>.json` (id, name, resource refs, base/negative prompt, default params, profiles, note_path),
  - a human note stub `style_presets/human/<id>.md` with frontmatter `preset_id` matching the id (so it passes note validation),
  - then reindexes so the new preset appears in listings.
- Refuse to clobber an existing preset unless `overwrite` is set (avoid silent overwrite of hand-authored recipes).
- Return the created preset plus its validation result (missing resources reported as data, not blocking) so the agent/user can see if referenced models aren't installed.

## Capabilities

### Modified Capabilities
- `style-preset-catalog`: Add an authoring path — create a preset (machine recipe + human note) from supplied fields, with id/name required, no-overwrite by default, automatic note_path + frontmatter consistency, and reindex.

## Impact

- Backend core: `backend/app/core/style_presets.py` — `create_preset` on the directory provider (write detail + human note + reindex; collision check).
- Backend API: `backend/app/api/style_presets.py` — `POST /api/style-presets/` create endpoint + request schema.
- MCP: `mcp-server/mcp_server/tools/style_presets.py` — `create_style_preset` tool.
- Docs: `style_presets/README.md` (authoring), `docs/PROGRESS.md`.
- Unchanged: list/get/validate/compose/reindex behavior; note frontmatter validation rules.
