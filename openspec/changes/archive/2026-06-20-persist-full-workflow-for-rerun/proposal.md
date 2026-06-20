## Why

`gallery_rerun` rebuilds a flat `params` dict from denormalized DB columns and re-submits through the **template path** (`backend/app/api/gallery.py` `rerun_image` → `submit`). This silently loses the entire workflow graph, so any image produced by `generate_image_custom_workflow` (ControlNet, img2img, inpaint, multi-`KSampler`) **cannot be faithfully reproduced** — rerun re-runs a default/named template instead of the original graph. Storing the full submitted workflow makes rerun exact and removes the fragile per-field reverse-extraction (e.g. the `steps`/`cfg` recording gap for custom workflows).

## What Changes

- Persist the final submitted ComfyUI workflow (the prompt dict that the queue actually sends) on each recorded image as `workflow_json`.
- Persist the gallery-relative source references `source_image` and `source_mask` so img2img/inpaint reruns can re-upload the originals (the workflow only embeds ephemeral ComfyUI input filenames).
- Change `gallery_rerun` to re-submit the stored `workflow_json` via the custom path (`submit_custom`): re-upload `source_image`/`source_mask` from the gallery and re-inject them into the `LoadImage`/`LoadImageMask` nodes before submission.
- Rerun reproduces exactly: the stored seed (already baked into `workflow_json`) is reused as-is; no re-randomization, because the purpose of rerun is precise reproduction.
- Backward compatible: records without `workflow_json` (older rows) fall back to the current column-based template reconstruction.

## Capabilities

### New Capabilities
- `faithful-rerun`: Persisting the full submitted workflow plus gallery-relative source/mask references on each generated image, and reproducing it exactly on rerun (re-upload sources, re-inject, reuse stored seed), with a documented fallback for legacy records.

### Modified Capabilities
<!-- None: the recording/rerun behavior was never captured as a spec; introduced here as a new capability. -->

## Impact

- Backend DB: `backend/app/db/models.py` (`GeneratedImage` gains `workflow_json`, `source_image`, `source_mask`); requires a lightweight migration / column add.
- Backend core: `backend/app/core/queue.py` (`_process_pending` captures the submitted prompt + source refs into `job.params`; `_check_running_complete` passes them to recording) and `backend/app/core/recording.py` (`save` accepts and stores the new fields).
- Backend API: `backend/app/api/gallery.py` (`rerun_image` re-submits `workflow_json` via `submit_custom` with source re-upload; legacy fallback) and `backend/app/schemas/gallery.py` if rerun response/detail shape changes.
- Tests: recording persists workflow/sources; rerun reproduces a custom (e.g. inpaint) workflow; legacy-row fallback still works.
- Docs: `docs/PROGRESS.md`.
