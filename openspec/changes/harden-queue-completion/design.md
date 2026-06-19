## Context

`_check_running_complete` (backend/app/core/queue.py) runs every ~2s after `_process_pending`. Today it:
1. reads `_running`; returns if none.
2. `comfy.get_queue()` → if `prompt_id` in `queue_running` → return (still running).
3. otherwise clears `_running`, `get_history(prompt_id)`, `get_output_images(...)`; if empty → logs "completed but no output images" and returns; else saves files + `recording.save`.

Failure modes that silently drop the job (no DB row, not in `_failed`, `_running` already cleared → `get_job_status` returns None):
- prompt is in ComfyUI `queue_pending` (not yet started): step 2 misses it → step 3 finds no history → dropped.
- history lag: prompt just finished, history not populated → no images → dropped.
- execution error: `status_str == "error"`, no outputs → dropped (and the actual error is discarded).
- `recording.save` raises → exception bubbles, job dropped.

#4 already added a `_failed` store + `structure_node_errors` for submission-time `ComfyUIError`; this change reuses that machinery for the completion path. The live ComfyUI history shape was confirmed: `entry.status = {status_str: "success"|"error", completed: bool, messages: [...]}`, and `execution_error` messages carry `{node_id, node_type, exception_message, exception_type, ...}`; `entry.outputs` is empty on error.

## Goals / Non-Goals

**Goals:**
- Every terminal job ends as `completed` (DB) or `failed` (reason) — no silent drop.
- Tolerate ComfyUI history lag without losing good jobs, without blocking the worker forever.
- Surface execution-time errors with the same structured `{node_id, class_type, reason}` shape as submission errors.
- Keep the single-job-at-a-time worker model and 2s cadence.

**Non-Goals:**
- Cross-process / multi-worker shared queue state (queue stays in-memory; separate concern).
- Retrying transient ComfyUI failures (terminal by design, consistent with #4).
- Changing API/MCP shapes (failed surfacing already wired through `get_generation_status` in #4).

## Decisions

### Decision 1: "Still processing" = in `queue_pending` OR `queue_running`
Check both ComfyUI queue lists before concluding the prompt has left. Prevents the "pending mistaken for done" drop.

### Decision 2: Decide terminal state from `history[prompt_id].status`, not image presence
- absent → lag → wait (Decision 3).
- `status_str == "error"` → `failed`, structured from `execution_error`.
- success + outputs → `completed` (existing save path).
- success + no outputs → `failed` ("no output images").

*Alternative:* keep inferring from images only — rejected, conflates lag/error/empty.

### Decision 3: Bounded wait for history lag via a per-job poll counter
Add `completion_polls` to `_Job`. When the prompt has left the queue but history is absent, increment and keep `_running`; at `MAX_COMPLETION_POLLS` (≈ 30s / 15 ticks) give up → `failed` ("no result from ComfyUI"). Guarantees forward progress; the slot is always eventually released.

*Alternative:* unbounded wait — rejected, a stuck prompt would block the whole queue forever.

### Decision 4: Reuse the `_failed` store and structured-error mapping from #4
Completion failures call the same `_record_failure(job, error, node_errors)` and a small helper that maps a history `execution_error` to `[{node_id, class_type, reason}]` (mirrors `structure_node_errors`). One terminal-failure representation across submission and execution.

### Decision 5: Guard the save path
Wrap output fetch + `recording.save` so an exception marks the job `failed` (not an unhandled drop). The `_running` slot is released before recording so a slow save never blocks the queue lock.

## Risks / Trade-offs

- **[False "no result" on a very slow run]** → A job whose history is delayed beyond the bound is marked failed though it may later succeed. Mitigate: set the bound generously (≈30s after it already left the queue); the actual lag is typically sub-second. Tunable.
- **[ComfyUI history schema drift]** → Relies on `status.status_str` and `execution_error` fields. Mitigate: defensive `.get(...)` access with a generic fallback reason; verified against the live instance.
- **[Double-processing]** → Releasing `_running` before save must happen exactly once; keep the clear inside the lock and guard on `job_id` identity (as the current code does).

## Migration Plan

Pure behavior change in the worker; no schema or API change. Roll out by replacing `_check_running_complete`. Rollback = revert the function. Jobs in flight are unaffected (state is per-tick).

## Open Questions

- Exact value of `MAX_COMPLETION_POLLS` (default ≈15 ticks / 30s) — revisit if real workloads have longer post-queue history lag.
- Whether to also persist `failed` jobs to the DB (currently in-memory `_failed`, lost on restart). Out of scope here; would pair with the broader cross-process work.
