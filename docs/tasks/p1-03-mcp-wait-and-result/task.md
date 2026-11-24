# Task specification

## Task
Add `wait_for_job` so an agent can wait for a job and get its result in one call.

## Purpose
Agents now poll `get_generation_status` themselves and look up results separately. Phase 1's exit needs a simple generate → result flow.

## Outcome
An agent calls `wait_for_job(job_id, timeout_seconds)` and receives the final status plus artifact IDs, file paths and URLs, or a timeout result it can safely call again.

## Scope
Included: generation jobs and LoRA training jobs; a bounded overall timeout, including Backend request durations, below the established MCP client tool-call limit (find and record it first; if unknown, use the 50-second fallback and label the client limit unverified); every real media artifact listed with `artifact_id`, kind (image/video), host file path under `MCP_GALLERY_DIR` and Backend URL. Training completion reports its existing output/status truthfully and returns an empty media-artifact list when none exists; preserve real smoke-generation links without inventing a Gallery artifact or starting training.
Excluded: Backend changes beyond reading job and artifact state; push notifications.
Open questions: none.
Read first: [docs/ARCHITECTURE.md](../../ARCHITECTURE.md) (queue completion rules), [docs/mcp.md](../../mcp.md), the p1-02 result.

## Done when
- [ ] For a job that completes, `wait_for_job` returns `ok: true`, status `completed` and every artifact's ID, kind, path and URL. Check: test with a mocked Backend. Evidence: test output.
- [ ] For a job that fails, it returns `ok: false` with the Backend's failure reason in `error`. Check: test. Evidence: test output.
- [ ] When the timeout passes first, it returns a `timeout` result with the current status and a hint to call again, without cancellation/resubmission; requests above the maximum are clamped within an overall call budget. The maximum is below a sourced client limit, or uses the explicit 50-second fallback with that limit marked unverified. Check: test + manual. Evidence: timeout/clamping tests and the measured/configured limit with source, or the stated unknown and fallback.
- [ ] It works for LoRA training IDs as well as generation IDs, reports training output/status without fabricated media artifacts and preserves real smoke-generation references when present. Check: tests against mocked existing Backend shapes; no real training run required. Evidence: test output.
- [ ] `docs/mcp.md` documents the tool, its timeout limits and the result shape. Check: manual. Evidence: doc link.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: real-run behavior is verified in p1-05.
