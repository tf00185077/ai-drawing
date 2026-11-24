---
name: compute-target-and-resource-scope
description: "Which host runs generation, training and resource listing; do not read worker readiness from the Backend resource list."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

Generation picks `execution_target` `local` or `worker` (default `local`). LoRA training always runs as a subprocess of the Backend's own environment and never goes to a worker today. Smoke generation after training picks its own target. `GET /api/generate/available-resources` takes no target: it lists files directly under the Backend's configured model directories (no recursion) and workflows on the Backend filesystem.

## Why

Agents have assumed a worker smoke image meant training ran on the worker, or that the Backend resource list described a worker's models.

## How to apply

Do not infer worker readiness or missing worker models from the Backend resource list. Check where training ran from the training job, not from its smoke image.

## Evidence

- `backend/app/api/generate.py` — available-resources endpoint
- `backend/app/services/lora_trainer.py` — training subprocess
- [Architecture → LoRA training](../ARCHITECTURE.md#lora-training)
