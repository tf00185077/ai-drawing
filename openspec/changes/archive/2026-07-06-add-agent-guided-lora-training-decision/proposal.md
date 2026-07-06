## Why

CTY wants LoRA training to happen only after an agent inspects a dataset and the user asks to train a specific LoRA. A deterministic training decision preflight gives Hermes a repeatable train / needs review / do not train result with reasons and suggested next actions, without starting training automatically.

## What Changes

- Add backend training decision preflight that combines metadata, caption suitability, validation, curation status, hashes, and configured training constraints.
- Return a decision of `train`, `needs_review`, or `do_not_train` with reasons, blocking issues, recommended next actions, and suggested training parameters.
- Add MCP access for the decision preflight.
- Require that decision preflight is side-effect free and never enqueues training.
- Keep the existing explicit `lora_train_start` tool/API as the only training trigger.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `lora-training-workflow`: Add deterministic agent-guided training decision preflight.
- `lora-training-mcp-tools`: Add MCP access to training decision preflight.

## Impact

- Affected backend areas: LoRA dataset assessment/validation orchestration, schemas, API routes, tests.
- Affected MCP areas: LoRA tools and catalog.
- Prerequisites: `add-lora-dataset-metadata-profiles`, `add-lora-dataset-agent-inspection-mcp`, and `add-lora-dataset-curation-workflow`.
