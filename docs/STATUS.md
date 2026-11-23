# Status

Last updated: 2026-11-23. Based on `main` at `32b59fd` (Mac integration of the retained LoRA, Gallery and maintenance work). "Verified" means seen working in a real run, not only in tests.

## Summary

| Goal | Built on main | Verified | Next |
|---|---|---|---|
| 1. Agent-ready MCP server | Mostly | Partly | Uniform responses, wait tool, real end-to-end smoke |
| 2. Prompt dashboard | Mostly | Partly | Recipes that bind prompts to templates and models |
| 3. LAN Windows workers | Partly | No | Auth, same-project check, durable concurrent queue, registry |
| 4. LoRA training | Mostly | No | First real training run |

Tests on `main` (from the [consolidation checkpoint](checkpoints/2026-11-23-progress-consolidation.md)): Backend 2032 passed / 26 failed (known baseline) / 125 skipped; MCP, Discord and Frontend suites pass.

## 1. MCP server

**Works on main:** tools for generation (image, custom workflow, video), job status and cancel, resource listing, Gallery, Civitai, style presets, Prompt Library, LoRA training, Discord delivery, ComfyUI restart/node install/memory. Image generation accepts a revision context (`request_ref`, `parent_artifact_id`, feedback), so revisions are traceable. The tool list is in `mcp-server/mcp_server/tool_catalog.py`.

**Verified:** retrieval of an existing Gallery image through MCP. A full request → generate → retrieve → revise journey has not been run.

**Gaps:**
- Responses mix plain text, JSON strings and objects.
- No tool that waits for a job to finish.
- No way to list workers or their capabilities.

## 2. Prompt dashboard

**Works on main:** Prompt Workbench at `/prompt-library/workbench` — browse, order and weight positive/negative fragments, save combinations, manage categories and entries, submit to a generation form. Gallery keeps full seed precision, has a readable detail modal, and the dev proxy no longer intercepts `/gallery` page loads.

**Verified:** used in the UI during development; no recorded end-to-end generation from the Workbench.

**Gaps:**
- A combination stores prompt text only, not the workflow template, models, LoRAs or sampler settings.
- Little progress/error/result feedback on the Workbench page.

## 3. LAN Windows workers

**Works on main:** a worker service that proxies a remote ComfyUI; Backend client with optional LAN discovery and hostname/protocol validation; `execution_target=worker` on generation.

**Verified:** nothing. The worker has never been installed successfully on the owner's machine.

**Gaps:**
- One worker URL only; no registry, heartbeat or scheduling.
- No check that the worker runs the same project version, nodes and models.
- PowerShell control routes have no authentication.
- Queue limits block parallel workers (see [Architecture → Known limitations](ARCHITECTURE.md#known-limitations-to-optimize)).
- Large updater/migration code for retired APIs.

## 4. LoRA training

**Works on main:** dataset inspection, curation and auto-captioning; preflight; recipe compiler; sd-scripts runner for SD1.5, SDXL and Anima; required readable `output_name` with automatic serial numbers; a separate folder per run with an effective-parameter record; registration status reported separately from training; smoke-test submission with reconciliation and image validation; status, logs, cancel; UI page and MCP tools.

**Verified:** trainer Python imports on the Backend host. No real training run has completed.

**Gaps:**
- No real end-to-end run: train → register → select → smoke image.
- Training cannot run on a worker.
