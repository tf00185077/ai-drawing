# Task specification

## Task
Consolidate the generation, job, Gallery, prompt, style-preset and ComfyUI tools to one tool per intent, each with a single risk label.

## Purpose
Overlapping tools make it hard for an agent to pick the right one. The owner approved consolidation ([decision](../../decisions/mcp.md)). Civitai and LoRA tools are left as they are because Phase 2 and Phase 5 redesign them; merging them now would be done twice.

## Outcome
An agent sees a short tool list where each tool has one intent and one risk label, and can still do everything it needs for the Phase 1 flow.

## Scope
Included: the [tool map](../../decisions/mcp.md#tool-map); `tool_catalog.py` gains a `risk` field (`read`, `mutate`, `admin`), exactly one per tool; `generate` keeps only the `template` and `custom_workflow` modes; Wan keyframe video, custom video and `civitai_generate_like` are removed from the registered tools (Backend code stays, frozen); `test_saved_style_preset_workflow` moves to `style_preset_test`; old names removed; friction items from [p1-00](../p1-00-mcp-friction-run-mac/task.md) mapped to this task; `docs/mcp.md` tool table and flows rewritten; tool names in `docs/OPERATING-POLICY.md`, `docs/ARCHITECTURE.md`, `style_presets/README.md`, `backend/workflows/README.md` and `docs/memory/` updated; Paperclip role prompts under `docs/team/` that name old tools or response shapes updated.
Excluded: Civitai tools and all LoRA tools, including `lora_train_job_status` and `lora_train_cancel` (envelope from p1-01 and one risk label only; no rename or merge); new behavior beyond the map (`wait_for_job` in p1-03; `health` and `list_workers` in p1-04); Backend API changes.
Open questions: final tool names may differ from the map if QA agrees each intent still has exactly one tool.
Read first: [decisions/mcp.md](../../decisions/mcp.md), the p1-00 friction log, the p1-01 result, [docs/mcp.md](../../mcp.md).

## Done when
- [ ] The registered tools match the catalog, and every old tool is either reachable through exactly one new tool, kept unchanged (Civitai, LoRA) or listed as removed (video, Civitai generate-like) — mapping table in the manifest. Check: test (`test_tool_catalog.py`) + manual review of the mapping. Evidence: test output and the table.
- [ ] Every tool has exactly one `risk` label in the catalog and its description states it. Check: test. Evidence: test output.
- [ ] Each mode or action of a merged tool has at least one test through the MCP call path. Check: test. Evidence: test names.
- [ ] Every p1-00 friction item mapped to p1-02 is fixed or explained in the manifest. Check: manual. Evidence: the list.
- [ ] `docs/mcp.md` lists the new tools and the common flow `health → list_resources → generate → wait_for_job → gallery_get`, and the MCP suite passes with no new failures. Check: manual documentation review + test. Evidence: doc link, command and summary line.

## Delivery
- Artifact: commit on a feature branch after p1-01, merged together with it; `manifest.md` with the old → new mapping.
- Known limitations: breaking change for existing MCP clients. Video generation is not reachable through MCP until the Phase 4 image-to-video tool.
