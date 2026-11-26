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
- **Phase close.** Producer records actual exit evidence and reviews order, scope and the next phase against this accepted roadmap. When its requirements are met without changing the project boundary, adopt the recommended continuation, log the review under Review history and proceed; report choices with results. Ask CTY before changing approved order, scope, architecture or constraints. CTY's artistic judgment remains separate ([current delegation](../requests/2026-11-26-phase-2-start-and-key-file.md)).

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
- Civitai API key: use the owner-provided file `/Users/tf00185088/Desktop/civitai.txt`, outside the repo. The Phase 2 Backend reads it through private `CIVITAI_API_KEY_FILE` configuration; [credential guidance](../civitai-credentials.md) distinguishes this planned file reader from the existing authorization setting and explains the First check bridge. The key is never committed, logged or returned through MCP; without it, only files that need no login download, and login-required files fail with a clear error.
- Resource record: one Backend-owned record for every downloaded or already-present model, with source, type, base model, mapped model family, file hash, trigger words, recommended parameters and license. Unknown local files are identified by hash lookup. Agents list and filter the record, and reuse a registered resource instead of downloading it again. It replaces the overlapping local identity ledger and source aliases rather than adding a second record.
- Base-model mapping: one table from Civitai base models to manifest `model_family`. Phase 2 supports only the SDXL group (`SDXL 1.0`, `Illustrious`, `Pony`, `NoobAI` → `sdxl`); every other base model returns "no matching workflow".
- Workflow selection: given the chosen resources, pick the matching template from the existing workflow manifests (for checkpoint + LoRA, `default_lora`), or return a clear "no matching workflow" error.
- Trigger words and recommended parameters: `generate` applies them from the resource record by default (trigger words added to the prompt; recommended sampler/steps/CFG/size when the agent gives none); the agent can override; the job records what was applied.
- Licenses: personal, non-commercial use only, so models are not filtered by commercial-use permission; the license is still stored in the record.
Remove: Civitai services and tools this flow does not use. The First check lists the services the hand run actually touches; recipe import, recipe variants and variation sets, generate-like and any service outside that list are deleted, with their tests. The Phase 1 Civitai tools (`civitai_source_info`, `civitai_resource_acquire`, `civitai_resource_status`) are replaced by the new ones.
Unknowns, riskiest first: whether login-required files download with the free API key, and whether rate limits allow normal use; whether checkpoint + LoRA through `default_lora` produces a correct image on the Mac (p1-05 ran only `default` without a LoRA, and the template's own meta says its output needs re-verification); how the Civitai base-model labels map to the installed loaders; how much of the existing Civitai code (about 20 services) fits this flow.
First check: one manual search → download (with the key) → register → `default_lora` generate run with the real Civitai API before writing task specs; record every failure and the list of services the run used.
Execution: [First check accepted](../tasks/p2-00-civitai-first-check/acceptance.md), Coding `0d571b7d` / independent observation PASS `9caf92fe`. One real free-key login-required LoRA download, adopted existing checkpoint and default_lora image 3878; 20 manual interventions/77 overlapping work units, no automatic flow or phase exit. Five historical source hashes missing to over-redaction remain disclosed. [Ranked intake](../tasks/p2-00-civitai-first-check/implementation-intake.md) begins with [p2-01 private file loading and credential-safe requests](../tasks/p2-01-civitai-key-file/task.md), with actual [round-1 kickoff CLEAR](../tasks/p2-01-civitai-key-file/kickoff-review.md) at 316327d, report 04629d2b. The [cleared handoff](../tasks/p2-01-civitai-key-file/implementation-handoff.md)
led to original delivery 1 FAIL R1/P1/D3 (301c5dee), followed by correction 1 and
[accepted exact delivery 2](../tasks/p2-01-civitai-key-file/acceptance.md): candidate
2e385030, independent D1–D5 PASS155e2209. Stateless cookies/final request policy
resolves R1; source publication does not deploy it. Producer next establishes
[p2-02 resource-record identity/metadata/mapping](../tasks/p2-02-resource-record/task.md)
before download-job/reservation persistence, following the joint intake and
[adopted existing-row decision](../decisions/civitai-resource-record.md). Fresh
independent [kickoff1 CLEAR](../tasks/p2-02-resource-record/kickoff-review.md)
(14b4c98a, fixed f8d3143/unchanged taskc43339e4) permits separate Coding and
exact delivery QA under [the handoff](../tasks/p2-02-resource-record/implementation-handoff.md).
[p2-02 is accepted](../tasks/p2-02-resource-record/acceptance.md) at Codingc705d211,
independent exact review10 PASSa94324fe. All D–Z items pass; nine earlier delivery
rejections/five historical P1 findings remain. Source publication integrates the
Backend foundation and exact72-row QA registry, without runtime deployment.
[p2-03](../tasks/p2-03-bounded-download/task.md) has actual independent
[kickoff1 CLEAR](../tasks/p2-03-bounded-download/kickoff-review.md) at86837c7/task285af6d1,
report9dfdf9f1. [Delivery review1 FAIL](../tasks/p2-03-bounded-download/review-round-1.md) at9db56097/report3ed5ae8f
has two P1s: post-commit adoption failure/current-state and duplicate active
acquisition. [Correction1](../tasks/p2-03-bounded-download/repair-round-1.md) and new
exact QA2 apply unchanged D3/D4; one rejection/two findings, rejected product/tests
off main. Durable attempts and aggregate reservations remain subsequent work. These are in-phase dependency refinements under current delegation,
not a change to owner scope/order/architecture/Not now. Search/hash lookup/newMCP/
defaults/proven removals and real qualification remain pending.

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

Report and reassess after 3 tasks in a row that do not advance the active milestone, a blocker longer than 2 days, or 3 review rejections of one task. Under CTY's current delegation, Producer adopts an in-boundary recommendation and continues; ask CTY when resolution requires a project-boundary decision.

## Review history

- 2026-11-27 — p2-03 actual review1 FAIL: adoption after a real commit loses its
  current timeout/file-change outcome; retained install ignores an active resource
  owner and submits again. Adopt existing-ID failure publication and active admission
  ownership within unchanged D3/D4, with meaningful repair faults/current exact QA2.
  One rejection/two P1s; original task/CLEAR/scope/order/Not now stay. Report results
  under current delegation, no routine owner gate, phase exit or artistic acceptance
  ([decision](../decisions/civitai-download-limits.md),
  [repair](../tasks/p2-03-bounded-download/repair-round-1.md)).


- 2026-11-27 — Accept actual p2-03 kickoff1 CLEAR9dfdf9f1 at fixed86837c7 and
  unchanged task285af6d1. Both-caller admission/failure/ownership and selected-size
  work apply the current contract, with explicit feature-preserving replacements
  for obsolete assertions. Dispatch separate Coding/exact delivery QA. No scope/
  order/architecture/Not now change or owner gate; baseline tests are not delivery
  or phase exit ([handoff](../tasks/p2-03-bounded-download/implementation-handoff.md)).

- 2026-11-27 — Accept p2-02 exact review10 PASS atc705d211/reporta94324fe, with
  nine previous rejections/five P1 histories preserved. Next bound stock download
  execution (8GiB/file,20GiB observed destination free-space floor, configurable;
  safetensors checkpoint/LoRA selection, valid resume and no-overwrite publication)
  before durable attempts/aggregate reservations. Actual source writes before
  checks and replaces targets. Fresh p2-03 kickoff then exact delivery QA; no
  boundary change, Phase2 exit or CTY artistic acceptance ([decision](../decisions/civitai-download-limits.md)).

- 2026-11-27 — Ninth p2-02 rejection: supplied QA8 unit/new-note/status cases,
  R2-R4 and checked R5 bounds pass, but raw outer local-ledger AIR/path copies
  expose complete synthetic values beside safe typed diagnostics. Reassess whole
  response coverage; retain internal identity/locator semantics and apply the
  shared complete-value policy at public serialization, with full-field/consumer
  inventory and a real outer-boundary fault. Correction9/exact QA10 stay original
  task/CLEAR/current delegation; report results, no routine owner gate or boundary
  change ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-9.md)).

- 2026-11-27 — Eighth p2-02 rejection: supplied review7 cases/R5 checked bounds
  pass, but original R1 remains at context-dependent JSON-unit extraction and
  narrower new-note/legacy-response redaction. Reassess the complete pipeline;
  adopt bounded representation candidates and the shared complete-value policy
  on new-note/public-response seams while preserving old storage. Correction8 and
  exact QA9 remain unchanged task/CLEAR; report results under current delegation,
  no boundary/architecture change or phase exit
  ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-8.md)).

- 2026-11-27 — Seventh p2-02 rejection: review7 leaves original R1 incomplete
  because preceding prose quotes hide complete explicit assignments. Supplied
  serialization and checked R5 bounds pass. Reassess the disjoint candidate
  premise; adopt bounded delimiter-associated label candidates independent of
  enclosing prose pairing, retaining full-value exclusion/useful safe output.
  Correction7 and independent exact QA8 remain unchanged task/CLEAR; report the
  in-boundary option under current delegation, no phase exit or boundary change
  ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-7.md)).

- 2026-11-26 — Sixth p2-02 delivery rejection: review6 confirms R5's checked bounds
  repair, but original R1 fails for once-serialized quoted assignments. Retain
  identity and monotonic scanning; adopt bounded representation handling before
  label/delimiter association, complete-value exclusion and useful safe output.
  Correction6 and independent exact review7 stay within unchanged task/CLEAR;
  report actual results under current delegation. No new boundary or phase exit
  ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-6.md)).

- 2026-11-26 — Fifth p2-02 delivery rejection: review5's current R1-R4 probes pass,
  but new R5 makes ordinary terminal-escape descriptions quadratic on actual
  provider/resource reads. Reassess the changed failure mode, retain identity and
  secrecy work, adopt monotonic quote/escape traversal with explicit end-of-input
  handling and real bounds/fault coverage. Correction5 and independent exact
  review6 remain under unchanged task/CLEAR. Report results under current delegation;
  no boundary change or phase exit ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-5.md)).

- 2026-11-26 — Fourth p2-02 rejection: review4 leaves R1 incomplete because quoted
  label extraction disagrees with key recognition; R2-R4 still pass. Extend the
  third-rejection reassessment, retain current identity/complete-value boundaries
  and adopt complete quoted-label parsing with consistency/whitespace/serialization
  class and fault coverage. Correction4 and independent exact review5 continue
  within unchanged task/CLEAR. Report actual results; no boundary change or Phase2
  exit ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-4.md)).

- 2026-11-26 — Third p2-02 delivery rejection: actual review3 R1 incomplete, while
  R2-R4 pass. Threshold reassessment retains current resource identity and adopts
  one credential key/assignment recognition policy with prefix-class guards;
  correction3 and independent exact review4 remain inside the approved contract.
  Report the threshold and adopted option under current delegation; no boundary
  change or Phase2 exit ([decision](../decisions/civitai-resource-record.md),
  [repair](../tasks/p2-02-resource-record/repair-round-3.md)).

- 2026-11-26 — Producer accepts p2-01 exact delivery review2 PASS after one R1 correction. Within the active Phase2 intake, establish existing resource-row metadata/identity before persistent download accounting; source aliases describe images and stay preserved pending dependency-proven removal. Scope/order/Not now and exit unchanged; fresh kickoff for p2-02. This is an in-phase sequencing review, not Phase2 close ([decision](../decisions/civitai-resource-record.md)).

- 2026-11-26 — CTY supplied the concrete Civitai key-file locator and instructed Producer to start Phase 2 from the updated main, adopt recommended in-boundary options, continue when roadmap requirements are met and report choices with results. Routine progression is delegated; project-boundary changes and artistic judgment remain with CTY ([request](../requests/2026-11-26-phase-2-start-and-key-file.md), [credential guidance](../civitai-credentials.md)).
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
