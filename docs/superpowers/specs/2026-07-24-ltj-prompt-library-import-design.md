# LTJ Prompt Library Import Design

## Goal

Replace the test Prompt Library content with a user-facing library extracted from
`LTJ/scenario_gui.py`. Keep the existing AI Drawing application, API, UI, and MCP
tool contracts unchanged.

## Scope

- Permanently remove the existing category JSON documents under
  `prompt_library/positive/` and `prompt_library/negative/`.
- Keep `prompt_library/manifest.json` and the Prompt Library implementation.
- Start the local backend and MCP server, then use `prompt_library_save` to create
  every replacement category and entry.
- Import selectable LTJ Prompt fragments only. Do not import LTJ's model-family
  selection, automatic ordering, conflict rules, generation settings, or LoRA
  filesystem discovery behavior.

## Data Model

Each imported entry uses the existing schema without changes:

- `id`: stable lowercase slug.
- `name_zh`: meaningful Chinese label.
- `description_zh`: short usage explanation for the selected Prompt fragment.
- `prompt`: the exact English tag or comma-separated tag fragment from LTJ.
- `aliases` and `keywords`: Chinese and English search terms.
- `order`, `revision`, and `archived`: standard library fields.

There is no model-family partitioning. Model-quality fragments are ordinary
positive entries and users select them manually.

## Categories

Positive categories: quality-ratings, body-appearance, clothing, underwear,
accessories, environment, camera-composition, poses, actions-interactions,
expressions, physical-effects, and lora-manual.

Negative categories: base-negative and solo-negative, populated only when LTJ
defines reusable negative Prompt fragments.

## Import Flow

1. Validate the existing Prompt Library root and physically delete only its old
   positive and negative category documents.
2. Start the backend with the project Prompt Library directory as its active root.
3. Start the MCP server against that backend and verify its health.
4. Extract static LTJ choice tuples into a deterministic import manifest.
5. Create categories and entries through `prompt_library_save`.
6. Read the catalog through `prompt_library_search` and verify entry totals,
   unique slugs, and required bilingual fields.

## Safety and Verification

- No files outside `ai-drawing/prompt_library/positive/` and
  `ai-drawing/prompt_library/negative/` are deleted.
- The import fails rather than silently falling back to direct JSON writes if MCP
  is unavailable.
- Existing tests for Prompt Library models, API, and MCP tools are run after the
  import tooling is added.
