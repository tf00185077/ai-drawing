# Style presets

Recipes describe reusable style intent; saved ComfyUI graphs are exact replay inputs; human notes record each preset's purpose and exceptions. See [Prompt dashboard](../docs/prompt-dashboard.md), [MCP](../docs/mcp.md) and [style preset replay](../docs/memory/style-preset-saved-graph-replay.md).

## Files and authority

| Location | Authority |
|---|---|
| `agent/presets/<id>.json` | Recipe resources, prompts, defaults and profile overrides |
| `agent/workflows/<id>/<profile>.api.json` | Exact saved graph, including text, wiring, filenames, seed, size and batch |
| `agent/preservation_manifests/*.json` | Recorded source and resource locks, where available |
| `agent/index.json` | Generated list summaries |
| `human/<id>.md` | Intent, profile differences and limitations |
| [human/_template.md](human/_template.md) | Authoring template, not a preset |

Recipe `id`, filename, note frontmatter `preset_id` and index summary must agree. Prompts live in the JSON, not in the notes.

## Operations

### Compose new content

`style_preset_compose(preset_id, content_prompt, profile?, overrides?)` returns a `data.generation` payload in the MCP envelope without submitting a job: base prompt + profile prefix + content + suffix, merged negatives, and defaults → profile parameters → explicit overrides. Pass it to `generate`. Choose the profile explicitly.

### Replay a saved graph

`style_preset_test(preset_id, profile?, execution_target?)` queues the saved graph unchanged and accepts no overrides. An omitted profile means `__base__.api.json`.

### Create or save

`style_preset_save(from_source=fields)` writes a recipe and initial note, then reindexes; complete the note from the template. `style_preset_save(from_source=successful_job, source=..., preset_id=..., prompt_keywords=..., negative_prompt_keywords=..., profile=...)` stores a recorded successful result's graph when the user asks to save it.

## Resource rules

- Ordered `loras` takes precedence over the legacy single `lora` field ([explicit LoRA list](../docs/memory/explicit-lora-list-semantics.md)). Check loaders and filenames against the target host ([model family loaders](../docs/memory/model-family-loader-compatibility.md)).
- Preset-specific exceptions are in the notes, for example Digital Painting has no LoRA, NihilMania uses the checkpoint VAE, Soft Mist saves batch 4 but replays batch 1.
- Style descriptions are authored intent. Only CTY accepts a result.

## Source interfaces and maintenance

Source: [provider](../backend/app/core/style_presets.py), [API router](../backend/app/api/style_presets.py), [saved-workflow service](../backend/app/services/style_preset_workflows.py).

| Route under `/api/style-presets` | Purpose |
|---|---|
| `GET /`, `POST /` | List, create |
| `GET /{preset_id}`, `POST /{preset_id}/compose` | Detail, compose |
| `GET /validate` | Recipe, resource and note checks |
| `POST /reindex` | Rebuild `agent/index.json` (no MCP tool) |
| `POST /{preset_id}/workflow/save`, `GET /{preset_id}/workflow`, `POST /{preset_id}/workflow/test` | Save, read, replay |

After editing recipes, call `POST /reindex`, then check frontmatter IDs, `note_path` and profile graph paths.
