## Why

Agents can list raw checkpoints, LoRAs, diffusion-model components, and workflow templates, but they do not know which resources belong together or what prompt structure is needed to reproduce a creator's style. Users are currently pushed toward filling ad hoc templates each time; a persistent style preset catalog lets users name a recipe, describe the desired image content, and have the agent generate through the existing MCP pipeline.

## What Changes

- Add a structured style preset catalog that records creator/style recipes: checkpoint or diffusion-model components, LoRAs, trigger words, base prompt, negative prompt, optional profiles, and source note metadata.
- Keep Obsidian/Markdown notes as human-facing documentation, while using YAML/JSON as the runtime source that backend and MCP tools can validate and return.
- Add backend endpoints and MCP tools to list presets, fetch a preset, validate catalog resources against installed ComfyUI assets, and compose a preset with a user content prompt.
- Preserve one generation path: preset-based requests expand into the same parameter payload used by `generate_image`; manual checkpoint/LoRA requests continue to call `generate_image` directly.
- Update generation skill guidance so daily image creation uses presets when specified, falls back to manual resource selection when requested, and only asks the user to fill a new recipe when no suitable preset exists.

## Capabilities

### New Capabilities

- `style-preset-catalog`: Structured creator/style recipes that agents can list, validate, compose with user content prompts, and use to submit generation through the existing MCP generation path.

### Modified Capabilities

<!-- None. Existing custom workflow behavior is not changed; preset composition feeds existing generation APIs. -->

## Impact

- Backend core/API: new catalog loader/validator and `/api/generate/style-presets`-style endpoints, likely under `backend/app/core/` and `backend/app/api/generate.py` or a dedicated API module.
- MCP server: new tools for preset listing, detail, validation, and composition; optional convenience flow may compose then call existing `generate_image`.
- Data/config: a repo-managed YAML/JSON catalog file plus optional Markdown note references; no secrets or creator downloads are stored in the catalog.
- Existing generation: `generate_image` remains the single submission path for template-based generation; manual checkpoint/LoRA usage remains supported.
- Docs/tests: API/MCP contract docs, SOP/skill guidance, unit tests for catalog parsing, resource validation, prompt composition, and MCP tool payloads.
