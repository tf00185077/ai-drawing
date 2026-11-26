# Task specification

## Task

Persist Civitai download operations in the existing Backend and let an agent wait
on their actual job IDs through the existing wait_for_job intent. Keep resource
IDs as resource IDs and preserve verified stock execution and historical data.

## Purpose

Accepted p2-03 bounds bytes/space/publication and admission waiting. Acquisition
still starts per-resource daemon threads; its integer acquisition_id identifies a
resource row, not a persisted job. A process exit can leave downloading state with
no accountable operation, and wait_for_job only reads generation/training domains.
Phase2 needs a real asynchronous download job before new search/MCP/default flows.

## Outcome

One admitted request returns a durable namespaced download job ID plus unchanged
resource IDs. Retrying an idempotent request or inspecting/waiting on that job does
not submit another body. A fresh Backend process can read its persisted terminal
outcome or honestly record an interrupted previous operation; no automatic replay
or completed result inferred solely from a file's presence. The existing resource
row remains the sole model/metadata authority.

## Scope and contract

Included:
- Existing Backend SQLAlchemy/SQLite, resource writers, lifecycle, Civitai API and
  existing MCP acquire/status/wait surfaces. A small additive download-operation
  record and component/resource associations are allowed for execution history;
  they are not a second resource registry or a generic job/workflow engine.
- One immutable public job identity per admitted logical selected-version request,
  with component results for the existing split-package behavior. Namespaced
  download IDs distinguish this domain from generation/training and integer resource
  IDs. Persist selected identity/resource links, safe effective policy, admission/
  start/update/finish times, actual progress, terminal result and sanitized reason.
  Credentials/private key bytes/signed locators are never stored in job evidence.
- `idempotency_key` is optional on the current acquisition API/MCP arguments,
  1–128 ASCII letters/digits/period/underscore/colon/hyphen when supplied. Bind it to
  the canonical selected operation and destination; exact same-key replay returns
  the same job and cannot launch another body even after completion/failure/restart.
  Same key for conflicting selection/destination refuses with a stable conflict.
  Do not echo raw keys in diagnostics/logs. A new explicit key permits a legitimate
  retry after a terminal failure, preserving previous attempts. Keyless callers
  keep useful old retry/reuse behavior and dedupe an already-active selection to
  its current job. A competing different request returns the owning job/resource
  identity or a clear active refusal, without stealing ownership.
- Validate the full package/policy/selection before admission. Atomic durable
  admission commits job/resource ownership before background work; DB failure
  cannot launch an unrecorded body. Independent connections/simultaneous callers
  must not both claim one resource. Existing accepted process-local deadline-aware
  admission is not a cross-process database claim. No new generation queue/scheduler.
- Use existing bounded stock helper/request machinery. Acquisition remains async;
  synchronous retained install keeps its existing result/timing contract but
  participates in the same durable operation ownership/finalization so it cannot
  bypass or corrupt an active job. Job IDs may be added to its result. Current
  verified ready-file adoption may record its present operation without inventing
  a historical network download. Existing acquisition_id(s) and resource IDs never
  change meaning or value. Preserve all already-installed resources and old notes.
- Durable queued/running/completed/failed states distinguish admission, actual work
  and terminal outcome. Progress is measured/recorded by execution, bounded by
  selected size and labelled with its update time; reads do not stat/hash/download
  a model to fabricate progress. A package job completes only when every selected
  component has verified success; failures expose successful components truthfully
  without deleting their files or claiming whole-package success. Stale callbacks
  from an earlier attempt cannot modify a newer owner or regress a terminal job.
- On a verified Backend-process restart, queued/running operations whose worker
  cannot still be executing become failed with a stable interrupted reason and
  explicit same-job/next-retry guidance. Preserve identity, partial association,
  evidence and files. Never auto-resubmit/resume or mark completed by file presence.
  A concurrently live Backend/worker must not be stolen or reconciled as dead;
  fail-safe rejection of unsupported concurrent Backend ownership is acceptable.
  Record the supported single-Backend lifecycle and actual ownership/fencing proof;
  no cluster lease service, worker registry or scheduler is added.
- Add a bounded read route for persisted download jobs in the current Civitai
  router. Public status uses the existing complete-value policy and includes job
  domain, resource IDs/component states/progress/reason. Resource status adds current
  job linkage while retaining old fields. Reads are DB-only, with finite indexed
  queries and stable not-found/invalid/failure behavior across fresh sessions/processes.
- Existing `wait_for_job(job_id, timeout_seconds)` gains this download domain using
  the new namespaced IDs and authoritative Backend read, preserving generation/
  training behavior and all31 intent names/risks. It returns download resources/
  verified-result metadata, with no fabricated Gallery image/media locator, no
  artifact_locator_unavailable solely because a successful download has no image.
  Same overall default/max50s budget includes domain/read/body/error preparation and
  polling; current calling-client limit remains unverified. Timeout retains actual
  last-known job status and only advises reading the same job, never submit/cancel/
  retry/download/registration/generation. Known download-domain errors do not fall
  through to unrelated domains. Malformed/unknown IDs fail truthfully and safely.
- Additive schema/init for old databases, two-pass initialization and complete
  schema/old-value audit. Never rewrite old notes/IDs/metadata/job/Gallery rows or
  invent backfilled attempts for historical downloading rows without evidence.
  Legacy rows with no attempt must be distinguishable from a current durable job;
  provide truthful unsupported/legacy guidance instead of phantom job IDs.

Excluded: aggregate quotas/reservations/total-budget enforcement (next bounded
spec after operation identity), automatic restart resume/retry, cancellation API,
generation-queue durability/concurrency rewrite, new search/hash/resource MCP
intents, automatic defaults/removals/UI/workers/cloud/video/training, production
backfill/deployment and live key/provider/model/runtime/generation actions. Per-file
8GiB/20GiB observed floor remain current; neither is aggregate reservation. The
First check's temporary10GiB guard is not a new persistent quota/default.

Open questions: none requiring CTY within this scope. Coding chooses the smallest
schema/ownership mechanism after actual independent CLEAR; report demonstrated
contract ambiguity/boundary conflict to Producer instead of silently narrowing.
Read first: current owner request, ROADMAP/CURRENT, [job decision](../../decisions/civitai-download-jobs.md),
[p2-03 acceptance](../p2-03-bounded-download/acceptance.md), [download topic](../../civitai-downloads.md),
[p2-02 acceptance](../p2-02-resource-record/acceptance.md), [p2-01 acceptance](../p2-01-civitai-key-file/acceptance.md),
credentials/resource topics and memory on additive schema/runtime source/revision
lineage. [Source handoff](source-handoff.md) identifies the actual current paths.

## Done when

- [ ] **D1 / P1:** Real acquisition API/MCP admission returns a persisted download
  job plus unchanged resource IDs; same-key/active replay cannot duplicate work,
  conflicting key refuses and a new terminal retry retains history. Check: test.
  Evidence: actual registered callers/ORM, independent-connection/simultaneous
  admission, full-package/pre-admission/commit-failure counters and a production
  duplicate-claim/idempotency bypass fault that fails before a second body can hide.
- [ ] **D2 / P1:** Both execution paths retain stock D/C/E bounds and publish
  measured progress/truthful component/terminal outcomes under fenced ownership.
  Check: test. Evidence: real helper/ProviderOperation/registered background and
  retained install, success/size-space-range-hash/deadline/collision/DB failure/
  stale callback/package partial-failure traces, unchanged files/rows/notes and
  meaningful current-owner/terminal-publication/progress faults. No synthetic
  configured-key/transport bypass is presented as a production caller proof.
- [ ] **D3 / P1:** Fresh-session/process reads survive lifecycle boundaries;
  verified dead queued/running work becomes interrupted once without body replay,
  while live owners/terminal jobs and legacy rows are preserved. Check: test.
  Evidence: isolated real process death/restart, admission-before-launch and
  publication-before-finalization boundaries, same-job history/owned partials,
  live-owner refusal/fencing, additive full-schema/old-value audit twice and a
  reconciliation/replay fault that fails. Do not mutate production DB/runtime.
- [ ] **D4 / P1:** Registered existing acquire/status/wait return the same durable
  download identity/outcome, use bounded DB-only status and complete-value secrecy,
  preserve generation/training and overall50s wait semantics. Check: test. Evidence:
  fresh Backend exporters then independent MCP/stdio readers, completed resource
  results without fake media, failed/interrupted/not-found/timeout/transport cases,
  no-submit/body/hash/stat counters, budget/domain/identity faults and retained
  31-tool/envelope/risk plus current wait/PNG/generation/training contracts.
- [ ] **D5 / P1:** Independent exact-final-commit QA verifies all above after
  meaningful production faults/exact restoration/complete GREEN, preserving87
  prior registry items and all old task evidence. Check: test + delivery. Evidence:
  manifest/caller-compatibility inventory, actual freeze/FINAL/tree and complete
  ordinary fingerprints, raw attempts, current affected/full Backend/MCP/fresh
  exports/standing guards with isolated roots/pinned imports/per-test60s long-suite
  limits; official self-contained artifacts/prerequisites and exact restores.
  No silent feature deletion/new unexplained skip or registry supersession.

## Delivery

New persistent isolated worktree at the fixed published source in the native initial
plan. Actual independent kickoff CLEAR precedes Coding; then separate Coding and
exact-final-commit QA cards. Update matching job/credential/resource/MCP topic docs
for actual behavior. Preserve source/instruction/settings/root/fixture identities,
old schema/data/raw histories and every failure/intervention. QA pins actual NEW
FINAL/tree before review, completes own verdict even adverse; Producer handles
findings/acceptance. Changed code needs new exact review; merge only after PASS.
Offline test fixtures and official artifact retrieval only; running service/real
provider/model download/generation/liveGallery bytes remain unrun and separately
reported. No automatic Phase2/CTY artistic acceptance.
