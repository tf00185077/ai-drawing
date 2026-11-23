# Architecture

## Overview

```
 Agent (MCP client)        Browser              Discord
        │                     │                    │
        ▼                     ▼                    ▼
   MCP server  ───────►  Frontend (React)    Discord bot
   (stdio)     │              │                    │
        │      │              ▼                    │
        │      └──────►  Backend (FastAPI) ◄───────┘
        │                     │  ▲
        │   direct ops        │  │ SQLite + data/gallery
        ▼                     ▼  │
   Local ComfyUI ◄──── queue ─┴──┴──► Windows worker ──► remote ComfyUI
                              │
                              └──► sd-scripts subprocess (LoRA training)
```

Docker Compose runs the Backend (host port 8001 → container 8000) and the Frontend (5173 → 80). ComfyUI, the MCP server, the Discord bot and workers run outside Compose.

## Components

### Backend — `backend/app/`

FastAPI app started in `main.py`. On startup it initializes the database and starts four background services:

| Service | Source | Purpose |
|---|---|---|
| Generation queue | `core/queue.py` | Runs generation jobs against ComfyUI |
| ComfyUI history watcher | `services/comfyui_history_watcher.py` | Imports images made directly in the ComfyUI web UI into the Gallery |
| Dataset folder watcher | `services/watcher.py` | Auto-captions new training images with WD Tagger |
| LoRA trainer worker | `services/lora_trainer.py` | Runs training jobs |

Routers (`api/`): `generate`, `gallery`, `prompt_library`, `prompt_templates`, `style_presets`, `workflow_catalog`, `civitai_easy`, `civitai_recipes`, `lora_train`, `lora_docs`, `comfyui`, `workers`, `system`, `analytics`.

Storage:
- SQLite at `backend/auto_draw.db` by default (`config.py`). Main tables: `generated_images`, `generated_artifacts`, `generation_batches`, `lora_training_jobs`, `downloaded_resources`, plus Civitai alias/variation tables (`db/models.py`).
- Image and video files under `data/gallery`.
- Prompt library as versioned files in `prompt_library/`.

### Generation queue — `core/queue.py`

- In-memory: pending list, one running job at a time, failed-job cache. A loop polls every 2 s to submit the next job and check the running one.
- Jobs are written to SQLite and the Gallery only when they finish.
- Each job has an `execution_target`: `local` uses `core/comfyui.py`; `worker` uses `services/nvidia_worker.py`. A failed worker job is not retried locally.
- The queue tracks its own ComfyUI prompt IDs so the history watcher skips them.

### Workflows

- Templates: `backend/workflows/*.json` (ComfyUI API format) with `*.meta.json` describing form fields and capabilities. Served by `GET /api/workflow-catalog/generation-forms`.
- `core/workflow.py` and related modules fill templates with prompts, models, LoRAs, sampler settings and seeds.
- Style presets (`style_presets/agent/`): recipes plus saved graphs per preset/profile.
- Custom workflows can be submitted as full graphs (`/api/generate/custom`).

### MCP server — `mcp-server/`

Python MCP SDK over stdio. Tools are listed in `mcp_server/tool_catalog.py`. Most tools call the Backend (`MCP_BACKEND_API_URL`). Three call ComfyUI directly (`MCP_COMFYUI_API_URL`): `free_comfyui_memory`, `comfyui_node_provision`, `comfyui_restart`. Discord delivery calls the bot's operator endpoint (`MCP_DISCORD_OPERATOR_URL`).

### Frontend — `frontend/`

React + Vite. Routes: `/` (status), `/generate`, `/gallery`, `/prompt-library/workbench`, `/prompt-library/categories`, `/lora-docs`, `/lora-train`. Talks only to the Backend.

### Windows worker — `worker/windows/`

A Python service on a remote Windows host. It proxies that host's ComfyUI (`/prompt`, `/queue`, `/history`, `/view`, `/upload/image`) and exposes PowerShell submit/status/cancel. The Backend reaches it through `NVIDIA_WORKER_URL`, with optional `/24` LAN discovery. Only one worker URL is supported today.

### LoRA training

`services/lora_trainer.py` runs kohya sd-scripts as a subprocess of the Backend's environment (SD1.5, SDXL, Anima). Recipes are compiled by `lora_training_recipe.py`; datasets are handled by `lora_dataset*.py`. Training always runs on the Backend host.

### Discord bot — `discord-bot/`

Slash commands that call the Backend directly, plus an operator HTTP endpoint (`/operator/v1/deliver-result`) used by MCP to post finished results to allowlisted channels.

## Known limitations (to optimize)

| Limitation | Effect | Planned in |
|---|---|---|
| The generation queue lives only in memory | No durable record of pending/running jobs | Phase 3 |
| Only one job runs at a time | Multiple workers cannot run in parallel | Phase 3 |
| Jobs are persisted only on completion | A Backend restart loses pending and running jobs | Phase 3 |

## Main flows

**Agent generates an image**
1. Agent calls `list_available_resources`, then `generate_image`.
2. Backend validates, builds the graph and enqueues; returns a job ID.
3. Queue submits to local ComfyUI or the worker, then polls for completion.
4. Outputs are saved to `data/gallery` and recorded in SQLite.
5. Agent polls `get_generation_status`, then reads the result with `get_gallery_image` / `get_gallery_artifact`.

**User composes prompts in the dashboard**
1. Workbench reads fragments and combinations from the Prompt Library API.
2. User orders and weights fragments, saves a combination.
3. `GenerationPanel` picks a generation form and submits to `/api/generate/`.

**LoRA training**
1. Dataset folder is prepared; the watcher captions new images.
2. `lora_training_decision_preflight` checks the dataset and recipe.
3. `lora_train_start` launches sd-scripts; status and logs are read by job ID.
4. Output is registered as a LoRA; `lora_train_smoke_test` submits a test generation.

## Configuration

| Setting | Where |
|---|---|
| Backend settings (ComfyUI URL, paths, worker, DB) | `.env` → `backend/app/config.py` |
| MCP server | `MCP_*` process environment (not `.env`) |
| ComfyUI mounts | `.ai-drawing/compose.local.yaml` (generated by the launcher) |
| Discord bot | `discord-bot/.env` |
