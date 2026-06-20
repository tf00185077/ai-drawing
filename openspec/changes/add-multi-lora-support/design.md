## Context

`apply_params` (app/core/workflow.py) injects a single `lora`/`lora_strength` into every `LoraLoader`/`LoraLoaderModelOnly` node. The single value is threaded from `StylePreset.lora`, `compose`, `GenerateRequest`, queue params, and the MCP tools. The catalog vocabulary already has `multi_lora`/`lora_model_only` conditioning tags, but no parameter channel fills multiple LoRAs.

## Goals / Non-Goals

**Goals:**
- An ordered `loras` list (`{name, strength_model, strength_clip?}`) end to end: preset → compose → generate → apply_params.
- Positional mapping to loader nodes; per-LoRA strengths.
- Full backward compatibility with single `lora`/`lora_strength`.

**Non-Goals:**
- Auto-inserting loader nodes (templates must already contain enough).
- A denormalized DB column for the lora list (persisted `workflow_json` already captures the applied result).
- Named/`node_id`-keyed mapping (rejected in favor of positional; simpler, author-controlled by node order).

## Decisions

### Decision 1: Ordered list, positional mapping by workflow-JSON node order
`loras[i]` → the i-th `LoraLoader`/`LoraLoaderModelOnly` node, collected in workflow dict iteration order (= JSON file order, preserved by `json.load`). The template author controls assignment by ordering loader nodes in the file.
- *Alternatives:* node_id-keyed (preset must bind to node ids — brittle across template edits) or named slots (more machinery). Positional is simplest and matches the list shape.

### Decision 2: Coexist with single lora; loras wins
Keep `lora`/`lora_strength`. In `apply_params`, if `loras` is provided use the positional path; else keep the current "single value into all loaders" behavior. If both, `loras` wins.
- *Why:* zero breakage for existing presets/templates and the `default_lora` path.

### Decision 3: strength defaults
Each entry: `strength_model` defaults to 1.0; `strength_clip` defaults to `strength_model`; `LoraLoaderModelOnly` sets only `strength_model` (no clip).

### Decision 4: Data shape
`LoraSpec` = `{name: str, strength_model: float = 1.0, strength_clip: float | None = None}`. Represented as plain dicts in core (workflow/queue/preset JSON) and as a Pydantic `LoraSpec` in API schemas. Preset JSON stores `loras: [ {...} ]`.

### Decision 5: Extra/short handling
More loras than loader nodes → apply the first N (N = node count), ignore the rest (no error). Fewer loras than nodes → remaining loader nodes are left as the workflow defines them.

## Risks / Trade-offs

- **[Order ambiguity]** positional mapping relies on stable workflow-JSON node order → Mitigation: `json.load` preserves order; document that loader-node order defines lora slots; the multi_lora template owns that order.
- **[Summary index]** adding `loras` to the lightweight index slightly enlarges it → negligible (a few entries per preset).
- **[Mixed signals]** both `lora` and `loras` set → defined precedence (loras wins) avoids ambiguity.

## Migration Plan

Additive and backward compatible. Existing single-`lora` presets/requests behave exactly as before. No data migration. Reindex is unaffected (summary just gains an optional `loras`).

## Open Questions

- Whether to validate each lora `name` against installed LoRAs at compose/create time — current behavior reports missing resources non-blocking for the single lora; extending that to the list is a later refinement.
