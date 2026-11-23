# Four-pillar assessment and roadmap draft (2026-11-23)

> Status: **draft proposal**. It does not replace `docs/roadmap/ROADMAP.md` until the owner adopts it.
> Method: static reading of docs, source, test inventory and git history. Services were not started and test suites were not run (`mcp-server/.venv` lacks pytest; offline `uv` could not resolve dependencies).

## 1. Summary

| Pillar | Source completeness | Verified in real runs | Current state |
|---|---|---|---|
| 1. Agent-facing MCP server | ~75% | ~10% | 40 registered tools with mocked tests; the real request → generate → retrieve → revise journey (M1) is not complete |
| 2. Prompt-combination dashboard | ~70% | ~20% | Prompt Workbench is feature-rich; linkage to workflow templates and style presets is thin |
| 3. Same-LAN Windows worker | ~45% | 0% | Single-worker proxy exists; not installed, no authentication, no multi-worker support, no same-project version check |
| 4. LoRA training | ~60% | 0% | 8k+ Backend lines; three QA-accepted candidates are **not in main**; no successful real training run |

**The main systemic problem is process, not code.** Since November, nearly every commit on main is governance documentation. Several candidates that passed independent QA (`ab95a2a` naming/isolation, `7314a8c` smoke validation, `bf3f1ee` lifecycle, the Gallery fix) are not in main. Integration must be unfrozen before any pillar can advance.

## 2. Pillar details

### 2.1 MCP server (`mcp-server/`, ~2.2k lines of tool code)

Present:
- Generation (image / custom workflow / video), status, cancel, resource listing, Gallery, Civitai, style presets, Prompt Library, LoRA training, Discord delivery, ComfyUI node install / restart.
- `tool_catalog.py` with a registration-alignment test; `execution_target=local|worker`.

Gaps for agent usability:
- **Inconsistent responses**: `plain_text`, `json_string` and `dict` are mixed.
- **Large flat tool surface**: 40 tools with no read / mutate / admin labelling.
- **No wait-for-completion tool**: agents must poll `get_generation_status`.
- **No worker visibility**: agents cannot list workers or their models, nodes or load.
- No MCP resources or prompts (e.g. exposing prompt combinations and presets as resources).
- Mocked tests only; no end-to-end MCP smoke against a real Backend and ComfyUI.

### 2.2 Prompt-combination dashboard (`frontend/src/components/prompt-library/`)

Present:
- `/prompt-library/workbench`: ordering and weighting of positive/negative fragments, saved combinations, category management, entry editing, `GenerationPanel` submission; good test coverage.
- `prompt_library/` holds many categories and five combinations.

Gaps:
- Combinations cover prompt text only; there is **no single reusable recipe binding combination + workflow template + model/LoRA + parameters** (style presets do this, but the Workbench does not list preset graphs).
- Weak in-page feedback loop for progress, errors and results after submission.
- The Gallery readability fix was rolled back (AID-138) and is not in main.
- `Dashboard.tsx` is a system-status card, not a combination entry point.

### 2.3 Windows worker (`worker/windows/`, ~7.6k lines, over half updater code)

Present:
- Worker service proxies ComfyUI `/prompt`, `/queue`, `/history`, `/view`, `/upload/image`; Backend `NvidiaWorkerClient` with optional `/24` discovery; `execution_target=worker` never falls back to local.
- Install / start / migrate PowerShell scripts; a reviewed first-install guide.

Gaps:
- **One worker URL only**: no registry, capability reporting, scheduling or load distribution.
- **"Same project" is not enforced**: no commit/version handshake; workflows, custom nodes and models are not compared.
- **Security blocker**: the PowerShell control routes are unauthenticated.
- Large updater/migration code, mostly for retired APIs.
- Never successfully installed on the owner's machine; installation is currently deferred.

### 2.4 LoRA training (`backend/app/services/lora_*`, ~8.3k lines)

Present:
- Dataset inspection/curation/assessment, captioning, preflight, recipe compiler, sd-scripts subprocess (SD1.5 / SDXL / Anima), logs, cancel, output registration, smoke submission; `LoraTrain.tsx` UI; nine MCP training tools.

Gaps:
- Readable naming and per-run folders, effective-parameter records, smoke image validation and lifecycle fixes all live in **unmerged candidates**.
- On main, the smoke test only records `submitted`; a registration failure can still show `completed`.
- No real run of train → select → smoke image.
- No path to run training on a worker.

## 3. Roadmap draft

Order follows the owner's priorities (MCP → dashboard → worker → LoRA), preceded by an unfreeze phase.

### Phase 0 — Unfreeze integration and rebuild docs (blocks everything)
- Decide whether to rebase/merge the QA-accepted candidates into main.
- Make Backend, MCP and frontend test suites runnable in one command and green on main.
- Rebuild documentation from scratch in English (see `2026-11-23-doc-inventory.md`).
- **Exit**: main contains all accepted code; tests are green; the new doc set is adopted.

### Phase 1 — MCP that agents use smoothly
1. Uniform structured responses: `{ok, data, error: {code, hint}}`.
2. Add `wait_for_job(job_id, timeout)` and a result tool that returns artifact paths/URLs.
3. Risk labels (read / mutate / admin) for documentation only. **Owner decision (2026-11-23): `comfyui_restart` and `comfyui_node_provision` are enabled by default.**
4. Consolidate tools so the common flow is `list_resources → compose → generate → wait/result`.
5. Add `list_workers` / `worker_status` (ready for Phase 3).
6. A real end-to-end MCP smoke script (generate one image on local ComfyUI and retrieve it).
- **Exit**: an agent goes from nothing to a retrieved image and one revision without human help.

### Phase 2 — Prompt-combination dashboard
1. A "recipe": prompt combination + workflow template + model/LoRA + sampler parameters, saved and loaded together (unified with style presets).
2. Choosing a template in the Workbench renders its adjustable parameters from `.meta.json`.
3. Progress, errors and result thumbnails on the same page; one-click "save result as recipe".
4. MCP `generate_from_recipe`.
- **Exit**: a combination built in the UI is used by an agent through MCP to generate an image.

### Phase 3 — Same-LAN Windows worker
1. Security first: remove or disable open PowerShell control; shared token between Backend and Worker.
2. Same-project guarantee: the Worker is a checkout of this repository and reports git commit, workflow hashes, custom-node list and model list at startup; the Backend refuses dispatch on mismatch with a clear hint.
3. Durable, concurrent queue: persist jobs at submission, survive Backend restarts, and run one job per available target in parallel (see Known limitations in `docs/ARCHITECTURE.md`).
4. Worker registry: multiple workers (manual config plus optional discovery), heartbeat, capabilities, queue length.
5. Scheduler: `execution_target=auto` chooses by capability and load; failures are not silently resubmitted.
6. Results return to the Backend Gallery with provenance (which worker).
7. Replace the updater with "git pull + restart"; delete retired code.
- **Exit**: a second Windows machine on the LAN produces an image that is traceable in the Gallery.

### Phase 4 — LoRA training
1. Using the merged code, run one real training on a small dataset and one base model (SDXL or Anima).
2. Smoke tracking: training completion → smoke image → linked to the training job.
3. Report registration success/failure separately from training completion.
4. Dispatch training to a worker (reusing the Phase 3 registry and version handshake).
5. Select the new LoRA in a dashboard recipe.
- **Exit**: one real training → clearly named model → used in a recipe → smoke image retrievable.
