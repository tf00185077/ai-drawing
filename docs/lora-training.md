# LoRA training

The Backend prepares datasets and trains LoRA models with kohya sd-scripts, then registers the result and can run a smoke-test generation.

## Status

**Built:** dataset inspection, curation and auto-captioning; preflight; recipe compiler; sd-scripts runner for SD1.5, SDXL and Anima; required readable `output_name` with automatic serial numbers; a separate folder per run with an effective-parameter record; registration status reported separately from training; smoke-test submission with reconciliation and image validation (code only: its tests were removed on 2026-11-24 and are rewritten in Phase 4); status, logs, cancel; UI page and MCP tools.

**Verified in a real run:** trainer Python imports on the Backend host. No real training run has completed.

**Gaps:**
- No real end-to-end run: train → register → select → smoke image.
- Training cannot run on a worker.

Overall project state: [CURRENT.md](CURRENT.md).

## Supported models

| Family | sd-scripts entry point |
|---|---|
| SD 1.5 | `train_network.py` |
| SDXL / Pony | `sdxl_train_network.py` |
| Anima | `anima_train_network.py` (requires a VAE) |

Training runs as a subprocess of the Backend's own environment, on the Backend host. It cannot run on a worker yet.

## Flow

1. **Prepare a dataset** — put images in a folder under the training directory. The dataset watcher auto-captions new images with WD Tagger. Captions can be edited in the UI (`/lora-docs`) or generated with an LLM (`caption_image`).
2. **Inspect** — `lora_dataset_list`, `lora_dataset_inspect`; validation, caption assessment and curation endpoints check image and caption quality.
3. **Preflight** — `lora_training_decision_preflight` checks the dataset, base model and recipe and returns the effective parameters.
4. **Start** — `lora_train_start` with a readable `output_name`. Duplicate names get an automatic serial number.
5. **Monitor** — `lora_train_job_status`, `lora_train_logs`, `lora_train_cancel`.
6. **Result** — each run has its own folder with the model and a record of the effective parameters. Registration status is reported separately from training status.
7. **Smoke test** — `lora_train_smoke_test` submits a generation with the new LoRA; the result is tracked and the image is validated.

## Rules

Datasets:
- A dataset folder is locked while it is prepared, curated or trained, so the caption watcher and training never touch it at the same time.
- Preparation and curation preview their changes first (dry run), back up before applying, and can be restored. Manually edited captions are kept.
- Dataset profiles and folder size never start training on their own; training always needs an explicit start.

Preflight and recipe:
- Preflight is deterministic and runs nothing. It suggests parameters; the caller decides what to submit.
- A training recipe is a versioned object. Every effective parameter is filled in before the job is queued, and the full recipe is stored with the job.
- A random seed is drawn once and stored, so the run can be repeated.
- Text-encoder training is off unless requested.
- The recipe has a hash of its semantic content, used to match approvals and detect changes.
- The base checkpoint must exist before a job is created; model paths are searched across the configured model folders.
- MCP passes the Backend's field-level validation errors back unchanged.

## UI

| Route | Purpose |
|---|---|
| `/lora-docs` | Upload images, edit captions, batch prefix, download dataset ZIP |
| `/lora-train` | Configure, start and monitor training |

## API

Router `backend/app/api/lora_train.py`, prefix `/api/lora-train`:

| Endpoint | Purpose |
|---|---|
| `GET /config`, `GET /folders`, `GET /status` | Configuration and overview |
| `GET /datasets`, `GET /datasets/{folder}`, `GET /datasets/{folder}/agent-inspect` | Datasets |
| `POST /datasets/prepare`, `/restore`, `/validate`, `/caption-assessment`, `/curate`, `/training-decision-preflight` | Dataset preparation and preflight |
| `GET/PUT /datasets/{folder}/metadata`, `POST .../metadata/validate` | Dataset metadata |
| `POST /start` | Start a run |
| `GET /jobs/{id}`, `GET /jobs/{id}/logs`, `POST /jobs/{id}/cancel` | Job control |
| `POST /jobs/{id}/smoke-test` | Smoke generation |

Router `backend/app/api/lora_docs.py` handles dataset files and captions (`/files`, `/upload`, `/caption/...`, `/batch-prefix`, `/download-zip`, `/caption-llm/...`).

## Configuration

In `.env` / `backend/app/config.py`:

| Setting | Purpose |
|---|---|
| `SD_SCRIPTS_PATH` | Path to kohya sd-scripts |
| `SD_SCRIPTS_PYTHON` | Python with sd-scripts dependencies |
| `LORA_TRAIN_DIR`, `LORA_TRAIN_LOGS_DIR` | Datasets/runs and logs |
| `LORA_DEFAULT_CHECKPOINT`, `LORA_CHECKPOINT_DIRS` | Base model and where to find it |
| `LORA_MODEL_FAMILY` | `sd15`, `sdxl` or `anima` |
| `LORA_ANIMA_VAE` | VAE for Anima |
| `LORA_RESOLUTION`, `LORA_BATCH_SIZE`, `LORA_LEARNING_RATE`, `LORA_NETWORK_DIM`, `LORA_NETWORK_ALPHA`, `LORA_NUM_REPEATS`, `LORA_MIXED_PRECISION`, `LORA_SAVE_EVERY_N_EPOCHS` | Default training parameters |
| `WD_TAG_LIMIT`, `WD_TRIGGER_WORD`, `WATCH_DIRS` | Auto-captioning |

`setup`/`reconfigure` drop these keys from `.env`; re-add them afterwards.

## Source

`backend/app/services/lora_trainer.py` (runner, registration, smoke), `lora_training_recipe.py` (recipe compiler), `lora_training_decision.py` (preflight), `lora_dataset*.py` (datasets), `watcher.py` and `wd_tagger.py` (captioning), `mcp-server/mcp_server/tools/lora_train.py`.
