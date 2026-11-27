# Task specification

Respecified 2026-11-27 under the owner-directed [verification scope](../../decisions/verification-scope.md).
This replaces the earlier spec (kickoff 1 CLEAR, report `c1d5ffc0`, in Git history),
whose implementation handoff is withdrawn. A fresh kickoff of this spec is required.

## Task

Make each Civitai download a persisted Backend job that an agent can start, read and
follow with `wait_for_job`, and that survives a Backend restart truthfully.

## Purpose

Checkpoints (about 6.5 GB for SDXL) cannot finish inside one MCP call, so the
roadmap's Phase 2 scope requires downloads to be a Backend job the agent follows.
Today acquisition starts daemon threads keyed by resource IDs; nothing records the
operation, so a restart leaves rows stuck in `downloading` with no job to read.

## Outcome

An agent calls the existing acquire tool, gets a `dl_…` job ID plus the resource IDs,
and calls `wait_for_job` (or the status read) until the job is completed or failed.
Calling acquire again for the same selection does not start a second download. After
a Backend restart, an unfinished job reads as failed with reason `download_interrupted`
and tells the agent to acquire again; nothing resumes on its own.

## Scope

Included:
- Continue from the owner-requested partial implementation on `main`
  ([checkpoint](owner-checkpoint-2026-11-27.md): `download_jobs.py`, models, acquire/install
  wiring, `/api/civitai/download-jobs/{job_id}`, MCP wait routing). Trim it to this spec;
  it carries no review result.
- **Admission.** `POST /api/civitai/resources/acquire` and the MCP acquire tool return
  `{job_id: "dl_<32 hex>", resource_ids: [...]}` alongside the existing fields. The job
  row is committed before any background work starts. Optional `idempotency_key`
  (1–128 chars of `[A-Za-z0-9._:-]`): the same key and selection returns the same job;
  the same key with a different selection is refused with a stable conflict code.
  Without a key, a selection that already has an active job returns that job.
- **Lifecycle.** States `queued → running → completed | failed`. Progress is bytes
  written so far and the update time, recorded by the downloading code (reads never
  stat or hash files). A multi-file selection completes only when every file is
  verified; a partial failure reports which files succeeded. The synchronous install
  path records its work under the same job so the two callers cannot download the
  same resource at once. The p2-03 limits (8 GiB per file, 20 GiB free floor,
  safetensors, hash, no overwrite) are unchanged.
- **Restart.** One Backend process is supported. At startup, jobs left `queued` or
  `running` by a previous process become `failed` with `download_interrupted`; files
  and partial downloads are kept; nothing is resubmitted or marked completed because a
  file exists. A simple per-process boot identifier is enough; no lease service.
- **Reads.** `GET /api/civitai/download-jobs/{job_id}` returns status, progress,
  per-file results, resource IDs and a failure reason, from the database only.
  Resource status gains the current job ID. Unknown or malformed IDs return stable
  404/422 errors. Output goes through the shared filter defined in
  [p2-02a](../p2-02a-allowlist-projection/task.md).
- **Wait.** `wait_for_job` accepts `dl_` IDs and returns the download result (resource
  IDs, verified sha256/size) with no image locator. The existing 50-second overall
  budget, generation/training behavior and the 31 intent names and risks stay as they
  are. On timeout it returns the last known status and advises waiting again.
- **Schema.** Additive tables/columns created at startup; old rows and notes are never
  rewritten. Old rows without a job report no job ID rather than an invented one.

Excluded: total disk budget / reservations (next task), cancel API, automatic resume or
retry, multiple Backend processes, generation-queue changes, new search/record MCP
tools, defaults, removals, UI, live downloads.

Open questions: none.

Read first: [verification scope](../../decisions/verification-scope.md),
[download-jobs decision](../../decisions/civitai-download-jobs.md),
[download topic](../../civitai-downloads.md), [p2-03 acceptance](../p2-03-bounded-download/acceptance.md),
[source handoff](source-handoff.md), memory on additive schema.

## Done when

- [ ] **D1 / P1:** Acquire through the registered API and MCP tool returns a persisted
  `dl_` job and the resource IDs; repeating the call (same key, or no key while active)
  returns the same job and starts no second download; a conflicting key is refused;
  two simultaneous calls for one selection produce one download. Check: test.
  Evidence: API/MCP tests with mocked provider HTTP and a download counter.
- [ ] **D2 / P1:** Success, size/space/hash failure and partial multi-file failure end in
  the right terminal state with progress and per-file results, through both the async
  acquire path and the synchronous install path. Check: test. Evidence: tests through
  the real helpers with mocked HTTP.
- [ ] **D3 / P1:** After a Backend process exits mid-download and a new one starts, the
  job reads `failed` / `download_interrupted` exactly once, no download is replayed, and
  files are kept; a completed job is unchanged. Check: test. Evidence: one test that
  kills a real subprocess Backend against an isolated database.
- [ ] **D4 / P1:** `wait_for_job` on a `dl_` ID returns completed, failed, interrupted and
  timeout results correctly within the 50 s budget, without image locators, and
  generation/training waits are unchanged. Check: test. Evidence: MCP tests against the
  Backend status route.
- [ ] **D5 / P2:** An old database starts with the new tables added and every old row
  and note unchanged; old rows show no job ID. Check: test. Evidence: migration test
  from the p2-02 previous-schema fixture.

## Delivery

- Artifact: a branch from current `main` (after p2-02a); `manifest.md` with the
  Done-when matrix, reviewed SHA and suite counts. Evidence follows
  [verification scope](../../decisions/verification-scope.md#evidence-that-is-committed)
  (at most 2 MB; no inventories, raw logs or per-round evidence folders).
- Review: fresh kickoff of this spec, then delivery review of the exact commit. Full
  suites once on the final candidate; correction rounds rerun affected tests and the
  REGISTRY guards. At 3 rejections Producer pauses and asks CTY.
- Known limitations: single Backend process only; no disk budget yet; restart marks
  interrupted jobs failed instead of resuming them.
