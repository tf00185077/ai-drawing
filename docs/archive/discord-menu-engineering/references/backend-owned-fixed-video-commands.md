> Historical import from `ai-drawing-discord-menu/references/backend-owned-fixed-video-commands.md`.
> The original body below is preserved verbatim. Operational advice, platform limits,
> setup permissions, restart/sync instructions, and implementation claims are historical
> and unverified against the current project. They grant no current execution authority.
> Consult the archive index and current project code/specs before any separately authorized work.

# Backend-owned fixed-video Discord commands

Use this reference when a native Discord slash command must wrap a known-good local video workflow without allowing users to submit arbitrary ComfyUI JSON.

## Boundary and pipeline

Keep the Discord Bot thin and the Backend authoritative:

```text
Discord attachment + prompt + timing fields
→ Bot validates Discord metadata and sends multipart form data
→ Backend validates bytes and stages opaque files on external storage
→ Backend-owned fixed workflow builder
→ queue / ComfyUI
→ raw video artifact
→ exact FILM interpolation
→ persist only the final artifact
→ `/result` delivery
```

The Bot may collect user-controlled images, prompts, driver videos, and timing values. It must not accept workflow JSON, model filenames, node IDs, arbitrary filesystem paths, or output locations.

## Interactive slash-command and Modal boundary

Discord Modal text inputs cannot reliably upload attachments, and one Modal supports at most five text fields. Use a two-step interaction:

1. The slash command collects only required attachments (`image`, or `reference_image` plus `driver_video`) and performs synchronous metadata validation without reading bytes.
2. Its initial interaction response is `send_modal(...)`; never `defer()` and then attempt to open the Modal.
3. The Modal collects exactly five editable fields: positive motion prompt, optional negative prompt, timeline-span seconds, source frame count, and exact FILM target frame count.
4. On Modal submit, parse and validate all fields before reading attachments. Invalid input replies ephemerally and reads/submits nothing. Valid input defers immediately, then reads attachments and submits the Backend multipart request.

Keep short-animation defaults editable (for example 3 seconds, 49 source frames, 97 FILM frames). Test that the slash command schema exposes only attachment parameters, that the Modal is the initial response, that invalid values do not read files, and that both AnimeGen and driver-based Wan submissions preserve the parsed contract.

## Timing contract

Define `total_seconds` explicitly as the first-frame-to-last-frame timeline span:

- source FPS: `(source_frames - 1) / total_seconds`
- output FPS: `(target_frames - 1) / total_seconds`
- MP4 container duration: `target_frames / output_fps`

These are not interchangeable. Persist both `timeline_span_seconds` and `container_duration_seconds`; the artifact `duration` field should hold the actual container duration.

Wan-family source generation commonly requires `source_frames = 4n+1`. That restriction belongs only to source generation. FILM may target any exact integer `target_frames >= source_frames` within resource limits.

For exact arbitrary output counts, map output frame index `j` to source position:

```text
position = j * (source_frames - 1) / (target_frames - 1)
```

Copy integer positions and ask FILM for the fractional time between the adjacent source pair. This preserves both endpoints and produces exactly the requested count without requiring ×2/×4 multipliers.

## Safe attachment staging

Validate twice: inexpensive Discord-side checks before reading bytes, authoritative Backend checks after receipt.

Backend checks should include:

- MIME type and suffix agreement
- bounded size
- magic-byte/container signature
- opaque generated staging filename
- staging-root containment
- no caller-supplied filesystem paths

Upload reference images through ComfyUI's image-upload API and rewrite `LoadImage` to the returned input-relative name. For driver video nodes that consume ComfyUI input paths, hardlink or copy the staged video into a Backend-controlled Comfy input subfolder and submit only the relative path. Track every staged copy for cleanup.

## Queue and artifact invariants

- Post-processing is part of job completion, not an optional afterthought.
- If FILM fails, mark the job failed and delete raw/partial Gallery outputs; do not expose a raw pre-FILM video as success.
- Persist and deliver only the final post-processed artifact.
- Clean staged inputs on success, failure, and cancellation where supported.
- Cleanup helpers must return immediately when a job has no staged inputs. Otherwise a video-only cleanup path can break unrelated image-job failures or tests whose Settings fixture intentionally lacks video fields.
- Preserve API compatibility: optional media metadata (`fps`, `frame_count`, `duration`, `width`, `height`) should be omitted when absent rather than added as new `null` keys to every legacy artifact response.

For Wan Animate single-segment output, keep `ImageFromBatch.length` equal to the requested nonzero source frame count. Never wire the no-continuation `trim_image=0` output directly to that length.

## Verification matrix

Minimum automated coverage:

1. Fixed builder keeps exact model/LoRA/sampler resources and injects only allowed fields.
2. Prompt, negative prompt, source length, FPS, reference image, driver, face, and pose routes are wired correctly.
3. Wan output trim length is nonzero and equals requested source frames.
4. Multipart endpoints reject bad type, signature, size, frame contract, and path escape.
5. Queue rewrites staged files to Comfy-safe input references.
6. FILM success persists one final artifact; FILM failure persists none and cleans partial files.
7. Legacy non-video queue failures still retain their original error behavior.
8. Discord command registration, attachment-only slash schemas, initial-response Modal opening, invalid-input no-read behavior, both fixed-video multipart shapes, `/result`, and video delivery all have tests.
9. Run one real, low-load FILM smoke with a tiny video at a model-safe resolution (for this local FILM pyramid, 128×128 is safe; 32×32 is below the pyramid minimum). Verify decoded frames, FPS, dimensions, and container duration with `ffprobe`.

A lightweight FILM smoke does not replace a heavy AnimeGen/Wan render. Report those scopes separately.

## Activation evidence

After integration:

- restart the Backend and verify both fixed routes in live OpenAPI;
- restart the Bot and verify it remains running;
- require evidence that Discord command sync completed, not just process liveness.

In the current native Bot architecture, `on_ready()` performs `tree.sync()` before starting the local operator server. Therefore the operator port listening is a useful indirect sync-completion signal. Only use this proof when that ordering remains true in the code.

When integrating from an isolated worktree into a dirty local `main`, preserve unrelated work with a named stash, merge locally, restore the stash, rerun tests against the integrated tree, and remove the fully merged worktree/branch. State separately whether local `main` was integrated and whether `origin/main` was pushed.
