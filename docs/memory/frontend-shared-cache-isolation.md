---
name: frontend-shared-cache-isolation
description: Vitest writes its cache into node_modules; with a symlinked shared node_modules this leaks across worktrees.
metadata:
  type: project
---

Vite and Vitest use separate cache locations. When a worktree symlinks a shared `node_modules`, Vitest's results cache is written into the shared directory even if Vite's cache was redirected.

**How to apply:** in parallel worktrees, set Vite `cacheDir` and Vitest cache directory separately to worktree-local paths.
