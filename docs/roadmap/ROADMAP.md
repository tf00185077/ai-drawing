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

### Phase 1 — MCP that agents use smoothly (active: real Mac smoke and exit proof)

Role: core. Depends on: Phase 0.
Scope: a friction run on today's tools that records every manual fix; one response envelope for every tool (`{ok, data}` / `{ok: false, error: {code, message, hint}}`); generation, job, Gallery, prompt, style-preset and ComfyUI tools consolidated to one per intent with one risk label each (Civitai and LoRA tools keep their names until Phase 2 and Phase 5; video and Civitai generate-like leave MCP); `wait_for_job` returning artifact paths/URLs within the client's call limit; `health` and `list_workers`; a real end-to-end smoke script on the Mac ComfyUI. Tasks: [p1-00](../tasks/p1-00-mcp-friction-run-mac/task.md) → [p1-01](../tasks/p1-01-mcp-response-envelope/task.md) + [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md) (shipped together) → [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md) → [p1-04](../tasks/p1-04-mcp-health-and-workers/task.md) → [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md); decisions in [mcp](../decisions/mcp.md).
Execution status: [2026-11-24 plan and native backlog](../tasks/p1-planning-2026-11-24/plan.md). The no-repair baseline and prerequisite [Mac runtime/retrieval repair](../tasks/p1-00a-mac-runtime-and-retrieval/acceptance.md) are accepted. p1-01/02 are accepted together at corrected `616f67f` after independent round-2 PASS for both (`28cd451`), integrated unchanged at `7ba2059f7e46920eaf860e19e61aa84bae8bf02c` ([acceptance](../tasks/p1-01-mcp-response-envelope/acceptance.md)). One prior p1-02 delivery rejection/correction round 1 is preserved. p1-03 is accepted at exact `77e3e3c` after independent delivery review 1 PASS (`d088c32`), with its one kickoff ambiguity/clarification 1/round-2 CLEAR preserved and zero implementation rejections ([acceptance](../tasks/p1-03-mcp-wait-and-result/acceptance.md)). Completion/publication of AID-144 released AID-145 for fresh p1-04 kickoff. AID-165 returned AMBIGUITY K4-1 (configured versus observed worker identity); [clarification 1](../tasks/p1-04-mcp-health-and-workers/kickoff-clarification-1.md) is independently CLEAR at fixed `5cf158b` after AID-166 review `e75a94e`. Producer accepted actual p1-04 feature `72f4834` after independent D1-D4 PASS `3422ccd`, preserving its one kickoff ambiguity/clarification 1/round-2 CLEAR and delivery review 1 PASS with zero rejections ([acceptance](../tasks/p1-04-mcp-health-and-workers/acceptance.md)). AID-145 is done. [QA AID-169](/AID/issues/AID-169) returned p1-05 kickoff AMBIGUITY K5-1/K5-2 at fixed `d95f1a3`, report `039c0ae`. Producer adopts [clarification 1](../tasks/p1-05-mcp-e2e-smoke-mac/kickoff-clarification-1.md): bounded canonical PNG content on existing Gallery read and strict one-wait/reset/preparation accounting, preserving all owner exit rules. [QA AID-170](/AID/issues/AID-170) returned round-2 CLEAR at fixed `4fc3ff2`, report `a745998`; [kickoff acceptance](../tasks/p1-05-mcp-e2e-smoke-mac/kickoff-acceptance.md) retains the unchanged contract. Kickoff history remains one ambiguity event/two findings, clarification 1/round-2 CLEAR. Coding AID-171 delivered `8736298`; independent QA AID-172 returned delivery review 1 FAIL R5-1 (P1, D3 interruption reset/accounting), report `f510a0a`. D1 and recorded D2 passed independent checks; D4 stays unchecked. [Correction 1](../tasks/p1-05-mcp-e2e-smoke-mac/repair-round-1.md) requires actual signal regressions and a fresh frozen three-pair real proof, followed by renewed exact-final-commit QA and CTY demo acceptance. First implementation rejection/correction 1/next delivery review 2 is preserved; product remains off main. Old three-pair/six-MCP-PNG evidence and 81-unit total retain their limits; the actual client limit stays unverified with explicit 50-second overall wait fallback. CTY's delegated-choice authority remains in effect. No phase-exit result is claimed.

Remove: Wan keyframe video, custom video and Civitai generate-like tools from MCP (Backend code frozen); every old tool name replaced by the consolidation.
Unknowns, riskiest first: which manual fixes a run needs today and whether they are MCP problems or Backend/ComfyUI problems; the MCP client's tool-call time limit; how many tools can be merged without losing needed control.
First check: p1-00 — run the flow on the Mac with today's tools and log every manual fix; the count is the baseline.
Exit: an agent goes from nothing to a retrieved image and one traceable revision, in 3 consecutive real runs with zero manual fixes.
Demo: run the smoke script against the Mac ComfyUI; show the image, its revision and their Gallery records.

### Phase 2 — One-sentence flow: resources → workflow → image

Role: core. Depends on: Phase 1 (envelope, `wait_for_job`).
Scope:
- Civitai tools for agents: search models by text, type (checkpoint, LoRA, …) and base model; inspect a version (files, trigger words, recommended parameters); download safely, with an optional API key from the environment.
- Resource record: every downloaded or already-present model registered with source, type, base model, file hash, trigger words and recommended parameters; unknown local files identified by hash lookup; agents list and filter the record.
- Workflow selection: given the chosen resources, pick the matching template from the existing workflow manifests, or return a clear "no matching workflow" error.
Remove: existing Civitai services and tools this flow does not use (about 20 services today); the Phase 1 Civitai tools replaced by the new ones.
Unknowns, riskiest first: whether files that require login download with a free API key, and whether rate limits allow normal use; how much of the existing Civitai code (about 20 services) fits this flow.
First check: one manual search → download → register → generate run with the real Civitai API before writing task specs.
Exit: from one sentence, an agent finds a checkpoint and a LoRA on Civitai, downloads and registers them, and gets back an image, in 3 consecutive real runs with zero manual fixes.
Demo: give an agent one sentence; show the Civitai search, the resource records, the selected workflow, the image and its Gallery record.

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

- 2026-11-24 — CTY authorized executable work after planning inside existing project boundaries and delegated routine reference choices. Phase 1 proceeds through the existing kickoff/build/review workflow; scope/order/exit rules are unchanged ([request](../requests/2026-11-24-proceed-within-project-boundaries.md)).

- 2026-11-24 — Phase rules added: every phase has Remove and First check fields; exits need 3 consecutive real runs with zero manual fixes; the roadmap is reviewed at every phase close ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Phase 2 split: image flow stays Phase 2; image-to-video with interpolation becomes Phase 4, after workers, because it needs the NVIDIA machine. LoRA moves to Phase 5, dashboard to Phase 6 ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Phase 1 re-scoped: p1-00 friction run first (Mac suite moved there), Civitai and LoRA tools not merged, `generate` keeps two modes, video leaves MCP until Phase 2, `wait_for_job` capped below the client limit ([decisions](../decisions/mcp.md)).
- 2026-11-24 — Phase 0 closed on the Windows result (Backend 2018 passed, MCP 314 passed); the macOS Backend rerun moved into p1-05 ([decisions](../decisions/roadmap.md)).
- 2026-11-24 — Destination rewritten around the one-sentence flow; new Phase 2 (Civitai tools, resource record, workflow selection, fixed image-to-video with interpolation); LoRA marked core and moved ahead of the dashboard. Order: MCP → one-sentence flow → workers → LoRA → dashboard ([decisions](../decisions/roadmap.md)).
- 2026-11-23 — Order changed to MCP → workers → dashboard → LoRA (Phase 2 and 3 swapped).
- 2026-11-23 — Four goals and phase order set by CTY; Phase 0 activated; roadmap accepted; thresholds and Not now approved ([decisions](../decisions/roadmap.md)).
