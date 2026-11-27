# p1-01 — uniform MCP response envelope

Corrected combined delivery with [p1-02](../p1-02-mcp-tool-consolidation/manifest.md), 2026-11-24.

Correction round 1 addresses F2-1 under the unchanged cleared p1-02 D2.
Production labels/behavior and original task contracts are unchanged. The first
candidate was p1-01 PASS / p1-02 FAIL; this candidate awaits independent review 2.

## Done when evidence

| Item | Check | Level | Result / evidence | Layer and real boundary |
|---|---|---|---|---|
| D1 — every registered success/failure envelope | test | P1 | test_intent_boundary.py::test_catalog_registered_success_failure_envelope (29 × success/HTTP/connection), test_pre_body_validation_is_enveloped_and_no_http, test_prompt_compose_legacy_save_presence_rejected_before_http, test_lora_start_unknown_field_is_validated_before_http; test_server.py::test_stdio_envelope_success_and_non_lora_validation_before_http | Real catalog registration, SDK validation and actual adapters/HttpBackendClient. Only HTTP transport is replaced; formal stdio uses a separate test HTTP server. No replacement tool callable/stub. |
| D2 — retain code/hint/details and HTTP status/recovery | test | P1 | test_structured_backend_code_hint_details_preserved; test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; test_lora_uncertain_admission_keeps_canonical_job_and_no_resubmit; catalog unknown HTTP 598 cases; existing test_revision_parent_errors.py and LoRA safe projection tests | Real registered HTTP path plus existing domain projections. Canonical hints remain safe; uncertain-admission ID/classification and generation node/recording context survive in error.details. No retry/fallback. |
| D3 — envelope/error list documented | manual | P2 | [Response contract](../../mcp.md#response-envelope), [error codes](../../mcp.md#error-codes-and-recovery), restored discovery | Author compared prose with responses.py, registration and real call assertions; independent QA reads actual docs. |
| D4 — full MCP suite, no new failures | test | P1 | Corrected MCP log, receipt; 460 passed / 2 unchanged optional export skips | Full separate MCP interpreter; isolated scratch; --timeout=60. Fresh Backend exports strengthen the registered cross-layer checks. |

Implementation: tools/responses.py handles shared HTTP/connection projection and
one success/error shape at registration. ContractFastMCP covers pre-body SDK
argument validation for every registered tool, retaining LoRA's migration and
safe diagnostics. Failures retain prior context in error.details; successful
fields live under data. Catalog response_category is now always envelope.

Original implementation evidence (immutable at b1082a8; fresh correction evidence below): source/spec/catalog audit,
Backend log/receipt,
parity, mutations,
initial RED, baseline.
Evidence helpers are retained as text in this directory. Source and snapshot
checks exclude manifests/evidence themselves to avoid self-reference; final
external receipts hash the complete exact package.

## Correction delivery identity and review gate

- Coding correction: [AID-159](/AID/issues/AID-159); Producer: [AID-143](/AID/issues/AID-143).
  Branch `aid-159-risk-guard`, worktree
  `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-159-risk-guard`.
- Exact repair base: rejected combined feature
  `b1082a855a66eedba6a4f11fbd4fcec0e9e867ab`. Original feature handoff base:
  `cee10138db8e6e944409701cdae6fb9cfe55c74f`.
  Only the published correction document was imported from
  `1d4fb0df9c6c78e38c217aefed6afb91b0576c9a`; main's old product was not imported.
- Cleared task/decision/clarification bytes remain exactly
  `496cee2f842dc9386d336afb237075bf952271ce`. Both independent kickoff reports
  remain at `9d79d203f65cf3802651a16559da13cbcc4ba14b`.
- **Combined candidate is the final commit containing both refreshed manifests
  on `aid-159-risk-guard`.** Resolve with `git rev-parse aid-159-risk-guard`.
  The external delivery receipt and AID-159 completion pin its one full final
  SHA for both tasks, plus the exact combined patch, repair delta, verified
  bundle and indexed source/evidence package. A commit cannot contain its own hash.
- [Independent QA AID-160](/AID/issues/AID-160) owns delivery review round 2,
  natively after this Coding card. It must pin that full SHA, reassess both
  original contracts and F2-1, preserve round-1 reports/evidence and own registry
  updates. Coding supplies evidence, not independent PASS. Producer alone
  accepts/publishes after actual PASS for both; new code requires new review.
- No merge/push, main integration, runtime replacement or later-task release.
  Active AID-151 runtime/private configuration, canonical component environments
  and all retained data were preserved. Test roots and timeout installation
  were confined to this run's scratch directory.

## Correction and verification

F2-1 is the automated guard's circular oracle, not an incorrect delivered label.
Two new tests in `mcp-server/tests/test_tool_catalog.py` use an explicit literal
`APPROVED_INTENT_RISKS` for all 29 intents, hand-stated from the cleared
[policy](../../decisions/mcp.md#tool-map), retained capabilities and staged ping:

- `test_catalog_risks_match_approved_intent_policy` checks exact names/labels,
  cardinality and exposed entries, without deriving expected risks from catalog.
- `test_discovered_risks_match_approved_intent_policy` calls real
  `mcp.list_tools()` and checks the exact 29 names and exactly one approved
  description label per tool against that independent expectation.

The existing envelope/risk consistency test and every existing test body remain
unchanged. Existing compose no-write/legacy-presence rejection, replacement-save
fragment/concurrency/conflict tests and all merged request/capability cases run
in the full suite. No wrapper, registration, description, label, Backend API,
product dependency or other behavior changed. No new task-spec deviation.

Fresh evidence is in
correction-1-evidence,
separate from immutable original AID-157 `evidence/` and AID-158 `qa-evidence/`.
Full argument arrays, allowlisted environments, UTC times, exits and logs are
retained for each command. The helpers are saved as `.py.txt`; all HTTP is
mocked below real registration/dispatch/adapters, including the restart probe.

| Check | Fresh outcome | Evidence under correction-1-evidence |
|---|---|---|
| Original catalog baseline | 12 passed, exit 0 | baseline-catalog.log/json |
| Before-fix admin-to-read fault | old catalog tests still 12 passed; registered restart advertises read and emits one mocked POST /manager/reboot | before-fix-mutant-catalog.log/json; before-fix-admin-to-read.patch; before-fix-restart-probe.json |
| Corrected guards, same one-field fault | **2 failed, exit 1**, specifically comfyui_admin read versus admin | mutant-policy-guards.log/json |
| Corrected full MCP, same fault | **2 failed, 458 passed, 2 skipped, exit 1** | mutant-full-mcp.log/json |
| Byte-for-byte restore | original/restored SHA-256 both `d57d6a93e3529ca31746e172a37c24574bf068e9d87e433a7e80a204383c9e70` | after-fix-mutation.json; restored-discovery-restart.json |
| Restored full MCP | **460 passed, 2 skipped in 1.95s**, exit 0 | final-mcp.log/json |
| Full Backend | **1900 passed, 124 skipped, 76 warnings in 41.58s**, exit 0 | fresh-backend.log/json |
| Cross-layer LoRA parity | **5 passed, 1 warning in 0.32s**, exit 0 | final-parity.log/json |
| Source/contracts/preservation | production and existing test bodies unchanged; prior official artifacts hash-verified | source-scope-audit.json; prior-official-artifacts.json |

The mutation changes only the production catalog's `comfyui_admin` risk from
admin to read; its dispatch/request implementation is untouched. Both trials
restore the original source in `finally` and record matching SHA-256. The same
registered restart still requests exactly one POST to `comfy.invalid/manager/reboot`
under mocked transport. The restored probe exposes admin. No live restart occurs.
Final full MCP is after restoration and uses fresh serialized Backend exports.

Reproduce from this worktree (exact resolved paths are in receipts):

```sh
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PAPERCLIP_RUN_SCRATCH_DIR"
export PYTHONPATH="$PAPERCLIP_RUN_SCRATCH_DIR/timeout-plugin"
export MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python
export REVISION_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/revision-http.json"
export MULTI_LORA_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/multi-lora-http.json"
export LORA_LIFECYCLE_HTTP_FIXTURE="$PAPERCLIP_RUN_SCRATCH_DIR/backend/http-export.json"
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -B -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/final-mcp" \
 "$MCP_TEST_PYTHON" -B -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$PAPERCLIP_RUN_SCRATCH_DIR/backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -B -m pytest -c pytest.ini backend/tests/test_lora_start_contract_parity.py -q --timeout=60 -ra
```

pytest-timeout 2.4.0 was installed with system Python `pip --no-deps --target`
in run scratch only; the MCP environment has no pip. Component dependencies
were not modified. All suites used isolated roots and per-test timeout 60.
Both baseline/repair standing registry guards and the three p1-01 guards in
QA's five-item registry at `1001586788d89d2c346619a5c1b0ffe1390897f8` are covered
by these fresh full suites. Coding did not edit the registry or certify new items.
No previous Backend test result was reused. Fresh revision, multi-LoRA and
uncertain-admission HTTP exports were consumed through real MCP registration.

All 124 Backend skips require Windows. The two unchanged MCP smoke-export
skips require optional HTTP/image-validation fixtures not produced here; they
are not the revision/uncertain-admission consumers, which executed. Existing
Pydantic/other Backend warnings remain, with the same 76-warning count as QA.
Frontend/build/native Windows checks were not run: those inputs are unchanged,
and this is macOS. Raw logs retain their original whitespace; source/docs
whitespace validation excludes only raw `.log` evidence.

## Preserved history and limits

Read actual [Coding AID-157](/AID/issues/AID-157) manifests and
[QA AID-158](/AID/issues/AID-158) reports, source and mutation evidence before
repair. Prior delivery `b1082a855a66eedba6a4f11fbd4fcec0e9e867ab` remains immutable;
its official manifests/archive/receipt and QA's corresponding reports/archive/
receipt were downloaded and hash-verified. Original reports/evidence/registry
remain QA-owned at `1001586788d89d2c346619a5c1b0ffe1390897f8`; none is overwritten
or merged here. Original Coding evidence remains byte-identical in this tree.

Accounting remains **one p1-02 delivery rejection / correction round 1 /
next delivery review round 2**, following p1-01 PASS and p1-02 FAIL F2-1 (P1,D2)
at the first candidate. No new PASS for either task is claimed by Coding.
One kickoff ambiguity K2-1 / clarification round 1 / kickoff round 2 CLEAR
for both and p1-00a's separate history retain their counts. Original baseline
is 23 intervention units/eight incidents; accepted live evidence remains one
cached-original/revision pair with decoded host paths for a colocated Mac client.

- **Offline tests:** fresh full Backend/MCP, parity, real registered mocked-HTTP
  request/discovery proof, mutation RED/restore/GREEN and scope/artifact audits.
- **Running product services:** no probe, deployment, restart or identity claim.
- **Real generation:** none; no training/download/worker dispatch.
- **Generated artifact retrieval:** no live Gallery bytes; fixture locators and
  downloaded review materials do not establish new generated-image retrieval.

Breaking client migration, later wait/health/worker tools, remote URL consumption,
live timeout/cancel/dedup recovery, aesthetics, three zero-intervention runs and
phase closure remain outside this correction. The existing implementation
choices and original red/green evidence remain inspectable at the prior delivery;
the only new implementation is the bounded test guard above. There are no
unresolved feature failures, widened scope or abandoned product approaches.
