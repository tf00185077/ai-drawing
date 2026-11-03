---
name: explicit-lora-list-semantics
description: "Preserve explicit LoRA-list meaning through connected graph rewrites and asynchronous job outcomes."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

The compiler distinguishes omitted LoRAs from an explicit complete active set, including an empty list. It maps entries in workflow JSON loader order and bypasses unused template loaders by reconnecting their model and, where present, CLIP inputs. Capacity validation occurs during queued compilation, after the public acknowledgement.

## Why

List contents alone cannot prove the resulting graph uses only the requested models; a queued acknowledgement cannot prove that graph fits the workflow.

## How to apply

Preserve omission and an explicit empty list through every caller. Check connected model/CLIP paths, model-only loaders, legacy single-LoRA behavior and full registered relative locators. Follow the acknowledged job ID through compilation before reporting capacity acceptance. Reconcile contradictory legacy tests with the adopted contract and connected-graph/public-boundary evidence; avoid changing conforming product code or silently truncating entries to satisfy an obsolete expectation. These are source-contract checks, separate from runtime and image acceptance.

## Evidence

- [Workflow compiler](../../backend/app/core/workflow.py), [workflow checks](../../backend/tests/test_workflow.py) and [legacy multi-LoRA checks](../../backend/tests/test_multi_lora.py).
- [Generation schema](../../backend/app/schemas/generate.py) and [current contract record](../PROGRESS.md#company-preparation-and-next-step) — adopted semantics and retained independent boundary evidence.
