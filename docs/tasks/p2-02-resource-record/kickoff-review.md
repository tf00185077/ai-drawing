# p2-02 kickoff review

Verdict: CLEAR
Review round: 1
Assignment: AID-185; Producer AID-146.
Date: 2026-11-26

Reviewed source: **f8d3143a7ab5a0f2c8c2c9955817276aa5bcff7a**.
Reviewed tree: **a634ce583d387dd1849978f3f47055d07b71e515**.
Task SHA-256: **c43339e42ff1a160cfb87cf9742e53606db17c37ffe12439745b115ca6a8beda**.
The report commit/tree and official attachments are recorded after commit on
[AID-185](/AID/issues/AID-185), avoiding a circular self-hash.

Difference: none requiring a specification change. No demonstrated P0/P1 kickoff
defect, unresolved contract ambiguity, or ASK OWNER/BLOCK finding. This clears
the fixed specification for Coding; it does not certify implementation D1–D5.
There is no p2-02 manifest or delivery candidate yet.

## Independent reading of owner direction

Recorded after reading the owner request and active Phase 2 roadmap, before
opening the repository task file. The full task was already supplied inline in
the assignment; this is an independent interpretation, not a claim of blindness.

CTY expects the existing FastAPI Backend to own reusable model identities,
provider metadata and an exact SDXL-group mapping, followed by search/download
jobs and automatic workflow/default use. Existing records should be reused,
not duplicated under filenames or image aliases. The real First check must
precede detailed implementation. Personal-use license metadata is retained
without a commercial-use filter. Producer may choose bounded implementation
steps within this scope without another routine owner approval. A foundation
that keeps the current model rows authoritative and lets actual producers and
readers share a typed representation is a valid prerequisite; it cannot claim
full Phase 2 flow, replacement of every alias, a live deployment, or image
acceptance. Data, credentials and independent QA boundaries remain in force.

## Scope and authority comparison

The [owner source](../../requests/2026-11-26-phase-2-start-and-key-file.md), active
[Phase 2 roadmap](../../roadmap/ROADMAP.md) and [resource decision](../../decisions/civitai-resource-record.md)
agree with task lines 5–59. The owner delegates routine in-boundary technical
choices to Producer. Establishing existing row IDs before persistent download
accounting is the explicitly recorded joint-intake dependency refinement, not
a replacement architecture, phase-order change, or extra owner gate. Producer's
decision remains attributed to Producer rather than presented as an owner quote.

The accepted real First check precedes this software specification. Its
[friction ledger](../p2-00-civitai-first-check/friction-ledger.md) records manually
assembled resources, family selection and defaults; its service inventory
distinguishes seven touched modules, including one value type, from 12 modules
without operational invocation. That evidence supports foundation work, not
deletion of the latter modules. The 20 interventions, 77 overlapping units and
five missing historical source hashes remain unchanged.

I read the actual [p2-01 manifest](../p2-01-civitai-key-file/manifest.md),
[round-2 independent PASS](../p2-01-civitai-key-file/review.md) and
[acceptance](../p2-01-civitai-key-file/acceptance.md). Candidate
2e3850307f767ec2be213781accde367f321dc1d and QA report
155e2209a9910556dfa0255223a9b4a30f120d87 resolve the cookie-channel defect after
freeze 2491ceb7555fe49e3f6a1261113a3e6398185743. History stays kickoff 1 CLEAR,
delivery 1 FAIL, one P1 R1/one implementation rejection, correction 1, delivery
review 2 PASS. The 22 standing contracts are not replaced or re-certified here.

Unknown-local hashing/adoption, complete alias replacement, download jobs/budgets,
search/new MCP tools and automatic generate defaults remain later work. Task
lines 50–55 and 161–163 make this increment's limits explicit. No source
publication, prior HEAD comparison or static review establishes deployment,
fresh model qualification, a zero-fix Phase 2 exit, or CTY's aesthetic verdict.

## Fixed-source trace

Paths and line spans below refer to the reviewed source, not a later checkout.
The static audit records exact symbol spans,
constructor sites, direct import dependencies, catalog and registry rows.

| Boundary | Baseline evidence | Assessment against the task |
|---|---|---|
| Identity | `backend/app/db/models.py:354` defines DownloadedResource with the existing integer ID, provider/source/path/hash/size/status, nullable file/AIR IDs and notes. The two explicit application constructor sites are acquire:398 and install:318. | D1 extends the existing authority. A typed projection may refer to these fields without duplicating identity/path/hash/status in a second authoritative record. Adding nullable metadata and verification evidence is implementable with the current stack. |
| Acquire | `civitai_resource_acquire.py:323` resolves the actual version, picks files, admits rows and schedules `_run_one:491`; completion assigns result.bytes and result.actual_sha256. Admission initially stores provider-declared size/hash. | D1/D2 must keep declared admission evidence distinct from actual completion. Tests must reach admission, background publication, failure/status and installed reuse, including a conflicting provider file/hash under an otherwise matching version/name. Repeated publication must not create another row or rebind identity. |
| Inspect/install | `api/civitai_recipes.py:276` narrows a requested version before inspect/select/install. `civitai_resource_install.py:130` produces descriptors, `:239` requires their exact field set, and `:296` persists a row by provider file ID. | Metadata cannot be tested only on a new isolated writer. Current descriptors omit triggers/recommendations and their Pydantic models are strict. Any snapshot carried through this path must survive the actual request/schema/select boundary. Legacy inputs lacking it remain unknown; additive internal/schema choices are delegated. |
| Ledger | `civitai_local_identity_ledger.py:47` independently interprets notes.model_family; `:95` reads DownloadedResource rows. API recipes, civitai_easy and recipe_variants import this adapter. | D2 makes it derive from the shared representation, retaining documented legacy adapter limits. Neither legacy notes parsing nor recipe response enums may become a competing Phase 2 mapping authority. |
| Mapping and legacy routing | Acquire's substring normalizer is at `:71`; admission uses its Anima result to route split packages at `:354`. `civitai_easy.py:53` uses the same normalizer for AIR ecosystems. Recipe compatibility accepts historical sdxl/illustrious values. | D1's new exact four-label mapping must preserve raw labels and return null/no_matching_workflow for every other label. Preserve legacy package/recipe behavior through clearly scoped adapters; do not reuse broad filename/AIR inference as Phase 2 mapping. Mapping alone cannot establish checkpoint/LoRA pair compatibility. |
| Startup/backfill | `db/database.py:20` declares additive columns; `init_db:68` calls create_all then adds missing nullable columns. Old notes can contain both provider and previously normalized family values. | D3 requires a whole-schema/old-value fixture audit, not only querying new ORM columns. Backfill must preserve original notes, IDs, duplicates, alias/history rows and file contents; malformed or insufficient evidence stays incomplete. No startup rehash, production backfill or guessed image-to-model conversion is needed. |
| Alias evidence | `schemas/civitai_source_aliases.py:35` requires an immutable image/media target. Registry records/history/repoint tables are separate image/recipe evidence; registry:72 validates persisted identity/evidence. | Keeping these frozen is consistent with the explicit bounded increment. Direct callers include the recipes router, recipe_pipeline, source_alias_parent and source_alias_backfill; parent materialization reaches variants/variation_sets. This static inventory supplements First check usage; neither proves safe removal. |
| HTTP reads | `main.py:110` registers the retained routers. New /api/resources routes are absent. Existing API errors use HTTPException detail objects with code/message and optional hint. | D4 explicitly requires real registration/OpenAPI, bounded database pagination and matching detail projection; a service helper alone is insufficient. Resource-not-found needs the stable code and recovery hint in Backend conventions. No MCP envelope/tool change is authorized. |
| Credential boundary | Retained adapters use ProviderOperation and accepted prepared-request/cookie policy. | D2/D4 retain p2-01 provenance, credential snapshot, secrecy, deadlines and closure. External HTTP fixtures can substitute wire responses; injecting a key or domain transport to manufacture working production loading cannot. No live provider operation is needed for this task. |

## D1–D5 assessment and delivery focus

| Item | Kickoff assessment | Judgeable evidence required at delivery |
|---|---|---|
| D1 / P1 | CLEAR: observable identity, normalization, unknown and verification rules are specified at task lines 74–98 and 121–124. | Real ORM round trips; all four labels with case/outer whitespace; unsupported prefix/substring/filename/AIR and malformed labels; original label retention; selected version/file provenance, ordered deduplicated triggers, invalid entries, typed finite recommendations with origin names, absent metadata and explicit license gaps. Declared hashes/status/sizes cannot be promoted to measured facts. Repeated and conflicting publication must be distinguished. |
| D2 / P1 | CLEAR: actual current writers and the retained reader are explicitly included at lines 42–45 and 125–130. | Real registered acquire and inspect/select/install paths, resolver/ORM/background execution with synthetic bytes, plus ledger reads of the same row. Select a non-first version/file so wrong-source metadata cannot pass. Prove measured result publication, failed/incomplete truth and stable existing response IDs. Replace only external HTTP/scheduling; enumerate fixtures and unchanged legacy limits. "Without new resource rows" applies to duplicate metadata publication/reuse; initial actual acquisition can still create its one authoritative row. |
| D3 / P1 | CLEAR: startup and explicit backfill are separately bounded at lines 99–107 and 131–135. | Copy the preceding schema into an isolated synthetic fixture; audit all old columns/values and all tables before/after, not just resource counts. Include malformed/nonobject notes, conflicting identity/metadata, duplicate candidates, unsupported old families, missing/offline paths, aliases/history and synthetic files. Repeat startup/backfill and compare IDs/counts/projections. Deny network/model writes and preserve old notes verbatim. |
| D4 / P1 | CLEAR: route, pagination, filters and errors are concrete at lines 108–117 and 136–140. | Actual HTTP/ORM/OpenAPI tests of default/max/invalid limit, nonnegative offset, ascending IDs, filtered pre-pagination total, every exact filter, trimmed text, case-insensitive 64-hex hash, sdxl-only family filter, valid unmatched filters, malformed selectors, missing/invalid IDs and same list/detail item. Observe no SQL writes, provider traffic, metadata repair or model-body reads. Credential/signed-query and bad-notes diagnostics must be excluded. |
| D5 / P1 | CLEAR: exact candidate, meaningful faults, restored GREEN and prior-contract retention are specified at lines 141–160. | Independently break the exact map, promote status/declared hash to verification, bypass shared publication in one writer, destructively alter backfill, and unbound or write during list. Each violation must fail a relevant feature guard. Restore exact source, run affected/full Backend/MCP and registry checks with pinned imports, isolated roots and per-test 60-second timeout. Keep failures/history and all 22 contracts; certify additions only after sensitivity. |

These are delivery requirements, not newly added owner conditions. Internal
metadata field layout, projection version representation, finite recommendation
types and safe opaque-evidence representation may be documented implementation
choices within the fixed contract. Missing source fields stay unknown rather
than triggering a new provider lookup during reads or backfill.

Two existing feature assertions require deliberate compatibility handling:
`backend/tests/test_civitai_easy.py:553` expects the old normalizer to return
illustrious/Anima; `backend/tests/test_civitai_resource_install_api.py:533` expects
historical illustrious in a recipe resolution lock. The task expressly permits
frozen historical adapter outputs. Preserve those behaviors in that boundary,
or document any obsolete assertion and its meaningful replacement under D5.
Do not globally relabel recipe/training behavior, remove tests, add skips or
silently supersede a certified contract to obtain GREEN.

Cancellation/job recovery and live artifact retrieval are not new APIs in this
foundation. Retained acquisition failure/same-ID status and duplicate behavior
still need regression evidence. Reads must not resubmit, download or repair
state. Real cancellation/accounting qualifications belong to their later tasks;
they are not inferred from static review or synthetic installed bytes.

## Commands and verification limits

Persistent worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-185-kickoff-review`.
Branch: `aid-185-p2-02-kickoff-review`, created at the assigned full SHA. Shared
main's 13 concurrent memory edits were not staged, stashed, reset or copied.

- `git rev-parse`, `git ls-tree`, `git show`, targeted `rg`/`sed` reads and AST
  inspection identified the fixed source, contracts, writers/readers and callers.
- `shasum -a 256 docs/tasks/p2-02-resource-record/task.md` matches the assigned hash.
- `python3 -B docs/tasks/p2-02-resource-record/kickoff-evidence/check_source.py`:
  **238 static checks passed**, including **211** tracked inventory files matched
  byte-for-byte to fixed Git blobs. The inventory
  covers all tracked Backend app/workflows and MCP implementation, plus the
  explicitly listed review documents and relevant tests. No ordinary source
  hashes are suppressed by token-like path names. The first run passed 234 checks
  on 207 files; adding four review inputs produced the final 238/211 audit.
- Product/tests/workflows, MCP implementation/tests, frontend and the registry
  have exactly the accepted p2-01 QA tree objects at 155e2209. Its recorded full
  suites remain historical context: Backend 1,978 passed/124 skips and MCP
  666 passed/four skips. No fresh product test result is claimed here.
- `git diff --cached --check`: passed for the staged report/evidence, the
  only authored paths. The registry remains unchanged: this kickoff adds no
  delivery review.md coverage and no product certification, so no rebuild is needed.

No implementability probe or product suite was necessary for this specification
review. The audit uses Python standard-library parsing and Git reads; it imports
no application modules, loads no settings or credentials, opens no database,
and makes no network call. It is not a simulation of the requested implementation.
Exploratory searches encountered guessed nonexistent filenames and were resolved
with the tracked file inventory; no failed test/probe result is omitted.

**Offline:** source/specification review and static identity audit only; no new
feature/full suites or mutations. **Running service:** no probe, startup,
restart or deployment. **Provider/generation:** no key read, provider request,
download, registration or generation. **Retrieval:** no model/Gallery bytes;
official report/evidence uploads and byte verification are separate handoff
operations recorded on this card. Windows is untested. Shared private settings,
runtime, environments, prior worktrees and all model/dataset/output/Gallery data
remain outside this review's mutations.

## Disposition and history

p2-02 history: kickoff round 1 CLEAR; zero kickoff ambiguities, owner questions
or implementation delivery rejections. D1–D5 are unimplemented/unreviewed here.
No product/test/task/decision/registry changes, merge, push or parent owner/status
write are included. This QA-owned card completes with the actual verdict and
official report/evidence. Producer reads it before dispatching separate Coding
and exact-final-commit delivery QA. Changed specifications need a fresh kickoff;
later implementation changes need a new exact delivery review. CLEAR is not PASS.
