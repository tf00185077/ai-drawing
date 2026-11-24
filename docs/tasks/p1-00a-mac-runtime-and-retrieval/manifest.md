# p1-00a Mac runtime and retrieval repair

[AID-151](/AID/issues/AID-151), 2026-11-24 UTC. The bounded journey succeeded through a known-source Backend, existing Gallery local paths, and one fresh original/revision pair with decoded bytes and persisted canonical-artifact lineage. This is a runtime/client-configuration/documentation delivery; no product source or tests changed. Independent exact-commit QA and Producer acceptance remain pending.

## Source and delivery identity

- Fixed cleared specification: `4ac3d5653d7bffee2698809d32d0f5ea0f506cbc`; task SHA-256 `be8814ca4f3bbaaa16e14f8a7b236a1fd5c34d0d1cd4a2ee88570631bea06359`. [QA kickoff](/AID/issues/AID-150#comment-0160c15e-8db0-43dc-a1de-a4b94af6b51b) is in QA commit `9bd002968c77484fba89e1d2b59cd021b30b939d`, also available on [AID-150](/AID/issues/AID-150).
- Implementation/runtime base: published `eaf11b8f75fb573db3d0a4e858973d59385b5087`.
- Isolated worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-151-runtime-retrieval`; branch `aid-151-runtime-retrieval`. The shared checkout stays on `main` and was not edited by this execution.
- Delivery commit: the commit containing this manifest (`git log -1 --format=%H -- docs/tasks/p1-00a-mac-runtime-and-retrieval/manifest.md`). Its full final SHA is in AID-151's completion and the uploaded delivery receipt; the commit cannot contain its own hash. The upload contains exact committed files, patch, integrity receipt and byte evidence.
- Backend/MCP source trees are identical to accepted baseline execution `3081952e0ba12a339ab7e60b8081ede61a131b7f`. [Source/environment receipt](evidence/source-environment.json) fingerprints 364 tracked component files and records both interpreters/packages. The final delivery changes docs/evidence only. No merge or push was performed.

## Done when

| Item | Check | Level | Result and evidence | Layer / real boundary |
|---|---|---|---|---|
| D1 — identified clean runtime and revision contract | manual | P1 | Satisfied: [before](evidence/runtime-before.json), [immediate active-job check](evidence/restart-active-job-check.json), [relaunch](evidence/runtime-relaunch.json), [live schema](evidence/after-openapi.json), [source/environment](evidence/source-environment.json), persisted round trip below | Actual host process and original DB/Gallery roots; current OpenAPI and persisted generation. No service mocks or health-derived source claim. |
| D2 — supported consumed locators and original bytes | manual | P1 | Satisfied: [baseline before](evidence/baseline-before-retrieval.json), [baseline after](evidence/baseline-after-retrieval.json), [original](evidence/original-retrieval.json), complete raw stdio and byte events | MCP metadata over stdio, then actual Mac client `Path(returned local_path).read_bytes()` and Pillow decode outside MCP. Locator code unchanged; conditional locator-change regression requirement does not apply. |
| D3 — fresh original/revision with stored lineage | manual | P1 | Satisfied: [fresh flow](evidence/fresh-flow.json), [raw stdio](evidence/stdio-fresh.jsonl), [second-session round trip](evidence/persisted-roundtrip.json), [stored DB rows](evidence/fresh-persisted-db-rows.json), [audit](evidence/persistence-audit.json) | Actual current MCP → known Backend → local ComfyUI → stored image/artifact rows and consumed bytes. New jobs, no rerun or replay of a Backend job; ComfyUI's identical original graph uses its existing cache, disclosed below. |
| D4 — applicable regressions/full checks | test | P1 | Satisfied: full Backend `1900 passed, 124 skipped, 76 warnings in 44.12s`; full MCP `314 passed, 4 skipped in 1.20s`; both exit 0. [Backend command/timing](evidence/backend-suite.json), [log](evidence/backend-suite.log); [MCP command/timing](evidence/mcp-suite.json), [log](evidence/mcp-suite.log) | Existing offline suites with their existing mocks, isolated scratch roots and `--timeout=60`. No new source behavior/test cases, changed expectations, removed tests or concealed failures. Real boundaries separately verified above. |
| D5 — inspectable exact delivery / distinct baseline | manual | P1 | Satisfied by this manifest, [intervention record](evidence/repair-interventions.md), [call index](evidence/stdio-call-index.md), integrity index and exact-commit uploaded archive/patch/receipt on AID-151 | Reviewable files and uploaded byte evidence. Producer/independent QA owns acceptance; this delivery does not change the coordinator's disposition. |

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

Immediately before SIGTERM, Backend generation queues and ComfyUI queues were empty, and trainer status was idle with no current/queued jobs. The database had 408 old nonterminal training rows; these were not an active in-memory queue. No matching training subprocess existed. All 419 training rows compare byte-for-value equal after relaunch; no training was started or resumed.

After observing old-process exit, the relaunch started PID `392` at `08:52:20 UTC` with:

```text
/Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
cwd=/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-151-runtime-retrieval/backend
PYTHONPATH=<that cwd>
PYTHONNOUSERSITE=1
```

The tracked source was clean at the full base SHA. The live schema now contains both revision contract elements. The normal source startup added the nullable `generated_images.revision_context_json` column to the existing database. Every preexisting baseline field is identical before/after; the new field stays NULL. No old lineage was backfilled. No active-work recovery was needed. The worktree and canonical Backend venv remain dependencies of this running service; retain them until a reviewed deployment replaces it. Runtime log: canonical `data/logs/aid-151-runtime.log`, with a retained [snapshot](evidence/backend-runtime.log).

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

Both suites ran at this worktree with the existing dedicated component interpreters; source/dependency snapshots are retained. To supply the required timeout without modifying either venv, install `pytest-timeout==2.4.0` into run-scratch `timeout-plugin` with `uv pip install --target ... --no-deps`, and add that directory to test `PYTHONPATH`. Both independent test roots are below injected `TMPDIR`; `MCP_TEST_PYTHON` names the separate existing MCP interpreter. Exact commands, environment, UTC start/end, wall time and exit codes are in the command receipts.

Backend wall time 45.441s (pytest 44.12s); MCP wall time 1.444s (pytest 1.20s). All 124 Backend skips require Windows, as listed in `-ra`; the four MCP skips require separately exported Backend HTTP/lifecycle fixtures. No skip/expectation changes were made. Live persisted lineage is separately demonstrated; offline mocks or skips are not substituted for that proof. No Frontend, Windows or worker acceptance result is implied.

Committed changes: this manifest and bounded evidence; `docs/mcp.md` documents the supported Mac path/client boundary, and `docs/setup.md` documents existing-host relaunch provenance and preservation. Runtime/private changes: one copied/pinned worktree `.env`, retained private SQLite snapshot, controlled Backend replacement, client Gallery configuration and log file. No component source, test, workflow, model, dataset or old output/record was edited or removed. Two authorized generation jobs added their new records and Gallery copies through normal Backend recording.

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
