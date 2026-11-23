# Prompt dashboard

The Prompt Workbench lets users build prompts from reusable fragments, save them as combinations and submit them to a generation form. Style presets and workflow templates are the other reusable building blocks.

Status and gaps: [STATUS.md](STATUS.md#2-prompt-dashboard).

## Pages

| Route | Purpose |
|---|---|
| `/prompt-library/workbench` | Compose prompts, save combinations, submit generation (`/prompt-library` redirects here) |
| `/prompt-library/categories` | Manage categories |
| `/prompt-library/categories/:polarity/:categoryId` | Edit entries in a category |
| `/generate` | Simple generation form |
| `/gallery` | Browse results |

Source: `frontend/src/components/prompt-library/` (`PromptWorkbench.tsx`, `GenerationPanel.tsx`, `compositionState.ts`), `frontend/src/pages/`.

## Workbench

- Browse and search entries by category, positive or negative.
- Add entries or literal text, reorder them and set weights.
- Save the result as a combination; load and edit existing combinations.
- `GenerationPanel` picks a generation form from `GET /api/workflow-catalog/generation-forms` and submits the composed prompts to the Backend.

## Prompt library data

Stored as versioned JSON in `prompt_library/` (mounted at `/workspace/prompt_library` in Docker).

| Path | Contents |
|---|---|
| `manifest.json` | Library metadata |
| `positive/*.json`, `negative/*.json` | One category per file: `id`, `name_zh`, `description_zh`, `aliases`, `parent_id`, `entries[]` |
| `combinations/*.json` | Saved combinations: ordered `positive[]` / `negative[]` items, each a `literal` or a `ref` to an entry, with `weight` and `order` |

Every file has a `revision` that increments on write. Archived items stay on disk with `archived: true` and can be restored.

## API

Router: `backend/app/api/prompt_library.py`, prefix `/api/prompt-library`.

| Endpoint | Purpose |
|---|---|
| `GET /catalog`, `GET /categories/{polarity}/{id}`, `GET /search` | Read |
| `PUT /categories/{polarity}/{id}`, `PUT .../entries/{entry_id}` | Create or update categories and entries |
| `GET /combinations`, `GET /combinations/{id}`, `PUT /combinations/{id}` | Combinations |
| `POST /compose` | Render a combination or fragments to positive/negative text |
| `POST /archive`, `POST /restore` | Archive and restore |

MCP equivalents: `prompt_library_search`, `prompt_library_compose`, `prompt_library_save`, `prompt_library_archive`, `prompt_library_restore`.

## Workflow templates

`backend/workflows/` holds ComfyUI API graphs. Each `<name>.json` has a `<name>.meta.json` describing its form fields and capabilities; these drive the generation forms. Example: `anima.json` + `anima.meta.json`.

## Style presets

A style preset is a reusable recipe: prompts, template, models/LoRAs and defaults. Some also have saved graphs.

| Path | Contents |
|---|---|
| `style_presets/agent/index.json` | Preset index |
| `style_presets/agent/presets/<id>.json` | Recipes |
| `style_presets/agent/workflows/<id>/__base__.api.json` or `<profile>.api.json` | Saved graphs |
| `style_presets/human/<id>.md` | Notes on intended use |

API: `backend/app/api/style_presets.py`. `GET /api/style-presets/{id}/workflow?profile=<p>` reads a saved graph. MCP: `list_style_presets`, `get_style_preset`, `compose_style_preset`, `save_successful_workflow_as_style_preset`, `test_saved_style_preset_workflow`.

A combination holds prompt text only; a style preset also holds the template and models. Unifying them into one recipe is planned for Phase 2 ([roadmap](roadmap/ROADMAP.md)).
