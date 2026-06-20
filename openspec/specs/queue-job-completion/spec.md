# queue-job-completion Specification

## Purpose
TBD - created by archiving change harden-queue-completion. Update Purpose after archive.
## Requirements
### Requirement: A job in the ComfyUI queue is still in progress

The worker SHALL treat a running job as still in progress while its `prompt_id` appears in ComfyUI's `queue_pending` or `queue_running`, and SHALL NOT conclude completion until the prompt has left both.

#### Scenario: Prompt still pending in ComfyUI is not concluded done

- **WHEN** a job's `prompt_id` is present in ComfyUI's `queue_pending` (queued behind other work) and absent from `queue_running`
- **THEN** the worker keeps the job in `running` state and does not record completion or failure

### Requirement: Completion is determined from history status, not image presence alone

After a job's `prompt_id` has left ComfyUI's queue, the worker SHALL consult the history entry's status to decide the terminal state, rather than inferring success solely from the presence of output images.

#### Scenario: Successful run with outputs is recorded completed

- **WHEN** the history entry reports `status_str == "success"` and contains output images
- **THEN** the worker saves the images and records a `completed` `GeneratedImage`

#### Scenario: Execution error is recorded as failed with a structured reason

- **WHEN** the history entry reports `status_str == "error"` (an `execution_error` during the run)
- **THEN** the job is marked `failed`
- **AND** the failure exposes the offending node as `{node_id, class_type, reason}` derived from the ComfyUI `execution_error`

#### Scenario: Success with no output images is recorded as failed

- **WHEN** the history entry indicates the run finished but yields no output images
- **THEN** the job is marked `failed` with a clear reason rather than silently dropped

### Requirement: History lag is tolerated with a bounded wait

When a job's `prompt_id` has left the ComfyUI queue but no history entry is available yet, the worker SHALL keep the job in `running` and re-check on a later tick, up to a bounded number of attempts, after which it SHALL mark the job `failed`. The worker SHALL NOT remain blocked on a single job indefinitely.

#### Scenario: History appears after a short delay

- **WHEN** the prompt has left the queue but its history entry is not yet present
- **AND** the history entry becomes available on a subsequent check
- **THEN** the job is resolved to its real terminal state (completed or failed) and is not lost

#### Scenario: History never appears within the bound

- **WHEN** the history entry remains unavailable beyond the allowed number of re-checks
- **THEN** the job is marked `failed` with a no-result reason
- **AND** the running slot is released so subsequent jobs can proceed

### Requirement: Recording failure does not lose the job

If saving outputs or writing the `GeneratedImage` record raises, the worker SHALL mark the job `failed` rather than leaving it without any terminal state.

#### Scenario: Save error surfaces as a failed job

- **WHEN** output fetch or `recording.save` raises while finalizing a successful run
- **THEN** the job is marked `failed` with the error
- **AND** it does not silently disappear from status queries

### Requirement: Every terminal job has a discoverable terminal state

For every job that reaches a terminal outcome, a subsequent status query SHALL return either `completed` (with image references) or `failed` (with a reason) — never not-found due to a silently dropped job.

#### Scenario: Failed run is queryable

- **WHEN** a job fails for any reason (execution error, no output, recording error, history timeout)
- **THEN** querying that job's status returns `failed` with a reason rather than not-found

