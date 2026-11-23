---
name: compute-target-and-resource-scope
description: Which host does what — generation target vs training subprocess vs resource listing scope.
metadata:
  type: project
---

- Generation chooses `execution_target` `local` or `worker` (default `local`).
- LoRA training always runs as a subprocess of the Backend's own environment; it never goes to a worker today.
- Smoke generation after training picks its own target, so a worker smoke image does not mean training ran there.
- `GET /api/generate/available-resources` takes no target. It lists files directly under the Backend's configured model directories (no recursion into nested folders) and workflows on the Backend filesystem. It says nothing about a worker's models.

**How to apply:** do not infer worker readiness or missing models from the Backend resource list.
