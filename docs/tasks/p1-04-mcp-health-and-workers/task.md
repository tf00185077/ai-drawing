# Task specification

## Task
Let agents check system health and see the configured worker through MCP.

## Purpose
`mcp_ping` only checks Backend `/health`, so an agent cannot tell whether ComfyUI or a worker is usable before generating. Phase 3 (workers) builds on this view.

## Outcome
An agent calls `health` to learn whether the Backend, local ComfyUI and the worker are reachable, and `list_workers` to see the configured worker and its status.

## Scope
Included: `health` reports Backend, Backend-local ComfyUI (via `/api/system/status`) and worker reachability. `list_workers` returns the existing configured worker with configured URL/expected identity separate from nullable current observed identity, reachability and current error, under the [configured-worker contract](../../decisions/mcp.md#configured-worker-health-and-identity). Reuse `/health`, `/api/system/status` and `/api/workers/status`; an additive read-only extension of the existing worker-status response is permitted to expose those fields while preserving its existing flags and nested worker response. No second status endpoint is needed.
Excluded: multi-worker registry, heartbeat and scheduling (Phase 3).
Open questions: none after [clarification 1](kickoff-clarification-1.md); fresh independent kickoff is still required.
Read first: [Windows worker](../../windows-worker.md), [configured-worker contract](../../decisions/mcp.md#configured-worker-health-and-identity), [resource-scope memory](../../memory/compute-target-and-resource-scope.md), `backend/app/api/workers.py`, `backend/app/api/system.py`, `backend/app/services/nvidia_worker.py`.

## Done when
- [ ] `health` returns one entry each for Backend, ComfyUI and worker, with `reachable` and a safe reason when not reachable. Backend-down or partial status-read failure retains all three entries and distinguishes dependencies not observed through the Backend from failed dependency probes; ComfyUI `no_models`/`degraded` can remain reachable. Check: registered-tool tests with mocked endpoints for up, down, not-configured, Backend-down and partial read failure. Evidence: test output and recorded requests.
- [ ] `list_workers` returns an empty list only after a successful Backend read confirms no worker is configured, otherwise one configured entry even when its probe fails. `url` is the configured URL; expected hostname/protocol are separate from nullable current `hostname`/`protocol_version` and validated `resolved_url`; `last_error` describes only the current failed observation and is null on success. Backend-read failure returns the common error envelope, never an inferred empty list. Check: registered-tool/Backend-route tests for unconfigured, configured up/down, identity mismatch, successful URL-only configuration without hostname, and an existing-discovery resolved URL distinct from configuration. Evidence: test output and response/request samples against the linked contract.
- [ ] Both tools are read-only and labelled `read` in the catalog/discovery. Replace temporary `mcp_ping`, retain the other 29 intent names/risks including bounded wait, and expose 31 intents. Check: independent literal risk/discovery expectations and registered HTTP request tests proving only the existing GET/status paths, with no submission/control requests. Evidence: test output and recorded requests.
- [ ] `docs/mcp.md` documents both delivered tools, current flow, configured/observed identity, unknown/error recovery and Backend-local versus direct-admin ComfyUI configuration consistently. Check: manual against source and discovery. Evidence: doc link.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: one worker only until Phase 3.
