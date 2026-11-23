---
name: frontend-shared-cache-isolation
description: "Check Vite and Vitest cache destinations separately before reusing symlinked frontend dependencies in isolated QA."
metadata:
  type: project
  curated_on: "2026-11-13"
---

## Context

With a shared `node_modules` directory symlink, the test runner's cache destination needs checking separately from the source and preview cache. In the reviewed Vite/Vitest environment, a results cache reached the canonical dependency directory, and an explicit task-owned test cache stopped further changes to that observed entry.

## Why

An unchanged source snapshot and an isolated preview cache do not establish that the separate test runner's writes stayed inside the task workspace.

## How to apply

Before authorized frontend QA with shared dependency symlinks, inspect each runner's effective root and resolved cache destination. Configure Vite and Vitest caches separately in task-owned locations while retaining the relevant project settings, then check the observed write paths. Recheck the selected versions and effective configuration; a preview's cache setting alone does not configure an independently launched test runner.

Report ignored tooling-cache effects separately from source and frozen-candidate preservation. If an unexpected shared write lacks a preimage, preserve and disclose it rather than guessing old contents or deleting the entry. A corrected final run does not erase the earlier side effect or establish a complete audit of ignored paths.

## Evidence

- [Retained Gallery readability QA and Producer assessment](../PROGRESS.md#m1--current-checkpoint-continuation) — routes to the shared-cache observation, explicit-cache final checks and disclosed preservation limits.
- [Frontend runner configuration](../../frontend/vite.config.js) and [test command](../../frontend/package.json) — inspect the selected configuration and invocation rather than assuming preview settings cover tests.
- [Preservation boundary](../../AGENTS.md#safety-and-scope) — preserve unrelated work rather than reconstructing an unknown preimage.
