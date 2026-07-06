# Change: Fix MCP tool catalog exposure and LoRA resource contract

## Why

The ai-drawing MCP server has grown feature-by-feature, and the exposed tool catalog is no longer clearly aligned with backend capabilities, documentation, Hermes-visible tools, and test coverage.

Recent runtime supervision found concrete inconsistencies:

- `generate_video_custom_workflow` exists in `mcp-server/mcp_server/tools/generate.py`, but it is not visible through the current Hermes ai-drawing MCP tool surface used in this session. Hermes had to import the Python MCP helper directly to run the video OpenSpec runtime smoke, which is not an acceptable normal workflow.
- LoRA-related exposure is split and confusing: generation resources return `loras`, training dataset tools return structured dictionaries, older tools return JSON strings or human-readable strings, and not every backend LoRA route has an agent-facing tool or documented omission.
- The user previously reported that `loras` were not correctly exposed by the MCP server. This needs a focused audit and fix, especially across `list_available_resources`, style preset composition, multi-LoRA support, video LoRA resources, and tool registration/schema visibility.
- Tool return contracts are inconsistent: older MCP tools return strings containing JSON, while newer LoRA tools return dictionaries. This makes downstream agents brittle and hides schema errors until runtime.
- There is no single regression test proving every intended tool is registered, documented, callable, and maps to a live backend route or an intentionally documented local-only operation.

## What Changes

- Add a machine-readable MCP tool catalog expectation and tests that compare registered tools against implemented tool functions and docs.
- Ensure all supported ai-drawing MCP tools are actually registered and visible to MCP clients, including video workflow tools and LoRA-related tools.
- Fix LoRA resource exposure so `loras` and, where supported, ordered multi-LoRA payloads are consistently visible in MCP resource listing, style preset composition, and generation payloads.
- Normalize agent-facing tool responses toward structured JSON-compatible dictionaries, or explicitly document and test transitional string-return compatibility where changing return type would break existing clients.
- Add structured error handling for missing backend endpoints, unavailable runtime resources, and schema/registration mismatches.
- Update MCP setup docs and progress notes with the audited tool list and known intentional omissions.

## Out of Scope

- Rewriting backend generation/training workflows beyond what is required for MCP tool exposure and contract correctness.
- Installing large models, ComfyUI nodes, or external dependencies.
- Completing heavy runtime jobs; runtime smoke should be low-load and may record blockers when local resources are missing.
- Archiving existing OpenSpec changes.

## Impact

- Affected specs: `mcp-tool-catalog`.
- Affected code: `mcp-server/mcp_server/server.py`, `mcp-server/mcp_server/tools/*`, MCP tests, possibly backend tests for resource payload consistency, and docs.
- Affected runtime integrations: backend `:8001`, ComfyUI `:8188`, resource inventory, workflow templates, LoRA/style preset payloads.
