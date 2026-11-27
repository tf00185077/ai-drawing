---
name: frontend-shared-cache-isolation
description: "Use a worktree-local AI_DRAWING_VITE_CACHE to isolate Vite and the locked Vitest 2.1.9 results cache when node_modules is shared."
metadata:
  type: project
  curated_on: "2026-11-25"
---

## Context

With the locked Vitest 2.1.9 and no `test.cache.dir` override, the test results cache lives under Vite's `cacheDir` in `vitest/`. This project's `AI_DRAWING_VITE_CACHE` sets `cacheDir`; its default, `node_modules/.vite`, is shared when `node_modules` is symlinked across worktrees.

## Why

Parallel runs can write the same results cache through shared `node_modules` unless the cache root is isolated.

## How to apply

Set `AI_DRAWING_VITE_CACHE` to an absolute directory inside each worktree. The current Vitest configuration derives its results-cache location from that Vite directory.

## Evidence

- [Vite configuration](../../frontend/vite.config.js) — cache environment override and no separate Vitest cache override.
- [Dependency lock](../../frontend/package-lock.json) — pins Vitest 2.1.9; its installed `resolveConfig` derives the results-cache directory from Vite's `cacheDir` unless overridden.
