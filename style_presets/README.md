# Style presets

Recipes describe reusable style intent. Saved ComfyUI graphs define exact replay inputs. Human notes retain profile purposes, exceptions and provenance. None establishes current image quality or CTY acceptance. See the [resource guide](../docs/prompt-and-workflow-resources.md) and [MCP setup](../docs/mcp-setup.md).

## Files and authority

| Location | Authority |
|---|---|
| `agent/presets/<id>.json` | Recipe resources, prompts, defaults and profile overrides |
| `agent/workflows/<id>/<profile>.api.json` | Exact saved graph, including text, wiring, filenames, seed, size and batch |
| `agent/preservation_manifests/*.json` | Recorded source/resource locks and classifications, where available |
| `agent/index.json` | Generated list summaries, not a prose or execution authority |
| `human/<id>.md` | Intent, profile differences, limitations and historical evidence |
| [human/_template.md](human/_template.md) | Authoring template, not a preset |

Recipe `id`, filename, note frontmatter `preset_id` and index summary must agree. Recipe `note_path` resolves from the repository root; Markdown links resolve from their containing note. Human prose does not configure prompts. Read the linked JSON instead of maintaining duplicate prompts, default tables or node listings in notes.

## Operations

### Compose new content

`compose_style_preset(preset_id, content_prompt, profile?, overrides?)` returns a `generation` payload without submitting a job. It combines base prompt + profile prefix + content + suffix, merges negatives and applies defaults → profile parameters → explicit overrides. Review that payload before an authorized `generate_image` call.

Composition uses the recipe/template, not the saved graph. Missing size, scheduler or seed may come from the selected workflow/runtime; do not assume saved values are recipe defaults. Choose a profile explicitly. Names such as `neutral`, `source-image` or `default` do not establish content neutrality, automatic selection or acceptance. Read each note's content locks and negative-prompt conflicts.

### Replay a saved graph

`test_saved_style_preset_workflow(preset_id, profile?, execution_target?)` queues the saved graph unchanged, including prompts, resources, fixed seed and batch. It accepts no new content or sampler overrides. Omitted profile maps to `__base__.api.json`, not a profile named `default`.

This test performs real generation. Obtain execution authority, poll `get_generation_status(job_id)` and inspect the returned artifact. A source-image profile expresses reconstruction intent; it does not guarantee source pixels, processing stages or style.

### Create or save

`create_style_preset` writes a recipe and initial note, then reindexes. Complete the note using the template; missing-resource warnings do not establish usability. Creating a recipe does not execute it.

Use `save_successful_workflow_as_style_preset(source, preset_id, prompt_keywords, negative_prompt_keywords?, profile?)` only after an explicit user request to save a successful recorded result. The Backend retrieves, sanitizes and stores the graph. Do not promote an unreviewed variant or invent a success record.

## Resource and evidence rules

- Ordered `loras` takes precedence over the legacy single `lora` field. The workflow needs enough compatible loaders. Anima examples use `LoraLoaderModelOnly`, which consumes model strength, not CLIP strength; their `CLIPLoader` type is `qwen_image`. Check exact filenames, family and wiring in JSON, then target inventory before authorized execution.
- Distinguish a Detailer LoRA from a face-detailer stage, source upscale/inpaint metadata from saved stages, and prompt “8K” from actual dimensions. Notes retain preset-specific exceptions, including Digital Painting's absence of LoRA, NihilMania's checkpoint VAE, Soft Mist batch 4 versus replay batch 1, and campus/white-wolf content locks.
- All current notes remain **Needs re-verification**. Style descriptions express authored intent, not observed current output. Historical sample descriptions and CTY reports apply only to their recorded artifacts; they are not fresh acceptance of a profile or modified graph.
- Historical paths/hashes are provenance, not current availability or recomputed file checks. Filenames do not establish versions, compatibility or licenses. Missing source/version/hash/license evidence remains unknown; do not invent manifests or resource locks.
- This prose cleanup performed no generation, downloads, installs, live inventory/model checks, image inspection or new CTY review. Earlier database-inspection findings in notes remain earlier evidence, not checks repeated here.

For re-verification, first check the chosen recipe payload or saved graph and required resources/nodes. After authorized execution, record job/artifact IDs and actual dimensions, inspect style/content drift, and obtain CTY aesthetic acceptance for that exact artifact/profile/graph. Technical success alone is not acceptance.

## Source interfaces and maintenance

Authorities: [provider](../backend/app/core/style_presets.py), [API router](../backend/app/api/style_presets.py), [saved-workflow service](../backend/app/services/style_preset_workflows.py), [MCP source catalog](../mcp-server/mcp_server/tool_catalog.py). Source support does not prove the deployed Backend version; use its OpenAPI when deployment behavior matters.

MCP exposes list, get, compose, create, save-successful-workflow and test-saved-workflow operations. Source HTTP routes under `/api/style-presets` include:

| Route | Purpose |
|---|---|
| `GET /`, `POST /` | List/create |
| `GET /{preset_id}`, `POST /{preset_id}/compose` | Detail/compose |
| `GET /validate` | Recipe/resource/note checks, not GPU or aesthetic validation |
| `POST /reindex` | Rebuild generated summaries |
| `POST /{preset_id}/workflow/save`, `GET /{preset_id}/workflow`, `POST /{preset_id}/workflow/test` | Save/read/replay; read supports `profile` |

The default factory uses `DirStylePresetProvider(DEFAULT_AGENT_DIR, project_root=…)`. List reads the index; detail/compose read individual recipes. An absent index rebuilds on read; an existing stale index needs explicit refresh. The source catalog has no reindex/validate MCP tool.

After maintenance, check frontmatter IDs, `note_path`, profile graph paths and local Markdown links. Refresh stale summaries through the supported maintenance path when authorized. Do not rewrite preserved graphs/manifests to match prose. This documentation-only edit does not authorize service calls, index changes or generation.
