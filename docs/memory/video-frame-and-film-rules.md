---
name: video-frame-and-film-rules
description: "Frame-count and duration rules of the existing image-to-video + FILM interpolation path, and which video graphs are hidden."
metadata:
  type: project
  curated_on: "2026-11-25"
---

## Context

`source_frames` is the total frames the model generates: 17–321 and `4n+1` (Wan latent). `film_target_frames` runs from `source_frames` up to 1921 and may be any exact count. `total_seconds` is the span from first to last frame, not the MP4 duration, so FPS is `(frames-1)/total_seconds`. The Discord defaults are 3 s, 49 source frames and 97 FILM frames. The three `discord_*_fixed` graphs have no `.meta.json` and are not in the workflow selector; the MiniMax H3 command runs on Argus MLX (Mac), not its stored ComfyUI graph.

## Why

Phase 4 builds the fixed image-to-video + interpolation tool on this code; wrong frame counts fail validation and wrong duration math gives the wrong FPS.

## How to apply

Reuse these limits for the Phase 4 tool. Do not add metadata to the `discord_*_fixed` graphs just to expose them; Phase 4 decides whether the frozen video code is removed.

## Evidence

- [Fixed video workflows](../../backend/app/core/fixed_video_workflows.py).
- [Generation schemas](../../backend/app/schemas/generate.py).
- [FILM postprocessing](../../backend/app/services/film_postprocess.py).
