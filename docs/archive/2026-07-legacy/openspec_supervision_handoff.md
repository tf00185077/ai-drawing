# Hermes handoff — OpenSpec supervision

Date: 2026-07-06
Project: /Users/tf00185088/Desktop/ai-drawing

## User directive
CTY asked Hermes to act as senior verifier/supervisor, not implementer:
- Codex writes implementation using OpenSpec skill/process.
- Hermes verifies: diff, tasks, tests, OpenSpec validate, low-load runtime smoke.
- When one OpenSpec change is fully implemented and tested, Hermes archives and commits it.
- Do not mix incomplete OpenSpec work into another change's commit.

## Completed and committed
- `add-video-generation-mcp` archived and committed.
- Commit: `ea149a5 Archive video generation MCP OpenSpec`.

## Current situation
- `fix-mcp-tool-catalog-exposure` was implemented/tested/archived in the worktree, but NOT committed yet.
- Reason: it depends on LoRA training tools from active `add-lora-training-mcp-workflow`; committing now would mix an incomplete OpenSpec change.
- Hermes gate for `fix-mcp-tool-catalog-exposure` passed:
  - backend tests: 287 passed
  - MCP tests: 97 passed
  - OpenSpec validate all: passed
  - live smoke: backend health 200; FastMCP tool_count 43; `generate_video_custom_workflow`, `get_gallery_artifact`, `list_available_resources`, `compose_style_preset`, `lora_dataset_list`, `lora_train_start` visible; video schema has `lora`/`loras`; `list_available_resources.loras` list count 21.
- `fix-mcp-tool-catalog-exposure` archived as `openspec/changes/archive/2026-07-06-fix-mcp-tool-catalog-exposure/`; pending commit after dependency order is resolved.

## Active Codex process
Codex was started to resolve `add-lora-training-mcp-workflow` first:
- session_id: proc_16520c41eeb4
- command prompt file: /Users/tf00185088/Desktop/tmp/codex_finish_lora_training_mcp_workflow.md
- task: make `add-lora-training-mcp-workflow` archivable if legitimate, or split full Kohya runtime check into follow-up OpenSpec if blocked by missing sd-scripts; no commit/archive by Codex.

## Next steps after Codex completes
1. Poll process `proc_16520c41eeb4` if still in same Hermes process; after reboot it will be gone, so inspect files instead.
2. Run:
   - `cd /Users/tf00185088/Desktop/ai-drawing`
   - `git status --short --branch`
   - `openspec list`
   - `pytest backend/tests/ -x -q`
   - `(cd mcp-server && .venv/bin/python -m pytest tests/ -x -q)`
   - `openspec validate --all`
3. If `add-lora-training-mcp-workflow` is complete and validated, archive it and commit only its files.
4. Then commit the already archived `fix-mcp-tool-catalog-exposure` if still validated; ensure no incomplete change is mixed.
5. Continue with the next active OpenSpec change in order.

## Reboot recovery
If the computer restarts, open this file and the Discord/session history, then resume from `git status`, `openspec list`, and tests. Do not assume the background Codex process survived reboot.
