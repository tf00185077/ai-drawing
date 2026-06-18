## 1. Persist workflow and source references

- [ ] 1.1 In `backend/app/db/models.py`, add nullable columns to `GeneratedImage`: `workflow_json` (Text), `source_image` (String), `source_mask` (String).
- [ ] 1.2 Add a lightweight additive migration (or ensure create-all covers the dev SQLite) for the three new columns.
- [ ] 1.3 In `backend/app/core/recording.py` `save`, accept and store `workflow_json`, `source_image`, `source_mask`.

## 2. Capture data in the queue

- [ ] 2.1 In `backend/app/core/queue.py` `_process_pending`, after `apply_params`, store the submitted prompt dict into `job.params["workflow_json"]`.
- [ ] 2.2 In `_process_pending`, retain the original gallery-relative `image`/`mask` as `job.params["source_image"]`/`["source_mask"]` (do not overwrite with uploaded ComfyUI filenames).
- [ ] 2.3 In `_check_running_complete`, pass `workflow_json`, `source_image`, `source_mask` from `job.params` into `recording.save`.

## 3. Faithful rerun

- [ ] 3.1 In `backend/app/api/gallery.py` `rerun_image`, branch: if `row.workflow_json` exists, submit it via `submit_custom`, passing `image=row.source_image` and `mask=row.source_mask` so the queue re-uploads and re-injects them.
- [ ] 3.2 Ensure the rerun reuses the seed baked into `workflow_json` (no re-randomization on the custom path).
- [ ] 3.3 Keep the legacy fallback: when `row.workflow_json` is null, reconstruct params from columns and submit via the template path as today.
- [ ] 3.4 On missing source image/mask in the gallery, return a clear error instead of submitting a broken graph.

## 4. Tests and docs

- [ ] 4.1 Test: a completed generation persists `workflow_json` plus `source_image`/`source_mask` when applicable.
- [ ] 4.2 Test: rerun of an inpaint/custom record submits the stored workflow via the custom path with re-uploaded sources and reuses the stored seed.
- [ ] 4.3 Test: rerun of a legacy record (no `workflow_json`) still works via the column-based template path.
- [ ] 4.4 Run backend test suite; fix regressions.
- [ ] 4.5 Update `docs/PROGRESS.md`.
