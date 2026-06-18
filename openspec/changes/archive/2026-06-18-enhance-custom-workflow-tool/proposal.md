## Why

`generate_image_custom_workflow` is the single most flexible generation entry point: because a ComfyUI workflow JSON is a complete computation graph, this tool can in principle express any generation scenario (txt2img, img2img, ControlNet, inpaint). Today it falls short of that promise in two concrete ways — the MCP tool never forwards the img2img subject image, and the backend `apply_params` unconditionally overwrites `steps`/`cfg`/`seed` on every `KSampler`, silently corrupting agent-authored graphs (e.g. hires-fix / multi-sampler). Closing these gaps lets one tool cover ~90% of generation scenarios.

## What Changes

- Expose missing parameter channels on the `generate_image_custom_workflow` MCP tool: `image` (img2img subject), `mask` (inpaint mask), `batch_size`, and the diffusion-model-family components `diffusion_model` / `text_encoder` / `vae`.
- **BREAKING (custom path only):** `apply_params` switches to "override only when the caller provided a value." For custom workflows, omitted `steps`/`cfg`/`seed` now preserve the values already in the submitted workflow JSON instead of being forced to `20` / `7.0` / a random seed. This unblocks hires-fix and multi-`KSampler` graphs.
- Preserve `generate_image` (template-path) behavior with zero change: omitted `steps`/`cfg` still default to `20`/`7.0` and an omitted seed is still randomized — this responsibility moves from `apply_params` into the queue's template branch.
- Add an `inpaint` workflow template (`LoadImage` subject + `LoadImageMask` mask + `VAEEncodeForInpaint`) and wire mask upload through the queue so the mask is read from the gallery and uploaded to ComfyUI like `image` / `image_pose`.

## Capabilities

### New Capabilities
- `custom-workflow-generation`: Submitting an arbitrary ComfyUI workflow JSON for generation, the parameter channels the tool exposes (prompt, image, mask, model components, sampler params), the "override only when provided" injection semantics that respect the submitted JSON, and the gallery→ComfyUI upload of reference/mask images.

### Modified Capabilities
<!-- None: openspec/specs/ is empty; this is the first captured capability. -->

## Impact

- MCP server: `mcp-server/mcp_server/tools/generate.py` (`generate_image_custom_workflow` signature + body wiring + docstring).
- Backend API: `backend/app/api/generate.py` (`/custom` request → params mapping).
- Backend schema: `backend/app/schemas/generate.py` (`GenerateCustomRequest`: optional `steps`/`cfg`, new `mask`, `diffusion_model`/`text_encoder`/`vae`).
- Backend core: `backend/app/core/workflow.py` (`apply_params` override semantics + `LoadImageMask` injection) and `backend/app/core/queue.py` (template-vs-custom branch for defaults/seed, mask upload, `GenerateParams`).
- New template: `backend/workflows/inpaint.json`.
- Tests: backend `apply_params`/queue tests and mcp tool tests.
- Docs: `docs/PROGRESS.md` (per project rule, sole progress source).
