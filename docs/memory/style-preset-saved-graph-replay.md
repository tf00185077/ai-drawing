---
name: style-preset-saved-graph-replay
description: "Style preset compose vs saved-graph replay, profile naming, and index refresh."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

`style_preset_compose` returns a payload built from the recipe and template without submitting; size, scheduler or seed it leaves out come from the workflow at run time, not from the saved graph. `style_preset_test` submits the saved graph unchanged (prompts, resources, fixed seed, batch) and accepts no overrides. An omitted profile means `__base__.api.json`, not a profile named `default`. Listing reads `agent/index.json`; a missing index rebuilds on read, but a stale one needs `POST /api/style-presets/reindex`, which has no MCP tool.

## Why

Agents expect saved-graph values in a composed payload, pick the wrong profile, or see stale lists after editing recipes.

## How to apply

Choose a profile explicitly. After editing recipes, call the reindex endpoint. Treat preset style notes as authored intent; only CTY accepts a result.

## Evidence

- `backend/app/services/style_preset_workflows.py`
- `backend/app/core/style_presets.py`
- [style_presets/README.md](../../style_presets/README.md)
