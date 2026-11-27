# Progress

Progress against the [roadmap](roadmap/ROADMAP.md), based on the code on `main` (2026-11-27). Current state in one screen: [CURRENT](CURRENT.md).

Status: **Done** = in code with tests · **Partial** = some of it in code · **Not started** = not in code.
Real run: **Yes** = seen working against a real ComfyUI/GPU · **No** = tests only.

## Task log

One row per task. Each task folder keeps only its spec, kickoff, manifest, review and
acceptance ([verification scope](decisions/verification-scope.md)); per-round evidence
was removed on 2026-11-27 and remains in Git history.

| Task | Accepted | Feature commit | Rejected deliveries | Result |
|---|---|---|---|---|
| [p0-01](tasks/p0-01-windows-utf8-lora-files/task.md) | 11-24 | `531a68d` | 0 | LoRA run files read as UTF-8 on Windows |
| [p1-00](tasks/p1-00-mcp-friction-run-mac/acceptance.md) | 11-24 | `c02ebe7` | 0 | Mac friction baseline with today's tools; macOS Backend suite 1900 passed |
| [p1-00a](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md) | 11-24 | `ad2458e` | 1 | Mac runtime and image retrieval repair |
| [p1-01](tasks/p1-01-mcp-response-envelope/acceptance.md) + [p1-02](tasks/p1-02-mcp-tool-consolidation/acceptance.md) | 11-24 | `ef8302c` | 1 | One envelope for every tool; one intent tool per action (29) |
| [p1-03](tasks/p1-03-mcp-wait-and-result/acceptance.md) | 11-24 | `10d4593` | 0 | Bounded `wait_for_job` with result locators; 50 s fallback |
| [p1-04](tasks/p1-04-mcp-health-and-workers/acceptance.md) | 11-24 | `c5e10eb` | 0 | `health` and `list_workers` (31 intents) |
| [p1-05](tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md) | 11-26 | `411544f` | 1 | Real Mac smoke: three consecutive flows, zero manual fixes; **Phase 1 exit**, owner demo accepted |
| [p2-00](tasks/p2-00-civitai-first-check/acceptance.md) | 11-26 | `a9de233` | 0 | Hand run: search → key download → register → `default_lora` image 3878; 20 manual interventions ([ledger](tasks/p2-00-civitai-first-check/friction-ledger.md), [intake](tasks/p2-00-civitai-first-check/implementation-intake.md)) |
| [p2-01](tasks/p2-01-civitai-key-file/acceptance.md) | 11-26 | `24dad88` | 1 | Backend reads the private key file; credentials only on the final request |
| [p2-02](tasks/p2-02-resource-record/acceptance.md) | 11-27 | `211208a` | 9 | Resource row with typed metadata, SDXL base-model mapping, backfill, bounded Backend reads |
| [p2-03](tasks/p2-03-bounded-download/acceptance.md) | 11-27 | `0508ac4` | 2 | Bounded downloads: 8 GiB/file, 20 GiB free floor, safetensors, hash, resume, no overwrite |
| [p2-04](tasks/p2-04-durable-download-jobs/task.md) | — | `6ec6e7a` (WIP) | — | Kickoff CLEAR; owner-requested [partial checkpoint](tasks/p2-04-durable-download-jobs/owner-checkpoint-2026-11-27.md) on main; respec under the new verification scope |

Review cost note: p2-02 and p2-03 used 12 delivery rounds between them, mostly on
free-text credential recognition and evidence packaging. The
[2026-11-27 reassessment](decisions/verification-scope.md) replaces that with a typed
allowlist (next task p2-02a) and capped evidence.

## Phase 0 — Clean foundation (done 2026-11-24)

| Item | Status |
|---|---|
| Retained work integrated into `main` (`3fa5c31`) | Done |
| Docs rebuilt in English (entry, policy, architecture, current, roadmap, topics, team, memory) | Done |
| History, research data, OpenSpec and scratch files removed | Done |
| Progress table based on current code | Done (this page) |
| Known test failures removed (outdated snapshot, packaging and platform tests); fixtures pinned to LF | Done |
| Backend suite on Windows: no failures or hangs (2018 passed, 6 skipped); MCP 314 passed | Done 2026-11-24 |
| LoRA run files read as UTF-8 on Windows ([p0-01](tasks/p0-01-windows-utf8-lora-files/task.md)) | Done 2026-11-24 |
| Backend suite on macOS after the cleanup | Done in [p1-00](tasks/p1-00-mcp-friction-run-mac/review.md): Coding and QA each 1900 passed, 124 Windows-only skips, `--timeout=60` |

## Phase 1 — MCP for agents

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| 31 intents including health, configured workers and bounded wait, one risk each; catalog/discovery aligned | Done, p1-01 through p1-04 accepted | `mcp-server/mcp_server/tool_catalog.py`, `server.py`, `tools/intents.py`, `tools/health.py` | Independent literal risk/discovery guards; full MCP 606 passed/2 optional skips | Software verified offline; new surface not deployed here |
| Image template/custom-workflow generation; generation status/cancel; video submission removed from MCP | Done, p1-02 accepted | `tools/intents.py`, `tools/generate.py` | Registered mode/request preservation and full MCP | Prior Mac original/revision + status (p1-00a); consolidated surface offline |
| Revision context and parent lookup on generation | Done | `schemas/generate.py`, `tools/generate.py` | `test_revision_context.py` (Backend + MCP), `test_revision_parent_errors.py` | Yes, Mac original/revision canonical lineage (p1-00a) |
| Gallery read, artifact read, rerun | Done | `tools/gallery.py` | `test_tools.py` | Both readers' returned host paths consumed/decoded on Mac (p1-00a) |
| Prompt Library, style presets, Civitai tools | Done | `tools/prompt_library.py`, `style_presets.py`, `civitai.py` | matching `test_*` files | No |
| ComfyUI restart, node install, free memory | Done | `tools/comfyui_nodes.py`, `comfyui.py` | `test_comfyui_nodes.py` | No |
| Discord delivery of results | Done | `tools/discord_delivery.py` | `test_discord_delivery.py` | No |
| Uniform success `{ok, data}` / failure `{ok: false, error}` responses | Done, p1-01 accepted | `tools/responses.py`, registration/validation boundary | Registered/stdio envelope and recovery tests; independent full MCP 460/2 | Offline only for new surface |
| `wait_for_job` and truthful result locators | Done, p1-03 accepted | `tools/wait_for_job.py`, async GET client | 77 feature cases, fresh Backend route replays, independent 28 extra cases; full MCP 540/2 | Offline only; real wait remains p1-05 |
| `health` / `list_workers`, additive configured-worker status | Done, p1-04 accepted | `tools/health.py`, `api/workers.py` | Real route/client and registered mocked-HTTP checks; independent 51 calls/107 GETs, ten detected faults; Backend 1916/124 Windows skips, MCP 606/2 | Offline only; no real worker readiness claim |
| End-to-end smoke script against real ComfyUI | Done, p1-05 accepted after exact QA and native owner demo acceptance | Corrected `411544f`, reviewed source integrated | Review 2 actual signal regression PASS; MCP 672/4, Backend 1916/124 | Fresh three pairs/six MCP PNGs and persisted lineage independently corroborated |

## Phase 2 — One-sentence image flow (resources → workflow → image)

Accepted so far: real First check (p2-00), private key file (p2-01), Backend
resource record (p2-02) and bounded downloads (p2-03). Nothing agent-facing is new
yet: search, MCP record/reuse, workflow selection and defaults are still open.

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Retained Civitai resource acquire/status and source info (MCP); generate-like removed from MCP, Backend frozen | Done, p1-02 accepted | `tools/civitai.py`, `services/civitai_resource_*` | `test_civitai_*`, registration exclusion checks | No |
| Civitai recipe import, resource resolution, safe download, source aliases, local identity ledger | Done | `services/civitai_*`, `api/civitai_*` | `test_civitai_*` | No |
| Backend private key-file and bounded credential-safe retained provider paths | Done, p2-01 accepted | `services/civitai_provider.py` and retained callers | Exact review 2 D1–D5 PASS; fresh full/fault/registered-path proof | Read-only source HEAD auth comparison; no runtime deployment |
| Civitai model search by text, type and base model (MCP) | Not started | — | — | — |
| Resource row, typed metadata/mapping and bounded Backend reads | Done, p2-02 accepted; new MCP/unknown-local hash lookup pending | `services/resource_records.py`, `api/resources.py`, compatible writers | Exact review10 D–Z PASS, full suites and fault-sensitive guards | Offline fixtures only |
| Workflow selection from chosen resources | Partial (manifest match exists) | `core/workflow_manifest.py`, `api/workflow_catalog.py` | `test_workflow_match.py` | No |
| End-to-end one-sentence run | Not started | — | — | — |

## Phase 3 — LAN Windows workers

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

## Phase 4 — Image-to-video clip with interpolation

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Image-to-video workflows (Wan first frame, first+last frame) | Done | `backend/workflows/gen_img2video_wan_*`, `api/generate.py` | `test_wan_keyframes.py` | No |
| FILM frame interpolation | Done | `services/film_postprocess.py` | `test_film_audio_mux.py` | No |
| One fixed image-to-video + interpolation MCP tool | Not started | — | — | — |
| End-to-end sentence → image → clip run | Not started | — | — | — |

## Phase 5 — LoRA training

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Dataset listing, inspection, metadata, locks | Done | `services/lora_dataset.py` | `test_lora_dataset_service.py`, `test_lora_training_worker_lock.py` | No |
| Auto-captioning (WD Tagger), caption assessment, curation | Done | `services/watcher.py`, `wd_tagger.py`, `lora_dataset_*` | `test_watcher.py`, `test_wd_tagger.py`, `test_lora_dataset_*` | No |
| Preflight and explicit recipe compiler | Done | `services/lora_training_decision.py`, `lora_training_recipe.py` | `test_lora_training_decision.py`, `test_lora_training_recipe*` | No |
| sd-scripts runner for SD1.5, SDXL, Anima | Done | `services/lora_trainer.py` | `test_lora_trainer.py`, `test_lora_lifecycle.py` | No |
| Output name with serials, per-run folders, parameter record | Done | `services/lora_trainer.py` | `test_lora_delivery.py`, `test_lora_public_results.py` | No |
| Registration status separate from training status | Done | `services/lora_trainer.py` | `test_lora_projection_contract.py` | No |
| Smoke test with reconciliation and image validation | Done (tests removed 2026-11-24; new smoke tests come with Phase 5) | `services/lora_trainer.py` | — | No |
| UI pages and MCP tools | Done | `pages/LoraTrain.tsx`, `LoraDocs.tsx`, `tools/lora_train.py` | `LoraTrain.test.tsx`, `test_lora_train_tools.py` | No |
| First real training run | Not started | — | — | — |
| Training on a worker | Not started | — | — | — |

## Phase 6 — Prompt dashboard

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
