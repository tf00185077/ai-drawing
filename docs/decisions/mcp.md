# Decisions · mcp

## Settled
- Every MCP tool returns one envelope: `{ok, data}` on success, `{ok: false, error: {code, message, hint}}` on failure · why: agents learn one shape · owner-confirmed
- Tools are consolidated to one tool per intent (about 20, from 40) · why: a smaller surface is easier for agents to choose from · owner-confirmed · [tool map](#proposed-tool-map)
- End-to-end MCP verification runs on the Mac ComfyUI first, then extends to the Windows worker · owner-confirmed
- Phase 1 is implemented by the Paperclip team from the specs in `docs/tasks/p1-*`; this planning session only writes documents · owner-confirmed

## Log (newest first)

### 2026-11-23 · Phase 1 MCP direction
- Decision: uniform envelope for all tools; consolidate to ~20 intent tools; Mac-first end-to-end smoke; team implements.
- Why: Phase 1 exit needs an agent to go from nothing to a retrieved, revised image without help.
- Supersedes: the mixed `plain_text` / `json_string` / `dict` response categories.
- Provenance: owner-confirmed@"全部統一" · "精簡合併" · "mac優先，之後才擴充到worker的windows" · "這個session都只定義文件"
- Link: [ROADMAP Phase 1](../roadmap/ROADMAP.md#phase-1--mcp-that-agents-use-smoothly-next)

## Proposed tool map

Status: proposal for the consolidation task ([p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md)); the coding agent may adjust names with QA agreement, but each intent keeps one tool.

| New tool | Replaces | Risk |
|---|---|---|
| `health` | `mcp_ping` (adds ComfyUI and worker reachability) | read |
| `list_resources` | `list_available_resources` | read |
| `generate` (`mode`: `template`, `custom_workflow`, `video_keyframes`, `video_custom`, `style_preset_graph`, `civitai_like`) | `generate_image`, `generate_image_custom_workflow`, `generate_video_wan_keyframes`, `generate_video_custom_workflow`, `test_saved_style_preset_workflow`, `civitai_generate_like` | mutate |
| `job_status` | `get_generation_status`, `lora_train_job_status` | read |
| `wait_for_job` | new | read |
| `cancel_job` | `cancel_job`, `lora_train_cancel` | mutate |
| `gallery_search` | `gallery_list` | read |
| `gallery_get` | `get_gallery_image`, `get_gallery_artifact` | read |
| `gallery_rerun` | `gallery_rerun` | mutate |
| `prompt_search` | `prompt_library_search` | read |
| `prompt_compose` | `prompt_library_compose` | read |
| `prompt_write` (`action`: `save`, `archive`, `restore`) | `prompt_library_save`, `prompt_library_archive`, `prompt_library_restore` | mutate |
| `style_preset_get` (no id = list) | `list_style_presets`, `get_style_preset` | read |
| `style_preset_compose` | `compose_style_preset` | read |
| `style_preset_save` (`from`: fields or successful job) | `create_style_preset`, `save_successful_workflow_as_style_preset` | mutate |
| `civitai_inspect` | `civitai_source_info` | read |
| `civitai_acquire` (returns status when polled with its id) | `civitai_resource_acquire`, `civitai_resource_status` | mutate |
| `comfyui_admin` (`action`: `restart`, `free_memory`, `install_node`) | `comfyui_restart`, `free_comfyui_memory`, `comfyui_node_provision` | admin |
| `deliver_to_discord` | `deliver_generation_result_to_discord` | mutate |
| `lora_dataset` (`action`: `list`, `inspect`, `caption`) | `lora_dataset_list`, `lora_dataset_inspect`, `caption_image` | read / mutate |
| `lora_preflight` | `lora_training_decision_preflight` | read |
| `lora_train` (`action`: `start`, `logs`, `smoke_test`) | `lora_train_start`, `lora_train_logs`, `lora_train_smoke_test` | mutate |
| `list_workers` | new | read |

## Open questions
- Which checkpoint and workflow the Mac smoke test uses — needed by [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md).
