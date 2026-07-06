## Why

Agents need a safe way to propose caption fixes after inspection, but caption edits are high-risk because manual captions must not be overwritten silently. This change adds a deterministic curation workflow with dry-run plans, explicit apply, backup, rollback, noisy tag removal, trigger normalization, and outlier flagging.

## What Changes

- Add a backend curation plan operation that previews caption changes without writing files.
- Support trigger normalization, protected tag preservation, removable/noisy tag cleanup, duplicate cleanup, and outlier flagging.
- Add explicit apply and rollback with backups, expected hashes, and per-file change reporting.
- Protect manual captions by default; manual overwrites require explicit per-file approval or a clearly named override.
- Add MCP curation tools for dry-run, apply, and rollback.
- Keep the archived `lora_dataset_prepare` behavior intact and treat this as a stricter curation layer.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `lora-training-workflow`: Add safe dataset curation planning, apply, backup, and rollback behavior.
- `lora-training-mcp-tools`: Add agent-facing curation tools.

## Impact

- Affected backend areas: dataset/caption services, backup storage, schemas, API routes, tests.
- Affected MCP areas: LoRA tool wrappers, tool catalog, tests.
- Prerequisites: `add-lora-dataset-metadata-profiles` and `add-lora-dataset-agent-inspection-mcp`.
