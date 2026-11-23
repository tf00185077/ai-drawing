# Prompt Workbench and reusable workflows

Source/file reference, not live UI or GPU acceptance. Resource inspection does not authorize generation, downloads, edits or preset promotion.

## Recipes and saved graphs

A saved graph is a complete ComfyUI JSON workflow: nodes/connections, model files, prompts and sampler/size/seed settings. For example: model → optional LoRA → text encoding/sampler → VAE decode → output. It is neither an image nor a model file.

A recipe supplies reusable settings for new content; a saved graph records a concrete computation. Recipe composition and graph replay can differ in prompts, batch and defaults. Record those differences in [human style notes](../style_presets/human/). See the [preset guide](../style_presets/README.md) for style resources/evidence and [application templates](../backend/workflows/README.md) for technical inputs. Unverified effects carry **Needs re-verification (需要再驗證)**.

## Prompt Workbench

Route: `/prompt-library/workbench`; `/prompt-library` redirects there. Default URL: <http://127.0.0.1:5173/prompt-library/workbench>, if running.

The workbench orders/weights positive and negative fragments and saves combinations. GenerationPanel selects a Backend generation form and submits assembled prompts, unlike the simpler `/generate` page.

| Authored data | Location |
|---|---|
| Library root | [`prompt_library/`](../prompt_library/), not `data/prompt_library/` |
| Reusable entries and Chinese descriptions | [Positive](../prompt_library/positive/), [negative](../prompt_library/negative/) |
| Prompt combinations, not graphs | [Combinations](../prompt_library/combinations/), including [portrait](../prompt_library/combinations/portrait.json) and [character](../prompt_library/combinations/character.json) |

MCP: `prompt_library_search` discovers entries/categories/combinations; `prompt_library_compose` renders a combination or fragments into positive/negative text. Search/read does not mutate; save, compose-with-save, archive and restore do. See [MCP setup](mcp-setup.md) for schemas/endpoints.

Source: [routes](../frontend/src/App.tsx), [PromptWorkbench](../frontend/src/components/prompt-library/PromptWorkbench.tsx), [GenerationPanel](../frontend/src/components/prompt-library/GenerationPanel.tsx), [Prompt Library API](../backend/app/api/prompt_library.py).

## Style resources and graph access

| Resource | Location | Contents |
|---|---|---|
| Index | [Preset index](../style_presets/agent/index.json) | IDs, profiles, resources, human-note paths |
| Recipes | [Preset JSON](../style_presets/agent/presets/) | Prompts, templates, model/LoRA components, defaults |
| Notes | [Human notes](../style_presets/human/) | Intended use and evidence; some are unvalidated stubs |
| Saved graphs | [Workflow directory](../style_presets/agent/workflows/) | Raw API graphs by preset/profile |

Examples:

- Digital Painting: [recipe](../style_presets/agent/presets/digital-painting-a.json), [note](../style_presets/human/digital-painting-a.md).
- Soft Mist: [recipe](../style_presets/agent/presets/soft-mist-skin-anima.json), [note](../style_presets/human/soft-mist-skin-anima.md), [portrait graph](../style_presets/agent/workflows/soft-mist-skin-anima/portrait.api.json).
- Shattered Dreams/Detailer candidate: [recipe](../style_presets/agent/presets/anima-shattered-dreams-detailer-candidate.json), [base graph](../style_presets/agent/workflows/anima-shattered-dreams-detailer-candidate/__base__.api.json). Candidate status does not imply approval.

Graph convention: `style_presets/agent/workflows/<preset_id>/__base__.api.json`, or `<profile>.api.json` for a profile. Check files/API responses; not every recipe/profile has a graph. Saved files do not prove node/model availability or aesthetic acceptance.

- `list_style_presets` → `get_style_preset`: read index/recipe details.
- `compose_style_preset`: build a variation payload without submitting or replaying the graph.
- `GET /api/style-presets/{preset_id}/workflow?profile=<profile>`: read a graph; omit `profile` for the base. No dedicated MCP graph-read tool exists. Use the local file or authorized Backend GET.
- `test_saved_style_preset_workflow`: queue the saved graph without prompt overrides. This generates output; it is not inspection.
- Saving a successful graph as a preset requires an explicit owner save request.

Source: [preset API](../backend/app/api/style_presets.py), [graph service](../backend/app/services/style_preset_workflows.py).

## Application templates

[`backend/workflows/`](../backend/workflows/) contains application graphs and `.meta.json` capability/form metadata, separate from preset graphs. Example: [Anima graph](../backend/workflows/anima.json), [metadata](../backend/workflows/anima.meta.json).

The workbench reads `GET /api/workflow-catalog/generation-forms`, then submits the selected template ID and prompts. It does not list all saved preset graphs. MCP `list_available_resources` returns resource/form information; use local known-good graphs as starting points. For Backend read-only listing/matching, inspect the [catalog API](../backend/app/api/workflow_catalog.py) and schema; removed MCP lookup tools are not supported.

## Responsibilities

Inspect authored prompts/recipes before recreating them. Generation owns workflow applicability/adaptation; environment/resource management checks nodes/models; platform engineering owns integration changes. CTY evaluates style. Missing Windows acceptance or resources blocks execution, not asset retention, and does not authorize switching compute.
