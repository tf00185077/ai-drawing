---
name: explicit-lora-list-semantics
description: "How the `loras` list in a generation request behaves: omitted vs empty, loader bypass, late capacity check, legacy `lora` field."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

Omitting `loras` keeps the template's LoRA loaders as they are. An explicit list, including `[]`, is the complete active set. Entries fill LoRA loaders in workflow JSON order; unused loaders are bypassed by reconnecting their model (and CLIP, if present) inputs. Ordered `loras` takes precedence over the legacy single `lora` field. Too many LoRAs for a template is detected during queued compilation, after the request was acknowledged.

## Why

Callers that turn "no LoRAs" into an omitted field, or truncate lists, silently change which LoRAs run; the capacity error appears only on the job, not on submit.

## How to apply

Preserve the omitted/empty distinction in every caller (MCP, UI, presets) and never truncate a list. After submitting, follow the job ID to catch a capacity failure.

## Evidence

- `backend/app/core/workflow.py` — LoRA injection
- [MCP → Common flows](../mcp.md#common-flows)
