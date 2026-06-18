## Context

Recording happens entirely in the backend queue worker: `_process_pending` builds the submitted prompt dict via `apply_params`, and `_check_running_complete` calls `recording.save(...)` with values read from `job.params`. Today only flat fields are persisted, and `gallery_rerun` (`rerun_image`) rebuilds params from those columns and calls `submit` (template path). The submitted prompt dict — which already exists in memory inside `_process_pending` — is discarded after submission.

Two facts shape the design:
- The generated workflow embeds **ComfyUI input filenames** for `LoadImage`/`LoadImageMask` (returned by `comfy.upload_image`), which live in ComfyUI's transient input folder, not the persistent gallery.
- The **source images themselves are persistent** in the gallery, because `_upload_gallery_image` only ever uploads gallery-relative paths.

So a faithful rerun needs the graph (`workflow_json`) plus the persistent gallery source paths to re-upload.

## Goals / Non-Goals

**Goals:**
- Make rerun reproduce custom workflows (ControlNet/img2img/inpaint/multi-sampler) exactly.
- Keep denormalized columns for gallery filtering, display, and CSV export.
- Reuse the existing `_upload_gallery_image` + `apply_params(image=..., mask=...)` machinery on rerun.
- Stay backward compatible with rows that predate `workflow_json`.

**Non-Goals:**
- No "rerun with variations" / seed re-roll — rerun is precise reproduction by design.
- No editing of the stored workflow through the rerun endpoint (that is what `generate_image_custom_workflow` is for).
- No retroactive backfill of `workflow_json` for historical rows.

## Decisions

### Decision 1: Store the submitted prompt dict, not the pre-`apply_params` workflow

Persist the post-`apply_params` prompt (what ComfyUI actually ran), so reproduction is byte-faithful including the resolved seed and any reverse-extracted model filenames. The dict already exists at submission time in `_process_pending`; capture it into `job.params["workflow_json"]` right after `apply_params`.

*Alternative considered:* store the raw incoming workflow and re-derive params on rerun. Rejected — it reintroduces the reverse-extraction fragility this change exists to remove.

### Decision 2: Persist source/mask as gallery paths, re-upload on rerun

Store `source_image`/`source_mask` (the original `job.params["image"]`/`["mask"]`). On rerun, re-upload them via the existing gallery upload path and re-inject through `apply_params(image=..., mask=...)`. This avoids depending on ComfyUI's transient input filenames embedded in `workflow_json`.

*Alternative considered:* rewrite the embedded input filename to point back at a re-upload, bypassing `apply_params`. Rejected — duplicates logic already in `apply_params`/`_upload_gallery_image`.

### Decision 3: `workflow_json` stored as a TEXT/JSON column

Workflow graphs are small (a few KB). Store as serialized JSON text (or the DB's JSON type) on `GeneratedImage`. Adds three nullable columns: `workflow_json`, `source_image`, `source_mask`.

### Decision 4: Rerun branches on `workflow_json` presence

`rerun_image`: if `workflow_json` is present → custom-path reproduction; else → existing column-based template reconstruction. One branch, legacy-safe, no migration of old rows required.

## Risks / Trade-offs

- **[Schema migration]** → Three nullable columns added to `GeneratedImage`. Mitigate with a lightweight additive migration (or create-all for the dev SQLite); nullable means existing rows are valid immediately.
- **[Source image deleted from gallery]** → If a user deleted the original source image, rerun cannot re-upload it. Mitigate: detect missing source and return a clear error (reuse the existing "Image not found" path in `_upload_gallery_image`) rather than submitting a broken graph.
- **[Stored workflow references a model no longer installed]** → Same failure mode as the original generation; surface ComfyUI's error via the (separately tracked) error-feedback improvement. Out of scope here.
- **[Storage growth]** → Negligible per row (KB-scale JSON); acceptable.

## Migration Plan

Additive: add three nullable columns to `generated_images`. New generations populate them; old rows keep `workflow_json = NULL` and use the fallback path. Rollback is dropping the columns and reverting `rerun_image` — no data loss for the existing columns.

## Open Questions

- Whether to expose `workflow_json` in the gallery detail API/UI (useful for debugging/inspection) or keep it internal to rerun. Default: keep internal for now; revisit if a "view workflow" feature is wanted.
