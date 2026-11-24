---
name: ordinary-generation-revision-lineage
description: "Gallery rerun is not a revision; send a new generate request with revision context to record lineage."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

`gallery_rerun` replays recorded parameters and does not create a revision. A revision is a new `POST /api/generate/` request carrying a revision context (`request_ref`, `brief_revision`, optional `parent_artifact_id`, `feedback_ref`, `feedback_summary`). The Backend derives parent identity and stores it with the outputs; older images without context show as `legacy`.

## Why

The Phase 1 exit requires a traceable revision; a rerun leaves no parent link.

## How to apply

When changing a result based on feedback, send a new generate request with `parent_artifact_id` set; do not rerun.

## Evidence

- `backend/app/schemas/generate.py` (`RevisionContextRequest`, `RevisionContext`)
- [p1-05](../tasks/p1-05-mcp-e2e-smoke-mac/task.md)
