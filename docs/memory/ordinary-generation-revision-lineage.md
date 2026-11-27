---
name: ordinary-generation-revision-lineage
description: "Reruns preserve stored revision context; use a new generation to record a revision based on feedback."
metadata:
  type: project
  curated_on: "2026-11-26"
---

## Context

`gallery_rerun` replays recorded parameters and revision context without creating a new parent relationship. Images without stored context return `revision_context: null`. A parent artifact without stored context is marked `parent_context_status: "legacy"` in the child's context.

## Why

A rerun may retain an earlier parent link; that link cannot establish a new revision from the rerun's source.

## How to apply

Follow the [MCP revision flow](../mcp.md#common-flows): submit a new `generate(mode=template)` request with the canonical `parent_artifact_id`, the same `request_ref` and a new `brief_revision`; include feedback annotations when needed.

## Evidence

- [Revision projection and parent resolution](../../backend/app/core/revision_context.py).
- [Gallery replay](../../backend/app/api/gallery.py) — preserves recorded context.
- [Revision schemas](../../backend/app/schemas/generate.py).
