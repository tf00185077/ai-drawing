# Progress

Progress against the [roadmap](roadmap/ROADMAP.md), based on the code on `main` (2026-11-23). Current state in one screen: [CURRENT](CURRENT.md).

Status: **Done** = in code with tests · **Partial** = some of it in code · **Not started** = not in code.
Real run: **Yes** = seen working against a real ComfyUI/GPU · **No** = tests only.

## Phase 0 — Clean foundation (done 2026-11-24)

| Item | Status |
|---|---|
| Retained work integrated into `main` (`32b59fd`) | Done |
| Docs rebuilt in English (entry, policy, architecture, current, roadmap, topics, team, memory) | Done |
| History, research data, OpenSpec and scratch files removed | Done |
| Progress table based on current code | Done (this page) |
| Known test failures removed (outdated snapshot, packaging and platform tests); fixtures pinned to LF | Done |
| Backend suite on Windows: no failures or hangs (2018 passed, 6 skipped); MCP 314 passed | Done 2026-11-24 |
| LoRA run files read as UTF-8 on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)) | Done 2026-11-24 |
| Backend suite on macOS after the cleanup | Moved to [p1-05](tasks/p1-05-mcp-e2e-smoke-mac/task.md) |

## Goal 1 — MCP for agents

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| 40 intent-level tools, catalog kept in sync with registration | Done | `mcp-server/mcp_server/tool_catalog.py`, `server.py` | `test_tool_catalog.py`, `test_server.py` | — |
| Image, custom-workflow and video generation; status; cancel | Done | `tools/generate.py` | `test_generate_tools.py`, `test_tools.py` | No |
| Revision context and parent lookup on generation | Done | `schemas/generate.py`, `tools/generate.py` | `test_revision_context.py` (Backend + MCP), `test_revision_parent_errors.py` | No |
| Gallery read, artifact read, rerun | Done | `tools/gallery.py` | `test_tools.py` | Yes (read of an existing image) |
| Prompt Library, style presets, Civitai tools | Done | `tools/prompt_library.py`, `style_presets.py`, `civitai.py` | matching `test_*` files | No |
| ComfyUI restart, node install, free memory | Done | `tools/comfyui_nodes.py`, `comfyui.py` | `test_comfyui_nodes.py` | No |
| Discord delivery of results | Done | `tools/discord_delivery.py` | `test_discord_delivery.py` | No |
| Uniform structured responses `{ok, data, error}` | Not started | — | — | — |
| `wait_for_job` and result tool | Not started | — | — | — |
| `list_workers` / `worker_status` | Not started | — | — | — |
| End-to-end smoke script against real ComfyUI | Not started | — | — | — |

## Goal 2 — One-sentence flow (resources → workflow → image or clip)

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Civitai resource acquire/status, source info, generate-like (MCP) | Done | `tools/civitai.py`, `services/civitai_resource_*` | `test_civitai_*` | No |
| Civitai recipe import, resource resolution, safe download, source aliases, local identity ledger | Done | `services/civitai_*`, `api/civitai_*` | `test_civitai_*` | No |
| Civitai model search by text, type and base model (MCP) | Not started | — | — | — |
| Resource record agents can list and filter; hash lookup of unknown local files | Partial (ledger and aliases exist; no agent-facing record) | `services/civitai_local_identity_ledger.py`, `civitai_source_alias_registry.py` | `test_civitai_*` | — |
| Workflow selection from chosen resources | Partial (manifest match exists) | `core/workflow_manifest.py`, `api/workflow_catalog.py` | `test_workflow_match.py` | No |
| Image-to-video workflows (Wan first frame, first+last frame) | Done | `backend/workflows/gen_img2video_wan_*`, `api/generate.py` | `test_wan_keyframes.py` | No |
| FILM frame interpolation | Done | `services/film_postprocess.py` | `test_film_audio_mux.py` | No |
| One fixed image-to-video + interpolation MCP tool | Not started | — | — | — |
| End-to-end one-sentence run | Not started | — | — | — |

## Goal 3 — LAN Windows workers

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Worker service: ComfyUI proxy and PowerShell routes | Done | `worker/windows/worker.py`, `powershell_control.py` | `test_worker_runtime.py`, `test_worker_powershell_control.py` | No |
| Backend client, `execution_target=worker`, no local fallback | Done | `services/nvidia_worker.py`, `core/queue.py` | `test_worker_routing.py` | No |
| LAN discovery with hostname/protocol check | Done | `services/nvidia_worker.py` | `test_worker_pairing.py` | No |
| Install, start and packaging scripts | Partial (never installed successfully) | `worker/windows/*.ps1`, `scripts/build-windows-worker.py` | `test_worker_all_entrypoints.py` | No |
| Backend–worker authentication | Not started (token exists only in legacy updater) | — | — | — |
| Same-project check (commit, workflows, nodes, models) | Not started | — | — | — |
| Durable, concurrent queue | Not started (in-memory, one job at a time) | `core/queue.py` | — | — |
| Worker registry, heartbeat, `execution_target=auto` | Not started | — | — | — |
| Replace legacy updater | Not started | `worker/windows/updater/` | `test_worker_updater_*` | — |

## Goal 4 — LoRA training

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Dataset listing, inspection, metadata, locks | Done | `services/lora_dataset.py` | `test_lora_dataset_service.py`, `test_lora_training_worker_lock.py` | No |
| Auto-captioning (WD Tagger), caption assessment, curation | Done | `services/watcher.py`, `wd_tagger.py`, `lora_dataset_*` | `test_watcher.py`, `test_wd_tagger.py`, `test_lora_dataset_*` | No |
| Preflight and explicit recipe compiler | Done | `services/lora_training_decision.py`, `lora_training_recipe.py` | `test_lora_training_decision.py`, `test_lora_training_recipe*` | No |
| sd-scripts runner for SD1.5, SDXL, Anima | Done | `services/lora_trainer.py` | `test_lora_trainer.py`, `test_lora_lifecycle.py` | No |
| Output name with serials, per-run folders, parameter record | Done | `services/lora_trainer.py` | `test_lora_delivery.py`, `test_lora_public_results.py` | No |
| Registration status separate from training status | Done | `services/lora_trainer.py` | `test_lora_projection_contract.py` | No |
| Smoke test with reconciliation and image validation | Done (tests removed 2026-11-24; new smoke tests come with Phase 4) | `services/lora_trainer.py` | — | No |
| UI pages and MCP tools | Done | `pages/LoraTrain.tsx`, `LoraDocs.tsx`, `tools/lora_train.py` | `LoraTrain.test.tsx`, `test_lora_train_tools.py` | No |
| First real training run | Not started | — | — | — |
| Training on a worker | Not started | — | — | — |

## Goal 5 — Prompt dashboard

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Prompt Library storage, hierarchy, search, archive/restore | Done | `core/prompt_library*.py`, `api/prompt_library.py` | `test_prompt_library_*`, `test_prompt_search.py` | — |
| Comma-atomic fragments and migration | Done | `core/prompt_atomic.py`, `comma_atomic_migration.py` | `test_prompt_atomic.py`, `test_comma_atomic_*` | — |
| Workbench: compose, weight, order, save combinations | Done | `components/prompt-library/` | `PromptWorkbench.test.tsx`, `compositionState.test.ts` and others | No |
| Category and entry management pages | Done | `pages/PromptCategory*.tsx` | matching tests | No |
| Submit to a generation form | Done | `GenerationPanel.tsx`, `api/workflow_catalog.py` | `GenerationPanel.test.tsx`, `test_workflow_generation_form.py` | No |
| Workflow templates with capability manifests, match, backfill | Done | `core/workflow_manifest.py`, `api/workflow_catalog.py` | `test_workflow_manifest.py`, `test_workflow_match.py`, `test_template_backfill.py` | No |
| Style presets: catalog, compose, author, save and retest graphs | Done | `core/style_presets.py`, `services/style_preset_workflows.py` | `test_style_preset*` | No |
| Gallery: seed precision, readable modal, dev routing | Done | `pages/Gallery.tsx`, `vite.config.js` | `Gallery.test.tsx` | Yes (Mac, existing image) |
| Recipe = combination + template + models + parameters | Partial (style presets only) | — | — | — |
| Progress, errors and thumbnails on the Workbench | Not started | — | — | — |
| MCP `generate_from_recipe` | Not started | — | — | — |

## Other capabilities on main

| Capability | Code | Tests |
|---|---|---|
| Video beyond the fixed image-to-video flow (frozen): Wan keyframes, fixed Discord video workflows, Argus MLX (Mac) | `core/wan_keyframes.py`, `fixed_video_workflows.py`, `services/film_postprocess.py`, `argus_mlx_i2v.py` | `test_wan_keyframes.py`, `test_fixed_video_*`, `test_film_audio_mux.py`, `test_argus_mlx_*` |
| ComfyUI history import of UI-made images | `services/comfyui_history_watcher.py` | `test_comfyui_history_watcher.py` |
| Discord bot: slash commands, operator delivery endpoint | `discord-bot/bot/` | `discord-bot/tests/` |
| Launcher (setup, start, stop, status) | `setup.sh`, `setup.ps1`, `scripts/launcher/` | `scripts/tests/` |

## Log

### 2026-11-24 — Phase 0 closed
- Windows Backend and MCP suites pass with no hangs; non-feature failing tests removed; LoRA files read as UTF-8 (`1898378`). macOS rerun moved into p1-05 by the owner.

### 2026-11-24 — Roadmap rebuilt around the one-sentence flow
- New Goal 2 (Civitai tools, resource record, workflow selection, fixed image-to-video with interpolation); LoRA is core and moves ahead of the dashboard. Goals renumbered: MCP → one-sentence flow → workers → LoRA → dashboard ([decisions](decisions/roadmap.md)).

### 2026-11-23 — Four goals set; Phase 0 started
- CTY set the four goals and their order: MCP for agents → LAN Windows workers → prompt dashboard → LoRA training (workers moved ahead of the dashboard the same day).
- Retained LoRA, Gallery and maintenance work from 29 local branches integrated into `main` as `32b59fd`.
- Documentation rebuilt in English; operating policy made default-open; memory pruned ([decisions](decisions/roadmap.md)).
- History, research data, OpenSpec and scratch files removed; verified behavior rules moved into the topic docs.
