## Context

After layer-style-preset-catalog, presets live as `style_presets/agent/presets/<id>.json` (detail) + `index.json` (light), with human notes in `style_presets/human/<id>.md`. `DirStylePresetProvider` already does list/get/validate/compose/reindex and knows its `agent_dir` + `project_root`. Validation already checks that `note_path` exists and its frontmatter `preset_id` matches. There is no write path yet.

## Goals / Non-Goals

**Goals:**
- One MCP call creates a usable preset: machine recipe + human note + reindex.
- Both layers stay consistent (note_path auto-set, frontmatter preset_id == id).
- No accidental clobber; explicit overwrite for edits.
- Surface missing-resource validation without blocking creation.

**Non-Goals:**
- A full note editor / rich note authoring (we write a stub note the human can flesh out).
- In-memory authoring (the in-memory provider stays read-only; create is file-based).
- Deleting/renaming presets (out of scope).

## Decisions

### Decision 1: Create lives on the directory provider
Add `create_preset(fields, *, create_note=True, overwrite=False)` to `DirStylePresetProvider`, using `self._agent_dir` and `self._project_root`. The API endpoint calls it on the injected provider (tests override with a tmp-dir provider — no path monkeypatching).
- *Alternative:* a module function taking an explicit dir — rejected; the provider already carries the dir and is what the endpoint injects.

### Decision 2: note_path derived, frontmatter generated to match
`human_dir = agent_dir.parent / "human"`; note written at `human_dir/<id>.md`; `note_path` stored as that path relative to `project_root` (e.g. `style_presets/human/<id>.md`). The note stub's frontmatter carries `preset_id: <id>` so validation passes immediately.
- *Why:* guarantees the note↔catalog consistency the validator enforces.

### Decision 3: No-overwrite by default
If `presets/<id>.json` exists and `overwrite` is false, raise `PresetExistsError` → API 409. Protects hand-authored recipes.

### Decision 4: Validate-as-data, don't block
After writing, run the existing per-preset resource validation and return it. Missing checkpoint/LoRA is reported, not fatal (consistent with `validate_style_presets`).

### Decision 5: Reindex after write
Create calls `reindex` so the new preset is immediately listable from the index.

## Risks / Trade-offs

- **[Note clobber]** creating a preset whose human note already exists → only overwrite the note when `overwrite` is set; otherwise keep an existing note (it may have human edits) and just (re)write the recipe is inconsistent — so: on non-overwrite, refuse if the recipe exists (covers the normal case); if recipe is absent but a note exists, write recipe and leave the note as-is only if its frontmatter matches, else write the stub. Keep it simple: refuse when recipe exists; otherwise write both (stub note overwrites any stray note).
- **[Invalid id]** odd ids could create odd filenames → require a simple slug (non-empty, no path separators); reject otherwise.
- **[Partial write]** detail written but reindex/note fails → write detail + note first, reindex last; reindex is idempotent and self-heals on read.

## Migration Plan

Additive: new endpoint + tool + provider method. No data migration. Rollback = remove them.

## Open Questions

- Whether to support updating only metadata vs full replace on overwrite — for now overwrite is a full replace of the recipe.
- Whether to accept rich note body text from the agent (vs a generated stub) — deferred; stub now, agent can edit the note file afterwards.
