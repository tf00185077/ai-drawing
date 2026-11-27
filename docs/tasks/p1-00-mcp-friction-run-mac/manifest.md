# p1-00 Mac friction baseline — execution evidence

Execution completed on 2026-11-24 for [AID-148](/AID/issues/AID-148), coordinated by [AID-142](/AID/issues/AID-142). **The offline suite passed with existing skips; the product journey stopped at a documented retrieval blocker. This is not a passing end-to-end baseline or Phase 1 exit.** No repairs were made.

## Fixed source and handoff

- Approved source/specification: `e443f2e22a17f3ca61f69527bdd392e703b0e88b`.
- Worktree: `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-148-p1-00`.
- Branch: `aid-148-p1-00-evidence`. The evidence commit is the commit containing this manifest; resolve with `git rev-parse aid-148-p1-00-evidence`. Its full SHA is recorded in the Coding issue completion comment and uploaded bundle receipt.
- Shared checkout: `/Users/tf00185088/Desktop/tim-project/ai-drawing`, left on `main`. Concurrent Producer documentation edits and QA's untracked kickoff review were preserved; they were not copied into this branch.
- The actual CLEAR kickoff comment was read before the stdio run. This evidence requires independent review of the exact evidence commit. No merge or push was performed.
- This commit adds only this manifest and evidence under this task folder. No software, tests, graphs, model files, datasets, output files or Gallery records were edited, removed or quarantined. The authorized generation created one new output and its records.

## Done when evidence

| Item | Check | Level | Result / evidence | Layer and real boundary |
|---|---|---|---|---|
| D1: full Mac Backend suite, no failures/hangs | test | P1 | Exit 0; `1900 passed, 124 skipped, 77 warnings in 43.84s`. Full output, command/timing | Full offline Backend suite at the fixed source, isolated scratch database/files. Tests use their existing mocks; this is not live generation proof. |
| D2: retrieved original and revision, or documented blocker | manual | P1 | Documented blocker route: original completed and both Gallery metadata tools succeeded; image byte fetch failed locally on a relative URL. Revision not submitted. Raw ordered stdio, index, flow summary | Actual current-source MCP subprocess over stdio → existing host Backend → local ComfyUI → real Gallery metadata. No service mocks. |
| D3: complete friction log with task mappings | manual | P2 | Eight incidents below, with actions and counts; measurement/handoff overhead also disclosed | Source/environment inspection, actual tool responses and non-MCP diagnostics. |
| D4: state baseline count | manual | P2 | **23 manual intervention units across 8 incidents**, including 11 repeated status calls. Machine-readable count | Observed run and disclosed setup/diagnostics, not a projected count. |

## Offline suite and environment

The full suite ran first, before any live-service probe or generation in this execution. UTC start `08:09:54.195409`, end `08:10:44.168967`; wall duration **49.973s**, pytest duration **43.84s**, exit **0**. The exact executable and environment paths are in `backend-suite.json`.

```sh
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend-tests" \
MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python \
"$PAPERCLIP_RUN_SCRATCH_DIR/backend-venv/bin/python" \
  -m pytest -c pytest.ini backend/tests -q --timeout=60
```

The task-owned test root was below the injected `TMPDIR`/Paperclip run scratch directory. A separate Python 3.11.15 Backend environment was created there from unchanged `backend/requirements.txt` plus `pytest-timeout==2.4.0`. Existing Backend and MCP environments lacked pytest-timeout; neither was modified. The existing separate MCP environment (Python 3.10.20, MCP SDK 1.26.0) was used for cross-layer subprocess tests and stdio. Package versions and source/checkout state are retained in environment.json; installation commands/output are in environment-setup.log.

Limitations: dependencies other than the repository's explicit pins resolved to the available versions listed in the environment snapshot. The 124 existing skips were not changed. The quiet command did not print per-test skip reasons; no claim is made that those tests executed. Source contains Windows-only skip conditions, but this report does not attribute every skip without per-test evidence. This Mac result is not equivalent to CURRENT's earlier Windows `2018 passed, 6 skipped` result. No full MCP suite, Frontend suite/build or Windows worker acceptance run was requested or performed here.

## Running service and source mismatch

MCP `mcp_ping` returned `ok: Backend 連線正常`; it checks Backend `/health` only. Resource listing found the adopted checkpoint and `default` form. Neither response certifies runtime revision or compatibility.

Read-only process inspection found Backend PID `38433`, host Python 3.11 running `uvicorn app.main:app --host 127.0.0.1 --port 8001`, with cwd in the canonical checkout's `backend/`; process start was reported as 2026-09-01. ComfyUI PID `94811` listened on `127.0.0.1:8188`, cwd `/Users/tf00185088/comfyui`, process start reported as 2026-08-27. Docker daemon inspection failed, while both host listeners existed. No service was started, stopped, restarted or reconfigured.

**The exact loaded Backend commit is unknown. A source/runtime contract mismatch is demonstrated:** the live OpenAPI snapshot has no `GenerateRequest.revision_context` property or `RevisionContextRequest` schema, while the fixed source defines both in `backend/app/schemas/generate.py`. The original request explicitly supplied context, but submission, status and Gallery responses all returned null context. Missing schema plus the observed null response supports the inference that the running service did not persist this annotation; it does not identify the service's Git commit. Probe timing and raw-schema hash are retained. No health-derived revision claim is made.

## Actual flow and artifact locators

The stdio session ran from `08:12:24.610244` to `08:14:35.966483` UTC. The ordered index links request/response positions in the complete raw transcript, including initialization, the live tool schemas, stderr, wait events, the retrieval attempt and shutdown. There were **17 tool calls**: ping, resources, one generate, twelve status calls, image metadata, artifact metadata. No tool response was omitted or truncated in the retained transcript.

The generation explicitly used `checkpoint=Illustrious-XL-v2.0.safetensors`, `template=default`, `execution_target=local`, and `loras=[]`. Technical parameters: 512×512, batch 1, seed 20261124 fixed, 20 steps, CFG 7, Euler/normal. Prompt: `still life, a red ceramic cup on a wooden table, soft daylight, simple background`; negative: `low quality, blurry`. Context: `request_ref=AID-148:p1-00:2026-11-24`, `brief_revision=original`. These routine technical choices do not claim aesthetic acceptance.

The saved default graph contains the older `incursiosMemeDiffusion_v16PDXL.safetensors` filename. It was read only; the installed checkpoint was passed explicitly. Graph inspection and the returned artifact's compiled workflow show the distinction. No replacement model was downloaded.

| Field | Observed value |
|---|---|
| Original Backend job | `88891201-d6c1-4fad-a40d-98622b32f0ed`, completed |
| ComfyUI prompt | `615da0b0-fc27-41c2-a312-79b6fc61003f` |
| Image ID / canonical artifact ID | `4447` / `3862` — different namespaces |
| Gallery path | `2026-11-24/ComfyUI_00253_88891201_0.png` |
| Returned image/artifact URL | `/gallery/2026-11-24/ComfyUI_00253_88891201_0.png` (relative) |
| `get_gallery_image` local path | `/Users/tf00185088/Desktop/tim-project/ai-drawing/data/gallery/2026-11-24/ComfyUI_00253_88891201_0.png` |
| `get_gallery_artifact` local path | `/Volumes/AI-Drawing-16T/ai-drawing/gallery/2026-11-24/ComfyUI_00253_88891201_0.png` |
| Backend-reported file size | 241339 bytes; not independently byte-verified |
| Original lineage | Null in submission, status and both Gallery responses |
| Revision | Not submitted; no revision job, artifact or lineage claimed |

The two local paths are returned locators, not a claim that either path was opened or that they resolve differently. Gallery metadata was retrieved through MCP. **Generated image bytes were not retrieved:** the scratch client's external byte-fetch attempt passed the returned relative URL unchanged to `urllib.request.urlopen`, which raised `ValueError: unknown url type`. This was a local URL interpretation failure; no HTTP image request reached the Backend. The original was never resubmitted.

The run stopped here. No URL joining, local-file copy or alternate retrieval was applied to turn the blocked run into a success. The runtime lineage mismatch independently prevents a supported traceable-revision claim. A revision would require a new generate request with the same `request_ref`, a new `brief_revision` and `revision_context.parent_artifact_id=3862`; the image ID 4447 must not be used as that artifact ID. No fabricated revision request/result is included.

## Friction log and Phase 1 baseline count

Counting rule: count each non-MCP diagnostic/retrieval call attempt and each repeated status call beyond the first as one unit; count each distinct environment setup or response-format handling intervention once. A failed call attempt still counts. The eleven waits and their eleven repeated polls are the same interventions, counted once each. Report-only blockers add no extra unit unless an action was taken. This yields **23 units, 8 incidents**. These are agent interventions, with **0 new human confirmations, 0 generation resubmissions and 0 product repairs**. This conservative total includes preflight and post-stop diagnostics; it is not eight successful fixes.

| ID / step | Tool or boundary | What happened | Manual action / outcome | Likely cause | Units | Fix owner/task |
|---|---|---|---|---|---:|---|
| F1 — suite setup | Python/uv outside MCP | Existing environments lacked the required timeout plugin; default `python` belongs to Hermes | Checked component interpreters; created one task-owned Backend venv and installed unchanged requirements plus pytest-timeout. Suite then ran once. Setup | Test environment/timeout dependency is not completely provided by the documented command | 1 | p1-05 run-guide/setup coverage; new test-environment follow-up if Producer requires packaging changes |
| F2 — stdio bootstrap | Local process/environment outside MCP | MCP needs a separate dependency environment and explicit Backend/Gallery configuration; worktree has no preinstalled env | Used existing MCP interpreter, fixed-worktree `PYTHONPATH`/cwd, explicit MCP URLs and Gallery root, plus a scratch JSON-RPC recorder. Transcript process_start, provenance | Per-client host/environment binding is manual; no existing Phase 1 smoke driver | 1 | p1-05 |
| F3 — result parsing | `mcp_ping` vs remaining tools | Ping is plain text; other results contain JSON-encoded strings in MCP text blocks | Client branches between plain text and JSON parsing, instead of a single application envelope. No failed tool retry. Raw transcript | Mixed response formats | 1 | p1-01, shipped with p1-02 |
| F4 — runtime identity preflight | `docker ps`, two listener checks, `ps`, two cwd checks, all outside MCP | Ping cannot establish execution host/source; Docker daemon is unavailable but host services listen | Six read-only process/container diagnostic calls, including the failed Docker query. No repair. Full commands/output | Health exposes connectivity only; source/runtime identity is absent | 6 | p1-04 health visibility; **new proposed task:** runtime revision attestation/alignment, scoped by Producer before p1-05 |
| F5 — source/runtime lineage mismatch | Raw Backend `GET /openapi.json` outside MCP; generate/status/Gallery observations | Live schema omits revision context; explicit original annotation comes back null | One read-only schema call and comparison to fixed source. Record revision blocker; do not restart or patch. Schema probe | Existing host Backend contract differs from approved source; exact loaded revision unknown | 1 | Same new runtime-alignment task as F4; p1-05 must establish compatible deployed source before exit runs |
| F6 — wait for original | `get_generation_status` | Initial queued status, then running statuses without a wait primitive | Eleven 10-second waits and repeated calls on the same job, then completed on the 12th status call. No timeout or resubmission. Call index | No `wait_for_job` | 11 | p1-03 |
| F7 — post-stop queue diagnostic | Direct ComfyUI `GET /queue` outside MCP at `08:14:50` UTC | Needed to distinguish actual ComfyUI activity from Backend's earlier generic running status | One read-only call; running/pending counts both zero after completion. Only this task's prompt identity/counts retained, not unrelated graphs. Inspection | Current status is coarse; no combined execution-state view | 1 | p1-04 visibility / p1-03 result reporting; deeper progress behavior is new if Producer chooses it |
| F8 — byte retrieval, terminal blocker | `get_gallery_image`, `get_gallery_artifact` → external URL-open attempt | Both tools return a relative `/gallery/...` URL; the client cannot open it as an absolute URL | One non-MCP fetch attempt failed locally. No URL rewrite or alternate local-file read applied. No bytes retrieved; no revision submitted. Raw stop event, summary | Tools preserve Backend's relative URL; the scratch client expects a directly fetchable locator | 1 | p1-02 Gallery consolidation, p1-03 host paths/URLs, p1-05 retrieval proof |

Measurement/handoff overhead, outside this product-friction total: reading required instructions, owner records, specification, topic docs, relevant memory and source contracts; creating/inspecting the fixed worktree; checking environment/package metadata; the mandated full offline suite and capturing its output; reading CLEAR; writing/indexing/hashing this evidence; Git verification/commit; Paperclip progress comments, uploads, work products and final disposition. F1 includes all interpreter/package discovery for that setup incident. F2 includes the scratch recorder, environment binding and tool-schema discovery. The read-only default-graph inspection verifies the already-prescribed explicit checkpoint choice; it is not an additional workaround. No unlogged repair, retry or non-MCP product operation was performed.

## Verification boundaries and remaining limits

- **Offline tests:** full Backend suite exit 0 with 124 unchanged skips; no failing gate observed. No failing tests were repaired, removed or quarantined.
- **Running service:** actual MCP ping/resources and live schema/process evidence. Exact Backend loaded commit and ComfyUI commit/package compatibility remain unknown; contract mismatch is demonstrated.
- **Real generation:** one local job completed; artifact metadata includes the compiled Illustrious/default workflow. This proves this model/graph/parameter combination executed, not broader model-family compatibility.
- **Retrieved generated artifact:** Gallery metadata only. No generated-image bytes, no retrieved revision, no verified revision lineage.

No implementation approaches were abandoned because no product implementation was authorized. The stop-on-blocker path is explicitly permitted by the task; the observed URL failure and runtime mismatch were left intact. Fault injection/new tests would change the no-repair measurement and were not performed. Scratch harnesses remain only in the ephemeral Paperclip run directory; their requests/results and provenance are retained here.

Known limits: one Mac, one template, one checkpoint, one generated original. No worker, aesthetic judgment, CTY demo, three-run exit or phase acceptance is claimed. Producer decides repair scope and acceptance after independent exact-commit QA. This execution issue can be done while the measured journey remains blocked.
