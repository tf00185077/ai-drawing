# Task specification

## Task
Add `wait_for_job` so an agent can wait for a job and get its result in one call.

## Purpose
Agents now poll `get_generation_status` themselves and look up results separately. Phase 1's exit needs a simple generate → result flow.

## Outcome
An agent calls `wait_for_job(job_id, timeout_seconds)` and receives the final status plus artifact IDs, file paths and URLs, or a timeout result it can safely call again.

## Scope
Included: generation jobs and LoRA training jobs; a bounded timeout (default and maximum documented); every artifact listed with `artifact_id`, kind (image/video), host file path under `MCP_GALLERY_DIR` and Backend URL.
Excluded: Backend changes beyond reading job and artifact state; push notifications.
Open questions: none.
Read first: [docs/ARCHITECTURE.md](../../ARCHITECTURE.md) (queue completion rules), [docs/mcp.md](../../mcp.md), the p1-02 result.

## Done when
- [ ] For a job that completes, `wait_for_job` returns `ok: true`, status `completed` and every artifact's ID, kind, path and URL. Check: test with a mocked Backend. Evidence: test output.
- [ ] For a job that fails, it returns `ok: false` with the Backend's failure reason in `error`. Check: test. Evidence: test output.
- [ ] When the timeout passes first, it returns a `timeout` result with the current status and does not cancel or resubmit the job. Check: test. Evidence: test output.
- [ ] It works for LoRA training job IDs as well as generation job IDs. Check: test. Evidence: test output.
- [ ] `docs/mcp.md` documents the tool, its timeout limits and the result shape. Check: manual. Evidence: doc link.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: real-run behavior is verified in p1-05.
