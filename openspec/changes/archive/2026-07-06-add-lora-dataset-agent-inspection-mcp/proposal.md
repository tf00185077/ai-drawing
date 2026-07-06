## Why

Hermes/OpenClaw need stable agent entrypoints for inspecting LoRA datasets before proposing curation or training. The archived MCP tools expose basic dataset list/inspect/assessment, and this change adds metadata-aware inspection plus explicit metadata get/update/validate operations.

## What Changes

- Add backend metadata profile get, update, and validate operations for `.lora-dataset.json`.
- Enrich dataset inspection outputs with profile status, caption suitability summary, dataset hash, profile hash, and watcher/caption status references.
- Add MCP entrypoints for dataset metadata get/update/validate.
- Add an agent-ready MCP inspection entrypoint that composes existing list/inspect/assessment/profile signals without starting training.
- Require conflict checks for metadata updates through expected profile hashes.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `lora-training-workflow`: Add backend metadata management and agent inspection composition.
- `lora-training-mcp-tools`: Add MCP profile and agent inspection entrypoints.

## Impact

- Affected backend areas: LoRA dataset API routes, dataset profile service, schemas, tests.
- Affected MCP areas: `mcp-server/mcp_server/tools/lora_train.py`, tool catalog, MCP tests.
- Prerequisite: `add-lora-dataset-metadata-profiles` for profile schema and defaults, plus archived caption suitability assessment from `2026-07-06-improve-lora-watchdog-reliability`.
