Verdict: PASS
Review round: 2

Reviewed commit: `ef8302c959dfc97ce7cf7f118ac31583e31fb3d4`.
Review date: 2026-11-24 UTC. QA: [AID-160](/AID/issues/AID-160).
Coding: [AID-159](/AID/issues/AID-159#comment-20fdc35f-8488-40c7-a6c9-a2c526affa8b).
Cleared specification: `abe1272802bdead00ef0a9bf51d8709b58eb27d7`.
Task SHA-256: `3b1cc30be86041c671627bb29720d4c973c8c5a7712b339437f94a3bb1ccd6a6`.

This is a fresh same-candidate assessment of all four original acceptance items.
[p1-02 also passes](../p1-02-mcp-tool-consolidation/review.md) at this exact SHA.
Producer [AID-143](/AID/issues/AID-143) owns acceptance, integration/publication
and later-task release. Any changed candidate code needs a new review.

## Findings

No blocking defect or specification ambiguity found. Production envelope,
registration, adapter and domain-recovery code is byte-identical to the first
candidate. The two added catalog tests correct p1-02 F2-1. I reran applicable
suites, boundary probes and meaningful faults at the new exact candidate;
round-1 PASS is preserved as history, not relabeled as a fresh test result.

## Independent identity and contract check

The owner direction requires consistent MCP parsing, retained Backend state and
recovery, with the approved staged consolidation. Both original tasks, normative
decisions and compose/save clarification equal the independently cleared source.
The correction stays within that scope. Both actual refreshed manifests were
read and reconciled with the task items, code and saved evidence.

Before substantive review I pinned the full SHA on AID-160 in
[comment 12d8848c](/AID/issues/AID-160#comment-12d8848c-6a8f-420c-9ef3-8c0ad5c18dcf),
then created `ai-drawing-worktrees/aid-160-qa`, branch `aid-160-exact-review`,
at that immutable commit. Seven official Coding uploads match sizes/hashes;
both manifests equal Git; combined/correction patches equal raw binary diffs
from `c5991c50c0d0da400df565b1893ad663e412152d` / rejected `9a5e55a`;
the bundle verifies and names the candidate. All 147 archive members match the
inventory and named Git objects where applicable. Eight archived prior official
artifacts were also downloaded independently and compared byte-for-byte.
See identity audit.

The scope audit
confirms all production code, dependencies, other component inputs, original
Coding evidence and every existing catalog test function are unchanged from
`9a5e55a`. The only test delta is the two added policy tests. All temporary
mutations were restored byte-for-byte; QA delivers reports/evidence/registry
only. Main and the AID-151 runtime were untouched.

## Done when results

| Item | Level | Result | Independent evidence |
|---|---|---|---|
| D1 — every registered success/failure envelope | P1 | PASS | Real registered MCP calls for 29 tools × success/HTTP 598/connection; pre-body missing/type/mode/unknown-field validation includes non-LoRA tools and legacy compose-save. Formal stdio checks equal structured/text JSON. Flattened-success fault causes 29 failures. |
| D2 — Backend code/hint/details and unknown status | P1 | PASS | Known structured/domain errors, unknown HTTP status, safe revision-parent and LoRA projections, fresh Backend revision/uncertain-admission exports, prompt conflicts and no resubmission/fallback assertions pass. Lost Backend code causes four failures. |
| D3 — envelope/error list documented | P2 | PASS | Read docs/mcp.md response-envelope and error-code sections against responses.py, ContractFastMCP validation, real discovery and domain projections. Success has data; failures have code/message/hint and preserved safe context. |
| D4 — full MCP suite | P1 | PASS | After all faults were restored: 460 passed, 2 unchanged optional export skips, exit 0; isolated roots and --timeout=60. Fresh full Backend and all standing guards also pass. |

The new independent static audit
checks all 29 risks/registrations, 40 old-name dispositions and retained arguments.
Registered request coverage preserves revision_context/canonical parent IDs,
image/artifact namespaces and locators, precise seeds, omitted/empty/ordered
LoRAs, fragments/metadata/provenance/concurrency, saved graph replay, configured
local admin operations and distinct generation/training status/cancel paths.

## Commands and results

All commands ran independently from the pinned QA worktree. Full argument arrays,
allowlisted environments, UTC times, exits and complete output are retained in
round-2 evidence.
Full suites use per-test timeout 60 and isolated roots below TMPDIR, with
pytest-timeout 2.4.0 installed in run scratch only. Canonical venvs were unchanged.
MCP consumed fresh revision, multi-LoRA and lifecycle exports from this QA run.

```sh
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -B -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/qa-mcp-restored" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python \
 -B -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra
```

- Full Backend: **1900 passed, 124 skipped, 76 warnings in 41.60s**, exit 0.
  Every skip requires Windows. No prior Backend result was reused.
- Restored full MCP: **460 passed, 2 skipped in 1.95s**, exit 0. Skips are the
  unchanged optional smoke HTTP/image-validation exports; revision and
  uncertain-admission fixture consumers ran.
- Cross-layer LoRA parity: **5 passed, 1 warning in 0.31s**, exit 0.
- Additional registered QA boundary cases: **15 passed in 0.22s**, exit 0.
- Catalog baseline: **14 passed in 0.20s**, exit 0.
- Seven meaningful production faults fail their intended assertions, including
  full MCP failure for false admin risk. All source was restored before GREEN.
  Exact deltas, exits, summaries and hashes are in mutation-results.json.

The fresh full suites cover both preexisting baseline/repair registry items and
all three p1-01 items certified by QA `1001586`. The regenerated registry also
records p1-02's newly certified test items. No standing behavior is superseded.
Frontend/build/native Windows suites were not run: their source, tests,
dependencies and cross-layer inputs are unchanged; this is a macOS review.

## Preserved history and limits

Round-1 report is byte-identical to `1001586`; the complete
original shared QA evidence, including official archive
logs, is retained unchanged. Historical p1-01 PASS / p1-02 FAIL F2-1 and one
p1-02 delivery rejection remain recorded. This is correction round 1 / delivery
review round 2. Kickoff K2-1, clarification round 1, kickoff round 2 CLEAR and
p1-00a's separate rejection/correction history are unchanged.

One initial standalone QA probe imported an older installed package because
its helper lacked the pinned source path. Import-origin evidence identified
that QA environment error. Rebinding only the helper environment fixed it;
the failed attempt is retained and excluded from product results. Pytest source
binding was already correct; no candidate test, spec or production fix was made.

- Offline software: fresh suites, registered mocked HTTP, test-only stdio HTTP,
  serialized Backend fixtures, independent audits and mutation proof.
- Running product services: no probe, deployment, restart or loaded-source claim.
- Real generation/training/download/worker dispatch: none.
- Generated artifact retrieval: no live Gallery-byte read; review artifact
  downloads and offline locators do not prove new generated-image retrieval.

The active AID-151 runtime/private configuration, canonical environments and all
retained data remain preserved. Original baseline stays 23 units/eight incidents;
accepted live evidence is one cached-original/revision pair and decoded host
paths for a colocated Mac client. Live timeout/cancel/dedup recovery, remote URL
consumption, aesthetics, three zero-intervention runs and phase close remain
outside this review. No merge/push or next-task release was performed.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | mcp-server/tests/test_intent_boundary.py::test_catalog_registered_success_failure_envelope; mcp-server/tests/test_intent_boundary.py::test_pre_body_validation_is_enveloped_and_no_http; mcp-server/tests/test_server.py::test_stdio_envelope_success_and_non_lora_validation_before_http | active |
| D2 | P1 | mcp-server/tests/test_intent_boundary.py::test_structured_backend_code_hint_details_preserved; mcp-server/tests/test_intent_boundary.py::test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; mcp-server/tests/test_revision_parent_errors.py; mcp-server/tests/test_lora_admission_identity.py | active |
| D4 | P1 | mcp-server/tests (full suite with --timeout=60 and isolated roots) | active |
