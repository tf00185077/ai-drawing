## Context

The current agent flow can list raw resources through `list_available_resources` and submit generation through `generate_image`, but the agent has no durable knowledge of creator-specific combinations. A user may know that a creator style needs a specific checkpoint, LoRA, trigger words, negative prompt, and sometimes a workflow template, but that knowledge is not represented in backend data.

There is already a small hard-coded `character_style.py` resolver in the MCP server, and there is a prompt template provider in the backend. The new catalog should replace hard-coded style knowledge with a file-backed provider pattern while keeping generation itself routed through the existing `generate_image` tool/API.

## Goals / Non-Goals

**Goals:**

- Let users maintain creator/style recipes as named presets.
- Let agents list presets, inspect a preset, validate installed resources, and compose final generation params from a preset plus a user content prompt.
- Support two user modes through one generation path:
  - preset mode: user names a recipe and describes the desired image;
  - manual mode: user names checkpoint/LoRA directly and describes the desired image.
- Keep Obsidian/Markdown useful for human notes while making JSON the runtime source for backend/MCP.
- Support checkpoint workflows and diffusion-model-family templates such as Anima through the same `generate_image` payload.

**Non-Goals:**

- No UI for editing presets in this change.
- No automatic scraping or downloading creator resources.
- No multi-LoRA graph construction in this change; MVP supports one primary LoRA per preset through the existing template generation path.
- No separate generation engine for presets. Presets expand into normal generation parameters.

## Decisions

### Decision 1: JSON catalog as runtime source, Markdown notes as references

Create a repo-managed JSON catalog, for example `backend/style_presets/catalog.json`, with entries like:

```json
{
  "presets": [
    {
      "id": "creator-a",
      "name": "Creator A",
      "note_path": "Obsidian/Creators/creator-a.md",
      "template": "default_lora",
      "checkpoint": "model.safetensors",
      "lora": "creator-a.safetensors",
      "lora_strength": 0.75,
      "base_prompt": "creator_a_style, anime illustration",
      "negative_prompt": "low quality, bad anatomy",
      "default_params": {
        "steps": 28,
        "cfg": 6.5,
        "width": 1024,
        "height": 1024
      },
      "profiles": {
        "portrait": {
          "prompt_prefix": "upper body, looking at viewer"
        },
        "full-body": {
          "prompt_prefix": "full body, standing pose"
        }
      }
    }
  ]
}
```

JSON avoids adding a YAML parser dependency and is easy for tests and agents to consume. Obsidian notes stay human-facing and are referenced by `note_path`; they are not parsed on every generation request.

*Alternative considered:* Parse Obsidian Markdown frontmatter directly. Rejected for runtime because Markdown is flexible for humans but brittle for agent-safe validation and backend tests.

### Decision 2: File-backed provider with validation

Add a backend provider, similar in spirit to `PromptTemplateProvider`, that loads the catalog into typed models. The provider exposes:

- `list_presets()`
- `get_preset(preset_id)`
- `validate_presets(resources)`
- `compose(preset_id, profile, content_prompt, overrides)`

Validation compares catalog resource names against existing resource scanners: checkpoints, LoRAs, diffusion models, text encoders, VAEs, and workflow templates. Validation returns structured diagnostics instead of hiding invalid presets.

### Decision 3: Compose first, generate second

Preset composition returns a complete generation payload but does not submit a job:

```json
{
  "preset_id": "creator-a",
  "profile": "portrait",
  "generation": {
    "template": "default_lora",
    "checkpoint": "model.safetensors",
    "lora": "creator-a.safetensors",
    "lora_strength": 0.75,
    "prompt": "creator_a_style, anime illustration, upper body, looking at viewer, a girl in a raincoat",
    "negative_prompt": "low quality, bad anatomy",
    "steps": 28,
    "cfg": 6.5,
    "width": 1024,
    "height": 1024
  }
}
```

The agent then calls the existing `generate_image` MCP tool with the `generation` payload. This keeps debug visibility high: users and agents can inspect the exact prompt/params before generation.

*Alternative considered:* A single `generate_with_style_preset` tool. Rejected as the primary path because it hides prompt assembly and makes it less clear that user content still matters. A convenience wrapper can be added later, but it should internally call compose and then `generate_image`.

### Decision 4: Use `content_prompt` terminology

MCP and API composition inputs use `content_prompt`, not `prompt`, to distinguish "what the user wants in this image" from the full final prompt. The final prompt is built as:

1. preset `base_prompt`
2. profile `prompt_prefix`
3. user `content_prompt`
4. profile `prompt_suffix`

Blank parts are omitted and remaining parts are joined with commas. Negative prompts merge preset-level and profile-level negative prompts in the same way.

### Decision 5: Expand normal generation payload for diffusion components

The template path already has queue/workflow support for `diffusion_model`, `text_encoder`, and `vae`, but the normal `GenerateRequest` and MCP `generate_image` do not expose those fields. This change should expose them so an Anima-style preset can still use `generate_image` rather than forcing `generate_image_custom_workflow`.

### Decision 6: Skill guidance uses one daily generation skill

Daily use remains one generation skill:

- If the user specifies a preset, call list/get/compose preset tools, then `generate_image`.
- If the user specifies checkpoint/LoRA manually, validate with `list_available_resources`, then call `generate_image`.
- If no preset matches, ask whether to create a new preset recipe; that belongs to a separate curation workflow, not routine generation.

## Risks / Trade-offs

- **Catalog drift**: A preset can reference a deleted or renamed model file. Mitigation: validation endpoint/tool reports missing resources and composition returns a clear error for invalid required resources.
- **Prompt expectations**: A preset cannot guarantee a creator style for every content prompt. Mitigation: profiles make prompt variants explicit, and composition returns the final prompt for inspection.
- **Single LoRA MVP**: Some creator recipes may need multiple LoRAs. Mitigation: document this as out of scope for the first change; those recipes can use custom workflows until multi-LoRA template support is designed.
- **JSON editing ergonomics**: JSON is less pleasant than Markdown. Mitigation: Obsidian remains the writing surface for notes, and the JSON catalog stays compact and structured.
- **Diffusion-family support gap**: `generate_image` currently lacks public diffusion component fields. Mitigation: add those optional fields to backend schema and MCP tool while preserving existing behavior when omitted.

## Migration Plan

This is additive. Add the catalog file with an empty or example-safe preset list, new backend routes, and new MCP tools. Existing generation calls continue to work unchanged. Existing hard-coded character/style aliases can remain during transition, but new creator-style recipes should live in the catalog.

Rollback is removing the catalog routes/tools and leaving `generate_image` untouched except for harmless optional fields, which can remain backward compatible.

## Open Questions

- Exact catalog path: default to `backend/style_presets/catalog.json`, but this may become configurable if the user wants the file outside the repo.
- Whether the first curation workflow should create JSON directly or generate JSON from Obsidian note frontmatter.
