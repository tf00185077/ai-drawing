Verdict: PASS
Review round: 2

Reviewed commit: `b6d58468147e11a21b3d7a26ea25ed4353a28a28`
Prior delivery rejections: **1**. Correction round: **1**.
Rejected round-1 candidate: `00ebb4d73edf3efe54943f3e2d784200e3023cab`.
Fixed cleared specification: `4ac3d5653d7bffee2698809d32d0f5ea0f506cbc`.
Runtime launch source: `eaf11b8f75fb573db3d0a4e858973d59385b5087`.
Review date: 2026-11-24 UTC. QA: [AID-154](/AID/issues/AID-154); corrected delivery: [AID-153](/AID/issues/AID-153).

All original D1–D5 pass at this exact candidate. The correction closes F-QA1 by accounting for the complete observed startup schema footprint and distinguishing preservation of old values from additive schema changes. D1–D4 reuse applicable independent round-1 evidence; this review repeats the read-only schema audit, applicability and delivery-integrity checks. No software suite, restart or generation was repeated. Producer on [AID-142](/AID/issues/AID-142) owns acceptance, integration and dependent release.

The [round-1 FAIL report](/api/attachments/eeb8dc51-4575-4b5c-896e-590710bdfba2/content), [original independent archive](/api/attachments/e2e83594-d20b-4576-981f-5f31587a738f/content) and report commit `537d47f8194c306b54c61fe2eacdae262afeece0` remain unchanged on [AID-152](/AID/issues/AID-152). PASS here does not reset that rejection history. The new [QA receipts](evidence/qa-round-2/) record the checks below; the same files are supplied in the AID-154 upload.

## Findings

No blocking defect found. **F-QA1, P1/D5: resolved at the reviewed candidate.** Both the manifest and intervention inventory now name the image revision column, all eight nullable training columns, the new reservation table and its five indexes, their observed state, audit time and existing-source cause. Neither asserts unchanged training schema. The original narrower persistence evidence remains intact and is explicitly identified as an old-column value comparison.

The bounded correction changes 18 task-document/evidence files, with parent exactly `00ebb4d73edf3efe54943f3e2d784200e3023cab`. No product, test, workflow, dependency or topic-doc change is introduced by correction. The original task remains byte-identical to the cleared specification; correction assignment `c41815c25d2e6139f65c058ab1a8750bbecc6659` was read as a fixed Git object. No scope expansion or unexpected source/runtime/data change was observed.

## Done when outcomes

| Item | Level | Outcome | Evidence and limits |
|---|---|---|---|
| D1 — identified runtime and revision contract | P1 | PASS | Reuse round-1 independent process/source/configuration, launch/active-job receipts, live OpenAPI and persisted-contract observations. New read-only applicability checks confirm PID 392, creation time, cwd/command/import environment, canonical DB handle, clean tracked runtime source, 364 component fingerprints, configuration hashes and relevant live schemas unchanged. Old pre-relaunch loaded source remains unknown. |
| D2 — consumed supported locator and original bytes | P1 | PASS | Reuse round-1 actual stdio Gallery metadata followed by unmodified returned `local_path` reads and Pillow decodes for baseline/original. Locator implementation and client binding are unchanged. Existing archived payloads were independently rehashed and decoded this round; that is archive verification, not a new live locator journey. No locator code changed, so the conditional locator-change regression requirement is inapplicable. |
| D3 — fresh original/revision with stored lineage | P1 | PASS | Reuse inspected original raw stdio, real local ComfyUI histories, status/Gallery/SQLite reconciliation and independent byte reads. Fresh original job `8b826d11-5f52-4972-bbe2-1d0909fc20f9` / image 4448 / artifact 3863 and revision `08955297-4723-477c-875e-7f234a71a4da` / image 4449 / artifact 3864 share request `AID-151:p1-00a:2026-11-24`; revision uses canonical parent artifact 3863 and Backend-derived parent fields. Current audit matches the delivered schema and typed value aggregates, including the existing pair. This is a completed journey; no documented-blocker alternative is used. |
| D4 — applicable regression/full checks | P1 | PASS | Reuse independent full Backend and MCP results from round 1, with source/test/root test-input/package/platform equivalence checked anew. Backend 1900 passed, 124 skipped, 76 warnings, 42.40s; MCP 314 passed, 4 skipped, 1.10s; both exit 0 with `--timeout=60` and separate isolated roots below TMPDIR. Existing registry Backend guard is included in this reused run. No feature tests were changed/removed. |
| D5 — full inspectable inventory and exact delivery | P1 | PASS | Independently downloaded all seven new Coding deliverables; verified manifest, both patches, 90 committed archive files, three fixed references, 59 evidence checksum entries, archive inventory and three image payloads. Repeated full read-only schema/value audit agrees with correction and round-1 reference results. Full runtime footprint and baseline separation are now explicit. |

## Read-only schema and preservation verification

Coding's correction snapshot is `2026-11-24T09:20:47.402796+00:00`–`09:20:47.770053+00:00`. QA reviewed its recorder source and repeated it against the actual canonical `auto_draw.db` and retained private `data/backups/aid-151-before.sqlite`, using SQLite `mode=ro`, `query_only`, explicit read transactions and SELECT/PRAGMA only. It imports no application/startup code and performs no database write. QA's run was `2026-11-24T09:33:58.941714+00:00`–`09:33:59.305967+00:00`, exit 0. Only audit timestamps differ from Coding's schema/value receipt; schema objects, row counts, typed aggregate hashes and added-field states match exactly. No later state delta was observed.

The backup's SHA-256 remains `2dde3591a87464e34beee7e9457bd16d7b322e1b4e7367a6dfa1623d1340d00b`, equal to the original prelaunch receipt and unchanged after QA reads.

- `generated_images.revision_context_json`: nullable TEXT, no default; all 4447 old rows remain NULL and only the two delivered rows are non-NULL.
- `lora_training_jobs`: added nullable/no-default `output_name`, `resolved_output_name`, `output_serial`, `run_locator`, `output_config_hash`, `validation_status`, `output_sha256`, `registration_status`; each remains NULL across all 419 rows.
- `lora_output_reservations`: new empty table, seven NOT NULL columns, primary key `job_id`, uniqueness on `(request_key, serial)`, `resolved_key`, `run_locator`; one named index and four SQLite constraint autoindexes.
- No removed tables, columns or schema objects; no old-column definition changed. Only the two extended table CREATE statements changed. Every preexisting value across 14 user tables is preserved in its old columns. Row-count increases are exactly two images and two artifacts. Internal `sqlite_*` table values are outside the stated value audit; schema objects are included.

Existing `backend/app/main.py` invokes `init_db`; model registration plus `Base.metadata.create_all` creates the missing reservation table/indexes, and `_ADDITIVE_COLUMNS` adds the nullable fields. QA inspected these existing source paths without invoking them. The three quoted round-1 audit extracts are byte-identical to the official independent archive and its checksum index. New receipts publish schema, aggregates and hashes, with no database, private configuration or historical row contents.

## Applicability and package verification

QA used isolated branch `aid-154-exact-review` at `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-154-qa`. The shared main checkout and active runtime worktree were left untouched. Exact Backend and MCP tree IDs match candidate, rejected delivery, round-1 QA, cleared specification, original baseline and runtime base. The 364 tracked fingerprints also match the actual active runtime. Root test inputs, both interpreter versions/package inventories (34 Backend packages, 39 MCP packages), platform, private configuration hashes, process identity and revision schemas remain equivalent. All 43 retained original raw evidence files and 20 original baseline files match their fixed references. This supports the explicit reuse boundary; cwd/healthy ping alone is not the proof.

New Coding archive: 1,295,589 bytes; SHA-256 `da2a70f6bb2e9f702f3975100a294649d8dbe211054b5bb52e8d482cd8ed1ca9`. It has 99 files: 90 match the exact Git candidate, three reference files match named immutable Git objects, both patches equal Git output, and three PNG payloads decode correctly. The receipt's 98 non-self inventory entries match every corresponding archive member. The uploaded standalone manifest equals Git; the correction patch equals `git format-patch -1 <candidate> --stdout`; the complete series equals `git format-patch --stdout <runtime-base>..<candidate>`. Every outgoing Coding checksum and all 59 committed evidence entries verify. All seven uploads were read back independently.

Archived baseline/original PNGs are each 241339 bytes, SHA-256 `3205fe71ff38759cea79116947af7342275be3b778c034f415e2462e32fd96bc`; revision is 221328 bytes, SHA-256 `f86f0daf4aa9b36041189ab742d098f08034578b79018564bbaab2d105f8e644`. All decode as RGB PNG 512×512. Baseline and original identical bytes reflect the disclosed cached deterministic original graph; they still have different new Backend/ComfyUI identities. This is not another uncached diffusion computation.

The original independent archive was read back at 63004 bytes, SHA-256 `4ab81ac4332ec1a68df63033bfb1cc860c2a2422f13d2dbff8e949c07130f5b2`; all its indexed entries verify, and its official report equals Git. Known private credentials were checked against outgoing evidence without publishing their values.

## Commands and results

New check sources and exact receipts are in `evidence/qa-round-2/`. The substantive new commands were:

```sh
python "$PAPERCLIP_RUN_SCRATCH_DIR/qa-round2-verify.py"
python3 docs/tasks/p1-00a-mac-runtime-and-retrieval/evidence/correction-1/schema-audit.py.txt \
  /Users/tf00185088/Desktop/tim-project/ai-drawing/data/backups/aid-151-before.sqlite \
  /Users/tf00185088/Desktop/tim-project/ai-drawing/auto_draw.db \
  "$PAPERCLIP_RUN_SCRATCH_DIR/qa-round2/schema-repeat"
python3 <reviewspec-review>/scripts/build_registry.py
```

The first two exited 0; exact interpreter/path/times are in their receipts. Supplementary archive-inventory, fixed-object, checksum and credential checks passed. The registry builder is run after this report; its saved receipt records the structural outcome. No production mutation experiment applies because neither this correction nor the original delivery changed product code. No hidden fix was made. QA interpreter-discovery failures and their harmless resolution are retained in `preparation-notes.md`.

Reused suite command receipts/logs retain the full arguments and environment. Both ran independently in the AID-152 worktree with `-m pytest -c pytest.ini <component>/tests -q --timeout=60 -ra`, component interpreters, `PYTHONNOUSERSITE=1`, separate `AI_DRAWING_TEST_ROOT` paths below the injected TMPDIR, and a scratch-only timeout plugin. Backend wall time 43.653s; MCP 1.282s. Backend skips require Windows; four MCP skips require exported HTTP fixtures. These are disclosed exclusions. This evidence-only correction changes no relevant test input, so another full suite would add no task-relevant proof.

## Verification boundaries and notes

- **Offline tests:** reused applicable independent Backend/MCP full suites, including the standing registry guard. New scripts checked integrity, equivalence and schema aggregates. No new Frontend/build, Windows, worker or training result.
- **Running service:** new read-only process/configuration/source/live-schema and actual-DB checks. Historical idle-queue check and controlled restart rely on inspected original receipts and round-1 review; neither was repeated.
- **Real generation:** original delivered pair and independent round-1 ComfyUI reconciliation reused. No new generation. The cached original remains disclosed.
- **Artifact retrieval:** prior independent unmodified returned-host-path reads reused. New work decodes archived payloads only. Relative URL consumption and remote clients lacking host filesystem access remain outside the proof.
- **Errors, cancellation, recovery, duplicates:** no live timeout/resubmission/cancellation/recovery was exercised in this delivery. Applicable validation/error tests passed in the reused suite. The API is not certified idempotent; future timeout handling must inspect the existing job before resubmission.
- **Security/data:** origins remain loopback, no worker control was exposed, no message/model/download/training operation occurred, and no database/configuration/source/runtime repair or cleanup was performed. Keep the active AID-151 runtime worktree and canonical Backend venv until a reviewed deployment replaces them.

The preserved no-repair baseline stays **23 intervention units across eight incidents**, legacy/null context and its original unsuccessful retrieval/revision outcome. Repair interventions remain separate. F4 is resolved for the identified launch, F5 for new persisted revision context, and F8 for the colocated filesystem client. F1/F2 environment binding, F3 mixed responses, F6 polling and F7 execution visibility retain their documented later-task mappings. No three-run exit, aesthetic/owner-demo judgment, phase close, merge or push is certified. Any later candidate change needs another exact-commit review.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D4 | P1 | backend/tests and mcp-server/tests (full suites with --timeout=60; unchanged-source evidence reused) | active |

No earlier behavior is superseded. The existing baseline D1 Backend guard remains covered by the same applicable full-suite evidence.
