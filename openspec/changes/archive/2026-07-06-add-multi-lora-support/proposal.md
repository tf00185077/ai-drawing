## Why

The whole generation pipeline carries a single LoRA: `lora: str` + `lora_strength: float` on style presets, `GenerateRequest`, and the MCP tools, and `apply_params` writes that one value into **every** `LoraLoader` node. A creator recipe that needs several LoRAs (e.g. style + character + detail, each with its own strength) cannot be expressed, and a hand-built multi-LoRA graph cannot be parameterized per node (all loaders get clobbered with the same value). The template catalog can already *describe* a `multi_lora` template, but there is no data channel to *fill* it — a describable-but-unfillable gap.

## What Changes

- Add a `loras` channel — an ordered list of `{name, strength_model, strength_clip?}` — alongside the existing single `lora`/`lora_strength` (kept for backward compatibility).
- `apply_params` maps the `loras` list to the workflow's `LoraLoader` / `LoraLoaderModelOnly` nodes **in the order those nodes appear in the workflow JSON** (the i-th lora → the i-th loader). `strength_clip` defaults to `strength_model`; `LoraLoaderModelOnly` ignores clip. When `loras` is omitted, the existing single-`lora`-applied-to-all behavior is unchanged.
- Thread `loras` through: `GenerateRequest` + `/api/generate` + queue params; MCP `generate_image` / `generate_image_custom_workflow`.
- Thread `loras` through the style preset: `StylePreset` model + parse, `compose` (emits `generation.loras`), `CreatePresetRequest`, `StylePresetDetail`, and the index summary; `create_style_preset` accepts `loras`.
- Precedence: when both `lora` and `loras` are provided, `loras` wins.

## Capabilities

### Modified Capabilities
- `style-preset-catalog`: presets and composition support an ordered multi-LoRA list (each with per-LoRA strengths), in addition to the single-LoRA field.
- `custom-workflow-generation`: parameter injection fills multiple `LoraLoader` nodes from an ordered `loras` list (positional mapping), instead of only a single shared LoRA.

## Impact

- Backend core: `app/core/workflow.py` (`apply_params` multi-lora injection + ordered loader collection), `app/core/queue.py` (`GenerateParams.loras`, pass-through), `app/core/style_presets.py` (`StylePreset.loras`, `_parse_preset`, `compose_preset`, summary).
- Backend schemas/API: `app/schemas/generate.py` (`LoraSpec`, `GenerateRequest.loras` / custom), `app/schemas/style_presets.py` (loras on detail/create/summary), `app/api/generate.py`, `app/api/style_presets.py`.
- MCP: `generate_image`, `generate_image_custom_workflow`, `create_style_preset` gain `loras`.
- Docs: `style_presets/README.md`, `docs/PROGRESS.md`.
- Backward compatible: single `lora`/`lora_strength` keeps working; existing presets/templates unaffected.
- Out of scope: a denormalized multi-lora DB column (the persisted `workflow_json` already captures the applied loras for faithful rerun); auto-adding LoraLoader nodes to a graph (templates must provide enough loader nodes).
