Verdict: CLEAR
Kickoff round: 2

Reviewed published source: **`5cf158b65d924a9508a3b5bfb7b47adb92eff7a1`**.
Source tree: `19fbeb931a89f67afc991ec0cd37c94d624be1c7`.
[Task](task.md) SHA-256:
**`28077043ebe82e1371657219e6bab0685a8ec1918ec8130b122dad097dbc88e8`**.
[Full MCP decision](../../decisions/mcp.md) SHA-256:
**`d477af0600efb30ec35eccd9173e82ec01732294b8cc9257905208d1f345c7e0`**.
Clarification 1 SHA-256:
`8fc12d877dc004dddf4dbf09177ffcc7b2d7c98ee3ce91bf84aa3ac06768670f`.
Independent recipient: [QA AID-166](/AID/issues/AID-166).
Coordinator: [Producer AID-145](/AID/issues/AID-145). Date: 2026-11-24 UTC.

My reading: CTY wants agents to complete the image/revision flow through MCP
without manual repairs. Phase 1 needs truthful read-only visibility of the
Backend, Backend-local ComfyUI and the existing single worker. Configuration,
expected identity and current accepted observations must remain distinguishable.
Preserve the accepted envelopes, risks, wait, result identities and recovery;
leave registry, heartbeat and scheduling in Phase 3. Reachability does not prove
worker model parity, remote ComfyUI, generation readiness, loaded source or
artifact access.

I recorded my owner reading before opening
the repository task in this round. The assignment had already supplied the
complete task/decision text; this was independent reasoning, not a blind read.
The [later owner instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md)
authorizes ordinary technical choices within the existing boundaries. The
[roadmap](../../roadmap/ROADMAP.md), [plan](../p1-planning-2026-11-24/plan.md),
[team guide](../../team/README.md) and active state retain the independent
kickoff and exact-final-commit delivery gates. No routine owner confirmation
is needed for this bounded clarification.

Difference: **none remaining at specification level**. Clarification 1 resolves
K4-1 with an authoritative additive response contract on the existing status
route. All four revised requirements are implementable and testable. This
CLEAR permits Coding dispatch after Producer reads it; it is not implementation
acceptance, deployment, a readiness certification or Phase 1 exit proof.

## K4-1 disposition

**Resolved at specification level.** The actual round-1 result remains
AMBIGUITY, report/evidence commit
`3a980ec557e5ab23a91e917491b13c947587f63d`; it is not reclassified.

The original failure scenario remains real: the current worker-status route
returns configured/reachable/status/error_type but lacks the configured URL,
expected identity and current-error fields. The clarified contract explicitly
permits adding those meanings to that existing response, preserving its flags,
failure error_type and successful nested worker response. MCP consumes the
Backend response, without private Backend settings access, parallel configuration
or another endpoint.

The decision now fixes each previously disputed meaning:

- `url` is the normalized configured URL; expected hostname/protocol are
  configuration, including the existing protocol default.
- Current `hostname`, `protocol_version` and `resolved_url` require an accepted
  current probe. Failure or rejected identity clears these observations;
  expected or stale values cannot fill them. URL-only success can legitimately
  have null hostname and a valid protocol.
- Accepted discovery can supply a distinct `resolved_url`; it never rewrites
  the configured `url`. The derived runtime cache remains existing behavior.
- A failed configured-worker probe retains one entry and a safe current
  `last_error`; success sets last_error null. There is no persistent error history.
- Only a successful authoritative unconfigured response yields an empty list.
  Backend connection/HTTP/invalid-status failures return a common error envelope
  with stable code and safe read/configuration recovery guidance.

The new shape probe independently
exercises real existing routers/client validation with mocked HTTP and candidate
selection. In its discovery case the configured address is `192.0.2.10`, while
accepted discovery and a subsequent cached read use `192.0.2.11`. A later
identity failure leaves that cache available to a new client, but returns
unavailable and no accepted nested worker. This demonstrates why Coding must
capture the same successful probe's actual endpoint and clear failed current
observations, rather than treating a cached address as current evidence.
No live scan occurred. These are existing-source observations, not target
list_workers output or evidence that the required extension has been delivered.

## Done when assessment

| Item | Kickoff result | Reasons and required delivery proof |
|---|---|---|
| D1 — three truthful health entries | CLEAR | Existing GET /health, /api/system/status and /api/workers/status are sufficient sources. Keep one Backend, ComfyUI and worker entry on Backend-down or partial read failure. False reachability must distinguish not observed through Backend from an endpoint-reported failed probe; preserve ComfyUI configuration/state/hints. no_models/degraded may remain reachable. Registered-tool tests must cover up/down/unconfigured, Backend outage, partial/invalid reads and reachable no-model/degraded responses, with recorded GETs. No direct dependency fallback is authorized. |
| D2 — configured worker and accepted identity | CLEAR; K4-1 resolved | The normative field meanings above make empty/one/error outcomes judgeable and authorize the necessary additive response extension. Test actual Backend routes/client validation and registered MCP wrappers/client under mocked transport: unconfigured, up, connection/HTTP failure, hostname and protocol mismatch, invalid status, URL-only success without hostname, distinct discovered endpoint, and cached success followed by failed validation. Retain existing response consumers; never erase configuration, reuse stale observations or infer empty configuration on a failed Backend read. |
| D3 — read-only catalog/discovery and compatibility | CLEAR | Current registration has 30 intents with ping and bounded wait. Replacing ping with health and adding list_workers gives exactly 31, preserving the other 29 names/risks. The existing independent literal risk map/discovery guards can be explicitly updated from the normative policy; deriving expected risks from the catalog is insufficient. Record actual registered MCP HTTP requests to only the existing GET/status paths; no generation/training, cancellation, PowerShell, install or control request. Existing discovery/cache is not a new registry or scheduling path. |
| D4 — delivered tools and recovery documentation | CLEAR | docs/mcp.md currently documents the accepted 30-tool surface and staged health. Delivery must update its active table, flow, examples, identity/null/error recovery and configuration guidance together, checked against actual source/discovery. Explain Backend-local ComfyUI versus MCP_COMFYUI_API_URL for direct admin, one configured worker, and the limits of reachability. Preserve accepted wait/result/error guidance and distinguish software availability from deployment or retrieved bytes. |

These are specification verdicts. No p1-04 manifest or delivery review exists
at the reviewed source; no new delivery review.md or registry certification is
appropriate. Response layout and stable error-code spelling remain bounded
Coding choices under the existing common envelope.

## Source and acceptance boundaries

- [Worker route](../../../backend/app/api/workers.py), lines 51–77: current
  unconfigured/unavailable/ready branches and nested success. The extension is
  necessary implementation work, explicitly authorized by the revised scope.
- [Settings](../../../backend/app/config.py), lines 97–108, and
  [worker client](../../../backend/app/services/nvidia_worker.py), lines 175–285
  and 406–439: normalized configuration, expected identity, validation, discovered
  runtime URL/cache and successful status return. Existing LAN discovery remains
  constrained; no worker-control capability or public exposure is added.
- [System route](../../../backend/app/api/system.py),
  [schema](../../../backend/app/schemas/system.py) and
  [dependency status](../../../backend/app/services/dependency_status.py), lines
  198–279: dependency state/configuration/reachability are independent.
  Backend /health is application-only. Tests confirm reachable no_models and
  degraded; model inventory describes the Backend host, not the worker.
- [Registration](../../../mcp-server/mcp_server/server.py),
  [client](../../../mcp-server/mcp_server/client.py),
  [envelope](../../../mcp-server/mcp_server/tools/responses.py),
  [catalog](../../../mcp-server/mcp_server/tool_catalog.py) and
  [literal guards](../../../mcp-server/tests/test_tool_catalog.py) were checked
  together. MCP config has separate Backend and direct-admin ComfyUI URLs.
  The future aggregate must handle each read outcome safely; generic outer
  exception handling alone cannot satisfy D1's three-entry requirement.

Backend-down/partial-read output is a future registered-tool acceptance
obligation, explicitly settled by D1 and the normative decision. No implemented
aggregate exists to execute now. No job is created by discovery: duplicate
submission/cancellation concerns are addressed by proving their absence from
recorded requests and read-only recovery. A timeout is never permission to
resubmit an existing job. The accepted wait behavior is unchanged.

I read actual p1-03 [manifest](../p1-03-mcp-wait-and-result/manifest.md),
[PASS](../p1-03-mcp-wait-and-result/review.md) and
[acceptance](../p1-03-mcp-wait-and-result/acceptance.md). Accepted feature
`77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce` and independent QA
`d088c3258ab782623631d60daaaccc8ce6fcb6dc` are ancestors; their manifest/PASS
bytes are unchanged. All 13 standing registry items remain unchanged.
The actual client limit is still unverified; 50 seconds is policy fallback,
not measurement. Preserve canonical/image identity separation, safe errors,
nullable locators and same-ID recovery; locators prove neither bytes nor access.

## Commands, results and evidence limits

Evidence README identifies commands, full output,
argv, cwd, selected non-secret environment, UTC start, elapsed time and exit.
This worktree is `/Users/tf00185088/Desktop/tim-project/ai-drawing-worktrees/aid-166-kickoff-review`,
branch `aid-166-p1-04-kickoff-round-2`, created at the full reviewed SHA.

| Check | Result |
|---|---|
| Source/task/decision/preservation audit | Exit 0; exact hashes/tree; all 18 original QA paths preserved (original report mapped to round-1 snapshot); product/test/config inputs unchanged against round 1 and accepted p1-03; 13 registry rows retained |
| Selected existing Backend tests | Exit 0; **10 passed, 1 warning in 0.10s**; URL-only identity, rejected/matching identity, cached discovery factory, reachable no_models/degraded |
| Existing MCP catalog file | Exit 0; **14 passed in 0.23s**; 30 current literal risks, real registration/discovery, schemas/envelopes and current documentation |
| Additional existing-route/client probe | Exit 0; **11 cases, 12 worker GETs**; unconfigured/down/HTTP failure/matching/hostname mismatch/protocol mismatch/invalid protocol/URL-only/discovery/cached success/cached identity failure; zero submission/control requests |
| MCP import binding | Exit 0; registration/client/catalog/envelope origins resolve this pinned worktree |

Pytest used distinct roots below TMPDIR and --timeout=60. Canonical Backend/MCP
interpreters were unchanged; pytest-timeout 2.4.0 was installed into run-owned
scratch only. Two QA setup corrections are recorded in setup-notes.json: the
registry parser expected an absent status column, and the canonical interpreter
has no pip. Counting actual table rows and using uv with scratch --target fixed
the helpers without changing registry, product, dependencies or tests.

Prior round-1 Backend 9/one warning and catalog 14 passes remain prior evidence.
The audit confirms identical product/test/config and docs/mcp inputs, preserving
their source-contract relevance; that reuse does not certify current packages,
private runtime or future p1-04 behavior. Fresh selected checks above are this
round's results. Earlier full Backend 1900/124 Windows skips and MCP 540/two
optional skips remain the p1-03 QA result, not newly run suites here.

Offline checks and source/specification review only. Full Backend/MCP, Frontend,
build, native Windows and historical registry suites were not rerun for this
docs-only kickoff. No live service probe/restart/deployment, real generation,
training/download/worker dispatch or live Gallery-byte retrieval occurred.
Review-packet retrieval is distinct from product-artifact retrieval.
Shared main, AID-151 runtime/worktree/private configuration, canonical venvs,
models, datasets, outputs and Gallery records were preserved. No specification,
clarification, decision, product, existing test or historical evidence was
edited to obtain CLEAR. Registry bytes are unchanged; no delivery certification
was added or superseded.

## Disposition and accounting

Complete [AID-166](/AID/issues/AID-166) with **CLEAR** for the fixed clarified
specification. Producer reads this actual verdict before creating Coding and a
separate exact-final-commit delivery-QA card. Independent delivery PASS still
precedes feature merge/push and p1-05 release. No parent write is required.
The official report, indexed source/evidence packet, exact binary patch,
verified prerequisite Git bundle and external integrity receipt identify the
full report/evidence commit; the external receipt binds that commit because a
commit cannot contain its own SHA.

p1-04 accounting: **one kickoff ambiguity / clarification 1 / kickoff round 2
CLEAR; zero implementation delivery rejections**. The original round-1 task,
report/evidence and Producer clarification remain intact. Prior p1-03,
p1-02 and p1-00a histories retain their separate results and counts.
