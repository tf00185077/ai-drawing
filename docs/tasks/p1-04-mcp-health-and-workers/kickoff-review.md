Verdict: AMBIGUITY
Kickoff round: 1

Reviewed published source: **`c70162dee637bfa5e954aa446bf38faad97bbecd`**.
Source tree: `afd85386a1e3424cdbd308b87a698b3f68ca1602`.
[p1-04 task](task.md) SHA-256:
**`114c0518f1c960e9bae5e3cb94ab9ab3cc795ac883a6f14d0b037b29fc8d3558`**.
Independent recipient: [QA AID-165](/AID/issues/AID-165).
Coordinator: [Producer AID-145](/AID/issues/AID-145).
Date: 2026-11-24 UTC.

My reading: CTY authorized ordinary executable choices inside Phase 1, retaining
independent kickoff and exact-commit delivery gates. Agents need read-only views
of the Backend, Backend-local ComfyUI and the existing single configured worker
before generation. Replace temporary `mcp_ping` with `health`, add `list_workers`,
and preserve accepted unrelated capabilities, risks, envelopes and bounded wait.
Missing configuration and failed observations must remain distinguishable;
unknown worker identity cannot be invented. This introduces no registry,
heartbeat, scheduling, worker deployment or submission-based readiness check.

I recorded [this reading](kickoff-1-evidence/owner-reading.md) after reading the
owner request, active roadmap and settled decisions, before opening repository
`task.md`. The issue had already supplied the task text; this was not a blind
reading of that inline text. [The owner instruction](../../requests/2026-11-24-proceed-within-project-boundaries.md)
delegates technical choices inside the approved boundaries; it does not waive
review. [The roadmap](../../roadmap/ROADMAP.md) and
[accepted plan](../p1-planning-2026-11-24/plan.md) put this work before p1-05
and reserve the registry/heartbeat/scheduler for Phase 3.

Difference: **K4-1, configured-worker identity when observation fails**, below.
The objective matches the owner direction, but D2 does not settle the meaning
and source of required identity fields in that case. This is a Producer-owned
technical clarification, not an owner-boundary question or implementation defect.

## Done when assessment

| Item | Kickoff result | Assessment and required delivery boundary |
|---|---|---|
| D1 — three health entries, reachable/reason, up/down/unconfigured tests | CLEAR | Existing `GET /health`, `GET /api/system/status` and `GET /api/workers/status` provide the reachable/unconfigured observations. Backend failure must still leave one useful entry per component in the common envelope, with safe reasons distinguishing dependencies not observed through the unavailable Backend from a failed dependency probe. A single exception must not erase that view. Response layout and error-code spelling remain Coding choices. Mock Backend-down and partial status-read failure as well as endpoint-reported down/unconfigured. |
| D2 — empty or one configured worker with status fields | AMBIGUITY K4-1 | Existing worker status distinguishes configured/unconfigured but cannot supply the requested URL and down-case identity metadata to MCP. Decide which fields describe configuration versus observed worker identity, what is null on failed probes, and explicitly permit the minimal existing-response extension if that is the chosen source. No multi-worker inventory is required. |
| D3 — both tools read-only and catalog-labelled read | CLEAR | The selected health/status paths are GETs. The real worker client uses GET `/v1/worker/status`; optional existing discovery uses connection/status probes and a derived in-memory URL cache. No generation, training, cancellation, PowerShell, install or submission path is needed. Delivery tests must traverse real MCP registration/wrappers/client and record actual paths/methods, in addition to independent literal risk/discovery assertions. Replace ping, add two read intents, and preserve the other 29 names/labels: the resulting surface is 31 intents. |
| D4 — docs/mcp.md documents both tools | CLEAR | Update the active table, examples/current flow, configuration/recovery guidance and staged-ping statements together. Explain unknown observations and configured/observed identity as clarified for D2. Backend-reported local ComfyUI health and MCP direct-ComfyUI admin configuration must stay distinct. Document reachability without claiming worker model parity, generation readiness, deployment or artifact access. |

These are specification assessments, not p1-04 implementation PASS results.
No p1-04 manifest exists at the reviewed source. No delivery `review.md` or new
registry certification is appropriate for this kickoff.

## K4-1 — settle configured identity and unknown observed identity

Concrete case: configure `NVIDIA_WORKER_URL=http://worker.invalid:8791`, expected
hostname `EXPECTED-PC` and protocol 2, then let the worker connection fail.
The actual existing route returns:

```json
{"configured": true, "reachable": false, "status": "unavailable", "error_type": "ConnectError"}
```

It supplies no URL, expected hostname/protocol or nested observed worker.
The up response also supplies no worker URL. With URL-only configuration,
`health()` accepts a valid protocol response without a hostname, so reachable
cannot establish that every identity field is available. These cases were
reproduced through real existing routes and client validation with synthetic
settings and mocked HTTP; see [route-shapes.log](kickoff-1-evidence/route-shapes.log).

Sources:

- [workers.py](../../../backend/app/api/workers.py), lines 51–77: unconfigured,
  unavailable and ready branches; failure returns only `error_type` beyond flags.
- [Backend settings](../../../backend/app/config.py), lines 97–108: URL,
  optional expected hostname and expected protocol are Backend configuration.
- [worker client](../../../backend/app/services/nvidia_worker.py), lines 252–285
  and 406–439: observed identity validation and configured/resolved URL handling.
  A hostname/protocol mismatch also becomes unavailable; it must not be shown as
  a successfully observed configured worker.
- [worker status](../../../worker/windows/worker.py), lines 60–66: hostname and
  protocol observation, no URL or remote-ComfyUI/model-readiness check.
- [MCP settings](../../../mcp-server/mcp_server/config.py): Backend URL and a
  separate direct-ComfyUI URL; no authoritative Backend worker configuration.

The scope says to reuse existing endpoints and only add a read-only endpoint if
none exposes worker status. A worker-status endpoint already exists. The issue
is not absence of a status route; it is the required public identity contract
and missing fields in its response. Returning guessed expected identity as an
observation would be false. Returning an empty list would falsely mean no worker
is configured. Choosing null for all missing fields could omit even the required
configured URL. Adding a second route or reading private Backend configuration
from MCP should not be an undocumented resolution.

**Recommendation for Producer clarification:** permit a minimal read-only
extension of the existing `/api/workers/status` response. Preserve empty/one
semantics and expose the configured URL plus clearly named expected identity
separately from nullable observed hostname/protocol. State whether the displayed
URL is configured or resolved, retaining that distinction if existing discovery
changes the runtime URL. Failed probes retain the configured entry,
`reachable: false`, a safe current error/recovery reason and unknown observed
identity. Successful URL-only responses may retain an unknown hostname.
`last_error` should describe the current failed observation (null when clear),
without implying a new persistent history or heartbeat store. If Backend cannot
be read, `list_workers` must report unavailable/unknown through the common error
envelope rather than infer an empty configuration.

Producer may choose another truthful contract within delegated authority. Record
that choice in the normative task/clarification and request a new independent
fixed-commit kickoff. QA has not applied this recommendation as a specification
change. No CTY question is required by this demonstrated gap.

## Health, read-only and compatibility notes

`GET /health` is application-only
([main.py](../../../backend/app/main.py), lines 136–138).
[System schema](../../../backend/app/schemas/system.py), lines 16–30, and
[dependency status](../../../backend/app/services/dependency_status.py), lines
198–279, independently represent ComfyUI configuration, reachability, state and
hints. `no_models` and `degraded` can be reachable; do not collapse them into a
failed connection. On Backend outage, dependencies were not observed through
that Backend; a boolean false needs an explicit not-observed reason rather than
an invented assertion that their own probes failed. This remains a testable D1
implementation obligation, not a request for direct dependency probes.

[MCP common envelope](../../../mcp-server/mcp_server/tools/responses.py),
[registration](../../../mcp-server/mcp_server/server.py),
[catalog](../../../mcp-server/mcp_server/tool_catalog.py) and
[literal risk/discovery tests](../../../mcp-server/tests/test_tool_catalog.py)
were read together. Existing discovery/registration is 30 intents, including
`mcp_ping: read` and `wait_for_job: read`; health/workers are absent as expected.
The future literal policy must preserve all unrelated labels, especially
`comfyui_admin: admin`, and exercise the actual HTTP path, not just a label.
Derived cache refresh in existing LAN discovery is source context, not authority
for a registry or new persistent mutation. Preserve the private-LAN boundary
and expose no additional worker-control capability.

Health uses Backend-local ComfyUI configuration via system status. Direct admin
uses `MCP_COMFYUI_API_URL`, which may point elsewhere. A healthy worker endpoint
does not prove its ComfyUI, workflows, models or same-project parity are ready.
[Resource-scope memory](../../memory/compute-target-and-resource-scope.md)
expressly rules out using the Backend resource inventory as worker inventory.
No job is created by discovery, so duplicate submission and cancellation need
no new feature: tests should show no such requests, and recovery should repeat
reads or inspect the same existing job rather than submit work.

I read actual p1-03 [acceptance](../p1-03-mcp-wait-and-result/acceptance.md),
[manifest](../p1-03-mcp-wait-and-result/manifest.md) and
[QA report](../p1-03-mcp-wait-and-result/review.md), not only their summaries.
The accepted feature `77e3e3c1520b01cd6422e8ca2b0c0f4adb66e6ce` and QA commit
`d088c3258ab782623631d60daaaccc8ce6fcb6dc` are ancestors; manifest/report bytes
are unchanged at this source. Preserve the bounded wait, safe errors, result
identity and locator contract. Actual calling-client limit remains unverified;
50 seconds is policy fallback. Locators prove neither bytes nor client access.

## Commands, results and limits

[Evidence README](kickoff-1-evidence/README.md) lists the reproducible commands.
Each check has full argv, cwd, selected non-secret environment, UTC start,
elapsed process time, exit and raw output. Imports resolve this isolated worktree.
Both pytest checks use separate roots below `TMPDIR` and `--timeout=60`.
Canonical venvs were used unchanged; pytest-timeout 2.4.0 was installed only into
run-owned scratch.

| Check | Result |
|---|---|
| Source/task/prerequisite audit | Exit 0; exact source/tree/task hash; 41 source checkpoints byte-matched; no manifest; inherited tracked files unchanged |
| Selected existing Backend checks | Exit 0; **9 passed, 1 warning in 0.10s**; health application-only, ComfyUI disabled/down/no-models and worker identity/status boundaries |
| Existing MCP catalog suite | Exit 0; **14 passed in 0.22s**; actual registration/discovery, 30 literal risks, envelopes and current docs |
| Additional existing-route shape probe | Exit 0; unconfigured/down/matching/mismatch/URL-only worker and disabled/down/reachable-no-models ComfyUI shapes; four worker GETs, zero worker submission/control requests |
| MCP import binding | Exit 0; registration/client/catalog/envelope modules resolve this worktree |

Offline source-contract checks only. Full Backend/MCP, Frontend/build, native
Windows and historical registry suites were not rerun: no product change or
implementation acceptance is under review. Prior p1-03 full Backend 1900/124
Windows skips and MCP 540/two optional skips remain that prior review's results.
No live service probe/restart/deployment, real generation/training/download,
worker dispatch or live Gallery-byte retrieval occurred. Synthetic route
responses and official review-packet retrieval are separate evidence.
Shared main, AID-151 runtime/worktree/private configuration, canonical venvs,
models, datasets, outputs and Gallery records were preserved. No specification,
product code, existing tests or historical evidence was edited to obtain a verdict.

## Disposition and accounting

This completes [AID-165](/AID/issues/AID-165) with **AMBIGUITY K4-1**. Producer
owns clarification on [AID-145](/AID/issues/AID-145), followed by fresh fixed-source
independent kickoff before Coding dispatch. No parent write is a completion
condition. A later exact-final-commit delivery PASS still precedes feature
publication and release of p1-05.

p1-04: **kickoff round 1, one ambiguity, zero delivery rejections**. p1-03 retains
one kickoff ambiguity/clarification 1/round-2 CLEAR and delivery review 1 PASS with
zero implementation rejections. Earlier p1-02/p1-00a histories remain separate.
