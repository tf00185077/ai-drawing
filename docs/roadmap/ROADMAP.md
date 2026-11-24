# Roadmap

## Destination

**Core.** A user says one sentence to an agent ("draw character X in style Y", "make a short clip of it"). The agent searches Civitai through this project's MCP tools, downloads the checkpoint and LoRAs it needs, and registers them. This project keeps the record of every resource, picks the workflow that matches those resources, runs it on ComfyUI and returns an image or a short image-to-video clip with frame interpolation. Characters and styles stay consistent across images because the team trains LoRAs from the owner's datasets and the agent uses them by name. No human help is needed between the sentence and the result.

**Support and add-ons.** Jobs spread across same-LAN Windows machines because the Mac is too slow for real use (support). A user saves reusable prompt combinations in a dashboard and agents generate from them (add-on).

Division of work: the agent decides *what* to look for; this project provides the tools to search, download, register and generate, and owns the records. Only the ComfyUI features the owner actually uses are exposed.

Constraints: keep the FastAPI Backend, React/Vite UI, Python MCP server and host ComfyUI; the Backend owns job, artifact, resource and provenance records; Civitai is used through its free public API (an API key only where a file requires it); [operating policy](../OPERATING-POLICY.md) applies; CTY judges aesthetics. Current state: [CURRENT](../CURRENT.md).

Order: core before support, support before add-ons. MCP basics come first because every later phase is used through an agent; workers come before LoRA because training needs the NVIDIA machine.

## Milestones

### Phase 0 — Clean foundation (active)

Role: foundation.
Scope: integrated `main`; documentation rebuilt in English; history removed; a progress table based on the current code; a known, documented test result for every suite.
Unknowns, riskiest first: whether the full Backend suite passes on Windows after the outdated tests were removed.
Exit: a new agent understands the system, its state and its rules from README → AGENTS → INDEX; every failing test is fixed or explicitly quarantined with a reason.
Demo: CTY reads README, CURRENT and ROADMAP and finds them accurate; one command per suite runs with the documented result.

### Phase 1 — MCP that agents use smoothly (next)

Role: core. Depends on: Phase 0.
Scope: one response envelope for every tool (`{ok, data}` / `{ok: false, error: {code, message, hint}}`); tools consolidated to about 20, one per intent, with risk labels; `wait_for_job` returning artifact paths/URLs; `health` and `list_workers`; a real end-to-end smoke script on the Mac ComfyUI. Tasks: [p1-01](../tasks/p1-01-mcp-response-envelope/task.md) → [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md) → [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md) → [p1-04](../tasks/p1-04-mcp-health-and-workers/task.md) → [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md); decisions in [mcp](../decisions/mcp.md).
Unknowns, riskiest first: whether a real generation and retrieval through MCP works end to end on the owner's ComfyUI; whether changing response formats breaks existing agent callers; how many tools can be merged without losing needed control.
Exit: an agent goes from nothing to a retrieved image and one traceable revision with no human help.
Demo: run the smoke script against the Mac ComfyUI; show the image, its revision and their Gallery records.

### Phase 2 — One-sentence flow: resources → workflow → image or clip

Role: core. Depends on: Phase 1 (envelope, `wait_for_job`).
Scope:
- Civitai tools for agents: search models by text, type (checkpoint, LoRA, …) and base model; inspect a version (files, trigger words, recommended parameters); download safely, with an optional API key from the environment.
- Resource record: every downloaded or already-present model registered with source, type, base model, file hash, trigger words and recommended parameters; unknown local files identified by hash lookup; agents list and filter the record.
- Workflow selection: given the chosen resources, pick the matching template from the existing workflow manifests, or return a clear "no matching workflow" error.
- One fixed image-to-video workflow with frame interpolation, exposed as one MCP tool.
- Trim or freeze existing Civitai code that this flow does not use.
Unknowns, riskiest first: whether files that require login download with a free API key, and whether rate limits allow normal use; how much of the existing Civitai code (about 20 services) fits this flow; whether the chosen image-to-video model runs acceptably on the Mac or needs Phase 3.
First check: one manual search → download → register → generate run with the real Civitai API before writing task specs.
Exit: from one sentence, an agent finds a checkpoint and a LoRA on Civitai, downloads and registers them, and gets back an image and a short interpolated clip, with no human help.
Demo: give an agent one sentence; show the Civitai search, the resource records, the selected workflow, the image, the clip and their Gallery records.

### Phase 3 — Same-LAN Windows workers

Role: support (the Mac is too slow). Depends on: Phase 1 (`health`, `list_workers`).
Scope: Backend–worker authentication and secured PowerShell control; same-project check (git commit, workflows, custom nodes, models registered in the resource record); durable concurrent queue that survives restarts; worker registry with heartbeat, capabilities and load; `execution_target=auto`; results recorded with their worker; updater replaced by `git pull` + restart.
Unknowns, riskiest first: whether the worker can be installed reliably on the owner's second Windows machine; whether the in-memory queue can be made durable and concurrent without breaking the existing job flow; how to compare models across machines cheaply.
First check: install the worker by hand on the second Windows machine and record every step that fails, before writing task specs.
Exit: a second Windows machine produces an image traceable in the Gallery while local ComfyUI runs another job.
Demo: submit two jobs at once; show both complete on different machines and both Gallery records.

### Phase 4 — LoRA training for consistent characters and styles

Role: core. Depends on: Phase 2 (resource record), Phase 3 (training runs on the NVIDIA worker).
Scope: first real training run on a small owner dataset with one base model (SDXL or Anima); the chain train → register in the resource record → generate by name through MCP → smoke image; training dispatched to a worker.
Unknowns, riskiest first: whether the trainer environment on the worker actually trains the chosen base model; whether the produced LoRA loads in ComfyUI; whether the character stays recognizable across different prompts.
Exit: one real training yields a clearly named LoRA that an agent uses by name through MCP to produce several images of the same character.
Demo: show the run folder, effective parameters, the resource record and a set of images from different prompts; CTY judges consistency.

### Phase 5 — Prompt-combination dashboard

Role: add-on. Depends on: Phase 2 (resource record, workflow selection), Phase 4 (LoRAs to combine).
Scope: a recipe = prompt combination + workflow template + models/LoRAs + sampler parameters, unified with style presets; template parameters rendered from `.meta.json`; progress, errors and thumbnails on the Workbench; save a result as a recipe; MCP `generate_from_recipe`.
Unknowns, riskiest first: whether combinations and style presets can share one data model without breaking saved presets; whether `.meta.json` describes enough to build forms for every template.
Exit: a recipe built in the UI, including a trained LoRA, is used by an agent through MCP to generate an image.
Demo: CTY builds a recipe in the Workbench, then an agent generates from it by ID.

## Not now

- Non-Windows workers (macOS, Linux) and paid cloud compute.
- Workflow engines such as n8n or Zapier.
- UI redesign beyond what Phase 5 needs.
- Video beyond the one fixed image-to-video workflow with interpolation. Existing Wan keyframe, Argus MLX and Discord fixed-video code is kept but not developed further.

## Thresholds

Ask after 3 tasks in a row that do not advance the active milestone, a blocker longer than 2 days, or 3 review rejections of one task.

## Review history

- 2026-11-24 — Destination rewritten around the one-sentence flow; new Phase 2 (Civitai tools, resource record, workflow selection, fixed image-to-video with interpolation); LoRA marked core and moved ahead of the dashboard. Order: MCP → one-sentence flow → workers → LoRA → dashboard ([decisions](../decisions/roadmap.md)).
- 2026-11-23 — Order changed to MCP → workers → dashboard → LoRA (Phase 2 and 3 swapped).
- 2026-11-23 — Four goals and phase order set by CTY; Phase 0 activated; roadmap accepted; thresholds and Not now approved ([decisions](../decisions/roadmap.md)).
