## Why

Formal multi-LoRA requirements have already been archived into the main specs, but the current workspace still needs an implementation/test audit with explicit MCP coverage. This change tracks the remaining verification work without changing the accepted requirements.

## What Changes

- Audit backend workflow injection, generation request plumbing, style preset parsing/composition/creation, and MCP generation/preset tools against the formal multi-LoRA specs.
- Add missing regression tests proving ordered `loras` are forwarded by MCP tools and preserved by style preset MCP/API paths.
- Apply only minimal implementation fixes if the tests expose a real code gap.
- Record verification commands for Hermes to review before archive/commit/push.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

The formal generation and preset behavior already lives in:

- `custom-workflow-generation`: Multiple LoRAs fill loader nodes positionally.
- `style-preset-catalog`: Presets support an ordered multi-LoRA list.

This change modifies only:

- `mcp-tool-catalog`: make LoRA field exposure explicit for MCP tool input schemas, so catalog tests cover `loras` on supported generation and style preset tools.

## Impact

- Backend: workflow parameter injection, generate schemas/API/queue params, style preset provider and API.
- MCP server: generation tools, style preset tools, audited tool catalog schema exposure.
- Tests: backend multi-LoRA/style preset/generate API coverage and MCP tool/catalog coverage.
