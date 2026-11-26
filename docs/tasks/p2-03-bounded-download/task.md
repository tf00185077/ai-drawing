# Task specification

## Task

Bound stock Civitai download execution before it can exhaust disk or replace an
existing model. Deliver per-file byte/space enforcement, safetensors selection
for Phase 2 checkpoints/LoRAs, valid resume and verified no-overwrite publication
through the existing acquisition and retained inspect/install paths.

## Purpose

The real First check needed a custom transport. Accepted p2-01 supplies credential
and request limits; p2-02 supplies one resource identity. Stock safe_download still
writes before checking size/hash and publishes with os.replace. Fix this execution
boundary before durable download attempts, aggregate reservations and new MCP tools.

## Outcome

An agent using current resource acquisition/status or retained install receives a
truthful stable resource outcome when a download exceeds byte/space policy, has an
invalid resume response, or collides with an existing file. A successful installation
has exact selected-file size/SHA-256 evidence and has replaced no prior model.
These are existing acquisition IDs/status calls, not new durable Backend jobs.

## Scope

Included:
- Shared stock safe_download plus both production callers, relevant Settings and
  Backend/MCP projections of their actual outcome. One existing Backend/config path;
  settings names and effective values are documented in the delivery/topic doc.
- Positive integer byte settings: per-file default **8 GiB = 8589934592 bytes**,
  destination free-space floor **20 GiB = 21474836480 bytes**. Invalid, zero,
  negative, boolean or unavailable policy values fail clearly before download
  side effects; no unlimited or silently larger fallback. Small explicit fixture
  values are allowed. No persistent aggregate-budget counter is introduced.
- Checkpoint/LoRA acquisitions and retained install require the selected provider
  filename and destination extension to be `.safetensors` (case-insensitive),
  preserving selected IDs/hash/size. No pickle-based fallback. Other retained
  resource kinds keep their current format eligibility; byte/space/publication
  limits apply whenever they use this stock helper. Keep frozen Anima package
  selection/routing/refusal, recipe/alias/variant contracts and single family map.
- Exact selected-file declared size must be a positive integer within the cap;
  a valid 64-hex SHA-256 and existing availability/scan gates remain required.
  Refuse invalid/oversize metadata before opening a model body or partial file.
  Actual streamed total bytes, including any resumed prefix, may never exceed
  either the declared size or the configured cap. Check each chunk before writing;
  do not buffer a complete response, truncate an oversized file or retry policy
  refusals as transient network failures.
- Observe free bytes on the destination filesystem before starting with enough
  room for the remaining declared bytes plus floor. Recheck before every chunk
  write that free bytes minus that write retain the floor. Unknown/failed space
  reads fail safely; concurrent external disk use can invalidate an earlier
  observation, so report a check rather than a reservation guarantee.
- Existing safe resume may append only after validating 206 Content-Range start
  equals the retained offset, total equals selected size, and returned range/body
  coverage is consistent. Malformed/missing/mismatched ranges refuse before append.
  A 200 restart is allowed only on a safely owned partial and all fresh limits
  apply. Prefix bytes count toward limits and the final full-file hash. Oversize,
  linked/nonregular, changed or foreign partials must not be opened/truncated/deleted.
  A preexisting safe regular partial may be reused only when its association to
  the selected provider/version/file, declared hash/size and resource is verified;
  filename/size alone are insufficient. Unverifiable legacy partials are refused
  and retained. Delivery states the ownership/association checks and proves a
  different selected file cannot reuse it. No competing model metadata registry.
- Exact size/hash verification precedes final publication on the same filesystem.
  Publication is atomic and no-overwrite even if another writer creates a target
  after preflight. Existing target bytes, symlinks and files survive every branch;
  do not follow a part link or claim a collision file as verified/installed. Cleanup
  may remove only an invocation-owned temporary partial whose ownership is still
  verified. Keep preexisting/foreign data unchanged on refusal/failure.
- Preserve ProviderOperation's configured-file loading, stateless origin/redirect
  policy, absolute deadline across reads/retries/backoff/hash/publication and
  iterator/response closure on every exit. Public diagnostics use the accepted
  complete-value policy; never expose credentials/signed locators. Resource IDs,
  old notes and measured verification semantics remain exact. After admission,
  failures publish failed/current sanitized reason on the same row; no installed
  state, fabricated verification, hidden fallback or second download submission.
  Pre-admission refusals create no resource row. Existing safe reuse stays intact.

Excluded: persistent download jobs/attempts, restart recovery, aggregate quotas or
reservations, generation queue changes, wait_for_job integration, new search/hash
lookup/MCP intents, automatic defaults, removals, UI/workers/cloud/video/training,
production backfill and live key/provider/model/runtime actions. Offline external
HTTP, filesystem and controlled free-space fixtures exercise the production path;
manual transport/key injection is not configured-file or caller proof.

Open questions: none requiring CTY. Coding chooses the smallest implementation
within the contract after actual independent CLEAR. If source reveals a boundary
conflict, report the exact evidence to Producer rather than silently narrowing.

Read first: [owner request](../../requests/2026-11-26-phase-2-start-and-key-file.md),
[roadmap](../../roadmap/ROADMAP.md), [download decision](../../decisions/civitai-download-limits.md),
[p2-01 acceptance](../p2-01-civitai-key-file/acceptance.md),
[p2-02 acceptance](../p2-02-resource-record/acceptance.md),
[resource topic](../../resource-records.md), [credentials](../../civitai-credentials.md),
[operating policy](../../OPERATING-POLICY.md), memory
[additive schema](../../memory/backend-startup-additive-schema.md) and
[runtime identity](../../memory/runtime-source-contract-verification.md).
Inspect actual `backend/app/config.py`, `services/civitai_safe_download.py`,
`civitai_resource_acquire.py`, `civitai_resource_install.py`, `civitai_provider.py`,
existing registered routes/MCP adapters and all tests/callers before changing them.

## Done when

- [ ] **D1 / P1:** Both production entry paths reject ineligible checkpoint/LoRA
  formats and invalid/oversize declarations before model-body/partial/row side
  effects, read the effective positive settings, and retain safe reuse and frozen
  other-kind/package behavior. Check: test. Evidence: registered HTTP/MCP/real
  resolver/ORM fixtures, both callers, setting/metadata/type matrix and side-effect
  counters; list exact changed compatibility assertions and their feature replacement.
- [ ] **D2 / P1:** A stream and a resumed prefix cannot exceed declared/cap bytes;
  insufficient or unknown destination space stops before the violating write.
  Chunk accounting and 206 validation prevent corrupt append; valid resume and
  bounded 200 restart complete exact bytes. Check: test. Evidence: real temporary
  filesystem/chunk traces, unknown/malformed headers, lying/oversize/aborted bodies,
  decreasing-space fixtures, prefix/full-file hash and unchanged foreign partials.
- [ ] **D3 / P1:** Verified completion atomically publishes without overwriting a
  prior or racing target; refusal/failure preserves old files, rows/IDs/notes and
  safe-public/internal-locator boundaries. Same-ID status truthfully records current
  failure and never fabricates installed/hash evidence. Check: test. Evidence:
  registered/background/install traces, target/part race and link fixtures,
  exact before/after bytes/columns and successful measured-size/hash round trips.
- [ ] **D4 / P1:** Real production request machinery retains configured-file
  precedence, credential isolation, absolute deadline and response/iterator closure
  on success, cap/space/hash/range/collision/error exits and backoff. Check: test.
  Evidence: external HTTP fixtures through both callers, pinned code/settings,
  current p2-01/p2-02 regressions and bounded denial of unintended live side effects.
- [ ] **D5 / P1:** Independent exact-final-commit QA reproduces meaningful faults
  for byte cap, free-space check, range validation, no-overwrite publication and
  size/hash verification, then exact restoration/GREEN, with all 72 prior registry
  items preserved. Check: test + delivery. Evidence: complete manifest/failed-attempt
  ledger/source hashes, current affected/full Backend/MCP and fresh exports/standing
  consumers; isolated roots, pinned imports and 60 s per-test long-suite limits.
  No silent feature-test deletion, new unexplained skip or registry supersession.

## Delivery

Persistent isolated worktree from the fixed published kickoff source; actual CLEAR
precedes Coding. Update the matching download topic and provide D1–D5 evidence,
caller/dependency inventory, effective policy/error contract, immutable raw failures,
freeze and actual FINAL full SHA/tree. Independent QA pins that exact candidate
before review, publishes its own actual verdict and completes its own card even
if adverse. Producer handles findings/acceptance; changed code gets new exact QA;
merge only after actual PASS. Retain all shared edits/private configuration/key,
runtime/jobs, environments/worktrees and models/datasets/outputs/Gallery records.
Report offline tests, running service, real generation and artifact retrieval
separately. This task needs only offline synthetic fixtures, with no deployment,
live download or Phase 2/artistic acceptance inferred.
