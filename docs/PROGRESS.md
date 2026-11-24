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
| Backend suite on macOS after the cleanup | Done in [p1-00](tasks/p1-00-mcp-friction-run-mac/review.md): Coding and QA each 1900 passed, 124 Windows-only skips, `--timeout=60` |

## Phase 1 — MCP for agents

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| 30 intent tools including bounded wait, one risk each; catalog/discovery aligned | Done, p1-01/02 and p1-03 accepted | `mcp-server/mcp_server/tool_catalog.py`, `server.py`, `tools/intents.py` | Independent literal risk/discovery guards; full MCP 540 passed/2 optional skips | Software verified offline; new surface not deployed here |
| Image template/custom-workflow generation; generation status/cancel; video submission removed from MCP | Done, p1-02 accepted | `tools/intents.py`, `tools/generate.py` | Registered mode/request preservation and full MCP | Prior Mac original/revision + status (p1-00a); consolidated surface offline |
| Revision context and parent lookup on generation | Done | `schemas/generate.py`, `tools/generate.py` | `test_revision_context.py` (Backend + MCP), `test_revision_parent_errors.py` | Yes, Mac original/revision canonical lineage (p1-00a) |
| Gallery read, artifact read, rerun | Done | `tools/gallery.py` | `test_tools.py` | Both readers' returned host paths consumed/decoded on Mac (p1-00a) |
| Prompt Library, style presets, Civitai tools | Done | `tools/prompt_library.py`, `style_presets.py`, `civitai.py` | matching `test_*` files | No |
| ComfyUI restart, node install, free memory | Done | `tools/comfyui_nodes.py`, `comfyui.py` | `test_comfyui_nodes.py` | No |
| Discord delivery of results | Done | `tools/discord_delivery.py` | `test_discord_delivery.py` | No |
| Uniform success `{ok, data}` / failure `{ok: false, error}` responses | Done, p1-01 accepted | `tools/responses.py`, registration/validation boundary | Registered/stdio envelope and recovery tests; independent full MCP 460/2 | Offline only for new surface |
| `wait_for_job` and truthful result locators | Done, p1-03 accepted | `tools/wait_for_job.py`, async GET client | 77 feature cases, fresh Backend route replays, independent 28 extra cases; full MCP 540/2 | Offline only; real wait remains p1-05 |
| `list_workers` / `worker_status` | Not started | — | — | — |
| End-to-end smoke script against real ComfyUI | Not started | — | — | — |

## Phase 2 — One-sentence image flow (resources → workflow → image)

| Capability | Status | Code | Tests | Real run |
|---|---|---|---|---|
| Retained Civitai resource acquire/status and source info (MCP); generate-like removed from MCP, Backend frozen | Done, p1-02 accepted | `tools/civitai.py`, `services/civitai_resource_*` | `test_civitai_*`, registration exclusion checks | No |
| Civitai recipe import, resource resolution, safe download, source aliases, local identity ledger | Done | `services/civitai_*`, `api/civitai_*` | `test_civitai_*` | No |
| Civitai model search by text, type and base model (MCP) | Not started | — | — | — |
| Resource record agents can list and filter; hash lookup of unknown local files | Partial (ledger and aliases exist; no agent-facing record) | `services/civitai_local_identity_ledger.py`, `civitai_source_alias_registry.py` | `test_civitai_*` | — |
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

## Log

### 2026-11-24 — Roadmap set to six phases
- Order: MCP → one-sentence image flow → workers → image-to-video clip → LoRA → dashboard; phase rules added ([decisions](decisions/roadmap.md)).

### 2026-11-24 — Phase 0 closed
- Windows Backend and MCP suites pass with no hangs; non-feature failing tests removed; LoRA files read as UTF-8 (`1898378`). The macOS rerun is the first step of p1-00.

### 2026-11-24 — Fresh planning and authorized Phase 1 start
- Saved the [initial request](requests/2026-11-24-fresh-producer-planning.md) and [later owner instruction](requests/2026-11-24-proceed-within-project-boundaries.md) with exact quotations and relay provenance. The later instruction removes the earlier routine-confirmation wait and authorizes executable in-boundary work.
- Assessed fetched `6be499f` and existing Phase 1 implementation/specs. [Execution plan](tasks/p1-planning-2026-11-24/plan.md) reuses the current system; map/spec consistency corrections preserve all LoRA names, regroup acceptance checks and clarify wait output/timeout evidence.
- Producer adopted the installed Illustrious/default pair, no LoRA/local, for p1-00 and p1-05 under delegated authority; no individual CTY model selection or aesthetic acceptance is claimed.
- Created native Producer coordination AID-142–146 with prerequisite edges and released QA kickoff [AID-147](/AID/issues/AID-147) at a pinned published planning/spec commit. [AID-141](/AID/issues/AID-141) waits on the first execution coordinator; CLEAR precedes Coding/evidence-review dispatch.
- First execution remains p1-00: Mac Backend suite then current-tool friction baseline. This round verifies docs/source, native handoff and read-only services only; no suite rerun, generation, new artifact retrieval or phase-exit claim.

### 2026-11-24 — p1-00 cleared and dispatched
- Read QA's independent [CLEAR kickoff](tasks/p1-00-mcp-friction-run-mac/kickoff-review.md) on [AID-147](/AID/issues/AID-147), pinned to `e443f2e`. Its repository mirror matches the official attachment; no specification or software changed in kickoff.
- [AID-142](/AID/issues/AID-142) created [Coding AID-148](/AID/issues/AID-148) and separate [QA evidence review AID-149](/AID/issues/AID-149), each with the approved specification and delegated-choice authority in its native plan. Coding has a live execution run; QA waits natively on Coding, AID-142 waits on QA, and AID-141 continues to wait on AID-142.
- The first delivery still measures the full Mac Backend suite and current-tool original/revision flow without repairs. No routine CTY question was created. Producer verified documents, kickoff and handoff only; baseline test, generation and generated-artifact outcomes remain unaccepted until delivery review.

### 2026-11-24 — p1-00 evidence accepted; bounded repair required
- Producer read [Coding AID-148](/AID/issues/AID-148)'s exact evidence `3081952` and [QA AID-149](/AID/issues/AID-149)'s [evidence-only PASS](tasks/p1-00-mcp-friction-run-mac/review.md); official attachments, archive files and patches match Git. The unchanged evidence and QA report/registry `c377a02` are integrated. This accepts D1-D4, including D2's documented-blocker option.
- Offline: Coding full Mac Backend `1900 passed, 124 skipped, 77 warnings in 43.84s`; QA independent rerun `1900 passed, 124 skipped, 77 warnings in 44.13s`; both exit 0 with `--timeout=60`. All skips require Windows. No new full MCP/Frontend/Windows result.
- Live service: ping/resources and existing-job/Gallery reads work; identical live OpenAPI snapshots omit revision context while current source defines it. The loaded Backend commit remains unknown. Real generation: one original completed. Artifact retrieval: metadata only; relative URL interpretation failed locally before HTTP; no image bytes, revision or lineage success.
- Raw stdio confirms one submission, 12 same-job polls, no timeout/resubmission. The preserved baseline is **23 intervention units across eight incidents**, with complete mappings and no hidden product repairs.
- [AID-142](/AID/issues/AID-142) keeps AID-141/AID-143 gated and scopes [p1-00a](tasks/p1-00a-mac-runtime-and-retrieval/task.md) for runtime alignment and usable locator/byte retrieval, followed by a fresh original/revision pair. Independent kickoff CLEAR precedes Coding; exact-commit PASS precedes merge and release. The original baseline is not rewritten, and no routine CTY question is needed inside delegated boundaries.
- Published the fixed repair specification at `4ac3d56` and created [QA kickoff AID-150](/AID/issues/AID-150) with a verified native plan. AID-142 now waits natively on that review. After actual CLEAR, Producer creates separate Coding and delivery-QA cards; no implementation has been released by this handoff.
- Producer's acceptance round verifies docs, attachment integrity and raw evidence only; it does not rerun suites, probe services, generate or retrieve image bytes. Captured the durable [loaded-runtime verification rule](memory/runtime-source-contract-verification.md); job receipts/counts stay in task evidence.

### 2026-11-24 — p1-00a kickoff CLEAR and repair dispatched
- Read [QA AID-150](/AID/issues/AID-150)'s [CLEAR](tasks/p1-00a-mac-runtime-and-retrieval/kickoff-review.md) for fixed spec `4ac3d56`. Official report/archive/patch match QA report commit `9bd0029`; the specification, baseline evidence and Backend/MCP source are unchanged. No owner answer or new routine confirmation is required.
- Created [Coding AID-151](/AID/issues/AID-151) for the bounded runtime/locator repair and one fresh original/revision byte+lineage proof from published `eaf11b8`, plus separate [QA delivery AID-152](/AID/issues/AID-152) blocked natively by Coding. Both saved native plans match their assignments. Coding has an active run; QA reads the actual exact-commit delivery after execution.
- [AID-142](/AID/issues/AID-142) now waits natively on AID-152. AID-141/AID-143 remain gated until repair PASS and Producer acceptance/publication. A blocked journey cannot pass repair D3; the original no-repair baseline remains 23 intervention units/eight incidents. Later redesign, three-run exit and CTY acceptance remain separate.
- Producer verified kickoff bytes, native plans/dependencies, document links/whitespace and publication; no new software suite, live product probe, generation or image-byte retrieval. No additional durable lesson beyond the existing runtime/lineage memory was found; this dispatch stays in task records.

### 2026-11-24 — p1-00a delivery round 1 fails complete inventory
- Read [Coding AID-151](/AID/issues/AID-151)'s manifest at `00ebb4d` and [QA AID-152](/AID/issues/AID-152#comment-c64c55d7-ac7c-4849-94cf-8447f62d3e2b)'s exact-commit **FAIL** (`537d47f` report). Official manifest/report bytes match Git; the independent audit archive hash matches its receipt. The candidate remains unmerged; no dependent release follows a partial pass.
- D1-D4 pass: identified Backend relaunch, actual unmodified host-path byte reads/PNG decode for baseline/original/revision, fresh generation requests and persisted canonical lineage. QA generated nothing and independently matched the delivered ComfyUI histories; the deterministic original used cache. Original/revision artifacts are 3863/3864, with parent 3863; this is a colocated Mac-client proof, not remote URL support or phase exit.
- Offline: Coding Backend `1900 passed, 124 skipped, 76 warnings in 44.12s`, MCP `314 passed, 4 skipped in 1.20s`; QA independently Backend same counts in 42.40s, MCP same counts in 1.10s; exit 0, isolated roots, `--timeout=60`. No new Frontend/Windows result. Producer did not rerun suites, probe live services, generate or read live image bytes in triage.
- D5 fails because the runtime inventory omits eight nullable training columns and new empty `lora_output_reservations`, added by existing startup code. QA's complete schema/value audit finds all old values preserved and added training values NULL. Producer checked that audit and `init_db`; no product repair, rollback, restart or extra generation is indicated.
- [Correction 1](tasks/p1-00a-mac-runtime-and-retrieval/repair-round-1.md) stays under original cleared D5, adds complete schema accounting/evidence and a refreshed exact-candidate package, followed by independent review round 2. Carry one rejection across the new cards. AID-142 keeps AID-141/AID-143 gated; no owner escalation threshold is reached. Captured the durable [whole-schema startup inventory rule](memory/backend-startup-additive-schema.md), without storing database snapshots or incident receipts in memory.
- Published the correction assignment at `c41815c`, then created [Coding AID-153](/AID/issues/AID-153) and separate [QA round 2 AID-154](/AID/issues/AID-154), blocked natively by Coding. Both initial native plans include the unchanged original task and exact correction; readbacks match. AID-142 now waits on AID-154. Source/runtime/generation repetition is excluded from this correction unless a new scoped concern justifies it; D1-D4 evidence must remain applicable and explicitly reused.

### 2026-11-24 — p1-00a accepted after round-2 PASS
- Producer read [Coding AID-153](/AID/issues/AID-153)'s corrected `b6d5846` and [QA AID-154](/AID/issues/AID-154)'s [D1-D5 PASS](tasks/p1-00a-mac-runtime-and-retrieval/review.md). [Acceptance](tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md) retains one rejection/correction round 1/review round 2 and the byte-identical [first FAIL](tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md). F-QA1 is resolved by complete additive-schema accounting, read-only preservation evidence and independent repeat audit; no old values lost or extra runtime/product repair.
- All seven Coding and five QA uploads hash-check; manifests/reports/patches match Git, 90 Coding and 26 QA archive repository files match their exact commits, and PNG payload hashes/fixed references match. Corrected candidate plus QA metadata/registry `3d5d890` are integrated unchanged. Production/test trees equal prior main; original task and no-repair evidence remain intact.
- Offline: QA round-2 source/test/root-input/package/platform equivalence makes its prior full Backend `1900 passed, 124 skipped, 76 warnings in 42.40s` and MCP `314 passed, 4 skipped in 1.10s` applicable, both exit 0 with `--timeout=60`. No suite repeated in correction/round 2/Producer acceptance; no new Frontend/Windows result.
- Service: identified launch and independent source/config/schema/persistence checks. Generation: Coding's fresh original/revision and independent QA history reconciliation, with cached original disclosed. Retrieval: prior independent host-path byte reads/PNG decode reused; round-2 archive integrity checked. One colocated Mac pair, byte reads outside MCP, no three-run/aesthetic/demo/phase-close acceptance.
- [AID-142](/AID/issues/AID-142)'s accepted baseline/repair gate is satisfied; after publication its completion releases [AID-143](/AID/issues/AID-143) for baseline-informed p1-01/02 kickoff. F1/F2/F3/F6/F7 retain later mappings; Phase 1 scope/order/exit unchanged. Keep the active runtime worktree/venv and all data. Producer performs no new live operation. Existing runtime/startup-schema memory and updated MCP/setup topic docs cover the durable lessons; receipts stay in task records.

### 2026-11-24 — p1-01/02 baseline reconciled for fresh kickoff
- [AID-143](/AID/issues/AID-143) read the accepted original baseline, corrected repair manifest/acceptance, actual independent D1-D5 PASS and historical first FAIL at published `a963386`. The [complete friction disposition](tasks/p1-01-mcp-response-envelope/kickoff-context.md) retains all eight incidents/23 intervention units and the colocated-client limits: F3 targets envelopes; F5/F8 need preservation through consolidation; environment/polling/visibility remain with the later tasks.
- Clarified the existing p1-01 MCP-path validation requirement and p1-02's complete 40-tool intent/risk/mode mapping. All LoRA names remain, and temporary `mcp_ping` stays enveloped/read until p1-04. Documentation must distinguish delivered tools from later wait/health flow. Four/five Done when items remain, with no Backend or phase-scope change.
- Fresh independent kickoff must return an explicit verdict for each fixed spec before Coding. A combined final candidate still needs separate Coding/delivery-QA cards, a manifest per folder and actual exact-commit PASS before one merge/push; ordinary CTY confirmation is not needed. Recipient links and the live prerequisite are recorded in AID-143's native plan.
- Producer prepared documentation in an isolated worktree and checked source/evidence applicability, links and whitespace only. No new software suite, live product probe, restart, generation or live artifact-byte read; prior tests/journey remain attributed to their original runs. Existing runtime/lineage/client-boundary memory covers this round's lessons; no receipt or incident log is added to memory.

### 2026-11-24 — p1-02 kickoff ambiguity clarified; fresh review required
- Read [QA AID-155](/AID/issues/AID-155)'s actual [p1-01 CLEAR](tasks/p1-01-mcp-response-envelope/kickoff-review-round-1.md) and [p1-02 AMBIGUITY](tasks/p1-02-mcp-tool-consolidation/kickoff-review-round-1.md) for `d1ffb8d`, report commit `b32ac4f`. All four official uploads, report/patch Git equality and the complete 16-entry archive inventory/fixed references verify. Exact reports and historical mirrors are preserved; a completed review card did not release Coding.
- Source confirms K2-1: MCP compose forwards optional `save_as`, and the Backend provider calls the persistent combination writer. Producer adopted QA's recommended [bounded clarification](tasks/p1-02-mcp-tool-consolidation/kickoff-clarification-1.md): keep `prompt_compose` read-only, reject legacy save arguments before Backend access, and save returned fragments/metadata through `prompt_write(save)` with existing concurrency/provenance semantics. The [MCP decision](decisions/mcp.md#prompt-composition-and-saving) records this two-call migration and its lack of cross-call atomicity; Backend APIs stay unchanged.
- p1-02 D1-D3 now explicitly cover optional capabilities, truthful risk and registered-call no-write/rejection/replacement-save/conflict cases. Five acceptance items remain; p1-01 task bytes, all LoRA names, 40-name accounting, staged delivery and the original 23-unit/eight-incident baseline stay unchanged. One kickoff ambiguity, clarification round 1 and next kickoff round 2 are retained; no implementation delivery/rejection exists. Both tasks need fresh explicit fixed-spec verdicts before the combined Coding/delivery-QA handoff.
- Producer's isolated worktree changes docs/evidence only. No software suite, live product probe/restart, generation or live image-byte read; downloaded review artifacts are separate from generated-image retrieval. The new durable choice is saved in MCP decisions; no receipt/history is added to project memory. AID-143's native plan holds the fresh reviewer and dependency path; no ordinary CTY question is pending.

### 2026-11-24 — p1-01/02 both CLEAR; combined implementation released
- Read [QA AID-156](/AID/issues/AID-156)'s actual round-2 [p1-01 CLEAR](tasks/p1-01-mcp-response-envelope/kickoff-review.md) and [p1-02 CLEAR](tasks/p1-02-mcp-tool-consolidation/kickoff-review.md), fixed specification/source `496cee2`, exact report commit `9d79d20`. All four official uploads, all 29 indexed archive files, 16 fixed snapshots, prior verified archive and report/patch/bundle Git identities check. Only the two latest reports changed in QA's commit; original round-1 mirrors, task digests and normative decisions remain intact.
- K2-1 is independently resolved at specification level. Four/five acceptance items remain, with complete 40-name/29-provisional-destination capability accounting, every merged mode/action, safe compose/save and existing preservation contracts, staged delivery and F1-F8/23-unit boundaries. The one kickoff ambiguity/clarification round 1/kickoff round 2 remains recorded; no implementation delivery/rejection is claimed.
- Both actual CLEAR verdicts release combined p1-01/02 Coding. Producer uses separate executor/reviewer cards and a native QA dependency on Coding; [AID-143's live plan](/AID/issues/AID-143#document-plan) records their identities and the coordinator's waiting path. Delivery requires both manifests at one exact final commit, passing full MCP and affected checks, updated docs and actual independent PASS before one feature merge/push and p1-03 release. No routine CTY confirmation is needed.
- This round publishes unchanged kickoff reports and coordination documents only. Producer checks documents, official artifacts, fixed Git objects and publication; no software suite, product-service probe/restart, generation or live generated-image read. Historical tests and the colocated Mac pair remain prior evidence. Existing MCP decisions/runtime/lineage memory cover the durable facts; no new receipt or incident log is added to memory.

### 2026-11-24 — p1-01 PASS / p1-02 first delivery rejection; bounded correction
- Read [Coding AID-157](/AID/issues/AID-157)'s actual two manifests at exact `b1082a8` and [QA AID-158](/AID/issues/AID-158)'s full per-task reports at `1001586`: p1-01 PASS, p1-02 FAIL F2-1 (P1, D2). All twelve official uploads, exact raw Git diffs/bundles and Coding's 69/QA's 52 archive entries match their immutable references. The unmodified catalog risk labels are correct; no product mislabel is alleged.
- Source and saved mutation evidence confirm the circular test oracle: changing only ComfyUI admin to read leaves 458 MCP passes/two skips while registered restart still sends its mocked HTTP POST. [Correction 1](tasks/p1-02-mcp-tool-consolidation/repair-round-1.md) stays under the unchanged cleared D2 and requires an independent all-29 risk expectation checked in catalog/discovery, meaningful false-label failure and restored final GREEN. Product/Backend/spec/decision/runtime scope stays unchanged.
- Independent QA results: Backend 1900 passed/124 Windows skips, MCP 458 passed/two unchanged optional export skips (also after restoration), parity five passed and extra boundaries 15 passed; six other meaningful faults were caught. These are candidate-only QA results, not main, new live proof or F2-1 acceptance. Producer did not rerun software suites.
- Producer dispatches new recipient-owned Coding correction and separate delivery-QA round 2, with native Coding → QA → Producer ordering recorded in [the live plan](/AID/issues/AID-143#document-plan). Both tasks must PASS at one new exact final SHA before combined feature publication or p1-03 release. One p1-02 delivery rejection/correction round 1/review round 2 is retained; kickoff ambiguity/clarification and p1-00a history remain separate. No owner boundary or escalation threshold is reached.
- Main receives coordination/correction docs only; rejected candidate source stays unmerged. Producer verification covers source/docs/official review artifacts/Git/native handoff, no product probe/restart, real generation or live generated-image read. The active runtime/private configuration/canonical environments and retained data stay intact. The independent-risk-oracle lesson is captured in this task record; no new memory topic or incident log is needed.

### 2026-11-24 — p1-01/02 corrected delivery accepted and integrated together
- Read [Coding AID-159](/AID/issues/AID-159)'s two manifests at exact corrected candidate `616f67ff68fc27070e85861e94d70de1baf5082a` and [QA AID-160](/AID/issues/AID-160)'s independent same-candidate p1-01 PASS / p1-02 PASS, exact report/evidence/registry `28cd4512b8ec7d6594ec972ab81161b8c2d09d03`. [Combined acceptance](tasks/p1-01-mcp-response-envelope/acceptance.md) covers all four/five original task items and F2-1 resolution.
- The independent literal 29-intent policy checks catalog/real discovery; the exact false-admin-read fault now fails both guards/full MCP (2 failed/458 passed/2 unchanged optional skips), then restored source passes 460/2. Six other meaningful faults fail afresh. Fresh QA Backend 1900/124 Windows skips, parity five and extra boundaries 15 pass with isolated roots/timeout; no prior Backend result is reused. No new Frontend/Windows result.
- Verified all thirteen official uploads by size/hash, actual documents against Git, both exact Coding patches, QA patch/bundles and all 147 Coding/123 QA indexed archive entries (138/120 named Git bodies). Integrated reviewed source, manifests, reports, historical evidence and nine-item registry unchanged at **`7ba2059f7e46920eaf860e19e61aa84bae8bf02c`**. Subsequent changes are acceptance/current/progress/roadmap/handoff documents only; final remote main SHA is pinned in [AID-143's publication ledger](/AID/issues/AID-143#document-plan).
- Preserve exact first-round p1-01 PASS / p1-02 FAIL, one p1-02 rejection/correction round 1/review round 2 PASS. Kickoff ambiguity/clarification/rounds and p1-00a history remain separate. The QA helper import-origin misbinding is recorded and excluded from product results; only helper environment was corrected before the full fault/restore/GREEN rerun. No specification or product fix was hidden in review.
- Completion of [AID-143](/AID/issues/AID-143) releases [AID-144](/AID/issues/AID-144) for its own p1-03 CLEAR/build/exact-review cycle, using current envelopes/intents and the existing client-budget/training-output boundaries. Ordinary choices remain delegated; no new owner confirmation is needed. Wait → health → smoke order and CTY phase/aesthetic gates remain intact.
- Producer checks source/document/official artifact/Git identity and publication; no extra software suite on identical product/test inputs, no product probe/restart/deployment, real generation or live Gallery-byte read. Original 23 units/eight incidents and the bounded cached-original/revision colocated Mac proof keep their limits. Preserve the runtime/private configuration/canonical venvs and all retained data. Existing decisions/memory plus the correction record cover durable facts; no new memory incident log.

## 2026-11-24 — p1-03 kickoff ambiguity and locator clarification

[QA AID-161](/AID/issues/AID-161) returned [AMBIGUITY K3-1](tasks/p1-03-mcp-wait-and-result/kickoff-review-round-1.md)
at fixed `7a46cb70bde83ba18417620ead3759a78e3c7c14`, report/evidence
`b3276dc0c138fea8f99fed4a19b76e3a20043781`. Existing readers support completed
legacy images without artifact rows and canonical artifacts without Gallery URLs.
Producer inspected those source contracts and actual offline fixture responses,
verified all five official uploads, exact report/binary patch/bundle and all
68 indexed archive entries against hashes/Git. Original task/report/evidence
remain intact. QA's selected Backend 3 passed/one warning, MCP 19 passed and
isolated shape probe are attributed to QA; no new suite was run by Producer.

[Clarification 1](tasks/p1-03-mcp-wait-and-result/kickoff-clarification-1.md) adopts
the recommended truthful locator disposition inside delegated authority: canonical
media keeps its own IDs; legacy images stay separate; unavailable generation
locators return a recoverable common error retaining completed Backend status.
No fabricated ID, path/URL, file migration or Backend change is allowed. Training
output and independent nullable smoke references remain separate; all five
acceptance items and the overall bounded-wait/no-resubmit rule remain. The actual
client limit is unverified unless sourced; 50 seconds is the approved fallback.

This is one p1-03 kickoff ambiguity/clarification 1/next kickoff round 2, not a
software delivery rejection. Producer's [native plan](/AID/issues/AID-144#document-plan)
records the fresh QA recipient and fixed source. Actual CLEAR is required before
Coding and a separate exact-commit delivery review; p1-04 remains gated. Prior
p1-02/p1-00a histories, nine registry guards and the original 23-unit/eight-incident
baseline remain. This round changes docs/evidence only, with no product-service
probe/restart, real generation/training or live Gallery-byte retrieval. Active
runtime/private configuration, canonical environments and retained data are preserved.

## 2026-11-24 — p1-03 kickoff CLEAR and implementation handoff

[QA AID-162](/AID/issues/AID-162) independently returned [round-2 CLEAR](tasks/p1-03-mcp-wait-and-result/kickoff-review.md)
at fixed `522c2f10b550d90f7b88ab1a3c9d1f6352439c8e`, exact report/evidence
`3bbcb9cdd30397c497c71da50ce83482642302e7`. Producer read the full report,
verified all five official uploads by size/hash, exact report/binary patch,
bundle head/prerequisite and all 90 indexed source/evidence payloads against Git
(92 total archive members). K3-1 is resolved at specification level, not erased:
one kickoff ambiguity/clarification 1/kickoff 2 CLEAR remains. No p1-03 delivery
or delivery rejection exists. Cleared task/decision bytes, round-1 task/report/
evidence and nine standing registry items stay unchanged.

Fresh QA source checks observed Backend 3 passed/one warning, MCP 19 passed and
an extended isolated real-route/SQLite fixture probe, including null canonical
smoke artifact ID and independent queued/failed/cancelled/unavailable smoke.
Producer does not rerun equivalent source checks or relabel those results as
wait implementation tests. Current software still has 29 tools; p1-03 will add
one read intent and retain current risk/namespace/envelope contracts.

Producer's [native handoff plan](/AID/issues/AID-144#document-plan) names separate
Coding and exact-commit delivery-QA cards with native Coding → Review → Producer
prerequisites. Coding owns implementation in an isolated worktree; QA independently
checks all D1-D5 at the actual delivered full SHA and completes its own verdict
card even for FAIL. A changed candidate needs new review; feature merge/push and
p1-04 remain gated by actual PASS. Source actual client-limit evidence or explicitly
retain unknown/50-second total fallback, including request/enrichment costs.

This handoff round integrates unchanged QA report/evidence and coordination docs
only; scoped document/Git/publication checks pass, with no extra software suite,
product-service probe/restart/deployment, real generation/training or live Gallery
retrieval. Active runtime/private configuration, canonical venvs and all retained
data stay intact. Prior full suites/live proof, 23-unit/eight-incident baseline,
separate p1-02/p1-00a histories, remote/aesthetic/three-run/phase-close limits remain.

## 2026-11-24 — p1-03 bounded wait accepted; health/workers next

[Coding AID-163](/AID/issues/AID-163) delivered `77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce`
from `a88b84a`. [QA AID-164](/AID/issues/AID-164) independently returned
[D1-D5 PASS](tasks/p1-03-mcp-wait-and-result/review.md) at that same final candidate,
exact report/evidence/registry `d088c3258ab782623631d60daaaccc8ce6fcb6dc`.
Producer read the actual manifest/report and verified all ten official uploads,
exact patches/bundles and all 203 Coding/262 QA indexed payloads against hashes,
blob IDs and immutable Git (205/264 archive members). [Acceptance](tasks/p1-03-mcp-wait-and-result/acceptance.md)
records the behavior/proof limits; reviewed product/tests/manifests/evidence and
QA registry are integrated unchanged. Final published main equality is in
[the native ledger](/AID/issues/AID-144#document-plan).

The 30th intent, wait_for_job=read, provides bounded existing generation/training
state/results with all canonical identities, separate legacy images, truthful
locator-unavailable/completed state, safe failures/cancellation and independent
training/smoke projection. One deadline covers lookup/status/body/enrichment/
sleep/preparation; timeout uses the same ID and sends no cancel/submission.
Actual client limit is **unverified**; 50 seconds remains approved overall
fallback policy. QA's 70 ms stages measured 71.5-73.7 ms and a 45 ms partial
enrichment measured 47.4 ms with SDK/setup overhead, aborting 300-400 ms reads;
these are short mocked-control checks, not a measured live client deadline.

Fresh independent Backend **1900 passed/124 Windows skips/76 warnings**, final
restored MCP **540 passed/two unchanged optional smoke-export skips**, wait
**77 passed** and additional QA **28 passed**. Isolated roots, pinned sources,
fresh Backend exports and per-test timeout 60 are retained. All seven meaningful
faults fail, then restore before final GREEN. QA preserves nine old registry rows
and certifies four new automated items (13 active), no supersession. Setup/helper
failures are preserved separately; no product failure remains. Frontend/build/
native Windows and other unchanged component scopes remain unrun.

Producer acceptance runs identity/document/integration/publication checks only;
no extra software suite on unchanged reviewed inputs, product-service probe/
restart/deployment, real generation/training or live Gallery-byte retrieval.
Retain active runtime/private configuration, canonical venvs and all data.
One p1-03 kickoff ambiguity/clarification 1/kickoff 2 CLEAR and delivery review 1
PASS with zero implementation rejections remains separate from p1-02/p1-00a
history. Original baseline/live proof and remote/aesthetic/three-run/phase limits
are unchanged. Completion/publication of [AID-144](/AID/issues/AID-144) releases
[AID-145](/AID/issues/AID-145) for its own p1-04 fresh kickoff/build/exact-review
cycle, using current envelopes and 30 intents. No routine owner confirmation.
