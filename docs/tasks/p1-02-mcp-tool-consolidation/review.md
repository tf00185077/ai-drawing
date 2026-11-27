Verdict: PASS
Review round: 2

Reviewed commit: `ef8302c959dfc97ce7cf7f118ac31583e31fb3d4`.
Review date: 2026-11-24 UTC. QA: [AID-160](/AID/issues/AID-160).
Coding: [AID-159](/AID/issues/AID-159#comment-20fdc35f-8488-40c7-a6c9-a2c526affa8b).
Cleared specification: `abe1272802bdead00ef0a9bf51d8709b58eb27d7`.
Task SHA-256: `9b9540278fdf041f66ce3fd80f218e4d7260d34a002814471ff8094e62102028`.

All five original acceptance items pass at this same exact combined candidate;
[p1-01 also passes](../p1-01-mcp-response-envelope/review.md).
Producer [AID-143](/AID/issues/AID-143) owns acceptance/publication and later-task
release. Any subsequent changed candidate code requires a new exact review.

## Findings

**F2-1 resolved at this candidate.** The original label was correct, but the
old test's expected value was circular. The correction adds an explicit literal
29-intent expectation, grounded in the unchanged cleared decisions/retained
capabilities and transitional ping. It is not constructed from production
catalog values or descriptions. Existing tests and correct product labels are
unchanged. No additional defect or specification ambiguity was demonstrated.

The two tests independently check exact catalog names/labels/cardinality and
real registered MCP discovery, including exactly one approved description
label for every intent. I checked their complete policy against the approved
map and exposed adapters: read composition/preflight/status, mutate
save/submission/acquisition/caption/cancellation, admin ComfyUI operations.
The tests retain separate real boundary proof that read composition cannot save.

## Independent fault / restore / GREEN

I changed only this production field in my pinned QA worktree:

```diff
- 'comfyui_admin', 'mcp_server.tools.intents', 'comfyui_admin', 'admin'
+ 'comfyui_admin', 'mcp_server.tools.intents', 'comfyui_admin', 'read'
```

- Both guarding tests fail: **2 failed**, exit 1, explicitly read versus admin
  in catalog and real discovery. No test expectation or dispatcher was changed.
- Full corrected MCP with fresh QA Backend exports: **2 failed, 458 passed,
  2 unchanged optional skips in 1.99s**, exit 1. The only failures are those
  same two risk guards. This reverses the demonstrated first-round fake green.
- Real registered `comfyui_admin(action=restart)` still advertises Risk: read,
  returns success and emits exactly one **POST comfy.invalid/manager/reboot**
  through mocked HTTP. No live ComfyUI operation occurred.
- The catalog was restored byte-for-byte: original/restored SHA-256 both
  `d57d6a93e3529ca31746e172a37c24574bf068e9d87e433a7e80a204383c9e70`.
  Restored discovery says Risk: admin; the mocked request stays the same.
- Fresh full MCP after restoration: **460 passed, 2 skipped in 1.95s**, exit 0,
  with isolated roots and --timeout=60. Final production diff is empty.

Exact delta, full failure assertion/output, command/exit receipts, discovery/
request/result probe and restoration hashes are in
round-2 evidence, especially mutation-risk-only.patch,
mutation-risk-targeted.log, mutation-risk-full.log, mutation-risk-probe.log,
risk-restoration.json and qa-mcp-restored.log.

## Done when results

| Item | Level | Result | Independent assessment |
|---|---|---|---|
| D1 — catalog/registration and all 40 old capabilities | P1 | PASS | Real catalog/discovery has exactly 29 names. Independently checked all 40 manifest rows once, retained arguments, intent/risk/mode/optional migrations and exactly three removed MCP submissions. All Civitai/LoRA names and temporary ping remain. Backend implementations are unchanged. |
| D2 — truthful single risk and read boundary | P1 | PASS | Literal policy independently matches catalog and actual discovery for all 29 names, one label each. False-admin-read fault fails both meaningful guards and full MCP. Compose sends no save_as; legacy presence fails before HTTP. |
| D3 — every merged branch and compose/save replacement | P1 | PASS | 14 registered merged request cases cover both generate/Gallery selectors, three writes, preset list/detail/two save sources and three admin actions. Legacy empty/null and extra false/zero/list saves fail before HTTP with replacement hint. Save carries fragment arrays, metadata/provenance, revision/ETag and conflict code/hint without overwrite/retry. |
| D4 — complete baseline friction mapping | P2 | PASS | Read F1–F8 in actual refreshed manifest against original baseline and accepted context. F3 fixed; F5/F8 preserve lineage/locators. Bootstrap, polling, visibility and future smoke remain assigned. Original 23 units/eight incidents remain intact. |
| D5 — delivered/staged docs and full MCP | P1 | PASS | docs/mcp.md's 29-tool table, envelope/errors and executable ping/resources/generate/status/Gallery flow agree with source/discovery. Final health/resources/generate/wait/Gallery flow is explicitly staged; later tools remain absent. Restored full MCP passes 460/2. |

The original task/decision/clarification bytes equal fixed `abe1272`; the
published correction equals `a9c8384`. I read both actual manifests and full
first-round reports/mutation proof. The precise new candidate was pinned on
AID-160 before substantive review, then reviewed in an independent immutable
worktree. Both manifests, seven official Coding uploads, exact combined/repair
patches, verified bundle and 147 archive members were reconciled. Eight prior
official artifacts were independently downloaded and compared. Full identity
and commands are documented in the [p1-01 report](../p1-01-mcp-response-envelope/review.md).

## Preservation, commands and results

Fresh independent offline runs from this candidate, all exit 0:

- Backend: **1900 passed, 124 Windows-only skips, 76 warnings in 41.60s**.
- Restored full MCP: **460 passed, 2 optional export skips in 1.95s**.
- Cross-layer LoRA parity: **5 passed, 1 warning in 0.31s**.
- Additional registered QA boundaries: **15 passed in 0.22s**.
- Catalog baseline: **14 passed in 0.20s**.

Full argument arrays, isolated root/fixture environment, UTC times and logs are
saved per command. Full suites use --timeout=60. Fresh Backend revision,
multi-LoRA and lifecycle exports were consumed by MCP. Two unchanged optional
smoke exports remain absent; the meaningful revision/admission consumers ran.
No prior Backend result was reused. Frontend/build/native Windows were not run:
their code/tests/dependencies/cross-layer inputs are unchanged; host is macOS.

Six other faults also fail afresh: flattened envelope (29 failures), lost
Backend code (4), compose save leak (1), lost ETag (1), wrong custom dispatch
(1), missing catalog tool (3). All were restored. Current production,
dependencies, other component inputs and every existing catalog test function
equal `9a5e55a`; only two policy tests were added. No guard was weakened.

I read active topic/policy/architecture/workflow/style/team/memory updates and
checked real wrappers/dispatch/request assertions. Preservation covers canonical
revision IDs, precise seeds/locators and image/artifact namespaces, ordered LoRAs,
saved graph replay, fragments/context/provenance/concurrency, safe domain errors,
separate generation/training status/cancel, Discord alias/dedup/force forwarding
and rejection of arbitrary channel/file or unsupported replay inputs. Timeout
and uncertain-admission paths retain job recovery and no retry/local fallback.
All standing registry guards pass in fresh full suites. QA regenerates the
registry only after these per-task PASS verdicts, with no supersession.

One standalone historical QA probe initially imported an older installed package
because its environment lacked pinned source binding. Import-origin evidence
identified the helper error; only the QA helper environment was corrected. The
failed attempt is retained, then the meaningful mocked probe and complete
risk RED/restore/GREEN were rerun at the pinned source. No product fix was made.

## History and limits

Round-1 FAIL and p1-01's round-1 PASS are exact copies from
QA `1001586788d89d2c346619a5c1b0ffe1390897f8`. All original shared QA evidence,
including official archived logs, is retained unchanged. History remains one
p1-02 delivery rejection / correction round 1 / delivery review round 2, now
PASS. Kickoff K2-1 / clarification round 1 / kickoff round 2 CLEAR and p1-00a's
separate history are unchanged; successful correction does not erase a rejection.

Offline software only: mocked registered HTTP, test-only stdio server, serialized
fixtures, audits and controlled faults. No running product probe/deployment/
restart, real generation/training/download/worker dispatch or live Gallery-byte
retrieval occurred. Review artifact downloads are separate from generated-image
retrieval. Active AID-151 runtime/private configuration, canonical venvs and all
retained data remain intact. Shared main was untouched and clean.

The historical 23-unit/eight-incident baseline and one cached-original/revision
pair with decoded host paths for a colocated Mac client keep their limits. Live
timeout/cancel/dedup recovery, remote URL consumption, aesthetics, three
zero-intervention runs and phase closure are not certified. No merge/push or
next-task release was performed.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | mcp-server/tests/test_tool_catalog.py::test_intended_catalog_matches_fastmcp_registration; mcp-server/tests/test_tool_catalog.py::test_removed_tools_and_staged_tools_are_not_registered | active |
| D2 | P1 | mcp-server/tests/test_tool_catalog.py::test_catalog_risks_match_approved_intent_policy; mcp-server/tests/test_tool_catalog.py::test_discovered_risks_match_approved_intent_policy; mcp-server/tests/test_intent_boundary.py::test_prompt_compose_legacy_save_presence_rejected_before_http; mcp-server/tests/test_intent_boundary.py::test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict | active |
| D3 | P1 | mcp-server/tests/test_intent_boundary.py::test_merged_modes_forward_exact_requests; mcp-server/tests/test_intent_boundary.py::test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; mcp-server/tests/test_intent_boundary.py::test_invalid_merged_inputs_fail_before_http | active |
| D5 | P1 | mcp-server/tests (full suite with --timeout=60 and isolated roots); mcp-server/tests/test_tool_catalog.py::test_catalog_docs_list_active_tools | active |
