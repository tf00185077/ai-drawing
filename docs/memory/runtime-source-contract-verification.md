---
name: runtime-source-contract-verification
description: "Verify the loaded Backend contract separately from the checkout before relying on revision lineage or another newly deployed behavior."
metadata:
  type: project
  captured_on: "2026-11-24"
  curated_on: "2026-11-24"
---

## Context

The host Backend is a long-running Python process. Its cwd can point at the current repository while its imported code still implements an older contract. MCP health checks reachability, not loaded-source identity. Repository revision support does not prove that the service persists revision annotations.

## Why

An agent can send valid current-source revision context to a reachable older Backend and receive null context in submission, status and Gallery responses. That cannot establish traceable revision lineage.

## How to apply

Before claiming deployed behavior, identify the source used to launch the Backend and verify its live schema plus an actual persistence round trip. For a controlled relaunch, record source SHA/fingerprints, command, cwd, process and effective non-secret data paths; preserve existing records and check active jobs. Do not infer the loaded commit from health, process cwd or a later checkout hash.

## Evidence

- [p1-00 independent review](../tasks/p1-00-mcp-friction-run-mac/review.md): live-schema comparison and read-only status/Gallery evidence.
- `backend/app/schemas/generate.py`: `RevisionContextRequest`, `RevisionContext` and `GenerateRequest.revision_context`.
- `mcp-server/mcp_server/tools/health.py`: Backend/dependency reachability reads.
