# Roadmap

> Status: **draft.** Phase order is set by the owner. Phase 1–4 details are discussed after Phase 0 is complete.

Current state per goal: [STATUS.md](../STATUS.md).

## Phase order

| Phase | Goal | State |
|---|---|---|
| 0 | Clean foundation: integrated code, rebuilt docs, known test baseline | In progress |
| 1 | MCP server that agents use smoothly | Not started |
| 2 | Prompt-combination dashboard | Not started |
| 3 | Same-LAN Windows workers | Not started |
| 4 | LoRA training | Not started |

## Phase 0 — Clean foundation

- [x] Integrate retained work into `main` (`32b59fd`).
- [x] Rebuild entry docs, operating policy, architecture, status and memory.
- [x] Rebuild this roadmap.
- [ ] Rebuild the five topic docs (setup, MCP, prompt dashboard, Windows worker, LoRA training).
- [ ] Extract the useful parts of team/governance docs.
- [ ] Consolidate specs and history (`SPEC.md`, `openspec/`, `docs/superpowers/`, `engineering/`, `tools/`, checkpoints, root `tmp_*` files).
- [ ] Fix or explicitly quarantine the 26 known Backend test failures.

**Exit:** a new agent can read README → AGENTS → INDEX and understand the system, its status and the rules; all test suites have a known, documented result.

## Phase 1 — MCP server that agents use smoothly

Candidate work:
1. Uniform structured responses: `{ok, data, error: {code, hint}}`.
2. `wait_for_job(job_id, timeout)` and a result tool returning artifact paths/URLs.
3. Risk labels (read / mutate / admin) on tools, for documentation only.
4. A short common flow: `list_resources → compose → generate → wait/result`; consolidate overlapping tools.
5. `list_workers` / `worker_status`.
6. A real end-to-end smoke script: generate on local ComfyUI, retrieve, revise with revision context.

**Exit:** an agent goes from nothing to a retrieved image and one traceable revision without human help.

## Phase 2 — Prompt-combination dashboard

Candidate work:
1. A recipe = prompt combination + workflow template + models/LoRAs + sampler parameters, unified with style presets.
2. Template selection in the Workbench renders adjustable parameters from `.meta.json`.
3. Progress, errors and result thumbnails on the Workbench page; save a result as a recipe.
4. MCP `generate_from_recipe`.

**Exit:** a combination built in the UI is used by an agent through MCP to generate an image.

## Phase 3 — Same-LAN Windows workers

Candidate work:
1. Authentication between Backend and worker; secure the PowerShell control routes.
2. Same-project check: worker reports git commit, workflow hashes, custom nodes and models; mismatches are refused with a clear hint.
3. Durable, concurrent queue: persist jobs at submission, survive restarts, run one job per available target in parallel.
4. Worker registry with heartbeat, capabilities and queue length.
5. Scheduler: `execution_target=auto` chooses by capability and load.
6. Results return to the Gallery with the worker recorded.
7. Replace the updater with `git pull` + restart; remove retired code.

**Exit:** a second Windows machine on the LAN produces an image that is traceable in the Gallery, while local ComfyUI runs another job.

## Phase 4 — LoRA training

Candidate work:
1. First real training run on a small dataset with one base model (SDXL or Anima).
2. Verify the full chain: train → register → select in a recipe → smoke image retrieved.
3. Dispatch training to a worker, reusing the Phase 3 registry and same-project check.

**Exit:** one real training produces a clearly named model that is used in a recipe and yields a retrievable smoke image.
