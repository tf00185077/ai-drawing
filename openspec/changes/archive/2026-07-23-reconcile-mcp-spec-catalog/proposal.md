## Why

The project's MCP specs have drifted from the code. A previous revision trimmed the MCP surface (the
LoRA tools now say the surface "keeps only the decision-and-train loop"), but the specs were never
updated: `lora-training-mcp-tools` still declares ~12 tools while the code implements 6, and both
`lora-training-mcp-tools` and `mcp-tool-catalog` still carry `TBD` Purpose placeholders from their
archive. Several specs reference MCP tool names that no longer match the 29 tools actually registered.
Once `add-anima-lora-training-support` lands, the tool set is final and should be reconciled once,
authoritatively.

## What Changes

**Depends on `add-anima-lora-training-support` being implemented first** — this change inventories the
final tool set, including the tools that change adds.

- Produce an authoritative inventory of every `@mcp.tool` registered in `mcp-server/mcp_server/tools/`
  and cross-check it against `tool_catalog.py`.
- Reconcile every MCP-referencing spec so declared tools match registered tools: remove requirements
  for tools that were intentionally dropped, keep/annotate those that are genuinely planned, and add
  any implemented-but-unspecified tools.
- Decide and record the fate of the remaining drifted dataset tools not restored by the anima change
  (`lora_dataset_prepare`, `lora_dataset_validate`, `lora_dataset_caption_assess`, metadata, curation,
  agent-inspect): either mark explicitly as planned/not-implemented or REMOVE with reason + migration.
- Replace the `TBD` Purpose placeholders in `mcp-tool-catalog` and `lora-training-mcp-tools` with real
  purpose statements.
- Ensure the `tool_catalog.py` audit test covers exactly the final registered set.

Non-goals: adding new tool behavior or changing generation/training logic — this change is
spec-and-catalog hygiene only.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
<!-- Concrete delta files are authored at apply time, after add-anima-lora-training-support lands,
     because they depend on the final registered tool set. Expected specs to touch: -->
- `mcp-tool-catalog`: real Purpose; audit catalog matches the final registered tool set.
- `lora-training-mcp-tools`: real Purpose; declared tools reconciled with code; drifted tools resolved.
- Other MCP-referencing specs as the inventory reveals mismatches (`video-generation-artifacts`,
  `style-preset-catalog`, `custom-workflow-generation`, `workflow-template-catalog`).

## Impact

- Specs under `openspec/specs/` (catalog + LoRA + any mismatched MCP-referencing specs).
- `mcp-server/mcp_server/tool_catalog.py` and its audit test.
- No runtime behavior change.
