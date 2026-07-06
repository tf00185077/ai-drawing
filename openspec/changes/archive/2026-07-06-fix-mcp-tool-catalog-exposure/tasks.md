## 1. Inventory and Diagnosis

- [x] 1.1 Generate an MCP tool inventory from server registration, tool modules, docs, and Hermes-visible tool names.
- [x] 1.2 Compare intended tools against registered tools and identify missing, stale, duplicate, or undocumented tools.
- [x] 1.3 Specifically diagnose why `generate_video_custom_workflow` exists in code but is not available through the current Hermes MCP tool surface.
- [x] 1.4 Audit LoRA/loras exposure across resource listing, style presets, generation tools, multi-LoRA payloads, video workflows, and training registration.

## 2. Tool Registration and Catalog Fixes

- [x] 2.1 Add or update tests that fail when an intended MCP tool function is not registered with the server.
- [x] 2.2 Ensure video workflow tools, gallery artifact tools, LoRA training tools, style preset tools, ComfyUI schema tools, and workflow catalog tools are all registered or intentionally documented as omitted.
- [x] 2.3 Fix the registration/schema exposure layer for tools missing from external MCP clients.
- [x] 2.4 Add docs listing the audited MCP catalog and any intentional omissions or reload requirements.

## 3. LoRA Resource Contract

- [x] 3.1 Add tests proving `list_available_resources` exposes `loras` as a stable list with correct type and names from the backend resource inventory.
- [x] 3.2 Add tests proving style preset detail/compose preserves LoRA fields and ordered multi-LoRA entries where supported.
- [x] 3.3 Add tests proving generation/custom workflow tools forward LoRA and multi-LoRA payloads without silently dropping them.
- [x] 3.4 Fix any discovered LoRA/loras exposure bugs in MCP server tools or backend payload mapping.

## 4. Response Contract Cleanup

- [x] 4.1 Classify existing MCP tools as structured dict, JSON-string transitional, or legacy human-readable.
- [x] 4.2 Convert machine-facing tools that currently return JSON strings into structured JSON dictionaries where safe.
- [x] 4.3 For tools that must remain string-returning for compatibility, add parseability tests and documentation.
- [x] 4.4 Standardize structured errors with `ok=false`, `tool`, and `error.code/message/details` where practical.

## 5. Verification

- [x] 5.1 Run MCP server tests and backend tests covering changed contracts.
- [x] 5.2 Validate this OpenSpec change with `openspec validate fix-mcp-tool-catalog-exposure --strict` and `openspec validate --all`.
- [x] 5.3 Run low-load live MCP/backend smoke for catalog visibility and LoRA resource exposure without starting heavy generation/training jobs unless CTY explicitly approves.
  - Hermes live smoke 2026-07-06: restarted backend on `127.0.0.1:8001`, `/health` returned 200; FastMCP `mcp.list_tools()` returned 43 tools and included `generate_video_custom_workflow`, `get_gallery_artifact`, `list_available_resources`, `compose_style_preset`, `lora_dataset_list`, and `lora_train_start`; `generate_video_custom_workflow` input schema/signature includes `lora`, `lora_strength`, and `loras`; `list_available_resources()` returned `ok=true`, `loras` as a list with 21 entries including Wan LoRA resources; style preset listing/detail parsed successfully. No generation or training jobs were submitted.
- [x] 5.4 Update `docs/PROGRESS.md` with audit findings, fixed issues, and remaining blockers.
