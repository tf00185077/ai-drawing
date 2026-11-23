# Roadmap

## Destination

An agent asks for an image through MCP and gets it back without help; a user sets up reusable prompt combinations in a dashboard and agents use them; jobs spread across same-LAN Windows machines running this project; and the team trains LoRAs from owner datasets and uses them in those combinations.

Constraints: keep the FastAPI Backend, React/Vite UI, Python MCP server and host ComfyUI; the Backend owns job, artifact and provenance records; [operating policy](../OPERATING-POLICY.md) applies; CTY judges aesthetics. Current state: [CURRENT](../CURRENT.md).

## Milestones

### Phase 0 — Clean foundation (active)

Scope: integrated `main`; documentation rebuilt in English; history removed; a progress table based on the current code; a known, documented test result for every suite.
Unknowns, riskiest first: which of the 26 Backend and 3 Windows-only MCP failures hide real defects.
Exit: a new agent understands the system, its state and its rules from README → AGENTS → INDEX; every failing test is fixed or explicitly quarantined with a reason.
Demo: CTY reads README, CURRENT and ROADMAP and finds them accurate; one command per suite runs with the documented result.

### Phase 1 — MCP that agents use smoothly (next)

Scope: uniform structured responses (`{ok, data, error: {code, hint}}`); `wait_for_job` and a result tool returning artifact paths/URLs; risk labels on tools; a short common flow `list_resources → compose → generate → wait/result`; `list_workers` / `worker_status`; a real end-to-end smoke script.
Unknowns, riskiest first: whether a real generation and retrieval through MCP works end to end on the owner's ComfyUI; whether changing response formats breaks existing agent callers; how many tools can be merged without losing needed control.
Exit: an agent goes from nothing to a retrieved image and one traceable revision with no human help.
Demo: run the smoke script against local ComfyUI; show the image, its revision and their Gallery records.

### Phase 2 — Prompt-combination dashboard

Scope: a recipe = prompt combination + workflow template + models/LoRAs + sampler parameters, unified with style presets; template parameters rendered from `.meta.json`; progress, errors and thumbnails on the Workbench; save a result as a recipe; MCP `generate_from_recipe`.
Unknowns, riskiest first: whether combinations and style presets can share one data model without breaking saved presets; whether `.meta.json` describes enough to build forms for every template.
Exit: a recipe built in the UI is used by an agent through MCP to generate an image.
Demo: CTY builds a recipe in the Workbench, then an agent generates from it by ID.

### Phase 3 — Same-LAN Windows workers

Scope: Backend–worker authentication and secured PowerShell control; same-project check (git commit, workflows, custom nodes, models); durable concurrent queue that survives restarts; worker registry with heartbeat, capabilities and load; `execution_target=auto`; results recorded with their worker; updater replaced by `git pull` + restart.
Unknowns, riskiest first: whether the worker can be installed reliably on the owner's second Windows machine; whether the in-memory queue can be made durable and concurrent without breaking the existing job flow; how to compare models across machines cheaply.
Exit: a second Windows machine produces an image traceable in the Gallery while local ComfyUI runs another job.
Demo: submit two jobs at once; show both complete on different machines and both Gallery records.

### Phase 4 — LoRA training

Scope: first real training run on a small dataset with one base model (SDXL or Anima); the chain train → register → select in a recipe → smoke image; training dispatched to a worker.
Unknowns, riskiest first: whether the trainer environment on the target host actually trains the chosen base model; whether the produced LoRA loads in ComfyUI; whether training can run on a worker with the Phase 3 checks.
Exit: one real training yields a clearly named LoRA that is used in a recipe and produces a retrievable smoke image.
Demo: show the run folder, effective parameters, the recipe using the LoRA and the smoke image; CTY judges the result.

## Not now

- Non-Windows workers (macOS, Linux) and paid cloud compute.
- Workflow engines such as n8n or Zapier.
- UI redesign beyond what Phase 2 needs.

## Thresholds

Ask after 3 tasks in a row that do not advance the active milestone, a blocker longer than 2 days, or 3 review rejections of one task.

## Review history

- 2026-11-23 — Four goals and phase order set by CTY; Phase 0 activated; roadmap accepted; thresholds and Not now approved ([decisions](../decisions/roadmap.md)).
