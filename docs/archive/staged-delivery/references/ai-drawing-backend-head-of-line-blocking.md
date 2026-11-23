# Historical import: backend queue head-of-line blocking

> Historical evidence only. This imported note describes an earlier observation; it is not proof that the current backend has this bug, a current implementation contract, or live operational authority. Revalidate against current code and runtime evidence before drawing conclusions. Cancellation, deletion, interruption, or restart requires separate current authorization.

Source: `~/.hermes/skills/autonomous-ai-agents/openclaw-agent-orchestration/references/ai-drawing-backend-head-of-line-blocking.md` (retired skill reference). Imported 2026-10-01 without changing the original body below.

Navigation: [archive index](../INDEX.md), [project document map](../../../INDEX.md), [supplemental historical submission evidence](backend-queue-submission-evidence-addendum.md).

## Original source body (verbatim)

# ai-drawing backend pending queue head-of-line blocking

Use this note when an OpenClaw / MCP-driven ai-drawing run appears to be "stuck in pending" even though ComfyUI itself is reachable.

## Symptom pattern

Observed pattern:
- `GET /api/generate/queue` shows one or more `queue_pending` jobs for a long time.
- `GET /api/generate/job/<job_id>` stays `queued`.
- ComfyUI `GET /queue` is empty, so the job never reached ComfyUI.
- After manually removing the first pending job, the next pending job immediately transitions to `running` and is submitted to ComfyUI.

This means the queue worker is alive enough to process jobs, but the queue is suffering from **head-of-line blocking**.

## Root cause in backend design

In `backend/app/core/queue.py`:
- `_process_pending()` pops the first pending job and attempts `comfy.submit_prompt(prompt)`.
- On `ComfyUIError` or `FileNotFoundError`, the code does:

```python
_running = None
_pending.insert(0, job)
```

So a bad job is reinserted at the **front** of the queue with no retry cap, no backoff, and no failed/dead-letter state.

Result: one invalid job can starve every later job behind it while the public API still reports only `queued`.

## What this explains

It explains the pattern where users think "the pending queue is frozen" but the real situation is:
- the worker thread is not totally dead,
- the first job is repeatedly failing submission,
- later jobs never get a turn.

## Fast verification path

1. Check backend queue:
   - `GET /api/generate/queue`
2. Check the specific job:
   - `GET /api/generate/job/<job_id>`
3. Check ComfyUI queue:
   - `GET http://127.0.0.1:8188/queue`
4. If backend shows queued jobs but ComfyUI queue is empty, suspect pre-submit failure.
5. If removing the first queued job causes the next one to run immediately, treat that as strong evidence of head-of-line blocking.

## Operational implication

When the user asks to "clear the stuck session/job", do not kill ComfyUI first.
- First remove or cancel the **front pending backend job**.
- Re-check whether the next backend job starts running.
- If it immediately moves to running and gets a ComfyUI `prompt_id`, the blockage was the front job.

## Durable fix direction

For the codebase, the robust fixes are:
- add `retry_count`,
- expose `last_error`,
- cap retries,
- move terminal failures to a failed/dead-letter state instead of reinserting forever at the front,
- optionally avoid using `uvicorn --reload` when validating a memory-backed queue + background thread design.

Do not summarize this as "queue worker broken" unless you have separate evidence that the worker thread never runs at all.