# p1-01 — uniform MCP response envelope

Combined implementation delivery with [p1-02](../p1-02-mcp-tool-consolidation/manifest.md), 2026-11-24.

## Done when evidence

| Item | Check | Level | Result / evidence | Layer and real boundary |
|---|---|---|---|---|
| D1 — every registered success/failure envelope | test | P1 | test_intent_boundary.py::test_catalog_registered_success_failure_envelope (29 × success/HTTP/connection), test_pre_body_validation_is_enveloped_and_no_http, test_prompt_compose_legacy_save_presence_rejected_before_http, test_lora_start_unknown_field_is_validated_before_http; test_server.py::test_stdio_envelope_success_and_non_lora_validation_before_http | Real catalog registration, SDK validation and actual adapters/HttpBackendClient. Only HTTP transport is replaced; formal stdio uses a separate test HTTP server. No replacement tool callable/stub. |
| D2 — retain code/hint/details and HTTP status/recovery | test | P1 | test_structured_backend_code_hint_details_preserved; test_compose_then_write_preserves_fragments_metadata_provenance_and_conflict; test_lora_uncertain_admission_keeps_canonical_job_and_no_resubmit; catalog unknown HTTP 598 cases; existing test_revision_parent_errors.py and LoRA safe projection tests | Real registered HTTP path plus existing domain projections. Canonical hints remain safe; uncertain-admission ID/classification and generation node/recording context survive in error.details. No retry/fallback. |
| D3 — envelope/error list documented | manual | P2 | [Response contract](../../mcp.md#response-envelope), [error codes](../../mcp.md#error-codes-and-recovery), [discovery snapshot](evidence/discovery.json) | Author compared prose with responses.py, registration and real call assertions; independent QA reads actual docs. |
| D4 — full MCP suite, no new failures | test | P1 | [Final MCP log](evidence/final-mcp-server.log), [command/exit receipt](evidence/final-mcp-server.json); final 458 passed / 2 unchanged optional export skips | Full separate MCP interpreter; isolated scratch; --timeout=60. Fresh Backend exports strengthen the registered cross-layer checks. |

Implementation: tools/responses.py handles shared HTTP/connection projection and
one success/error shape at registration. ContractFastMCP covers pre-body SDK
argument validation for every registered tool, retaining LoRA's migration and
safe diagnostics. Failures retain prior context in error.details; successful
fields live under data. Catalog response_category is now always envelope.

Shared evidence: [source/spec/catalog audit](evidence/source-audit.json),
[Backend log](evidence/final-backend.log)/[receipt](evidence/final-backend.json),
[parity](evidence/final-parity.log), [mutations](evidence/mutation-results.json),
[initial RED](evidence/red.log), [baseline](evidence/baseline-mcp.log).
Evidence helpers are retained as text in this directory. Source and snapshot
checks exclude manifests/evidence themselves to avoid self-reference; final
external receipts hash the complete exact package.

## Delivery identity and boundaries

- Coding: [AID-157](/AID/issues/AID-157); Producer: [AID-143](/AID/issues/AID-143).
- Branch/worktree: `aid-157-mcp-intents`,
  `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-157-mcp-intents`.
- Exact handoff base: `cee10138db8e6e944409701cdae6fb9cfe55c74f`.
  Cleared specification source: `496cee2f842dc9386d336afb237075bf952271ce`;
  actual independent round-2 kickoff reports at `9d79d203f65cf3802651a16559da13cbcc4ba14b`.
  Both task digests match the assignment; task/decision/kickoff bytes are unchanged.
- Candidate: **the one feature commit containing both manifests**. Resolve with
  `git rev-parse aid-157-mcp-intents`; the full final SHA is pinned in AID-157's
  completion and the external delivery receipt, since a commit cannot self-hash.
- Local delivery only. No merge/push or product deployment. Producer owns
  independent exact-commit delivery QA, acceptance and publication. Kickoff CLEAR
  and these test results are not implementation acceptance.
- Backend app/tests/APIs, Frontend, worker, Discord bot, graphs, resource data,
  old baseline/repair evidence and private runtime configuration are unchanged.
  Keep AID-151's active worktree and canonical Backend venv. Tests used the
  existing component interpreters without modifying installed dependencies;
  pytest-timeout 2.4.0 was installed only to run scratch.

## Verification

All commands ran from the feature worktree with isolated test roots below the
injected TMPDIR. Full command arrays, exact environment/times and exit codes are
in the linked JSON receipts. Common setup:

```sh
export PYTHONNOUSERSITE=1
export PYTHONPATH="$PAPERCLIP_RUN_SCRATCH_DIR/timeout-plugin"
export MCP_TEST_PYTHON=/Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python
export REVISION_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/revision-http.json"
export MULTI_LORA_HTTP_EXPORT="$PAPERCLIP_RUN_SCRATCH_DIR/multi-lora-http.json"
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-backend" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra
export LORA_LIFECYCLE_HTTP_FIXTURE="$TMPDIR/aid-157-final-backend/http-export.json"
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-mcp-server" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/mcp-server/.venv/bin/python \
 -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra
AI_DRAWING_TEST_ROOT="$TMPDIR/aid-157-final-parity" \
 /Users/tf00185088/Desktop/tim-project/ai-drawing/backend/.venv/bin/python \
 -m pytest -c pytest.ini backend/tests/test_lora_start_contract_parity.py -q --timeout=60
```

Results: Backend **1900 passed, 124 skipped, 76 warnings in 42.15s**, exit 0;
final MCP **458 passed, 2 skipped in 1.78s**, exit 0 (exact timing in receipt/log);
final Backend/MCP LoRA schema parity **5 passed, 1 warning in 0.29s**, exit 0.
All Backend skips require Windows. The two unchanged MCP skips require optional
smoke HTTP/image-validation exports whose producing harness is not part of this
checkout. No skip was added or expanded. Revision and uncertain-admission
export consumers did execute, now through the real registered MCP wrappers in
the separate MCP interpreter. No Backend package was imported into MCP tests.
The full Backend and MCP runs also satisfy both standing guards in REGISTRY.md;
Coding does not edit QA's registry or claim new certified coverage.

Raw pytest logs retain their original trailing whitespace; candidate whitespace
checks exclude only those evidence logs. Source/docs whitespace checks pass.

The clean baseline was **314 passed, 4 skipped in 1.03s**. Tests tied to removed
names/shapes were migrated, retaining their feature assertions. Two existing
export skips were resolved by supplying fresh Backend fixtures. No feature test
was deleted. The removed Civitai registration schema check became an absence
check, while its private adapter's existing feature tests remain. Prior repair
suite numbers are historical context only, not evidence for this surface.
The Backend full-suite result precedes later MCP-only validation/guidance/test
edits: its Backend code/test/dependency inputs remain identical, and final
cross-layer parity was rerun. Frontend/worker/launcher/build/Windows suites were
not run because their code/dependencies were unchanged.

Five deliberate production mutations failed their intended registered-path
tests: flat success shape (29 failures), lost Backend code (4), missing legacy
save replacement hint (4), accidental compose save payload (1), wrong custom
mode dispatch (1). Each file was restored byte-for-byte in a finally block.
The initial envelope tests and unknown-LoRA-field check also failed before their
respective fixes. Saved mutation commands/logs identify these checks; no mutant
is delivered. Final full MCP results apply to the restored final source.

Verification layers are distinct:

- **Offline software:** fresh full suites, registered HTTP-transport cases,
  formal stdio success/validation with a test-only HTTP server, Backend-generated
  serialized fixtures, mutation checks and static catalog/spec/scope audit.
- **Running product service:** no intentional product preflight/deployment or
  restart. The preexisting ping unit in baseline/intermediate suites could
  attempt the default Backend /health; it is now mocked and the formal protocol
  test uses its own test server. No runtime identity/readiness claim follows.
- **Real generation:** none. No GPU, training, download or worker dispatch.
- **Generated artifact retrieval:** none from the live Gallery. Synthetic
  offline fixtures check locators/metadata; accepted historical colocated Mac
  PNG decoding remains separate and does not establish remote URL consumption.

Known limits: this is a breaking MCP change, awaiting independent QA. Existing
smoke-export skips and Windows-only skips remain disclosed. No timeout retry,
failed-worker fallback, later wait/health/worker tool, Backend API change,
cross-call prompt transaction, aesthetic verdict or phase-close claim is added.
The original no-repair baseline remains **23 units/eight incidents**; accepted
repair remains one cached-original/revision pair for a colocated Mac client.

## Implementation choices and prior failures

Preexisting failing tests: none in the baseline. Intermediate expected failures
covered old result shapes and discovery names; one real SDK issue surfaced when
an optional workflow string was pre-parsed into a dict. The delivered workflow
field is a string with an empty default, preserving the original JSON-string
transport; custom mode requires a nonempty value. This avoids changing the
Backend or accepting a new graph format. A central catalog registration pass
initially exposed a circular import for tests importing an adapter first;
client construction was moved to client.py, eliminating adapter imports of the
server. Both cases have registered-path coverage in the final suite.

Routine implementation choices: central registration applies one envelope while
reusing private adapters; no large business-logic replacement. Old Python
adapter names remain internally for reuse/tests but are absent from MCP
discovery. Single risk labels and canonical tool names match the approved map.
style_preset_save uses the Python-safe selector `from_source=fields|successful_job`;
new dispatchers reject incompatible mode inputs rather than silently dropping
caller intent. Prompt archive/restore retain Backend concurrency enforcement,
including explicit revision 0; only omission is rejected before access. Legacy
LoRA migration errors retain precedence over generic unknown-field validation.

Intentional test changes are limited to discovered names, common generic error
codes, moved envelope context and updated next-step text; LoRA safe projection,
known revision-parent allowlist/redaction and existing forwarding constraints
remain checked. Unknown unstructured preset HTTP errors now follow the common
backend_http_error contract (including HTTP 409), while structured Backend codes,
hints and details remain preserved. There are no unresolved scope deviations.
A fresh review will be performed on the existing separate QA card; no author
self-review or kickoff verdict is represented as independent delivery PASS.
