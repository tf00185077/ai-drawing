## 1. Backend core: override-when-provided semantics

- [ ] 1.1 In `backend/app/core/workflow.py` `apply_params`, change `steps` to `int | None = None` and `cfg` to `float | None = None`; write them into `KSampler` only when not None.
- [ ] 1.2 In `apply_params`, remove the random-seed fallback in the `KSampler` block; write `seed` only when not None.
- [ ] 1.3 In `apply_params`, add `mask: str | None = None` and inject it into `LoadImageMask.image` when provided.
- [ ] 1.4 In `backend/app/core/queue.py`, add `mask` to the `GenerateParams` TypedDict.
- [ ] 1.5 In `queue.py` `_process_pending`, branch on `custom_wf`: template path fills `steps=20`/`cfg=7.0` when omitted and generates + stores a random seed when omitted; custom path passes `steps`/`cfg`/`seed` through as-is (None when omitted).
- [ ] 1.6 In `queue.py`, upload `mask` via `_upload_gallery_image` (mirroring `image`/`image_pose`) and pass the uploaded filename to `apply_params`.

## 2. Backend schema and API

- [ ] 2.1 In `backend/app/schemas/generate.py` `GenerateCustomRequest`, make `steps`/`cfg` optional (default None) keeping `ge`/`le` validation; add `mask`, `diffusion_model`, `text_encoder`, `vae` fields.
- [ ] 2.2 In `backend/app/api/generate.py` `/custom`, only add `steps`/`cfg` to params when not None; map `mask`, `diffusion_model`, `text_encoder`, `vae` when provided.

## 3. Inpaint workflow template

- [ ] 3.1 Add `backend/workflows/inpaint.json`: `CheckpointLoaderSimple` + `LoadImage` (subject) + `LoadImageMask` (mask) + `VAEEncodeForInpaint` (grow_mask_by) → `KSampler` (denoise≈1.0) → `VAEDecode` → `SaveImage`.
- [ ] 3.2 Verify `inpaint` appears in `/api/generate/workflow-templates` and the JSON loads (it is auto-discovered from the workflows dir).

## 4. MCP tool parameter channels

- [ ] 4.1 In `mcp-server/mcp_server/tools/generate.py` `generate_image_custom_workflow`, add params `image`, `mask`, `batch_size`, `diffusion_model`, `text_encoder`, `vae`; add each to the request body only when not None.
- [ ] 4.2 Update the tool docstring to document img2img (`image`), inpaint (`mask` + inpaint template), anima components, and the "workflow JSON values are respected unless a param is passed" semantics.

## 5. Tests and docs

- [ ] 5.1 Add backend test: custom path with omitted `steps`/`cfg` preserves workflow JSON values, including a two-`KSampler` workflow keeping independent values.
- [ ] 5.2 Add backend test: template path with omitted `steps`/`cfg`/`seed` still yields `20`/`7.0` and a recorded random seed (regression guard for `generate_image`).
- [ ] 5.3 Add backend test: `apply_params` injects `mask` into `LoadImageMask.image`; queue uploads subject `image` and `mask` and rejects gallery-escaping paths.
- [ ] 5.4 Add mcp test: `generate_image_custom_workflow` forwards `image`/`mask`/`batch_size`/`diffusion_model`/`text_encoder`/`vae` into the request body only when provided.
- [ ] 5.5 Run backend and mcp test suites; fix regressions.
- [ ] 5.6 Update `docs/PROGRESS.md` per project rule.
