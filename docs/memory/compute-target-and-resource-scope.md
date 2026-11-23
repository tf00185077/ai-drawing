---
name: compute-target-and-resource-scope
description: "Resolve trainer location and Backend-local inventory independently of a generation request execution target."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

In the inspected source, generation selects `local` or `worker`, defaulting to `local`, while training launches the persisted argv as a subprocess of the Backend environment. Smoke generation selects its own target. The available-resources endpoint takes no execution target: it scans direct files in configured Backend directories for supported extensions and discovers workflow names on that filesystem.

## Why

A Worker smoke result or a Backend model listing cannot establish that training or model loading occurs on the intended host. A missing nested or unsupported-format entry also does not establish a missing Worker resource.

## How to apply

Resolve the deployed trainer, generation route and resource observation scope before proposing execution. Keep training-job, registered-model and smoke-generation identities separate. Use authorized target-specific evidence for exact models, nodes and paths; preserve unknown target inventory rather than inferring a download need or changing hosts. Recheck deployed contracts and current compute authority before use.

## Evidence

- [Generation schema](../../backend/app/schemas/generate.py) and [trainer subprocess/smoke implementation](../../backend/app/services/lora_trainer.py) — separate routing mechanisms.
- [Resource endpoint](../../backend/app/api/generate.py) and [filesystem scanners](../../backend/app/core/resources.py) — Backend settings, direct-file scope and extension filtering.
- [Training authority](../training-status.md) and [compute boundaries](../team/README.md#shared-operating-boundaries) — readiness and permission remain separate.
