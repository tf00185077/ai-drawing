Verdict: CLEAR

Review type: independent kickoff only, 2026-11-24. QA: [AID-155](/AID/issues/AID-155).
Fixed specification/source: `d1ffb8d8d9db12f728ed98704e966e76489faafb`.
Task: `docs/tasks/p1-01-mcp-response-envelope/task.md`.
Task SHA-256: `3b1cc30be86041c671627bb29720d4c973c8c5a7712b339437f94a3bb1ccd6a6`.

This clears this specification, not an implementation. The separate
[p1-02 verdict](../p1-02-mcp-tool-consolidation/kickoff-review.md) is AMBIGUITY;
the combined Coding dispatch is therefore still gated. There is no p1-01/02
implementation manifest, delivery, delivery rejection or delivery review yet.

## Independent owner reading and comparison

My reading: an agent should parse one success/failure contract across the entire
MCP surface. Consolidation should preserve needed generation, revision, Gallery,
prompt and administration capabilities while respecting the existing Phase 1
boundaries. Civitai and LoRA names remain except the expressly removed
generate-like tool. Backend behavior remains authoritative. Wait/result,
health/workers and repeatable smoke/setup follow in their existing order.
Ordinary implementation choices need no renewed owner confirmation.

I formed and saved that reading after reading the preserved owner direction,
approved MCP decisions and active milestone, before opening the fixed on-disk
task files. The assignment already supplied their text, so this is independent
reasoning, not a blind review. Sources: the [later owner
instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md),
[MCP decision/tool map](../../decisions/mcp.md), [roadmap](../../roadmap/ROADMAP.md)
and [current execution plan](../p1-planning-2026-11-24/plan.md).

Difference: none for p1-01. Its common helper, single catalog response contract,
all-tool coverage, error preservation and documentation requirements implement
that reading without adding Backend APIs or later-phase subsystems. The
scope covers every tool registered in the combined delivered catalog, including
Civitai, all nine LoRA/caption tools and transitional `mcp_ping`; the three tools
removed by p1-02 need no post-removal registration or envelope.

## Acceptance gates against static source

| Item | Kickoff assessment | Observable delivery evidence |
|---|---|---|
| D1 — all registered success/failure envelopes | CLEAR | Parametrize from the actual delivered catalog, invoke the registered `mcp.call_tool` boundary with valid arguments, and mock dependencies below the tool body for success/failure. Inspect the converted MCP result, not just a response helper. Cover HTTP, connection and validation errors, including invalid arguments rejected before a non-LoRA body executes. |
| D2 — Backend codes, hints and unknown HTTP status | CLEAR | Inject real-shaped `httpx.HTTPStatusError` responses through the tool/client boundary. Known revision status/code pairs retain their canonical code and recovery hint; unknown/undecodable errors use the documented generic code and retain HTTP status in the message. Preserve existing safe LoRA diagnostics and admission-uncertainty job identity/recovery guidance when moving fields into the envelope. |
| D3 — documented envelope/error list | CLEAR | Compare `docs/mcp.md` with the implemented helper and public error branches, including the same parse contract for success and failure. A description of mixed plain text/JSON shapes is no longer accurate. |
| D4 — full MCP suite | CLEAR | Full isolated MCP suite with `--timeout=60`, command and summary in the manifest. Update old-shape assertions as an explicit intended contract change while retaining their feature checks. Additional suites and standing registry guards follow the actual software change and delivery-review rules. |

Concrete source checks at the fixed SHA:

- `mcp-server/mcp_server/tool_catalog.py` has 40 unique entries: three
  `plain_text`, 18 `json_string`, 19 `dict`. Static decorator enumeration matches
  all 40, and the retained original live discovery contains exactly those names.
- `mcp-server/mcp_server/server.py:94` specializes validation only for
  `lora_train_start`. The other tools' Pydantic argument failures escape its
  handler. Thus the new non-LoRA pre-body case tests a real boundary that a
  helper-only test would miss. Existing
  `test_server.py::test_protocol_start_missing_recipe_is_structured_and_redacted`
  already demonstrates the registered-call test seam.
- Static inspection of the installed MCP SDK's FastMCP `call_tool`, tool manager
  and `Tool.run` confirms argument validation precedes the callable and result
  conversion follows it. `ToolError.__cause__` carries validation failures.
  Generalizing the existing boundary needs no Backend change. Delivery must
  still prove serialization/schema consistency with its actual SDK environment.
- `tools/responses.py` currently emits tool-specific error payloads without a
  universal hint/data shape. `tools/generate.py:27` already projects known
  revision-parent status/code pairs; `client.py` raises HTTP exceptions carrying
  the response. Backend `core/revision_context.py` supplies the canonical
  `revision_request_conflict` and other parent codes/hints. These are observable
  inputs, not a request to trust arbitrary Backend diagnostic text.
- `tools/lora_train.py:415` preserves safe errors and, for `admission_uncertain`,
  a canonical job ID plus a do-not-resubmit hint. Envelope migration must retain
  that recovery meaning. Generation, Gallery, direct ComfyUI and Discord tools
  use different dependency seams; a mocked success/failure matrix must exercise
  each registered callable, not merely replace every callable with a stub.

No demonstrated p1-01 specification defect or owner question remains. These are
delivery-review expectations derived from the stated gates and existing
contracts, not claims that future code already passes them.

## Original friction and accepted repair reconciliation

I read the actual original [manifest](../p1-00-mcp-friction-run-mac/manifest.md)
and [evidence-only PASS](../p1-00-mcp-friction-run-mac/review.md), corrected
[repair manifest](../p1-00a-mac-runtime-and-retrieval/manifest.md),
[acceptance](../p1-00a-mac-runtime-and-retrieval/acceptance.md), final
[round-2 PASS](../p1-00a-mac-runtime-and-retrieval/review.md) and historical
[round-1 FAIL](../p1-00a-mac-runtime-and-retrieval/review-round-1.md).
I agree with every row of the [complete kickoff mapping](kickoff-context.md):

| Item | Original units | Accepted boundary and remaining obligation |
|---|---:|---|
| F1 — test setup | 1 | Scratch interpreter/timeout setup remains; p1-05 owns repeatable setup/documentation. No packaging work is added here. |
| F2 — stdio bootstrap | 1 | Explicit interpreter/source/Backend/Gallery binding remains; preserve it. Smoke driver and setup belong to p1-05. |
| F3 — mixed parsing | 1 | Direct p1-01 fix, applied and documented across p1-02's delivered catalog. |
| F4 — runtime identity | 6 | Repair identifies one controlled launch. General existing-endpoint visibility is p1-04; no attestation subsystem or restart here. |
| F5 — live revision contract | 1 | Repair proves newly persisted canonical lineage; old baseline stays legacy/null. Preserve `revision_context` and canonical parent-artifact semantics through consolidation; p1-05 rechecks deployment. |
| F6 — repeated polling | 11 | Status/cancel remain reachable; bounded wait is p1-03. No original timeout or resubmission occurred. Inspect the existing job before any timeout resubmission. |
| F7 — coarse visibility | 1 | Disclosed direct queue/history diagnostics remain evidence, not an MCP progress feature. Wait/result is p1-03, health visibility p1-04; no deeper subsystem here. |
| F8 — relative-URL retrieval | 1 | Repair consumes both tools' unmodified returned host paths for a colocated Mac client. Preserve locators and distinct image/artifact IDs; p1-03 reports them truthfully and p1-05 consumes/decodes them. Remote URL consumption remains unproved. |
| Total | 23 | Eight incidents; resolution does not subtract original intervention units. |

Accepted publication is `a963386a3141194a6a08853d89224b548d112aa2`, corrected
repair `b6d58468147e11a21b3d7a26ea25ed4353a28a28`, independent QA
`3d5d8902a89a8c3c8994ed89e944fcaee0260577`. The repair proves one fresh
original/revision request pair, with a cached deterministic original, persisted
canonical parent lineage and decoded PNG bytes through unchanged returned host
paths. It proves neither remote/relative-URL consumption nor a new uncached
original computation, aesthetics, demo, three zero-intervention runs or phase
exit. One delivery rejection, correction round 1 and delivery review round 2
belong to p1-00a alone.

The static audit verified all 20 original baseline files remain byte-identical,
the corrected manifest/raw fresh transcript and final/historical reviews match
their named immutable commits, and Backend/MCP tree IDs match baseline, repair,
accepted publication and this fixed specification. Prior independent Backend
`1900 passed / 124 Windows-only skipped` and MCP `314 passed / 4 exported-fixture
skipped` are prior repair evidence only, not results for the proposed changes.

## Commands, evidence and limits

QA worktree:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-155-kickoff-review`,
branch `aid-155-fixed-kickoff-review`, created at the full fixed SHA. Required
guides, memory, topic docs, decisions, source and tests were read there or as
fixed Git objects. No implementation manifests exist for these two tasks.

Checks performed: `git rev-parse`, `git show`, `git ls-tree`, `git diff`,
`shasum -a 256`, bounded `rg`/source reads, and:

```sh
python3 "$PAPERCLIP_RUN_SCRATCH_DIR/kickoff-static-audit.py" \
  /Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-155-kickoff-review \
  "$PAPERCLIP_RUN_SCRATCH_DIR/static-audit.json"
git diff --check
```

Static audit exited 0: 40 catalog/registration/live-baseline names reconciled;
40 dispositions accounted for; 29 provisional delivered names; 23 units/eight
incidents; 20 original files unchanged; evidence/source identity checks passed.
The script, JSON receipt and saved independent reading accompany the exact
reports/patch in this card's uploaded archive. Report digests and full report
commit are recorded in the external package receipt to avoid a self-hash.

- Offline software tests: none run; this is specification review with no product
  change. No all-suites-pass or implementation acceptance claim is made.
- Running service: no new product probe, configuration change or restart.
- Real generation: none; accepted historical evidence was read only.
- Generated artifact retrieval: no new live image-byte read; prior bounded
  retrieval was not repeated or broadened. Upload readback verifies review
  artifacts separately.
- Cancellation/recovery/duplicates/security: static contracts inspected only;
  live failure paths and idempotency are not certified. No cleanup, worker
  exposure or changes to shared main, AID-151 private/runtime files, canonical
  Backend venv or retained data were made.

Producer owns the p1-02 clarification and subsequent dispatch. Both tasks need
actual CLEAR before Coding. Later delivery requires one combined exact final
commit, a manifest per task, a separate recipient-owned QA card natively waiting
on Coding, independent PASS and then combined integration/publication. Any later
candidate change needs a new exact-commit review. No registry coverage is added
by a kickoff report.
