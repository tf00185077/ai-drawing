## 1. Structured execution-error helper

- [x] 1.1 Add a helper (in `backend/app/core/comfyui.py`) that maps a ComfyUI history `status` (its `execution_error` message) to `[{node_id, class_type, reason}]`, mirroring `structure_node_errors`
- [x] 1.2 Add a helper to read terminal info from a history entry: `status_str`, whether outputs exist, and the structured execution error

## 2. Rewrite completion handling

- [x] 2.1 Add `completion_polls` to `_Job.__slots__` (default 0) and a `MAX_COMPLETION_POLLS` constant
- [x] 2.2 In `_check_running_complete`, treat the prompt as still in progress while in ComfyUI `queue_pending` OR `queue_running`
- [x] 2.3 After the prompt leaves the queue, branch on the history entry: absent → bounded wait (increment `completion_polls`, keep `_running`; at the cap → `_record_failure` no-result and release slot)
- [x] 2.4 `status_str == "error"` → release slot + `_record_failure` with structured execution error
- [x] 2.5 success + outputs → existing save/record path; wrap fetch + `recording.save` so an exception → `_record_failure` (no silent drop)
- [x] 2.6 success + no outputs → release slot + `_record_failure` ("no output images")

## 3. Tests

- [x] 3.1 Pending-in-ComfyUI: prompt only in `queue_pending` → job stays `running`, no terminal state
- [x] 3.2 History lag then success: first check no history (stays running), next check success+outputs → `completed`
- [x] 3.3 History timeout: history never appears within the cap → `failed` (no-result) and `_running` released
- [x] 3.4 Execution error: `status_str == "error"` → `failed` with structured `{node_id, class_type, reason}`
- [x] 3.5 Success no outputs → `failed`
- [x] 3.6 `recording.save` raises → `failed`, queryable via `get_job_status`
- [x] 3.7 Run backend suite; fix regressions

## 4. Docs

- [x] 4.1 Update `docs/PROGRESS.md`; note this supersedes the open concern in `docs/backend-generate-queue-head-blocking-2026-06-16.md`
