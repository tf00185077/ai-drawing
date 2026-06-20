## Why

The queue worker's completion check (`_check_running_complete`) concludes a job is done the moment its `prompt_id` leaves ComfyUI's `queue_running`, then immediately reads history and gives up silently if no output images are present. This loses jobs in several real situations: ComfyUI history lags briefly after completion (race), the prompt is still in ComfyUI's `queue_pending` (not yet started), the run failed during execution (`status_str == "error"`), or `recording.save` raises. In all of these the job is neither recorded as `completed` (no DB row) nor marked `failed` — it silently vanishes and `get_generation_status` returns not-found. This makes generation unreliable and leaves no diagnostics, and it undermines any feature that gates on a trustworthy terminal state (e.g. template backfill).

## What Changes

- Treat a job as still processing while its `prompt_id` is in ComfyUI's `queue_pending` **or** `queue_running` (not just `queue_running`).
- After the prompt leaves ComfyUI's queue, consult the history entry's `status` instead of inferring from image presence alone:
  - **History not yet present** (post-completion lag): keep the job `running` and re-check on the next tick, bounded by a timeout; only after the timeout mark it `failed` so the worker is never stuck.
  - **`status_str == "error"`**: mark the job `failed` and surface ComfyUI's `execution_error` as a structured `{node_id, class_type, reason}` (same shape as submission `node_errors`).
  - **Success with outputs**: record `completed` as today; if `recording.save` raises, mark the job `failed` instead of losing it.
  - **Success with no outputs**: mark the job `failed` with a clear reason.
- Net guarantee: **every terminal job ends in exactly one of `completed` (DB) or `failed` (with a reason) — never a silent disappearance.**

## Capabilities

### New Capabilities
- `queue-job-completion`: Reliable terminal-state handling for generation jobs — distinguishing still-processing (ComfyUI running/pending or history lag) from success (recorded) and failure (execution error, no output, or recording error), with a bounded wait so the worker never stalls and never silently drops a job. This also covers surfacing ComfyUI **execution-time** `execution_error` as a structured failure (complementing the submission-time `node_errors` already handled in add-agent-workflow-authoring).

### Modified Capabilities
<!-- None: execution-error surfacing is captured within the new queue-job-completion capability rather than as a delta to custom-workflow-generation. -->

## Impact

- Backend core: `backend/app/core/queue.py` (`_check_running_complete` rewritten; `_Job` gains a completion-poll counter; reuse `structure_node_errors`-style mapping for `execution_error`). Possibly a small helper in `backend/app/core/comfyui.py` to extract history execution errors.
- Behavior: jobs that previously vanished now appear as `failed` via `get_generation_status` / `GET /api/generate/job/{id}` (already wired in #4). No API shape change.
- Tests: history-lag retry then success; execution-error → failed with structured reason; no-output → failed; recording exception → failed; pending-in-ComfyUI not treated as done.
- Docs: `docs/PROGRESS.md`; supersedes the open concern in `docs/backend-generate-queue-head-blocking-2026-06-16.md`.
- Out of scope: cross-process/multi-worker shared queue state (still in-memory); retrying transient failures (failures remain terminal by design).
