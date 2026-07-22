## 0. Precondition

- [ ] 0.1 Confirm `add-anima-lora-training-support` is implemented and archived (final tool set exists).

## 1. Inventory

- [ ] 1.1 Enumerate every `@mcp.tool` in `mcp-server/mcp_server/tools/` into an authoritative list (name, module, backend endpoint, one-line purpose).
- [ ] 1.2 Diff the inventory against `mcp-server/mcp_server/tool_catalog.py`; record tools missing from or extra in the catalog.
- [ ] 1.3 Grep `openspec/specs/` for MCP tool names and map each declared tool to present/absent in code.

## 2. Reconcile specs

- [ ] 2.1 Author the delta for `lora-training-mcp-tools`: reconcile declared tools with code; resolve the remaining drifted dataset tools (prepare/validate/caption_assess/metadata/curation/agent_inspect) as either annotated-planned or REMOVED (with reason + migration).
- [ ] 2.2 Author the delta for `mcp-tool-catalog`: real Purpose; requirement that the audited catalog equals the final registered set.
- [ ] 2.3 Fix mismatches in other MCP-referencing specs surfaced by 1.3 (`video-generation-artifacts`, `style-preset-catalog`, `custom-workflow-generation`, `workflow-template-catalog`).
- [ ] 2.4 Replace `TBD` Purpose placeholders in the touched specs with real purpose statements.

## 3. Align catalog + tests

- [ ] 3.1 Update `tool_catalog.py` so the catalog matches the final registered tool set.
- [ ] 3.2 Ensure the catalog audit test fails on any missing/renamed/extra tool and passes for the reconciled set.

## 4. Verification

- [ ] 4.1 Run the MCP catalog audit test and the MCP tool tests; confirm green.
- [ ] 4.2 Run `openspec validate reconcile-mcp-spec-catalog --strict`.
- [ ] 4.3 Update `docs/PROGRESS.md`.
