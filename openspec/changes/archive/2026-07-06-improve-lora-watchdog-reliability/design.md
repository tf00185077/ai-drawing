## Context

The current dataset watcher handles only file creation events and schedules one WD Tagger run for the parent folder after a short debounce. It does not wait for image writes to settle, does not distinguish missing/stale captions from current manual captions, and has no structured status for files that cannot be captioned. Existing backend dataset APIs already provide list/inspect/prepare/validate operations, and MCP already has thin LoRA dataset/training tools.

Agents need two separate capabilities: reliable local `.txt` generation when images arrive, and a deterministic caption suitability report before a human or Hermes explicitly starts training. This change must not add automatic LoRA training.

## Goals / Non-Goals

**Goals:**

- Make watchdog-triggered caption generation conservative: handle created, modified, and moved images; wait for stable image files; skip folders whose captions are current; preserve newer/manual `.txt` files.
- Persist lightweight watchdog status under the dataset folder for unreadable or corrupt images so failures are visible and not retried indefinitely for unchanged files.
- Add a backend caption assessment service/API that computes local counts, trigger-token coverage, tag frequency, tag dispersion/coherence metrics, warnings, recommendations, and a verdict.
- Expose the caption assessment through MCP for direct agent use.

**Non-Goals:**

- Do not implement automatic LoRA training.
- Do not call an external LLM for suitability assessment.
- Do not redesign the WD Tagger integration or add a new image decoding dependency.
- Do not change the existing dataset prepare/validate/start training contracts except for additive fields/endpoints/tools.

## Decisions

1. **Keep watchdog status as a dataset-local JSON file.**
   - Store structured errors in `.lora-watchdog/status.json` under the folder being captioned.
   - Include image name, code, message, size, mtime, and detection timestamp.
   - Alternative considered: database-backed status. Rejected for this step because the watcher has no existing DB status model and a local file is simpler to test and inspect.

2. **Use caption freshness to gate WD Tagger runs.**
   - A same-stem `.txt` file is current when it exists and its `mtime_ns` is greater than or equal to the image `mtime_ns`.
   - Missing or older `.txt` files make the image eligible for captioning.
   - Newer/current captions are snapshotted before WD Tagger runs and restored afterward if the external tagger rewrites them.

3. **Wait for stable files inside the debounced task.**
   - The watcher polls size and mtime until they remain unchanged for a small stability window before invoking WD Tagger.
   - If a file never stabilizes within the timeout, the watcher records a structured status and skips that run rather than invoking the tagger on partial data.

4. **Assess caption suitability in a separate service.**
   - Add `lora_dataset_assessment.py` so statistical logic stays out of `watcher.py` and does not crowd the existing prepare/validate service.
   - Compute deterministic metrics from comma-separated `.txt` tags: missing/empty counts, top tags, rare tags, singleton ratio, repeated-tag ratio, average tags per caption, and mean pairwise Jaccard similarity.
   - Verdicts are `suitable`, `needs_review`, or `not_suitable`; reasons and recommendations make the result agent-readable.

5. **Expose assessment through a POST endpoint and MCP tool.**
   - Use `POST /api/lora-train/datasets/caption-assessment` with `folder` and optional `trigger_token` to avoid conflict with the existing catch-all dataset inspect route.
   - Add `lora_dataset_caption_assess` as a thin MCP wrapper that returns the backend JSON without converting `not_suitable` into a transport failure.

## Risks / Trade-offs

- **WD Tagger may still rewrite current captions during a folder run** → Snapshot and restore current/manual captions after the tagger returns.
- **Lightweight image validation cannot detect every corrupt image format** → Detect empty/unreadable files now and surface them structurally; deeper image verification can be added later with an image library if needed.
- **Heuristic suitability verdicts are conservative** → Return metrics, warnings, and reasons so Hermes or another agent can override after inspection.
- **Status files add small local metadata** → Store under `.lora-watchdog/` and ignore it when scanning image/caption pairs.

## Migration Plan

- Additive backend and MCP changes only; no database migration is required.
- Existing watcher calls continue through `on_new_image`, with added event handlers for modified/moved images.
- Existing dataset inspect/validate/start endpoints remain compatible.
- Rollback is removal of the new endpoint/tool and reverting watcher gating logic.

## Open Questions

- Whether future production deployments should use a real image decoder for deeper corruption detection is intentionally left for a later change.
