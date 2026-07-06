## Why

LoRA training is currently split between watcher-generated captions, a backend training API, and thin MCP helpers, but agents cannot run the full workflow safely because dataset cleanup, validation, durable job progress, LoRA registration, and smoke testing are not modeled as one trackable operation. The current `/api/lora-train/start` path also references `generate_after` even though the schema and trainer no longer define it, which blocks reliable training starts.

## What Changes

- Add a backend-managed LoRA training workflow that covers dataset inspection, deterministic trigger-token normalization, AI-assisted caption cleanup, validation, training start, durable per-job tracking, cancellation, output registration, and smoke testing.
- Add dry-run/apply/backup/restore semantics for dataset preparation so agents can preview and recover caption rewrites before training.
- Add persistent LoRA training job records with `job_id`, `status`, `stage`, `progress`, epoch fields, log path/tail, output path, registered LoRA name, errors, dataset hash, and timestamps.
- Add dataset locks and hashes so watcher/caption writes, dataset preparation, validation, and training do not race each other.
- Add MCP tools with structured JSON responses for listing, inspecting, preparing, validating, starting, tracking, logging, cancelling, and smoke-testing LoRA training jobs.
- Register successful LoRA outputs into the ComfyUI LoRA directory and provide a generation smoke test that records the result through the existing generation/recording path.
- Fix the existing `generate_after` blocker in the LoRA training API by removing or replacing the stale reference in the implementation plan.

## Capabilities

### New Capabilities

- `lora-training-workflow`: Backend dataset preparation, validation, durable training job lifecycle, output registration, cancellation, logs, and smoke testing.
- `lora-training-mcp-tools`: Agent-facing MCP tools and structured JSON contract for the complete LoRA training workflow.

### Modified Capabilities

- None.

## Impact

- Affected backend modules: `backend/app/api/lora_train.py`, `backend/app/schemas/lora_train.py`, `backend/app/services/lora_trainer.py`, `backend/app/services/watcher.py`, `backend/app/services/caption_filter.py`, `backend/app/api/lora_docs.py`, `backend/app/db/models.py`, database migrations/initialization, and tests.
- Affected MCP modules: `mcp-server/mcp_server/tools/lora_train.py` and MCP tests.
- Affected runtime integrations: Kohya sd-scripts subprocess execution, ComfyUI LoRA model directory, ComfyUI generation smoke test, and existing watcher-generated caption flow.
- No breaking API removals are intended for existing frontend flows; new endpoints and MCP tools should be additive except for fixing the stale `generate_after` reference.
