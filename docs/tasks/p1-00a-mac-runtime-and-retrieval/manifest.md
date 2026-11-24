# p1-00a Mac runtime and retrieval repair

[AID-153](/AID/issues/AID-153), correction round 1, 2026-11-24 UTC. This corrects the D5 runtime/schema inventory of [AID-151](/AID/issues/AID-151) candidate `00ebb4d73edf3efe54943f3e2d784200e3023cab`. [Independent QA round 1](/AID/issues/AID-152#comment-c64c55d7-ac7c-4849-94cf-8447f62d3e2b) returned FAIL: D1–D4 PASS, D5 incomplete inventory. The successful journey and its raw evidence are retained and explicitly reused; no product/test change, runtime restart, database repair or new generation was performed in this correction. Accounting remains **one delivery rejection, correction round 1; next independent delivery review is round 2**. Round-2 PASS and Producer acceptance remain required before merge/push or dependent release.

## Source and delivery identity

- Fixed cleared specification: `4ac3d5653d7bffee2698809d32d0f5ea0f506cbc`; task SHA-256 `be8814ca4f3bbaaa16e14f8a7b236a1fd5c34d0d1cd4a2ee88570631bea06359`. [QA kickoff](/AID/issues/AID-150#comment-0160c15e-8db0-43dc-a1de-a4b94af6b51b) is in QA commit `9bd002968c77484fba89e1d2b59cd021b30b939d`, also available on [AID-150](/AID/issues/AID-150).
- Implementation/runtime base: published `eaf11b8f75fb573db3d0a4e858973d59385b5087`.
- Correction assignment: published `c41815c25d2e6139f65c058ab1a8750bbecc6659`, `docs/tasks/p1-00a-mac-runtime-and-retrieval/repair-round-1.md`, read from the shared main snapshot. It corrects original D5 without changing the cleared task or kickoff.
- Correction worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-153-inventory-correction`; branch `aid-153-inventory-correction`, created from exact rejected candidate `00ebb4d73edf3efe54943f3e2d784200e3023cab`. The active `aid-151-runtime-retrieval` worktree, its private configuration, canonical Backend venv and shared `main` were left untouched.
- Delivery commit: the commit containing this manifest (`git log -1 --format=%H -- docs/tasks/p1-00a-mac-runtime-and-retrieval/manifest.md`). Its full final SHA is in AID-153's completion and new uploaded delivery receipt; the commit cannot contain its own hash. The refreshed upload contains exact committed files, correction and cumulative patches, checksums, receipt and the existing byte evidence. The old AID-151 receipt describes only `00ebb4d`.
- Backend/MCP source trees are identical to accepted baseline execution `3081952e0ba12a339ab7e60b8081ede61a131b7f`. [Source/environment receipt](evidence/source-environment.json) fingerprints 364 tracked component files and records both interpreters/packages. The final delivery changes docs/evidence only. No merge or push was performed.
- [Correction applicability receipt](evidence/correction-1/reuse-equivalence.json) checks Backend/MCP tree identity (including tests/dependencies) against rejected candidate, runtime base, original specification, baseline and round-1 QA commit `537d47f8194c306b54c61fe2eacdae262afeece0`. All 364 recorded files match both correction and active runtime worktrees; task bytes, 20 original baseline files and 43 retained original evidence files match. Current component packages/interpreters, platform, PID/start time/cwd/command/import environment, configuration hashes, DB handle and relevant live revision schemas match retained facts. This supports reuse, not a new journey or suite execution.

## Done when

| Item | Check | Level | Result and evidence | Layer / real boundary |
|---|---|---|---|---|
| D1 — identified clean runtime and revision contract | manual | P1 | Reused AID-151 result and round-1 QA PASS: [before](evidence/runtime-before.json), [active-job check](evidence/restart-active-job-check.json), [relaunch](evidence/runtime-relaunch.json), [schema](evidence/after-openapi.json), [source/environment](evidence/source-environment.json); applicability receipt above | Actual host process and original DB/Gallery roots; retained OpenAPI/persistence. Correction rechecks process/source/config/schema equality only. No service mocks or health-derived source claim. |
| D2 — supported consumed locators and original bytes | manual | P1 | Reused AID-151 result and round-1 QA PASS: [baseline before](evidence/baseline-before-retrieval.json), [baseline after](evidence/baseline-after-retrieval.json), [original](evidence/original-retrieval.json), raw stdio/byte events unchanged | Recorded stdio metadata then actual `Path(returned local_path).read_bytes()`/Pillow outside MCP. Locator code unchanged; no new retrieval journey or conditional locator regression case. Existing byte payloads rehashed for packaging. |
| D3 — fresh original/revision with stored lineage | manual | P1 | Reused AID-151 result and round-1 QA PASS: [flow](evidence/fresh-flow.json), [raw stdio](evidence/stdio-fresh.jsonl), [persisted round trip](evidence/persisted-roundtrip.json), [stored pair](evidence/fresh-persisted-db-rows.json); new [aggregate audit](evidence/correction-1/schema-value-audit.json) | Historical real MCP → Backend → local ComfyUI → persistence/bytes; existing pair preserved. Correction generates nothing. Original graph caching remains disclosed below. |
| D4 — applicable regressions/full checks | test | P1 | Reused unchanged-source AID-151 checks: Backend `1900 passed, 124 skipped, 76 warnings in 44.12s`; MCP `314 passed, 4 skipped in 1.20s`, both exit 0. [Backend command](evidence/backend-suite.json)/[log](evidence/backend-suite.log), [MCP command](evidence/mcp-suite.json)/[log](evidence/mcp-suite.log). Independent round-1 QA also PASS; applicability receipt above | Existing offline suites/mocks, isolated roots and `--timeout=60`; no suite rerun in correction. Source, tests, dependency packages and platform are equal; only evidence/cwd/scratch context differs. No feature test changed/removed. |
| D5 — inspectable exact delivery / distinct baseline | manual | P1 | Corrected Coding delivery: this manifest, [interventions](evidence/repair-interventions.md), [schema audit](evidence/correction-1/schema-audit.md), [call index](evidence/stdio-call-index.md), refreshed integrity index and new exact-candidate uploads on AID-153 | Read-only real SQLite before/after schema and aggregate preservation, docs and package checks. Independent round-2 exact-commit verdict still required; no acceptance implied. |

## Runtime diagnosis and correction

Old PID `38433` listened on `127.0.0.1:8001`, with canonical `backend/` cwd, system Python 3.11 and a mixed Hermes/Homebrew `PYTHONPATH`. Its loaded Git commit and exact loaded package versions remain unknown. It had no live `GenerateRequest.revision_context` or `RevisionContextRequest`, and baseline status/Gallery context was null. Current checkout/cwd could not identify imported code.

Read-only inspection independently corroborated the active database through open handles and Gallery through the existing artifact response. Effective current canonical Settings were evaluated under the old process environment, then pinned in a private worktree `.env`. This preserves resolved defaults as well as configured paths; it does not reconstruct every unknown old imported default. The relaunch precheck asserted complete resolved-Settings equality using the dedicated Backend environment.

| Setting | Preserved value |
|---|---|
| Database | `sqlite:////Users/tf00185088/Desktop/tim-project/ai-drawing/auto_draw.db` |
| Gallery | `/Volumes/AI-Drawing-16T/ai-drawing/gallery` |
| Output | `/Volumes/AI-Drawing-16T/ai-drawing/backend-outputs` |
| Training / watcher | `/Volumes/AI-Drawing-16T/ai-drawing/training/lora` |
| Prompt Library | `/Users/tf00185088/Desktop/tim-project/ai-drawing/prompt_library` |
| Backend / ComfyUI | `http://127.0.0.1:8001` / `http://127.0.0.1:8188` |

Complete non-secret settings, private configuration hashes and model/data/cache/tool paths are in the runtime receipts. Canonical `.env` remains byte-identical. A private SQLite backup remains at canonical `data/backups/aid-151-before.sqlite`; no private config/environment/database is committed or uploaded.

Immediately before the original SIGTERM, Backend generation queues and ComfyUI queues were empty, and trainer status was idle with no current/queued jobs. The database had 408 old nonterminal training rows; these were not an active in-memory queue. No matching training subprocess existed. All 419 training rows retain identical values in every preexisting column; their schema gained eight nullable columns, as inventoried below. No training was started or resumed.

After observing old-process exit, the relaunch started PID `392` at `08:52:20 UTC` with:

```text
/Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
cwd=/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-151-runtime-retrieval/backend
PYTHONPATH=<that cwd>
PYTHONNOUSERSITE=1
```

The tracked source was clean at the full base SHA. The live schema contains both revision contract elements. Existing `app.main` startup calls `init_db`; model registration and `Base.metadata.create_all` create missing tables/indexes, then `_ADDITIVE_COLUMNS` adds missing nullable fields. That ordinary startup changed more than image revision schema; the initial inventory omitted its training/reservation footprint.

| Observed schema addition | State at correction audit, 2026-11-24 09:20:47 UTC |
|---|---|
| `generated_images.revision_context_json` (`TEXT`, nullable, no default) | NULL in all 4447 preexisting rows, including baseline; populated only for the two delivered images. No old lineage backfill. |
| `lora_training_jobs.output_name`, `resolved_output_name` (`VARCHAR(256)`); `output_serial` (`INTEGER`); `run_locator` (`VARCHAR(512)`); `output_config_hash`, `output_sha256` (`VARCHAR(64)`); `validation_status`, `registration_status` (`VARCHAR(32)`) | All eight nullable/no-default fields are NULL across all 419 preexisting/current training rows. Equality in old columns does not mean unchanged training schema. |
| New `lora_output_reservations` table | Empty (0 rows); seven NOT NULL columns `job_id`, `requested_name`, `request_key`, `resolved_name`, `resolved_key`, `serial`, `run_locator`. PK `job_id`, unique `(request_key, serial)`, `resolved_key`, `run_locator`; index `ix_lora_output_reservations_request_key` and four SQLite constraint autoindexes `_1`–`_4`. Full DDL is in the schema receipts. |

The [read-only correction audit](evidence/correction-1/schema-audit.md) compares every table, column and schema object against the retained private prelaunch backup. No tables/columns/objects were removed; no preexisting column definition changed. Only the two altered table CREATE statements and the above new table/five indexes differ. Every old value in all 14 preexisting user tables is preserved; only the expected two image/two artifact rows were added. This agrees with QA's schema/count audit, with no later difference observed at the stated snapshot. The backup hash still matches the original relaunch receipt. No database write/rollback/restart was used to obtain this evidence.

No active-work recovery was needed in the original execution. The active runtime worktree and canonical Backend venv remain service dependencies; retain them until a reviewed deployment replaces it. Runtime log: canonical `data/logs/aid-151-runtime.log`, with the unchanged historical [snapshot](evidence/backend-runtime.log).

## Retrieval and real pair

The earlier URL exception happened locally before HTTP. Both Gallery tools already supplied usable absolute host paths. The bounded correction sets the Mac client's `MCP_GALLERY_DIR` to the actual Gallery root and consumes each tool's returned `local_path` without alteration. Both tools' URL fields remain unchanged, including existing absolute URLs and relative `/gallery/...` URLs. No endpoint failure or URL normalization fix is asserted. Remote clients without access to these host paths remain outside this proof.

Every byte read was a separate operation outside MCP, recorded with timestamp, exact consumed locator, length, SHA-256 and successful PNG decode. No alternate file was copied to make retrieval pass. Packaging copies for the uploaded evidence archive occur only after those successful reads and are hash-checked against their receipts.

| Role | Backend job | Image ID | Canonical artifact ID | Bytes / decoded format | SHA-256 |
|---|---|---:|---:|---|---|
| Preserved baseline | `88891201-d6c1-4fad-a40d-98622b32f0ed` | 4447 | 3862 | 241339 / PNG RGB 512×512 | `3205fe71ff38759cea79116947af7342275be3b778c034f415e2462e32fd96bc` |
| Fresh original | `8b826d11-5f52-4972-bbe2-1d0909fc20f9` | 4448 | 3863 | 241339 / PNG RGB 512×512 | `3205fe71ff38759cea79116947af7342275be3b778c034f415e2462e32fd96bc` |
| Fresh revision | `08955297-4723-477c-875e-7f234a71a4da` | 4449 | 3864 | 221328 / PNG RGB 512×512 | `f86f0daf4aa9b36041189ab742d098f08034578b79018564bbaab2d105f8e644` |

The stdio journey used `Illustrious-XL-v2.0.safetensors`, `default`, `execution_target=local`, `loras=[]`, 512×512, batch 1, fixed seed `20261124`, 20 steps, CFG 7, Euler/normal. Original prompt: `still life, a red ceramic cup on a wooden table, soft daylight, simple background`; negative `low quality, blurry`. Revision changes `red ceramic cup` to `blue ceramic cup`, with technical feedback reference `AID-151:technical-feedback:1`. This feedback tests the revision contract; it is not CTY's aesthetic judgment.

Shared new request reference: `AID-151:p1-00a:2026-11-24`. Briefs are `original` and `revision`. The new revision generate request supplies only parent artifact `3863` plus feedback; Backend-derived fields are `parent_job_id=8b826d11-5f52-4972-bbe2-1d0909fc20f9`, the same parent request reference and `parent_brief_revision=original`, with `parent_context_status=available`. Status, image Gallery, canonical-artifact Gallery and raw stored DB rows agree.

[ComfyUI history](evidence/comfyui-fresh-history.json) reports new successful prompts `7062519c-f4fa-4ea0-bb05-b34ca622e4d5` (original) and `be0043f7-3a8e-475c-bad8-5fa209ea437c` (revision). The unchanged deterministic original graph was fully cached; that explains its identical bytes and original ComfyUI filename. The Backend submitted a new prompt and recorded a new job/image/artifact with new context. The revision cached only nodes 4/5/7 and produced different bytes. No forced cache flush or extra generation was performed.

Original required two status calls, revision three; three repeated polls used 10-second waits. No timeout, resubmission, cancellation or hidden repair occurred during the pair. A second current-tool stdio session retrieved both persisted results and the preserved baseline again. Twelve byte reads succeeded across the before/fresh/persisted sessions.

## Offline verification and changes

The reused suites ran in the original `aid-151-runtime-retrieval` worktree at `08:53:01–08:53:47 UTC`, with the existing dedicated component interpreters; source/dependency snapshots are retained. That execution installed `pytest-timeout==2.4.0` into its run-scratch `timeout-plugin` with `uv pip install --target ... --no-deps`, and added that directory to test `PYTHONPATH`, leaving both venvs unchanged. Both independent test roots were below injected `TMPDIR`; `MCP_TEST_PYTHON` named the separate MCP interpreter. Exact commands, environment, UTC start/end, wall time and exit codes remain in the original command receipts. No full suite or timeout installation was repeated for this evidence-only correction.

Backend wall time 45.441s (pytest 44.12s); MCP wall time 1.444s (pytest 1.20s). All 124 Backend skips require Windows, as listed in `-ra`; the four MCP skips require separately exported Backend HTTP/lifecycle fixtures. No skip/expectation changes were made. Live persisted lineage is separately demonstrated; offline mocks or skips are not substituted for that proof. No Frontend, Windows or worker acceptance result is implied.

Original committed changes (retained): manifest/evidence, `docs/mcp.md` for the supported Mac path/client boundary, and `docs/setup.md` for existing-host relaunch provenance/preservation. Original runtime/private changes: one copied/pinned worktree `.env`, private SQLite snapshot, controlled Backend replacement, client Gallery configuration, runtime log, **the complete additive schema footprint above**, and two authorized jobs' image/artifact rows and Gallery copies. No old output/record was edited or removed.

Correction changes: this manifest, the intervention inventory, read-only schema/value and applicability receipts/source, QA comparison, and refreshed evidence checksums/package identity. The original `persistence-audit.json`/source and `delivery-audit.json` are unchanged historical records of narrower checks; their training equality means old-column equality. Original checksums are preserved in [aid-151-checksums.json](evidence/correction-1/aid-151-checksums.json); [checksums.json](evidence/checksums.json) now covers all current evidence except itself. No product, test, workflow or topic-doc changes were added by correction, and no runtime/configuration mutation occurred. New audit output contains schema, counts and aggregate hashes only; private snapshots/configuration and historical table contents are excluded.

Correction checks: complete SQLite audit exit 0; QA schema/count reconciliation; source/test/task/baseline/runtime/package equivalence exit 0; evidence checksums and exact archive/patch/upload read-back checks in the new external delivery receipt. One scratch applicability assertion initially included later review/acceptance files in the earlier baseline commit; the corrected check separately verifies its 20 original files and all delivered baseline files. This was a read-only recorder correction, with no runtime/data effect. No newly scoped product blocker was found. Independent QA round-2 PASS is still unmet pending review, and Producer retains acceptance/release ownership.

Preexisting failing tests: none observed; both full suites exited 0. No approach requiring a source replacement was pursued. Preparation failures and the comparison adjustment for the nullable startup column are disclosed in the intervention record. There are no source deviations from the cleared task. Scratch client/check sources are retained as evidence text, not a permanent smoke framework.

## Baseline separation and remaining mappings

Accepted baseline execution `3081952e0ba12a339ab7e60b8081ede61a131b7f` and QA `c377a02c808589b225a6d5f386d7e47cc865b939` remain unchanged: **23 intervention units across eight incidents**, no repairs, no retrieved bytes or revision at measurement time. The baseline job/image/artifact ID namespaces remain distinct. This repair does not revise that count or reinterpret its no-repair outcome.

| Baseline incident | Repair resolution / continuing owner |
|---|---|
| F4 — runtime identity | This bounded launch has exact source/process/configuration evidence. General health/runtime visibility remains p1-04. No attestation subsystem added. |
| F5 — missing revision contract | Known-source relaunch exposes the schema and stores new original/revision context. Old baseline stays legacy/null. |
| F8 — local relative-URL exception | Resolved for the actual colocated Mac client via unmodified returned `local_path` from both tools. Relative URL and remote delivery design remain unchanged. |
| F1 — timeout/test setup | Still a scratch timeout-plugin setup; p1-05 run-guide/setup coverage, packaging only if Producer separately scopes it. |
| F2 — stdio/client binding | Explicit interpreter/source/URL/Gallery binding and scratch recorder still required; p1-05. |
| F3 — mixed formats | Client still branches for plain text and JSON strings; p1-01/02. |
| F6 — polling | Three repeated polls in this pair; wait tool remains p1-03. |
| F7 — coarse execution visibility | Direct read-only ComfyUI queue/history checks are disclosed; combined visibility remains p1-04, wait/result reporting p1-03. |

Known limits: one Mac/checkpoint/template, one fresh pair, colocated filesystem client, cached deterministic original. No zero-intervention benchmark, three-run exit, aesthetics, owner demo, phase closure or dependent release is claimed. Producer on [AID-142](/AID/issues/AID-142) coordinates independent exact-commit delivery QA and acceptance before merge/push.
