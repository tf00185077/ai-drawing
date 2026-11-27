Verdict: PASS
Review round: 1

Reviewed commit: `c02ebe75a25b949ca3408b5f5bfb0569225832cc`
Approved specification / direct parent: `66e6a7f39d0b202b30095d516f319b4d7fd0e249`
Review date: 2026-11-24 (UTC)
QA issue: [AID-149](/AID/issues/AID-149)

PASS applies to the evidence-only baseline, including D2's expressly permitted documented-blocker outcome. It does not certify a successful generate → retrieve → revise journey, deployed-source alignment, aesthetics, or Phase 1 exit. Producer on [AID-142](/AID/issues/AID-142) owns acceptance and bounded follow-ups before dependent release.

The [independent verification bundle](/api/attachments/2fd9cd68-3891-4cdd-83fc-94b39491cfb5/content) preserves QA's full test output, timings, skip reasons, environment, raw read-only stdio, live schema, and integrity audits. Coding's [manifest](/api/attachments/eb0f6ce2-90f4-4866-9ff7-22b9e713c8f9/content) and [complete evidence archive](/api/attachments/f8dc5696-8f5f-4bcf-be48-7f7a9a111c7f/content) remain inspectable on [AID-148](/AID/issues/AID-148).

## Findings

No task-introduced software, test, or evidence defect was demonstrated. The two observed product blockers were recorded accurately and left intact:

1. Both Gallery tools return `/gallery/2026-11-24/ComfyUI_00253_88891201_0.png`. The scratch client's attempt to open that relative URL fails locally with `ValueError: unknown url type`, before an HTTP image request. This establishes a locator/client handling blocker; it does not establish that the file is missing or the HTTP endpoint is broken. QA reproduced the local failure without joining the URL or opening the generated file.
2. The live Backend schema lacks `GenerateRequest.revision_context` and `RevisionContextRequest`, although the reviewed source defines them. The original submission supplied context; submission, job status and Gallery results returned null context. QA fetched an identical live OpenAPI snapshot (raw SHA-256 `06f3f0c233df6ae9f609f4f8de8ecad7b9a98cacb7cbbdca8f21dd052352dcd2`) and independently confirmed null context on the same existing job/artifact. The exact loaded Backend commit remains unknown. Health and process cwd cannot identify it.

The first maps to p1-02/p1-03 and retrieval proof in p1-05. The second maps to the manifest's proposed runtime attestation/alignment follow-up, with p1-04 visibility and a prerequisite for p1-05. These are baseline observations for Producer, not repairs made or certified by this review.

## Owner reading and fixed-tree review

Before opening the delivered manifest, I read both owner source records, the team/operating policy, Phase 1 roadmap, and compute/model/revision memory. My reading was: measure today's Mac tools without repairs; require the full bounded Backend suite for D1; permit an explicit flow blocker; disclose interventions, follow-up mappings and count. The delegated checkpoint/template choice requires no routine reconfirmation. This agrees with the fixed task specification.

I reviewed the full SHA above using Git objects and an isolated checkout at `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-149-qa`, branch `aid-149-p1-00-review`. The specification is byte-identical to the approved parent. All 19 additions are the manifest and task evidence; there are no changes elsewhere. No source, test, workflow, model or existing specification change was smuggled in. Shared `main` was left untouched.

All 19 entries in Coding's checksum list match their committed bytes. The uploaded ZIP's 20 task/evidence files match Git, its receipt names the reviewed SHA, and its patch equals `git format-patch -1 --stdout` for that commit. A completed prerequisite was therefore used to locate and inspect the actual delivery, not as acceptance evidence.

## Done when outcomes

| Item | Level | Outcome | Evidence and limits |
|---|---|---|---|
| D1 — full Mac Backend suite passes without failures/hangs | P1 | PASS | Coding: `1900 passed, 124 skipped, 77 warnings in 43.84s`, exit 0, wall 49.973s. QA independently: `1900 passed, 124 skipped, 77 warnings in 44.13s`, exit 0, wall 48.177s. Both use `--timeout=60`. |
| D2 — retrieve original/revision, or documented blocker | P1 | PASS via documented blocker | Ordered raw stdio reaches a completed original and Gallery metadata, then records the local relative-URL failure and stops. No generated-image bytes or revision were retrieved. The separate runtime context mismatch is also supported. |
| D3 — complete friction log and follow-up mappings | P2 | PASS | F1–F8 reconcile with setup/process/schema/queue records and the raw stdio. Each incident describes the action, cause and p1/new-task mapping. No repair or resubmission is present in the retained execution record. |
| D4 — baseline count stated | P2 | PASS | The explicit counting rule yields 23 intervention units across eight incidents; the arithmetic and call counts reconcile. This is a disclosed measurement, not 23 successful fixes. |

D1's independent full suite was the first execution check after required reading, checkout and environment setup, before QA's live probes. It used a new task-owned Python 3.11.15 environment, unchanged Backend requirements plus `pytest-timeout==2.4.0`, an isolated root below `TMPDIR`, and the separate existing MCP interpreter. No tests were edited, removed or quarantined.

QA added `-rs` to obtain reasons for the 124 skips: all require Windows, including PowerShell, ACL, junction, updater and process-semantics checks. These are unchanged platform exclusions, not executed tests or a setup failure. Both Mac and the recorded Windows summaries total 2024 cases, but the Windows result was not used to certify this Mac run. Warnings remain disclosed; no timeout or test failure occurred.

### Ordered-call and intervention reconciliation

The baseline has 90 timestamped records and 19 matched JSON-RPC request/response pairs: initialization, tool discovery and 17 tool calls. Raw lines are intact, timestamps are monotonic, the saved live catalog equals the raw discovery response, and summary results equal the decoded raw responses.

Tool order is ping → resources → one generate → 12 same-job status calls → image metadata → artifact metadata → failed non-MCP URL attempt → stop. Status advances from queued through running to completed. Eleven waits correspond to eleven polls beyond the first. There is one Backend generation POST and no `gallery_rerun`, revision submission, cancellation or resubmission. No call timeout occurred; timeout recovery is therefore not exercised.

The generation explicitly passes `Illustrious-XL-v2.0.safetensors`, `default`, `execution_target=local`, and `loras=[]`. The returned compiled graph uses that checkpoint despite the template's older saved filename. No graph edit or replacement download was applied.

| Incident | Units | Reconciled action / mapping |
|---|---:|---|
| F1 | 1 | Backend timeout-environment setup; p1-05 / proposed environment follow-up |
| F2 | 1 | Stdio environment/recorder binding; p1-05 |
| F3 | 1 | Plain-text versus JSON response parsing; p1-01 with p1-02 |
| F4 | 6 | Docker query, two listener checks, process query, two cwd checks; p1-04 / proposed runtime alignment |
| F5 | 1 | Direct OpenAPI inspection; same proposed runtime alignment |
| F6 | 11 | Repeated same-job polls; p1-03 |
| F7 | 1 | Direct post-completion ComfyUI queue check; p1-04/p1-03 |
| F8 | 1 | Non-MCP byte-fetch attempt failing locally; p1-02/p1-03/p1-05 |
| Total | 23 | Three setup/parser interventions + nine non-MCP diagnostic/retrieval attempts + eleven repeated polls |

The count deliberately includes setup and post-stop diagnostics, as the manifest states. Producer should preserve this accounting scope, or publish an explicit reconciliation, when comparing p1-05. No missing intervention was demonstrated against the retained record; the ephemeral scratch harness itself is represented by provenance/hash rather than retained Coding source.

## Verification commands and results

The independent suite command, expanded paths and UTC start/end are retained in `qa-backend-suite.json` in the verification bundle:

```sh
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/qa-backend-tests" \
MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python \
"$PAPERCLIP_RUN_SCRATCH_DIR/backend-venv/bin/python" \
  -m pytest -c pytest.ini backend/tests -q --timeout=60 -rs
```

Other checks: `git show`/`git diff` against the two fixed SHAs; SHA-256 and JSON-RPC audits; uploaded archive comparison with committed files and `git format-patch`; the retained `qa-readonly-check.py`; one read-only `GET http://127.0.0.1:8001/openapi.json`; and the review skill's `scripts/build_registry.py docs/tasks`. The registry had no active guarding tests before this review. It now records D1's full Backend suite; no earlier contract is superseded. No mutation experiment was appropriate for this evidence-only suite item: there is no changed production behavior to inject a fault into, and the assignment forbids hidden repairs/new generation.

QA's scratch audit scripts initially assumed the wrong checksum root and catalog envelope. Inspecting the actual formats resolved those script errors; final integrity checks passed. They were not product or suite failures.

## Verification boundaries and uncertainty

- **Offline tests:** independently verified the complete Mac Backend suite only. Full MCP, Frontend/build, launcher and Windows suites were not rerun; this documentation/evidence change introduces no software change. No all-platform certification is made.
- **Running service:** independently repeated current-source MCP stdio ping, status of the delivered original, image metadata and artifact metadata; checked the live schema. The mismatch is demonstrated; the loaded Backend revision remains unidentified.
- **Real generation:** reused the recorded execution evidence for job `88891201-d6c1-4fad-a40d-98622b32f0ed`, ComfyUI prompt `615da0b0-fc27-41c2-a312-79b6fc61003f`. QA confirmed the same completed job and its metadata without submitting another generation.
- **Retrieved generated artifact:** metadata only: image `4447`, canonical artifact `3862`, reported size 241339 bytes. Neither Coding nor QA byte-verified the generated image. No revision exists in this run. A future revision requires a new generate request with canonical `parent_artifact_id=3862`; image ID `4447` and `gallery_rerun` do not establish revision lineage.
- **Errors/recovery/security:** the URL error is locally reproduced. Cancellation, failure recovery and an actual timeout are not exercised. The recorded and QA calls use loopback services; no worker control was exposed. No models, datasets, outputs or Gallery records were removed or overwritten, and no restart, URL workaround or product/test repair was performed.

One run on one Mac/model/template is a baseline only. No aesthetic approval, owner demo, phase acceptance or merge/push is implied. New code or evidence commits require a new exact-commit review. This review is complete on its own issue; Producer owns the next decisions.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | backend/tests (full suite with --timeout=60) | active |
