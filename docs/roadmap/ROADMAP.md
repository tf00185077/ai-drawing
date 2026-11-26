# Roadmap

## Destination

**Core.** A user says one sentence to an agent ("draw character X in style Y", "make a short clip of it"). The agent searches Civitai through this project's MCP tools, downloads the checkpoint and LoRAs it needs, and registers them. This project keeps the record of every resource, picks the workflow that matches those resources, runs it on ComfyUI and returns an image or a short image-to-video clip with frame interpolation. Characters and styles stay consistent across images because the team trains LoRAs from the owner's datasets and the agent uses them by name. No human help is needed between the sentence and the result.

**Support and add-ons.** Jobs spread across same-LAN Windows machines because the Mac is too slow for real use (support). A user saves reusable prompt combinations in a dashboard and agents generate from them (add-on).

Division of work: the agent decides *what* to look for; this project provides the tools to search, download, register and generate, and owns the records. Only the ComfyUI features the owner actually uses are exposed.

Constraints: keep the FastAPI Backend, React/Vite UI, Python MCP server and host ComfyUI; the Backend owns job, artifact, resource and provenance records; Civitai is used through its free public API (an API key only where a file requires it); [operating policy](../OPERATING-POLICY.md) applies; CTY judges aesthetics. Current state: [CURRENT](../CURRENT.md).

Order: core before support, support before add-ons. MCP basics come first because every later phase is used through an agent; workers come before video and LoRA because both need the NVIDIA machine.

## Phase rules

- **Fields.** Every phase states Role, Depends on, Scope, Remove, Unknowns, First check, Exit and Demo. *Remove* names the code, tools or docs the phase deletes or freezes, so each phase leaves the project smaller outside its own scope. *First check* is a hand run of the riskiest part before any task spec is written.
- **Exit counts.** An exit is met only after **3 consecutive real runs with zero manual fixes**. A manual fix is any human action, retry, workaround or call outside MCP between the request and the result. The first run of a phase records its baseline count of manual fixes.
- **Phase close.** When a phase exits, the owner reviews this roadmap (order, scope and next phase) before the next phase is activated; the review is logged under Review history.

## Milestones

### Phase 0 — Clean foundation (done 2026-11-24)

Role: foundation.
Scope: integrated `main`; documentation rebuilt in English; history removed; a progress table based on the current code; a known, documented test result for every suite.
Unknowns, riskiest first: whether the full Backend suite passes on Windows after the outdated tests were removed.
Exit: a new agent understands the system, its state and its rules from README → AGENTS → INDEX; every failing test is fixed or explicitly quarantined with a reason.
Demo: CTY reads README, CURRENT and ROADMAP and finds them accurate; one command per suite runs with the documented result.

### Phase 1 — MCP that agents use smoothly (done 2026-11-26)

Role: core. Depends on: Phase 0.
Scope: a friction run on today's tools that records every manual fix; one response envelope for every tool (`{ok, data}` / `{ok: false, error: {code, message, hint}}`); generation, job, Gallery, prompt, style-preset and ComfyUI tools consolidated to one per intent with one risk label each (Civitai and LoRA tools keep their names until Phase 2 and Phase 5; video and Civitai generate-like leave MCP); `wait_for_job` returning artifact paths/URLs within the client's call limit; `health` and `list_workers`; a real end-to-end smoke script on the Mac ComfyUI. Tasks: [p1-00](../tasks/p1-00-mcp-friction-run-mac/task.md) → [p1-01](../tasks/p1-01-mcp-response-envelope/task.md) + [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md) (shipped together) → [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md) → [p1-04](../tasks/p1-04-mcp-health-and-workers/task.md) → [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md); decisions in [mcp](../decisions/mcp.md).
Result: exit met by [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/acceptance.md) at `91d6e37` (independent review `ade7814`): three consecutive real Mac flows, eight MCP calls each, zero manual fixes, original→revision pairs 3872→3873, 3874→3875, 3876→3877 with decoded MCP PNGs and persisted lineage. Demo accepted by CTY on 2026-11-26. Limits carried forward: zero fixes holds only inside the qualifying flows (Coding 36 and QA 15 preparation/audit units outside them); the MCP client's real call limit is unverified, so `wait_for_job` keeps the 50-second overall fallback. History: [execution plan](../tasks/p1-planning-2026-11-24/plan.md), [phase-exit evidence](../tasks/p1-05-mcp-e2e-smoke-mac/phase-exit.md).

Remove: Wan keyframe video, custom video and Civitai generate-like tools from MCP (Backend code frozen); every old tool name replaced by the consolidation.
Unknowns, riskiest first: which manual fixes a run needs today and whether they are MCP problems or Backend/ComfyUI problems; the MCP client's tool-call time limit; how many tools can be merged without losing needed control.
First check: p1-00 — run the flow on the Mac with today's tools and log every manual fix; the count is the baseline.
Exit: an agent goes from nothing to a retrieved image and one traceable revision, in 3 consecutive real runs with zero manual fixes.
Demo: run the smoke script against the Mac ComfyUI; show the image, its revision and their Gallery records.

### Phase 2 — One-sentence flow: resources → workflow → image (active 2026-11-26)

Role: core. Depends on: Phase 1 (envelope, `wait_for_job`).
Scope:
- Civitai tools for agents: search models by text, type (checkpoint, LoRA, …) and base model, returning what an agent needs to choose (base model, download count, rating, file size, NSFW level, license); safe content by default, NSFW only when asked; inspect a version (files, trigger words, recommended parameters).
- Download as a Backend job the agent follows with `wait_for_job` or a status call, since checkpoints (about 6.5 GB for SDXL) cannot finish inside one MCP call; `.safetensors` only, hash verified after download; a per-file size limit and a total disk budget, refusing with a clear error rather than filling the disk. Files the free key cannot download (for example Early Access) fail with a clear error.
- Civitai API key: the owner places a free key in a local file outside the repo; the Backend reads it from the path set in its private configuration (`CIVITAI_API_KEY_FILE`). The key is never committed, logged or returned through MCP; without it, only files that need no login download, and login-required files fail with a clear error.
- Resource record: one Backend-owned record for every downloaded or already-present model, with source, type, base model, mapped model family, file hash, trigger words, recommended parameters and license. Unknown local files are identified by hash lookup. Agents list and filter the record, and reuse a registered resource instead of downloading it again. It replaces the overlapping local identity ledger and source aliases rather than adding a second record.
- Base-model mapping: one table from Civitai base models to manifest `model_family`. Phase 2 supports only the SDXL group (`SDXL 1.0`, `Illustrious`, `Pony`, `NoobAI` → `sdxl`); every other base model returns "no matching workflow".
- Workflow selection: given the chosen resources, pick the matching template from the existing workflow manifests (for checkpoint + LoRA, `default_lora`), or return a clear "no matching workflow" error.
- Trigger words and recommended parameters: `generate` applies them from the resource record by default (trigger words added to the prompt; recommended sampler/steps/CFG/size when the agent gives none); the agent can override; the job records what was applied.
- Licenses: personal, non-commercial use only, so models are not filtered by commercial-use permission; the license is still stored in the record.
Remove: Civitai services and tools this flow does not use. The First check lists the services the hand run actually touches; recipe import, recipe variants and variation sets, generate-like and any service outside that list are deleted, with their tests. The Phase 1 Civitai tools (`civitai_source_info`, `civitai_resource_acquire`, `civitai_resource_status`) are replaced by the new ones.
Unknowns, riskiest first: whether login-required files download with the free API key, and whether rate limits allow normal use; whether checkpoint + LoRA through `default_lora` produces a correct image on the Mac (p1-05 ran only `default` without a LoRA, and the template's own meta says its output needs re-verification); how the Civitai base-model labels map to the installed loaders; how much of the existing Civitai code (about 20 services) fits this flow.
First check: one manual search → download (with the key) → register → `default_lora` generate run with the real Civitai API before writing task specs; record every failure and the list of services the run used.
Exit: from one sentence, an agent finds a checkpoint and a LoRA on Civitai, registers them and gets back an image that used the LoRA's trigger words, in 3 consecutive real runs with zero manual fixes. The three runs use three different sentences; at least one downloads both a new checkpoint and a new LoRA, and the others may reuse resources the agent finds in the resource record.
Demo: give an agent one sentence; show the Civitai search, the download job, the resource records, the selected workflow, the applied trigger words and parameters, the image and its Gallery record. CTY judges the image.

### Phase 3 — Same-LAN Windows workers

Role: support (the Mac is too slow). Depends on: Phase 1 (`health`, `list_workers`).
Scope: Backend–worker authentication and secured PowerShell control; same-project check (git commit, workflows, custom nodes, models registered in the resource record); durable concurrent queue that survives restarts; worker registry with heartbeat, capabilities and load; `execution_target=auto`; results recorded with their worker; updater replaced by `git pull` + restart.
Remove: the old worker updater and packaging; the single-URL worker setting once the registry replaces it.
Unknowns, riskiest first: whether the worker can be installed reliably on the owner's second Windows machine; whether the in-memory queue can be made durable and concurrent without breaking the existing job flow; how to compare models across machines cheaply.
First check: install the worker by hand on the second Windows machine and record every step that fails, before writing task specs.
Exit: a second Windows machine produces an image traceable in the Gallery while local ComfyUI runs another job, in 3 consecutive real runs with zero manual fixes.
Demo: submit two jobs at once; show both complete on different machines and both Gallery records.

### Phase 4 — One-sentence flow: image → short clip

Role: core. Depends on: Phase 2 (resource record, workflow selection), Phase 3 (runs on the NVIDIA worker).
Scope: one fixed image-to-video workflow with frame interpolation, exposed as one MCP tool that takes a Gallery image and returns a clip with its Gallery record; models it needs registered in the resource record; dispatched to a worker by `execution_target=auto`.
Remove: the other video code (Wan keyframe, Argus MLX, Discord fixed video) — deleted, or kept frozen only with a stated reason.
Unknowns, riskiest first: which image-to-video model and interpolation node give acceptable quality and time on the owner's NVIDIA machine; whether the workflow's custom nodes install cleanly through the same-project check.
First check: run one image-to-video + interpolation workflow by hand in ComfyUI on the worker and record model, nodes, time and VRAM, before writing task specs.
Exit: from one sentence, an agent gets an image (Phase 2) and then a short interpolated clip of it, in 3 consecutive real runs with zero manual fixes.
Demo: give an agent one sentence; show the image, the clip, the worker that ran it and both Gallery records.

### Phase 5 — LoRA training for consistent characters and styles

Role: core. Depends on: Phase 2 (resource record), Phase 3 (training runs on the NVIDIA worker).
Scope: first real training run on a small owner dataset with one base model (SDXL or Anima); the chain train → register in the resource record → generate by name through MCP → smoke image; training dispatched to a worker; LoRA MCP tools redesigned around this chain.
Remove: the Phase 1 LoRA tools replaced by the redesign; trainer paths for base models not chosen here are frozen.
Unknowns, riskiest first: whether the trainer environment on the worker actually trains the chosen base model; whether the produced LoRA loads in ComfyUI; whether the character stays recognizable across different prompts.
First check: train one small LoRA by hand on the worker with the chosen base model and load it in ComfyUI, recording every step that fails, before writing task specs.
Exit: one real training yields a clearly named LoRA that an agent uses by name through MCP to produce several images of the same character; the train → register → generate chain runs 3 consecutive times with zero manual fixes.
Demo: show the run folder, effective parameters, the resource record and a set of images from different prompts; CTY judges consistency.

### Phase 6 — Prompt-combination dashboard

Role: add-on. Depends on: Phase 2 (resource record, workflow selection), Phase 5 (LoRAs to combine).
Scope: a recipe = prompt combination + workflow template + models/LoRAs + sampler parameters, unified with style presets; template parameters rendered from `.meta.json`; progress, errors and thumbnails on the Workbench; save a result as a recipe; MCP `generate_from_recipe`.
Remove: the separate combination and style-preset data paths and UI once recipes replace them (saved presets migrated, not deleted).
Unknowns, riskiest first: whether combinations and style presets can share one data model without breaking saved presets; whether `.meta.json` describes enough to build forms for every template.
First check: turn one saved style preset and one prompt combination into a recipe by hand and generate from it, before writing task specs.
Exit: a recipe built in the UI, including a trained LoRA, is used by an agent through MCP to generate an image, in 3 consecutive real runs with zero manual fixes.
Demo: CTY builds a recipe in the Workbench, then an agent generates from it by ID.

## Not now

- Non-Windows workers (macOS, Linux) and paid cloud compute.
- Workflow engines such as n8n or Zapier.
- UI redesign beyond what Phase 6 needs.
- Video beyond the one fixed image-to-video workflow with interpolation. Existing Wan keyframe, Argus MLX and Discord fixed-video code is kept but not developed further.

## Thresholds

Ask after 3 tasks in a row that do not advance the active milestone, a blocker longer than 2 days, or 3 review rejections of one task.

## Review history

- 2026-11-26 — Phase 1 closed by CTY; order unchanged; Phase 2 activated with added scope: base-model mapping (SDXL group only), download as a job with size/disk limits, API key read from a local key file, one resource record replacing the ledger and aliases, trigger words and recommended parameters applied by `generate`, no commercial-use license filter (personal use), concrete Remove list, `default_lora` added as an unknown, and an exit with three different sentences and at least one fresh download ([decisions](../decisions/roadmap.md)).
- 2026-11-26 — p1-05 fixed demo accepted by native human-only Board confirmation; reviewed feature integrated after exact QA PASS. [Actual phase-exit evidence/proposal](../tasks/p1-05-mcp-e2e-smoke-mac/phase-exit.md) is submitted for the separate phase-close roadmap decision. No order/scope/Not now change or Phase 2 activation is inferred.

- 2026-11-24 — CTY authorized executable work after planning inside existing project boundaries and delegated routine reference choices. Phase 1 proceeds through the existing kickoff/build/review workflow; scope/order/exit rules are unchanged ([request](../requests/2026-11-24-proceed-within-project-boundaries.md)).

- 2026-11-24 — Phase rules added: every phase has Remove and First check fields; exits need 3 consecutive real runs with zero manual fixes; the roadmap is reviewed at every phase close ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Phase 2 split: image flow stays Phase 2; image-to-video with interpolation becomes Phase 4, after workers, because it needs the NVIDIA machine. LoRA moves to Phase 5, dashboard to Phase 6 ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Phase 1 re-scoped: p1-00 friction run first (Mac suite moved there), Civitai and LoRA tools not merged, `generate` keeps two modes, video leaves MCP until Phase 2, `wait_for_job` capped below the client limit ([decisions](../decisions/mcp.md)).
- 2026-11-24 — Phase 0 closed on the Windows result (Backend 2018 passed, MCP 314 passed); the macOS Backend rerun moved into p1-05 ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Destination rewritten around the one-sentence flow; new Phase 2 (Civitai tools, resource record, workflow selection, fixed image-to-video with interpolation); LoRA marked core and moved ahead of the dashboard. Order: MCP → one-sentence flow → workers → LoRA → dashboard ([decisions](../decisions/roadmap.md)).
- 2026-11-23 — Order changed to MCP → workers → dashboard → LoRA (Phase 2 and 3 swapped).
- 2026-11-23 — Four goals and phase order set by CTY; Phase 0 activated; roadmap accepted; thresholds and Not now approved ([decisions](../decisions/roadmap.md)).
