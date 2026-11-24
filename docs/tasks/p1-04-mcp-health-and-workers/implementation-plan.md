# Health and configured worker implementation plan

Implements the cleared [task](task.md) and configured-worker decision at fixed base b075f36c0eec532071e11328eb4f2b21b52e1c0f. Execution is inline; the existing native independent QA card reviews the final immutable commit. The assignment expressly authorizes execution without another confirmation.

- [x] D2: Add real worker route/client tests first, then additive configuration/current observation fields in backend/app/api/workers.py. Keep discovery/cache/identity validation unchanged; take resolved_url only after the current health call succeeds.
- [x] D1/D3: Add registered MCP HTTP transport tests and fresh Backend route exports; add tools/health.py, replace ping with health and list_workers in catalog, use HttpBackendClient and common envelopes. Validate Backend statuses, retain three health entries on all read failures and return a list error when configuration is unknown.
- [x] D3: Update the independent literal risk oracle to exactly 31; retain the other 29 labels and all standing registry guards. Migrate ping-dependent tests and fixtures to the delivered surface.
- [x] D4: Update docs/mcp.md, windows-worker.md and team topic guidance. Preserve fixed specifications, kickoff/history and QA-owned registry.
- [x] Prove meaningful production faults fail; restore source. Run final full affected Backend and MCP suites, fresh exports, explicit worktree imports, isolated TMPDIR roots and --timeout=60. Record exact commands, skips and boundaries in manifest/evidence.
- [x] Review the final diff and prepare this immutable source/manifest/evidence tree for commit. Exact commit identity, verified official uploads and Coding closure are recorded externally after commit. Producer owns integration after actual independent QA PASS; no deployment or main push.

Review focus: stale cached success after identity failure; URL-only no-hostname success; discovered endpoint distinct from configured URL; HTTP/invalid/partial Backend reads; reachable ComfyUI no_models/degraded. Tests exercise each with real routes/client/registration and mocked external I/O. No live LAN scans or product services.

Ruling: use the existing client base_url only after successful health validation in a request-local route invocation. This records its actual selected endpoint without treating the runtime cache as a new observation or changing client behavior.
