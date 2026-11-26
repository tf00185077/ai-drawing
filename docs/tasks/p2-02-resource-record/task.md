# Task specification

## Task

Make the existing Backend model-resource table the single typed source of
resource identity, metadata and Phase 2 workflow-family mapping; expose bounded
read/list/filter operations and use it from retained producers and readers.

## Purpose

Phase 2 needs reusable resources before download jobs, budgets and automatic
defaults can share reliable IDs. The First check manually assembled two rows;
`notes` contains partial metadata, family normalizers disagree, and acquisition
IDs are resource IDs rather than job IDs. Establish this contract first, as
permitted by the [joint download/record intake](../p2-00-civitai-first-check/implementation-intake.md).
This is a detailed software increment after the real First check, not a phase-exit
or complete resource-flow claim. Owner scope/order/Not now remain unchanged.

## Outcome

Backend clients can enumerate and inspect recorded models with stable existing
IDs and honest metadata/verification state. Successful current acquisition and
install paths publish the same representation; local-ledger reads derive from
it. Old database rows remain accessible without model-file changes or a second
registry. Later download attempts will reference these IDs.

## Scope

Included:

- Extend `DownloadedResource`/`downloaded_resources`, using additive nullable
  columns or a versioned typed JSON field on that row. Keep existing identity,
  path, hash and status columns authoritative; do not copy them into a competing
  record. Preserve existing integer IDs and legacy acquisition/status responses.
- A shared typed projection contains resource ID/name/type, provider/source URL,
  provider model/version/file IDs and AIR when known, raw base-model label,
  mapped workflow family, SHA-256 and whether it was actually verified, declared
  versus measured size, installed/path availability, ordered trigger words,
  recommended parameters, license snapshot, metadata origin/version and explicit
  missing/invalid/conflicting metadata diagnostics. Missing is unknown, not a
  fabricated default. Signed URL/query and credential material stay excluded.
- Production acquire and retained inspect/install publication, plus the existing
  local-ledger adapter, share that projection. Old recipe/image alias code stays
  frozen; inventory its actual dependencies and classify evidence for later
  migration/removal. No new alias features or second model-identity writer.
- New read-only Backend `GET /api/resources` and `GET /api/resources/{resource_id}`.
  No new MCP names/risks, model downloads, registration endpoint or live deployment
  in this increment. Backend app/router/schema/OpenAPI wiring is real in tests.

Excluded: download attempt/job/reservation persistence, disk/byte budgets,
unknown-local hashing/provider hash lookup and adoption, full resource dedupe or
alias removal, Civitai search/new MCP tools, automatic defaults/triggers/workflow
selection in generate, UI, worker/video/training changes, schema framework/new
database, and running-service restart/private settings/data rewrite. These remain
approved subsequent work, not implicit additions to this task.

Open questions: none requiring an owner decision. Producer handles actual
kickoff ambiguity; routine choices are delegated. Coding may choose small internal
representations that satisfy this observable contract and documents them.

Read first: AGENTS, MEMORY, INDEX, CURRENT, ROADMAP Phase 2, OPERATING-POLICY,
team roles; [owner direction](../../requests/2026-11-26-phase-2-start-and-key-file.md),
[resource decision](../../decisions/civitai-resource-record.md),
[credential decision](../../decisions/civitai-credentials.md),
[accepted p2-01](../p2-01-civitai-key-file/acceptance.md), actual manifest and
round-2 review; [First check acceptance](../p2-00-civitai-first-check/acceptance.md),
friction/service inventory; memory backend-startup-additive-schema,
model-family-loader-compatibility and runtime-source-contract-verification;
db/models.py, db/database.py, civitai_resource_acquire/install/resolution,
civitai_local_identity_ledger, source-alias schema/registry and their actual callers.

## Observable contract

1. **Identity and metadata.** `resource_id` equals the existing row ID. Metadata
   publication augments that row; it cannot silently rebind a conflicting provider
   file/hash to that ID or turn a declared hash/status into measured verification.
   Successful download/install uses its actual hash/size result. If current
   verification evidence is insufficient, expose unknown. Repeated publication of
   the same result is idempotent. Reads never create rows, download, hash large
   model files, perform provider traffic or mutate metadata.
2. **Mapping.** After outer whitespace trim and case-insensitive exact matching,
   only the four labels `SDXL 1.0`, `Illustrious`, `Pony`, `NoobAI` map to `sdxl`.
   No substring/prefix/filename inference. Preserve the original provider label.
   Every other/missing/non-string label yields null family with stable
   `no_matching_workflow` diagnostic. A mapped checkpoint/LoRA is not automatically
   a compatible pair. Do not change workflow graphs/training family behavior.
   Historical recipe compatibility enums may remain frozen adapter outputs;
   they are not another Phase 2 inference table or authority for new metadata.
3. **Provider snapshot.** Persist metadata from the actually selected version/file:
   trainedWords as ordered unique trimmed strings; invalid entries diagnosed.
   Recommendations retain only typed finite sampler/scheduler/steps/CFG/width/
   height/LoRA-strength values actually supplied by provider metadata, with origin
   field names; absent values stay absent. Do not derive defaults from sample-image
   prompts or silently fill model preferences. Keep unrecognized safe metadata as
   opaque source evidence, not applied parameters. License is stored, with missing
   fields explicit; no commercial-use filter. Use accepted production provider
   operations, secrecy and deadlines; never add a key or transport injection as
   proof that production loading works. Offline external-HTTP fixtures are valid.
4. **Migration.** On an isolated fixture copied from the previous schema, normal
   startup is additive and preserves all old columns/values. Provide an explicit
   idempotent metadata backfill for valid legacy notes, with before/after evidence
   and per-row diagnostics for malformed notes, conflicting values, old unsupported
   bases, duplicate candidates and missing/offline paths. Preserve old notes as
   immutable evidence. Do not merge/delete rows, guess identity, change files,
   rehash at startup or interpret an image alias as a model. Repeat startup/backfill
   gives the same IDs/counts/projection. Existing rows without enough evidence
   stay readable as incomplete. No production database backfill in this task.
5. **Reads.** List returns `{items, total, limit, offset}` in ascending resource ID;
   `limit` integer 1–100/default 25 and `offset` integer 0 or greater/default 0.
   Exact optional filters: resource_type, provider, raw base_model, model_family,
   status, and case-insensitive 64-hex SHA-256. Strings are trimmed; no fuzzy name
   selection. Family filter accepts `sdxl` only; malformed inputs return FastAPI
   422. Unknown valid filters return an empty list; total is the filtered count
   before pagination. Detail returns the same typed item or 404 with stable
   `resource_not_found` detail and recovery hint. Diagnostics expose no raw bad
   notes, credentials or signed locators. Preserve the established Backend error
   conventions; a later MCP task will apply common MCP envelopes.

## Done when

- [ ] **D1 / P1:** One row/ID authority and typed snapshot/mapping behave as specified
  for all four labels, unsupported/ambiguous/malformed cases and absent metadata;
  declared and verified facts remain distinct. Check: test. Evidence: real ORM
  round trips, complete schema/metadata contract and positive/negative cases.
- [ ] **D2 / P1:** Actual current acquire and inspect/install publication and
  local-ledger reads use the shared representation without new resource rows or
  incompatible identity replacement on repeated publication. Check: test. Evidence:
  registered Backend paths, real resolver/ORM/background fixture execution,
  selected version/file provenance and retained old response/ID contracts. Substitute
  external HTTP and scheduling only; list every fixture and unchanged legacy limit.
- [ ] **D3 / P1:** Old-schema startup and explicit backfill preserve all old values,
  notes, aliases/history and files, remain idempotent, and diagnose incomplete or
  conflicting records. Check: test. Evidence: full before/after schema/value audit
  on isolated fixtures, denied network/model writes and source-alias caller/removal
  inventory. No production private snapshot/database is attached.
- [ ] **D4 / P1:** Registered list/detail routes and OpenAPI expose the exact bounded
  filters/projection/errors; read calls cause no DB writes/provider/model-body
  reads. Check: test. Evidence: actual HTTP/ORM cases with old/new rows, pagination,
  invalid selectors, missing IDs, credential/signed-query exclusion and side-effect
  denial. These are offline service fixtures, not a running production claim.
- [ ] **D5 / P1:** Independent exact-commit review can reproduce feature guards and
  meaningful faults (wrong map, fabricated verification, split writer, destructive
  backfill, unbounded/writing list), followed by exact restoration/GREEN. Check:
  test + delivery. Evidence: manifest, source fingerprints, command roots/imports/
  argv, all failed attempts, current affected/full Backend/MCP and standing registry
  results; long suites use per-test 60 s timeout and isolated roots. Keep all 22
  prior contracts; document any obsolete assertion's feature replacement. No silent
  deletion/skips/registry supersession. QA certifies additions after sensitivity.

## Delivery

- Persistent isolated Coding worktree from the fixed published source; freeze exact
  source for review, manifest with D1–D5 matrix, schema/backfill/legacy dependency
  report, complete ordinary source hashes and replayable sanitized evidence.
- Independent QA pins the actual final full SHA/tree before review, publishes its
  own actual verdict and completes its own card even if adverse. Producer handles
  findings; changed source requires another exact review; merge only after PASS.
- Preserve shared-main edits, active runtime/private settings/key, environments,
  worktrees and all models/datasets/outputs/Gallery records. Offline fixtures use
  synthetic files/credentials only; no live provider or model action is needed.
- Known limitations: Backend foundation only; no completed agent record/search/
  download-job/default flow, source binding, fresh checkpoint/LoRA qualification,
  Phase 2 exit or CTY aesthetic decision. Report evidence levels separately.
