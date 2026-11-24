---
name: frontend-shared-cache-isolation
description: "Vitest caches into node_modules; a symlinked shared node_modules leaks results across worktrees."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

Vite and Vitest use separate cache locations. When a worktree symlinks a shared `node_modules`, Vitest's results cache is written into the shared directory even if Vite's cache was redirected.

## Why

Parallel worktrees then see each other's cached test results.

## How to apply

In parallel worktrees, set the Vite `cacheDir` and the Vitest cache directory separately to worktree-local paths.

## Evidence

- `frontend/vite.config.js` (closest project file; the behavior is Vitest's)
