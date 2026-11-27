# Task specification

## Task
Add `wait_for_job` so an agent can wait for a job and get its result in one call.

## Purpose
Agents now poll `job_status` themselves and look up results separately. Phase 1's exit needs a simple generate → result flow.

## Outcome
An agent calls `wait_for_job(job_id, timeout_seconds)` and receives the final Backend status plus truthful existing result references, or a timeout result it can safely call again. Incomplete generation locators produce an actionable error without changing a completed job into a failed job.

## Scope
Included: generation jobs and LoRA training jobs; a bounded overall timeout, including Backend request and artifact-enrichment durations, below the established MCP client tool-call limit (find and record it first; if unknown, use the 50-second fallback and label the client limit unverified); every existing canonical media artifact listed with its real `artifact_id` and kind (image/video). Supported Gallery locators supply a host file path under `MCP_GALLERY_DIR` and Backend Gallery URL. Preserve legacy image-only results separately by their real image ID/path/URL with no fabricated artifact ID; unavailable or unsafe generation locators follow the [wait-result contract](../../decisions/mcp.md#wait-results-and-media-locators). Training completion reports its existing output/status truthfully and returns an empty media-artifact list when none exists; preserve real smoke-generation references, including nullable artifact IDs and separate image IDs, without inventing a Gallery artifact or starting training.
Excluded: Backend changes beyond reading job and artifact state; push notifications; record backfill or file migration/copying to manufacture locators.
Open questions: none; clarification 1 settles kickoff K3-1 and awaits fresh independent CLEAR.
Read first: [docs/ARCHITECTURE.md](../../ARCHITECTURE.md) (queue completion rules), [docs/mcp.md](../../mcp.md), the accepted [p1-01/02 result](../p1-01-mcp-response-envelope/acceptance.md), [intent map](../p1-02-mcp-tool-consolidation/manifest.md) and [wait-result contract](../../decisions/mcp.md#wait-results-and-media-locators).

## Done when
- [ ] For a completed generation with supported Gallery locators, `wait_for_job` returns `ok: true`, status `completed`, every canonical media artifact's actual ID, kind, host path and Backend URL, and any legacy image-only result under its separate image namespace. An unavailable/unsafe locator returns `ok: false`, `error.code: artifact_locator_unavailable`, the unchanged completed Backend status/job ID, all known result identities and a recovery hint; it never invents or substitutes a locator or artifact ID. Check: registered MCP tests with a mocked Backend for mixed image/video, nested/Unicode paths, legacy image-only, missing/outside-root and unsafe locator cases. Evidence: test output.
- [ ] For a job that fails, it returns `ok: false` with the Backend's failure reason in `error`. Check: test. Evidence: test output.
- [ ] When the timeout passes first, it returns a `timeout` result with the current or last-known status (explicitly unknown if no read completed) and a hint to call again, without cancellation/resubmission; requests above the maximum are clamped within one overall call budget covering reads, lookup, enrichment and sleep. The maximum is below a sourced client limit, or uses the explicit 50-second fallback with that limit marked unverified. Check: tests + manual. Evidence: timeout/clamping/slow-request tests and the measured/configured limit with source, or the stated unknown and fallback.
- [ ] It works for LoRA training IDs as well as generation IDs, reports training output/status without fabricated media artifacts and preserves existing independent smoke-generation references/diagnostics, including null canonical artifact IDs and separate real image IDs. Training completion does not wait for or submit its smoke job. Check: tests against mocked existing Backend shapes; no real training run required. Evidence: test output.
- [ ] `docs/mcp.md` documents the tool, its timeout limits, the result/error shapes and supported host-path/URL/legacy-ID semantics. Check: manual. Evidence: doc link.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: real-run behavior is verified in p1-05; constructing a locator does not prove file availability or remote retrieval.
