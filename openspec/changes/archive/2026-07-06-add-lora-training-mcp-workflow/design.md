## Context

The project already has the pieces for LoRA training, but they are not yet one reliable agent workflow.

- `backend/app/services/watcher.py` watches training folders and runs WD Tagger to create same-name `.txt` captions.
- `backend/app/api/lora_docs.py` can upload training images, edit captions, add a prefix, download a dataset zip, and call an LLM caption endpoint for one image.
- `backend/app/services/caption_filter.py` contains deterministic tag cleanup rules, but there is no dataset-wide preflight workflow around it.
- `backend/app/api/lora_train.py` exposes start/status routes, but it still references `body.generate_after` even though `TrainStartRequest` and `lora_trainer.enqueue()` no longer define that parameter.
- `backend/app/services/lora_trainer.py` keeps queue/running/last-result state in process memory, parses subprocess output for coarse progress, and writes success/failure only to transient globals.
- `backend/app/db/models.py` has generated image/artifact records, but no durable LoRA training job table.
- `mcp-server/mcp_server/tools/lora_train.py` currently exposes thin string-returning helpers instead of complete structured workflow tools.

The new behavior should preserve the existing watcher and caption editing flow while adding an agent-first path that can inspect, prepare, validate, start, track, cancel, register, and smoke-test LoRA training.

## Goals / Non-Goals

**Goals:**

- Make the backend the workflow owner for LoRA dataset preparation and training jobs.
- Add deterministic trigger-token normalization so every caption gets the same stable trigger token exactly once.
- Add AI-assisted caption cleanup as an optional dataset preparation step with dry-run, apply, backup, and restore.
- Add dataset validation before training and reject stale/racing starts with dataset locks/hashes.
- Persist LoRA training jobs in the database with status, stage, progress, epochs, logs, output path, registered LoRA name, errors, dataset hash, and timestamps.
- Capture subprocess logs to per-job log files and expose bounded tails through API and MCP.
- Register successful LoRA outputs into the ComfyUI LoRA directory and provide a smoke test that uses the registered LoRA through the existing generation path.
- Expose MCP tools with structured JSON results so agents can branch on `ok`, `status`, `stage`, `job_id`, and `error`.
- Fix the stale `generate_after` reference while keeping existing frontend/API training starts working.

**Non-Goals:**

- Replacing Kohya sd-scripts or changing the core training engine.
- Replacing WD Tagger or the existing watcher-generated caption flow.
- Building a new frontend UI beyond any schema/API compatibility needed for existing screens.
- Introducing external workflow products such as n8n or Zapier.
- Training or hosting a new caption model inside this change.

## Decisions

### Backend-owned durable workflow

The backend SHALL own dataset preparation, validation, training lifecycle, output registration, and smoke testing. MCP tools SHALL be clients of backend APIs, not direct filesystem or subprocess controllers.

Alternatives considered:

- Thin MCP wrapper around existing APIs: simple, but keeps progress in memory and leaves agents to coordinate races.
- MCP directly edits captions and launches subprocesses: powerful, but duplicates backend rules and bypasses existing API/security boundaries.
- Backend-owned workflow: more implementation work, but gives one durable source of truth and lets frontend and MCP share the same behavior.

### Persistent job model

Add a `LoraTrainingJob` database model. The implementation should store at least:

- `job_id`
- `folder`
- `status`
- `stage`
- `progress`
- `current_epoch`
- `total_epochs`
- `log_path`
- `output_path`
- `registered_lora_name`
- `error`
- `dataset_hash`
- `params_json`
- `smoke_test_job_id`
- `created_at`
- `started_at`
- `completed_at`
- `cancel_requested_at`

Use clear status values such as `queued`, `running`, `completed`, `failed`, and `cancelled`. Use `stage` for finer workflow position, such as `preflight`, `training`, `registering`, and `smoke_testing`.

The in-memory queue can remain as an execution detail, but all externally observable job state must be written to the database. Status APIs should be able to answer for a specific `job_id` after process restart.

### Dataset service with locks and hashes

Introduce a backend dataset service that resolves folders under `lora_train_dir`, enumerates images/captions, computes a dataset hash, coordinates per-folder locks, and performs preparation/validation.

The hash should be deterministic from the trainable image set and caption contents. It should change when an image/caption is added, removed, renamed, or edited. Dataset operations that write captions or start training should either hold the dataset lock or verify that the hash has not changed between validation and start.

The watcher flow should remain active, but when a dataset is locked for preparation or training, watcher-triggered caption generation must not overwrite in-flight caption edits. It can skip and retry after debounce, or use the same dataset lock with a short timeout.

### Trigger-token and caption preparation

Dataset preparation should have two layers:

1. Deterministic normalization:
   - Sanitize the requested trigger token into a stable token accepted by caption text and Kohya `class_tokens`.
   - Add the trigger token exactly once at the beginning of every caption.
   - Remove duplicate occurrences of the trigger token elsewhere in the caption.
   - Keep captions parseable as comma-separated tags.
2. Optional AI-assisted cleanup:
   - Use the existing LLM caption provider pattern where configured.
   - Apply deterministic post-filtering after AI output.
   - Never apply AI edits without dry-run preview or explicit apply.

`dry_run` must produce a diff/summary without writing files. `apply` must create a backup manifest and backup files before changing captions. `restore` must restore a named backup.

### Validation before training

Training start should require validation success. Validation should report structured errors and warnings for:

- Dataset folder missing or outside `lora_train_dir`.
- Fewer trainable image/caption pairs than the configured minimum.
- Image missing a matching `.txt` caption.
- Caption missing the normalized trigger token.
- Empty or unparsable caption.
- Dataset hash mismatch when the caller supplies an expected hash.
- Dataset currently locked by another operation.

The validation result should include the normalized trigger token, image/caption counts, dataset hash, and blocking issues.

### Training execution and logs

The trainer should continue using Kohya sd-scripts via subprocess. The worker should write stdout/stderr to a per-job log file while updating the database from parsed progress lines. Log tail endpoints should return bounded lines or bytes, with an indicator when output was truncated.

Progress parsing may remain best effort. When epoch or step parsing fails, the job should still expose `stage`, `status`, log tail, and elapsed timestamps.

### Output registration and smoke test

After successful training, the backend should find the output `.safetensors`, copy or link it into the configured ComfyUI LoRA directory using an atomic temp-file-then-rename flow, and record `registered_lora_name`.

The smoke test should be callable after registration. It should submit a minimal generation request using the registered LoRA and the stable trigger token, then return the generation job/image reference through the existing generation status/recording path. Smoke test failure should be visible on the LoRA job but should not erase the successful training output.

### MCP structured contract

MCP tools should return JSON-serializable dictionaries, not human-readable status strings. Every result should include:

- `ok: bool`
- `tool: str`
- success payload fields appropriate for the tool
- `error: {code, message, details?}` on failure

This lets agents decide whether to prepare, validate, start, poll, cancel, inspect logs, or run a smoke test without scraping text.

### API compatibility and blocker fix

The implementation must remove or replace the stale `generate_after` reference in `backend/app/api/lora_train.py`. Existing request fields in `TrainStartRequest` should keep working. Any new automatic smoke-test behavior should be modeled with explicit new request fields or a separate endpoint, not with the removed `generate_after` shape.

## Risks / Trade-offs

- AI cleanup can introduce unwanted captions -> Require dry-run/apply separation, backup/restore, deterministic post-filtering, and structured change summaries.
- Dataset locks can delay watcher caption generation -> Use per-folder locks and bounded retry/debounce behavior rather than a global lock.
- Dataset hashes can reject legitimate changes made between validation and start -> Return the new hash and validation issues so agents can re-run validation and start again.
- Kohya progress output is not fully standardized -> Persist logs and expose stage/log tail even when numeric progress cannot be parsed.
- Registering LoRA files can fail because ComfyUI paths differ per install -> Add explicit configuration and report registration errors separately from training errors.
- Smoke test may fail due to ComfyUI model availability, queue state, or generation errors -> Record smoke-test status/error without losing the registered LoRA.

## Migration Plan

1. Add database schema support for durable LoRA training jobs.
2. Add backend dataset service and preparation/validation APIs without changing watcher defaults.
3. Refactor the trainer to persist job lifecycle state and logs while keeping existing queue behavior.
4. Add registration and smoke-test APIs.
5. Replace MCP string helpers with structured workflow tools while preserving function names where useful.
6. Add tests for dataset preparation, validation, stale hash/lock behavior, job status/logs/cancel, registration, smoke-test orchestration, and MCP JSON contracts.

Rollback is to stop using the new MCP tools/endpoints and keep the existing upload/caption/training paths. The new job table can remain unused if the change is disabled.

## Open Questions

- What exact config name should identify the ComfyUI LoRA directory? A likely implementation is `comfyui_lora_dir`, with fallback documentation if unset.
- Should registration use copy by default, or allow symlink/hardlink mode for large model files? Copy is the safer default across filesystems.
- Should `lora_train_start` optionally run smoke test automatically, or should agents always call `lora_train_smoke_test` after completion? The separate tool is safer and keeps training success independent from generation validation.
