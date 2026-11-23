# Roadmap

## Destination

An agent asks for an image through MCP and gets it back without help; jobs spread across same-LAN Windows machines running this project; a user sets up reusable prompt combinations in a dashboard and agents use them; and the team trains LoRAs from owner datasets and uses them in those combinations.

Constraints: keep the FastAPI Backend, React/Vite UI, Python MCP server and host ComfyUI; the Backend owns job, artifact and provenance records; [operating policy](../OPERATING-POLICY.md) applies; CTY judges aesthetics. Current state: [CURRENT](../CURRENT.md).

## Milestones

### Phase 0 — Clean foundation (active)

Scope: integrated `main`; documentation rebuilt in English; history removed; a progress table based on the current code; a known, documented test result for every suite.
Unknowns, riskiest first: whether the full Backend suite passes on Windows after the outdated tests were removed.
Exit: a new agent understands the system, its state and its rules from README → AGENTS → INDEX; every failing test is fixed or explicitly quarantined with a reason.
Demo: CTY reads README, CURRENT and ROADMAP and finds them accurate; one command per suite runs with the documented result.

### Phase 1 — MCP that agents use smoothly (next)

Scope: one response envelope for every tool (`{ok, data}` / `{ok: false, error: {code, message, hint}}`); tools consolidated to about 20, one per intent, with risk labels; `wait_for_job` returning artifact paths/URLs; `health` and `list_workers`; a real end-to-end smoke script on the Mac ComfyUI (Windows worker follows in Phase 2). Tasks: [p1-01](../tasks/p1-01-mcp-response-envelope/task.md) → [p1-02](../tasks/p1-02-mcp-tool-consolidation/task.md) → [p1-03](../tasks/p1-03-mcp-wait-and-result/task.md) → [p1-04](../tasks/p1-04-mcp-health-and-workers/task.md) → [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md); decisions in [mcp](../decisions/mcp.md).
Unknowns, riskiest first: whether a real generation and retrieval through MCP works end to end on the owner's ComfyUI; whether changing response formats breaks existing agent callers; how many tools can be merged without losing needed control.
Exit: an agent goes from nothing to a retrieved image and one traceable revision with no human help.
Demo: run the smoke script against the Mac ComfyUI; show the image, its revision and their Gallery records.

### Phase 2 — Same-LAN Windows workers

Scope: Backend–worker authentication and secured PowerShell control; same-project check (git commit, workflows, custom nodes, models); durable concurrent queue that survives restarts; worker registry with heartbeat, capabilities and load; `execution_target=auto`; results recorded with their worker; updater replaced by `git pull` + restart.
Unknowns, riskiest first: whether the worker can be installed reliably on the owner's second Windows machine; whether the in-memory queue can be made durable and concurrent without breaking the existing job flow; how to compare models across machines cheaply.
Exit: a second Windows machine produces an image traceable in the Gallery while local ComfyUI runs another job.
Demo: submit two jobs at once; show both complete on different machines and both Gallery records.

### Phase 3 — Prompt-combination dashboard

Scope: a recipe = prompt combination + workflow template + models/LoRAs + sampler parameters, unified with style presets; template parameters rendered from `.meta.json`; progress, errors and thumbnails on the Workbench; save a result as a recipe; MCP `generate_from_recipe`.
Unknowns, riskiest first: whether combinations and style presets can share one data model without breaking saved presets; whether `.meta.json` describes enough to build forms for every template.
Exit: a recipe built in the UI is used by an agent through MCP to generate an image.
Demo: CTY builds a recipe in the Workbench, then an agent generates from it by ID.

### Phase 4 — LoRA training

Scope: first real training run on a small dataset with one base model (SDXL or Anima); the chain train → register → select in a recipe → smoke image; training dispatched to a worker.
Unknowns, riskiest first: whether the trainer environment on the target host actually trains the chosen base model; whether the produced LoRA loads in ComfyUI; whether training can run on a worker with the Phase 2 checks.
Exit: one real training yields a clearly named LoRA that is used in a recipe and produces a retrievable smoke image.
Demo: show the run folder, effective parameters, the recipe using the LoRA and the smoke image; CTY judges the result.

## Not now

- Non-Windows workers (macOS, Linux) and paid cloud compute.
- Workflow engines such as n8n or Zapier.
- UI redesign beyond what Phase 3 needs.

## Thresholds

Ask after 3 tasks in a row that do not advance the active milestone, a blocker longer than 2 days, or 3 review rejections of one task.

## Review history

- 2026-11-23 — Order changed to MCP → workers → dashboard → LoRA (Phase 2 and 3 swapped).
- 2026-11-23 — Four goals and phase order set by CTY; Phase 0 activated; roadmap accepted; thresholds and Not now approved ([decisions](../decisions/roadmap.md)).
