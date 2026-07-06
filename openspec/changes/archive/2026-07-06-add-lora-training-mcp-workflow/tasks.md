## 1. Data Model and Compatibility

- [x] 1.1 Add a focused regression test proving `POST /api/lora-train/start` no longer reads a missing `generate_after` field from `TrainStartRequest`.
- [x] 1.2 Fix the stale `generate_after` reference in `backend/app/api/lora_train.py` while preserving existing training request fields.
- [x] 1.3 Add a durable `LoraTrainingJob` database model with job id, folder, status, stage, progress, epoch fields, log path, output path, registered LoRA name, error fields, dataset hash, params JSON, smoke-test fields, and timestamps.
- [x] 1.4 Add database initialization or migration coverage for the new LoRA training job table.
- [x] 1.5 Add backend Pydantic schemas for dataset list/inspect/prepare/validate, job start/status/logs/cancel, registration, and smoke-test responses.
- [x] 1.6 Add settings for LoRA training logs and ComfyUI LoRA registration target, using safe defaults or clear validation errors when unset.

## 2. Dataset Preparation and Validation

- [x] 2.1 Create a backend dataset service that safely resolves folders under `lora_train_dir`, enumerates trainable image/caption pairs, and rejects path traversal.
- [x] 2.2 Implement deterministic dataset hashing from image/caption membership and caption contents.
- [x] 2.3 Implement trigger-token normalization that sanitizes a requested token, inserts it exactly once at the start of each caption, and removes duplicate token occurrences.
- [x] 2.4 Implement dataset preparation dry-run responses with per-file proposed changes and summary counts.
- [x] 2.5 Implement dataset preparation apply mode with backup manifest creation, caption writes, post-write hash, and restore by backup id.
- [x] 2.6 Integrate optional AI-assisted caption cleanup with deterministic post-filtering and explicit error handling when the provider is not configured.
- [x] 2.7 Implement dataset validation for image/caption counts, missing captions, empty captions, trigger-token consistency, expected hash mismatch, and lock conflicts.
- [x] 2.8 Add per-dataset lock coordination and update watcher caption generation so locked datasets are not overwritten during preparation or training.
- [x] 2.9 Add unit tests for dataset discovery, hash changes, trigger-token normalization, dry-run/apply/restore, validation failures, stale hash conflicts, and lock behavior.

## 3. Backend LoRA Workflow APIs

- [x] 3.1 Add dataset endpoints for list, inspect, prepare, restore, and validate using the dataset service schemas.
- [x] 3.2 Refactor `lora_trainer.enqueue` and worker state so job lifecycle updates are persisted to `LoraTrainingJob` instead of only in module globals.
- [x] 3.3 Write each Kohya subprocess stdout/stderr stream to a per-job log file while updating persistent progress, current epoch, total epochs, status, and stage.
- [x] 3.4 Add job-specific status and logs endpoints that return durable state and bounded log tails by `job_id`.
- [x] 3.5 Add cancellation support for queued and running jobs, including subprocess termination, terminal status persistence, and lock release.
- [x] 3.6 Register successful `.safetensors` outputs into the configured ComfyUI LoRA directory with atomic completion and persistent `registered_lora_name`.
- [x] 3.7 Add smoke-test endpoint that submits generation with the registered LoRA and normalized trigger token, then records generation job/artifact references on the LoRA job.
- [x] 3.8 Keep existing aggregate training status behavior available for current frontend callers while adding the new job-specific workflow.
- [x] 3.9 Add backend API tests for start/status/logs/cancel, persisted terminal jobs, registration success/failure, smoke-test success/failure, and compatibility status.

## 4. MCP Tool Contract

- [x] 4.1 Add a shared MCP response helper that maps backend success and error responses into structured JSON with `ok`, `tool`, payload fields, and `error`.
- [x] 4.2 Implement `lora_dataset_list`, `lora_dataset_inspect`, `lora_dataset_prepare`, and `lora_dataset_validate` MCP tools against the backend dataset APIs.
- [x] 4.3 Implement `lora_train_start`, `lora_train_job_status`, `lora_train_logs`, `lora_train_cancel`, and `lora_train_smoke_test` MCP tools with structured JSON results.
- [x] 4.4 Preserve or clearly replace the existing LoRA MCP helper behavior so callers no longer need to parse human-readable strings.
- [x] 4.5 Add MCP tests for successful results, backend validation errors, stale hash conflicts, not-found jobs, log retrieval errors, cancellation, and smoke-test preconditions.

## 5. Verification and Documentation

- [x] 5.1 Run backend and MCP tests for LoRA dataset/training workflow with `pytest backend/tests/ mcp-server/tests/ -x -q`.
- [x] 5.2 Add or update setup/API documentation for new LoRA dataset workflow endpoints, ComfyUI LoRA directory configuration, and MCP tool payloads.
- [x] 5.3 Update `docs/PROGRESS.md` after implementation is complete, per project instructions.
- [x] 5.4 Verify the locally implementable LoRA workflow path and split the external Kohya runtime happy path into follow-up OpenSpec `install-verify-kohya-sd-scripts-runtime`. *(Completed 2026-07-06 without faking a training completion. Rechecked `.env`: `SD_SCRIPTS_PATH=./sd-scripts` resolves to `/Users/tf00185088/Desktop/ai-drawing/sd-scripts`; `train_network.py`, `sdxl_train_network.py`, and `finetune/tag_images_by_wd14_tagger.py` are absent, and repo-local search found no Kohya train/tagger entrypoints. Fresh in-process backend smoke with a temporary 2-image dataset completed list -> inspect -> prepare dry-run -> prepare apply -> validate. The start step returned structured 400 `sd_scripts_path_missing` before queueing or persisting a job (`persistent_job_count=0`, aggregate training status `idle`). Full real start/poll/logs/register/smoke requires installing/configuring external Kohya sd-scripts and is tracked by `openspec/changes/install-verify-kohya-sd-scripts-runtime/`.)*
