Verdict: PASS
Review round: 1

Reviewed FINAL implementation: **`72f483418524a613fb104b92ab483e39f7432bfc`**.
Candidate tree: `42e521bed0adbc7e9e1c6fe72d9c62babbec4d4e`.
Fixed base: `b075f36c0eec532071e11328eb4f2b21b52e1c0f`.
Task SHA-256: `28077043ebe82e1371657219e6bab0685a8ec1918ec8130b122dad097dbc88e8`.
Full MCP decision SHA-256: `d477af0600efb30ec35eccd9173e82ec01732294b8cc9257905208d1f345c7e0`.
Clarification SHA-256: `8fc12d877dc004dddf4dbf09177ffcc7b2d7c98ee3ce91bf84aa3ac06768670f`.
Date: 2026-11-24 UTC. Independent QA: [AID-168](/AID/issues/AID-168).
Coding: [AID-167](/AID/issues/AID-167). Producer: [AID-145](/AID/issues/AID-145).

All four cleared items pass for this exact candidate. QA made no candidate
product, test, dependency, specification or manifest repair. Producer owns
acceptance, integration/publication and later p1-05 release. Later candidate
code requires another exact-commit review.

## Findings

No blocking defect or specification ambiguity demonstrated. This delivery
replaces ping with health and adds list_workers, both read-only. It uses existing
status routes and existing worker validation/discovery/cache, with an additive
Backend response. Configuration survives probe failure; accepted current
observations remain separate from expectations and the derived runtime cache.

## Exact identity and preservation

I read the actual completed Coding card, official manifest and external
integrity record before substantive review. I pinned the full SHA on this
recipient card in [comment defab3fd](/AID/issues/AID-168#comment-defab3fd-3012-4d7d-9d3f-9cf9cb894a32),
then created my own worktree at that commit:
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-168-qa`,
branch `aid-168-exact-review`. Coding's directory and a moving branch did not
supply the reviewed source.

- All five official downloads match their attachment sizes and SHA-256 values.
  The uploaded manifest equals its exact candidate Git blob.
- All **159 indexed payloads / 160 ZIP members** match their hashes, sizes,
  Git blob identities and immutable candidate bytes.
- The official patch equals the binary/full-index base-to-candidate Git diff.
  Applied to the base index in a scratch repository, it reconstructs the exact
  candidate tree. The prerequisite bundle verifies and fetches the named SHA.
- All **509 inherited docs/tasks paths**, including every prior task/report,
  p1-04 kickoff/clarification/history and the 13-row registry, are unchanged
  between handoff base and candidate. Cleared task/decision/clarification hashes
  match those above. Accepted p1-03 feature `77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce`,
  QA `d088c3258ab782623631d60daaaccc8ce6fcb6dc` and kickoff-2 report
  `e75a94ec63a507bac194b702a87eb369ea1ccb20` are ancestors. I read the actual
  p1-03 manifest, PASS and acceptance, and the current cleared task/decision.
- QA's separate literal 31-name risk oracle matches actual catalog and SDK
  discovery. The other 29 names/labels match the fixed accepted policy, including
  ComfyUI admin and wait=read. No expectation is derived from the candidate catalog.

See [candidate integrity](qa-delivery-1-evidence/candidate-integrity.json),
[official upload metadata](qa-delivery-1-evidence/official-coding-attachments.json),
[Coding external record](qa-delivery-1-evidence/coding-external-integrity.json)
and [source/docs audit](qa-delivery-1-evidence/source-docs-audit.json).

## Done when assessment

| Item | Level | Result | Independently checked boundary |
|---|---|---|---|
| D1 — three truthful health entries | P1 | PASS | Actual registered wrappers/envelope and HttpBackendClient with mocked HTTP, consuming this QA run's real Backend route bodies. Backend, Backend-local ComfyUI and worker remain present for up/down/unconfigured, Backend outage, HTTP/JSON/shape failures, individual and simultaneous partial failures. Failed reads are not_observed with configuration unknown; reported failed probes and confirmed unconfigured have distinct reasons. no_models/degraded remain reachable with original configuration/counts/warnings/hints. Backend-down sends only GET /health; otherwise the two status reads are independent. |
| D2 — authoritative worker identity | P1 | PASS | Real FastAPI route and real worker factory/client validation, mocking only remote HTTP and discovery candidates. Configured up/down, connection/HTTP/JSON/object errors, hostname/protocol mismatch, URL-only success without hostname, distinct discovered endpoint and cached success followed by rejected identity all execute. Configured URL/expected identity survive failures; observations/resolved endpoint are null on failure; current last_error is safe and null on success. Existing flags/error_type/nested worker remain. Registered MCP returns empty only for confirmed unconfigured, one configured entry even unavailable, and common errors for unavailable/invalid/inconsistent Backend reads. |
| D3 — 31 intents and GET-only discovery | P1 | PASS | Independent literal policy verifies catalog and actual SDK discovery, exactly one risk label per tool, ping absent and other 29 labels retained. Request assertions traverse real wrappers/client. QA's separate probe records **51 registered calls / 107 GETs** exclusively to configured Backend /health, /api/system/status and /api/workers/status. Direct-admin URL is deliberately different. No submission/control path is used. Retained bounded wait, envelopes, errors, identities and capabilities pass in the full MCP suite. |
| D4 — documentation and recovery | P2 | PASS | Manual source/discovery comparison of docs/mcp.md table, current flow, health behavior, examples, configuration and recovery, plus matching worker/team/runtime-memory docs. The active table equals the independent 31-risk map; configured-unavailable and invalid_backend_status JSON examples equal actual registered responses. Configuration/expectation/current-null distinctions, unknown read recovery, one-worker limits and Backend-local versus direct admin are accurate. Accepted wait/result/error/locator guidance and unverified client-limit/50-second total fallback remain truthful. |

The [recorded samples](qa-delivery-1-evidence/registered-samples.json) retain full
envelopes, discovery schemas and exact requests. The 19 retained
[fresh exports](qa-delivery-1-evidence/fresh-export-index.json) come from QA's
final restored Backend run, with explicit MCP input bindings. Existing
test changes are the approved additive-response assertions, ping replacement,
31-count/literal-map migrations and health's specified aggregate-on-read-error
behavior. Legacy flag/nested/error checks remain; common-envelope guards still
execute. No standing item needs supersession.

## Commands and independent results

Commands run from the isolated worktree root using canonical Backend Python
3.11 and MCP Python 3.10, without changing either venv. Each pytest invocation
has **--timeout=60**, a fresh dedicated AI_DRAWING_TEST_ROOT below run-owned
TMPDIR, explicit worktree PYTHONPATH and MCP_TEST_PYTHON. Scratch-only
pytest-timeout 2.4.0 supplies the timeout plugin. Corrected import receipts pin
all Backend and MCP module origins to this exact worktree in their respective
interpreters. Full argv/cwd/environment/UTC/elapsed/exit/output receipts are in
[QA evidence](qa-delivery-1-evidence/README.md).

| Check / interpreter arguments | Actual result |
|---|---|
| Initial Backend: -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra | Exit 0; 1916 passed, 124 Windows-only skips, 76 warnings in 41.44s |
| Final restored Backend: same arguments, new isolated root and exports | Exit 0; **1916 passed, 124 Windows-only skips, 76 warnings in 42.21s** |
| Initial corrected MCP: -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra | Exit 0; 606 passed, two optional skips in 3.20s |
| Final restored MCP: same arguments, fresh final Backend exports | Exit 0; **606 passed, two unchanged optional skips in 3.27s** |
| Independent literal/discovery/HTTP probe: registered-probe.py.txt | Exit 0 both times; **51 registered calls, 107 recorded GETs**, exact 31 risks and other 29 preserved |
| Fresh p1-03 real-route/SQLite producer: delivery-1-evidence/backend-shape-export.py.txt under that task | Exit 0; 0.654s process; synthetic PNGs and mocked queue only, no product service |
| Additional registered fresh wait consumer: -m pytest -c pytest.ini scratch/test_fresh_wait_consumer.py -q --timeout=60 -s | Exit 0; **28 passed in 0.51s**; includes same-domain recovery, identity/locators/smoke and 45 ms partial-enrichment budget observed at 47.3 ms, three GETs |
| Official inputs, fixed history/source, module origins and docs/example checks | Pass, with setup corrections recorded below |

Full Backend/MCP reruns include all **13 earlier standing registry items**,
including the broad full-suite guards, LoRA parity/admission, envelopes, merged
capabilities, literal risks and bounded wait. The fresh full Backend produces
health/system/worker, revision, multi-LoRA and lifecycle exports consumed by
MCP. The existing p1-03 fixed fixture remains unchanged; a separate additional
consumer also uses freshly produced route/SQLite shapes. Prior kickoff or
Coding results do not substitute for these runs.

All Backend skips require Windows. MCP's two optional skips require
SMOKE_HTTP_FIXTURE_OUT and SMOKE_IMAGE_HTTP_FIXTURE_OUT; no new skip was added.
Fresh health, wait/smoke-shape and other exported consumers execute. Warnings
are the existing HTTP-422 naming, Pydantic/class/enum and collection notices,
retained in full logs. No final failure or hang remains.

## Fault, restoration and final GREEN

For each automated acceptance item I changed production in my isolated QA
worktree, ran related tests myself, and restored exact immutable bytes in
finally. Tests and tool callables were not replaced. All faults compile and
reach assertion failures; none is a collection/setup failure. Exact patches,
commands, full RED output and restoration hashes are in
[fault-summary.json](qa-delivery-1-evidence/fault-summary.json).

| Deliberate production fault | Observed RED |
|---|---|
| D1: drop worker component on Backend failure | 7 failed |
| D1: mark reachable no_models/degraded unreachable | 2 failed, 3 passed |
| D2: configured-down becomes empty | 7 failed, 3 passed |
| D2: unknown Backend read becomes empty | 6 failed |
| D2: failed observation filled from configuration | 7 failed, 3 passed |
| D2: overwrite configured URL with discovered endpoint | 1 failed, 9 passed |
| D2: skip real client hostname validation | 2 failed, 8 passed |
| D3: change real status reads to POST | 64 failed |
| D3: label new health admin | 2 failed, both literal catalog/discovery guards |
| D3: label retained ComfyUI admin read | 2 failed, both literal catalog/discovery guards |

All ten faults exit 1 and restore before final full Backend and MCP GREEN.
The source/docs audit confirms every tracked candidate byte restored before
the report/registry additions. Three new automated items are independently
certified; the regenerated registry retains all prior rows, totaling **16 active
items**, with no supersession. D4 is manual with supporting catalog/doc checks.

## Setup corrections and notes

Three QA setup corrections are recorded in [setup-notes.json](qa-delivery-1-evidence/setup-notes.json):
the import helper initially tried both stacks in each component interpreter
(missing mcp in Backend and FastAPI in MCP); the scratch bundle prerequisite
initially existed only as an unreferenced fetched object; and the first full
MCP attempt lacked the promoted lifecycle input (**1 failed, 605 passed, two
skips**). Component-specific imports, a scratch prerequisite ref and promotion
of QA's own fresh Backend http-export.json resolve these without candidate
changes. Failed import/MCP logs remain, and the bundle setup error is recorded
with the successful corrected integrity proof. No test/specification was
weakened or hidden to obtain PASS.

Health uses sequential five-second HTTP reads rather than an atomic snapshot
or a wait-style total deadline; this is accurately documented and not a cleared
task defect. Existing LAN discovery can probe/copy its derived runtime URL;
it adds no multi-worker registry, heartbeat, scheduling or control capability.

## Limits and disposition

- **Offline verification:** suites, real Backend routes/client validation under
  mocked transport/candidates, real registered/stdio MCP boundaries, fixtures,
  production faults, hashes and source/discovery documentation review.
- **Running product:** no probe, restart, deployment or loaded-source claim.
  Shared main, AID-151's active runtime/worktree/private configuration and
  canonical venvs were preserved.
- **Real generation/training/download/worker dispatch:** none. Discovery
  neither submits nor cancels; a timeout requires inspecting the same job ID
  before resubmission. No automatic worker-to-local fallback.
- **Product artifact retrieval:** no live Gallery bytes or remote URL
  consumption. Synthetic fixture PNG validation and review-packet downloads
  are separate evidence. Locators establish neither bytes nor client access.
- **Unchecked components:** Frontend/test/build, native Windows, worker runtime,
  launcher and Discord bot execution; their source/dependency inputs did not
  change. Reachability certifies neither remote ComfyUI, model parity, generation
  readiness nor source identity. The actual client call limit remains unverified;
  50 seconds is the retained total wait fallback policy, not a measurement.

Complete this recipient-owned review card with **PASS** and the exact report/
evidence/registry commit plus official uploaded report/archive/patch/bundle/
external integrity record. Producer reads the actual verdict and owns the next
action. No parent write, main merge/push, p1-05 release or later live smoke is
performed by QA. Models, datasets, outputs and Gallery records are retained.

Accounting: **p1-04 kickoff ambiguity 1 / clarification 1 / kickoff round 2
CLEAR; implementation delivery review 1 PASS, zero delivery rejections**.
Earlier p1-03, p1-02 and p1-00a histories remain separate and unchanged.

## Coverage

| item | level | guarding_test | status |
|------|-------|---------------|--------|
| D1 | P1 | mcp-server/tests/test_health_workers.py::test_health_retains_each_component_for_reported_worker_state; mcp-server/tests/test_health_workers.py::test_health_preserves_backend_local_comfyui_state_and_hints; mcp-server/tests/test_health_workers.py::test_backend_health_read_failure_keeps_dependencies_not_observed; mcp-server/tests/test_health_workers.py::test_partial_read_failure_does_not_invent_failed_dependency_probe; mcp-server/tests/test_health_workers.py::test_both_partial_reads_can_fail_without_losing_components | active |
| D2 | P1 | backend/tests/test_health_worker_status.py::test_worker_route_configuration_and_current_observation; mcp-server/tests/test_health_workers.py::test_list_keeps_configuration_and_only_current_accepted_observations; mcp-server/tests/test_health_workers.py::test_unknown_worker_configuration_is_common_error_never_empty; mcp-server/tests/test_health_workers.py::test_inconsistent_worker_status_is_unknown_in_both_tools | active |
| D3 | P1 | mcp-server/tests/test_tool_catalog.py::test_catalog_risks_match_approved_intent_policy; mcp-server/tests/test_tool_catalog.py::test_discovered_risks_match_approved_intent_policy; mcp-server/tests/test_tool_catalog.py::test_removed_tools_and_staged_tools_are_not_registered; mcp-server/tests/test_health_workers.py; mcp-server/tests/test_server.py::test_stdio_envelope_success_and_non_lora_validation_before_http | active |
