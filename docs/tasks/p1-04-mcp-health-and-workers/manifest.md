# p1-04 health and configured worker — Coding manifest

Implementation delivery round 1 for [Coding AID-167](/AID/issues/AID-167).
Feature branch `aid-167-health-workers`, isolated worktree
`/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-167-health-workers`.
Base: **`b06e3109e0ef1740bb0f0ad920d1b7cbae64887c`**.
This manifest belongs to the final immutable feature commit. Its full SHA is
pinned in the Coding completion comment and external integrity receipt because
a commit cannot contain its own SHA. [QA AID-168](/AID/issues/AID-168) owns the
independent exact-commit review; Producer owns later integration/publication.
No QA verdict, new certification, deployment or Phase 1 acceptance is claimed.

## Delivered behavior

`health` replaces temporary `mcp_ping`; `list_workers` is added. Both are read
intents through existing registration, common envelopes and HttpBackendClient.
Exactly 31 names/risks are exposed; all other 29 are retained, including bounded
wait. Health reads Backend /health and then the two existing status routes.
It retains three entries through outage, partial, invalid or inconsistent reads,
and distinguishes reported probe failures from dependencies not observed via
Backend. Reachable ComfyUI no_models/degraded keep configuration, state and hints.

Worker status is extended additively on the existing Backend route. Configured
URL/expected identity survive failures; current observations and the successful
probe endpoint are populated only after the same request-local client's health
validation. Existing discovery/cache semantics and client validation are unchanged.
Cached success followed by rejected identity clears current observations while
preserving the runtime cache. URL-only success can have a null hostname.

List results are empty only for a valid unconfigured Backend read, one configured
entry even when unavailable, or a common error when configuration is unknown.
Safe current failure copy replaces raw exception text; last_error is null on
success. No persistent history, new route, private settings access from MCP,
registry, scheduling, heartbeat or control capability is introduced.

## Done when evidence

| Item | Check / level | Tests or evidence | Layer and actual boundary |
|---|---|---|---|
| D1 — three truthful health entries | test / P1 | mcp-server/tests/test_health_workers.py: test_health_retains_each_component_for_reported_worker_state; test_health_preserves_backend_local_comfyui_state_and_hints; test_backend_health_read_failure_keeps_dependencies_not_observed; test_partial_read_failure_does_not_invent_failed_dependency_probe; test_both_partial_reads_can_fail_without_losing_components | Real registered wrappers, validation/envelope and HTTP client. Mock only HTTP transport, with real Backend-exported bodies. Both no_models and degraded, unconfigured/down, outage, simultaneous/partial/invalid reads and exact GET paths. Faults D1-drop-components and D1-no-models-unreachable fail. |
| D2 — authoritative configuration/current identity | test / P1 | backend/tests/test_health_worker_status.py; mcp-server/tests/test_health_workers.py: test_list_keeps_configuration_and_only_current_accepted_observations; test_unknown_worker_configuration_is_common_error_never_empty; test_inconsistent_worker_status_is_unknown_in_both_tools | Real FastAPI route, real worker factory/client identity validation and existing discovery/cache. Mock remote HTTP and candidate enumeration only; no live sockets/scans. Ten worker cases plus five real system-route states and actual /health. Registered MCP consumes fresh exports. Connection/HTTP/identity/protocol/JSON/object failures, URL-only success, distinct resolved URL and cached success then failed identity. Faults D2-backend-error-empty, D2-cache-as-current, D2-replace-configured-url and D2-skip-identity-validation fail. |
| D3 — exactly 31 read-only discovery intents | test / P1 | mcp-server/tests/test_tool_catalog.py: test_catalog_risks_match_approved_intent_policy; test_discovered_risks_match_approved_intent_policy; test_removed_tools_and_staged_tools_are_not_registered; test_intended_catalog_matches_fastmcp_registration; test_health_workers.py request assertions; test_server.py formal stdio health call | Independent literal all-31 oracle, actual MCP discovery/registration and real client HTTP requests. Preserves the other 29 labels. Only existing GET/status paths; direct-admin host/submission/control paths cannot satisfy request assertions. Both false health=admin and existing admin=read faults fail both guards. |
| D4 — current flow, semantics and recovery docs | manual source/discovery comparison / P2 | [docs/mcp.md](../../mcp.md), [worker topic](../../windows-worker.md), [team guide](../../team/README.md); recorded requests/envelopes/discovery | Author checked active table, source schemas, recorded registration/response examples, unknown/error recovery, Backend-local vs direct-admin configuration and wait/artifact/deployment limits. Catalog documentation guard passes. No product operation or independent QA certification is implied. |

The 16 new Backend and 64 new registered MCP tests are feature checks. Each
new feature group was observed RED before implementation, then GREEN. Production
faults are recorded with exact patches, failed pytest output, exits and restoration
hashes in mutation-summary.json.
No new test makes a broken implementation pass by replacing its tool callable.

## Final verification

All pytest runs use canonical component interpreters, explicit worktree
PYTHONPATH, fresh isolated AI_DRAWING_TEST_ROOT below run-owned TMPDIR and
**--timeout=60**. Full argv/cwd/environment/UTC/elapsed/exit/output receipts are
in delivery-1-evidence. No canonical venv was
replaced or installed into; pytest-timeout==2.4.0 is scratch-only tooling.

| Scope | Exact interpreter arguments (from worktree root) | Final result |
|---|---|---|
| Backend full | backend/.venv/bin/python -m pytest -c pytest.ini backend/tests -q --timeout=60 -ra (canonical absolute interpreter; source explicitly bound to worktree) | **1916 passed, 124 Windows-only skips, 76 existing warnings in 40.99s**, exit 0; final-backend-restored.json |
| MCP full | mcp-server/.venv/bin/python -m pytest -c pytest.ini mcp-server/tests -q --timeout=60 -ra (canonical absolute interpreter; source explicitly bound to worktree) | **606 passed, two unchanged optional smoke-export skips in 3.08s**, exit 0; final-mcp-restored.json |
| Targeted Backend compatibility | backend/tests/test_health_worker_status.py, test_worker_pairing.py, test_nvidia_worker_powershell.py, test_nvidia_worker_update.py, test_worker_runtime.py, test_system_status.py | **209 passed**, one existing warning; backend-compatibility.json |
| Targeted MCP compatibility | mcp-server/tests/test_health_workers.py, test_tool_catalog.py, test_intent_boundary.py, test_server.py | **231 passed**; mcp-compatibility-green.json |
| Integrated LoRA/worker baseline | backend/tests/test_integrated_baseline.py | **4 passed**, one existing warning; baseline-compatibility-green.json |
| Import/input preservation | backend-imports.json, mcp-imports.json, preservation-audit.json, verified-input-hashes.json | Worktree source origins, exact package versions, fixed input bytes and independent literal policy recorded |

The full Backend suite produced fresh health/worker/system, lifecycle, multi-LoRA
and revision exports. MCP consumed those exact fresh files through environment
bindings; retained copies are in delivery-1-evidence/fresh-exports. The 16 new
frozen fixtures match fresh route bytes. Existing wait fixture bytes remain
unchanged. The two optional skips request SMOKE_HTTP_FIXTURE_OUT and
SMOKE_IMAGE_HTTP_FIXTURE_OUT; no new skip was added. All 124 Backend skips
require Windows. Existing warnings are listed in full, HTTP 422 status-name
deprecations, class Config deprecation, enum serialization and collection notices. No hang or final
failure remains. All 13 standing registry items retain their guarding tests;
REGISTRY.md is unchanged and only independent QA can certify new items.

No Frontend/build, Discord, launcher or real Windows run: no inputs to those
components changed. Backend route compatibility and retained registered MCP
coverage justify the full affected suites; unrelated component checks add no
proof of this behavior.

## Changed files

- Backend: backend/app/api/workers.py; new backend/tests/test_health_worker_status.py;
  backend/tests/test_worker_pairing.py, test_nvidia_worker_powershell.py and
  test_integrated_baseline.py.
- MCP: new mcp-server/mcp_server/tools/health.py; tool_catalog.py and server.py;
  new tests/test_health_workers.py and sixteen tests/fixtures/health-workers/*.json;
  tests/test_tool_catalog.py, test_intent_boundary.py, test_server.py and
  test_wait_for_job.py.
- Docs: docs/mcp.md, docs/windows-worker.md, docs/team/README.md and
  docs/memory/runtime-source-contract-verification.md; this manifest,
  implementation-plan.md and delivery-1-evidence source/receipts/exports/faults.

The official source/evidence archive inventory and exact binary/full-index patch
provide exhaustive file paths, hashes and Git blob identity. The prerequisite Git
bundle and external receipt pin the complete final commit and base.

## Baseline, deviations and approaches

Selected clean original baseline: Backend **92 passed**, one existing warning;
MCP catalog **14 passed**. No known baseline feature failure was hidden or skipped.
Initial feature REDs and eight deliberate mutant failures are expected evidence.

Existing test changes required by the approved contract are explicitly recorded:
worker pairing/integrated baseline equality now compares all legacy response
fields while permitting additive fields; a URL-only fake gains its real-client
base_url attribute. The catalog/literal oracle and retained wait discovery count
move from 30 to 31. The obsolete ping unit test is removed; its formal stdio
boundary test now calls health and asserts all three exact GET paths. The
all-tools envelope fixture now uses actual status shapes; health's aggregate
success-on-read-failure is checked for false reachability/not-observed entries,
while other tools retain common error expectations. New dedicated cases verify
health's semantics beyond that general envelope test.

The first full Backend run found four old exact-response assertions; first full
MCP found one old 30-count assertion. These were assertion migrations, not
waived failures; original receipts are retained and final full suites pass.
The intermediate MCP documentation guard also caught the old table before its
update. No behavior/specification deviation, rewrite or abandoned architecture.
Implementation uses the accepted existing routes/client rather than a parallel
configuration or worker registry. Configured expected identity is read from
Backend settings in its route; MCP never reads private Backend configuration.

The author reviewed the final diff and source/discovery/docs comparison. This
is preparation for the existing native independent QA card, not a substitute
for its review. No review.md or registry certification is authored by Coding.

## Limits and verification categories

- **Offline:** real routes, worker validation/discovery/cache with mocked HTTP
  and candidates; registered MCP client/envelopes and an ephemeral fake-Backend
  formal stdio fixture; full affected suites, red/green and mutation evidence.
- **Running product service:** none probed/restarted/deployed. Shared main,
  AID-151 active runtime/private configuration and canonical venvs preserved.
- **Real generation/training:** none; no worker submission, download, install,
  cancellation, PowerShell or control request. Reachability is not readiness.
- **Artifact retrieval:** no live Gallery/output bytes retrieved. Existing wait
  locators and identity/error behavior remain covered offline only.

One worker until Phase 3; no heartbeat/scheduling/model parity/source-identity
certification. Health uses sequential five-second HTTP status reads, not an
atomic snapshot or wait-style overall deadline. Backend-local ComfyUI is separate
from MCP_COMFYUI_API_URL for direct admin. Actual client tool-call limit remains
**unverified**, with unchanged **50-second total wait fallback**. Timeout recovery
keeps the same job ID; no automatic resubmission or worker-to-local fallback.
No models, datasets, outputs or Gallery records were deleted.

Accounting remains **p1-04 kickoff ambiguity 1 / clarification 1 / kickoff round
2 CLEAR; implementation delivery round 1, zero delivery rejections so far**.
Earlier p1-03/p1-02/p1-00a histories and all fixed kickoff/specification bytes
remain unchanged. Independent QA reviews this exact final commit before
Producer integration; later code requires a new exact-commit review. No main
merge/push or p1-05 release is performed by this Coding delivery.
