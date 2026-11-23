# Task specification

## Task
Let agents check system health and see the configured worker through MCP.

## Purpose
`mcp_ping` only checks Backend `/health`, so an agent cannot tell whether ComfyUI or a worker is usable before generating. Phase 2 (workers) builds on this view.

## Outcome
An agent calls `health` to learn whether the Backend, local ComfyUI and the worker are reachable, and `list_workers` to see the configured worker and its status.

## Scope
Included: `health` reports Backend, local ComfyUI (via `/api/system/status`) and worker reachability; `list_workers` returns the configured worker (URL, hostname, protocol version, reachable, last error). Uses existing Backend endpoints; adds a read-only Backend endpoint only if none exposes worker status.
Excluded: multi-worker registry, heartbeat and scheduling (Phase 2).
Open questions: none.
Read first: [docs/windows-worker.md](../../windows-worker.md), `backend/app/api/workers.py`, `backend/app/api/system.py`.

## Done when
- [ ] `health` returns one entry each for Backend, ComfyUI and worker, with `reachable` and a reason when not reachable. Check: test with mocked endpoints for up, down and not-configured. Evidence: test output.
- [ ] `list_workers` returns an empty list when no worker is configured and one entry with status fields when one is. Check: test. Evidence: test output.
- [ ] Both tools are read-only and labelled `read` in the catalog. Check: test. Evidence: test output.
- [ ] `docs/mcp.md` documents both tools. Check: manual. Evidence: doc link.

## Delivery
- Artifact: commit on a feature branch, `manifest.md`.
- Known limitations: one worker only until Phase 2.
