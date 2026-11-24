---
name: gallery-artifact-identity-and-locators
description: "Keep canonical artifact IDs separate from image IDs and preserve unavailable or non-Gallery media locators."
metadata:
  type: project
  captured_on: "2026-11-24"
  curated_on: "2026-11-24"
---

## Context

The generation-status reader supports completed legacy `GeneratedImage` rows
without a matching `GeneratedArtifact`: it returns an image ID/path and an empty
artifact list. Image IDs and canonical artifact IDs are separate namespaces.
Gallery artifact details permit null URLs/local paths; an absolute stored path
outside the Backend Gallery root has no Backend Gallery URL. A valid legacy
training-smoke image can likewise have a null canonical artifact ID.

## Why

The normal current writer creates both image and artifact rows, but that does
not prove every supported read has both. Borrowing an image ID as an artifact
ID breaks provenance. Re-rooting an outside path's basename or manufacturing a
static URL can point to another file or falsely promise retrieval.

## How to apply

Preserve the Backend's actual identities and nullable references. Keep legacy
images separate from canonical artifacts. Construct host paths/URLs only from
supported Gallery mappings; keep missing/unsafe mappings explicit. A completed
Backend job does not establish retrievability, host-filesystem access or decoded
bytes. Training model output is not Gallery image/video media. For the proposed
wait tool, follow the [target result/error contract](../decisions/mcp.md#wait-results-and-media-locators);
its independent kickoff/delivery gates still determine when it is available.

## Evidence

- `backend/app/api/generate.py`: completed artifact/image read paths.
- `backend/app/api/gallery.py`: `_to_image_url`, `_artifact_local_path`.
- `backend/app/schemas/gallery.py`: nullable artifact locators.
- `backend/app/services/lora_smoke.py`: `reference` legacy-image fallback.
- [Independent source/fixture review](../tasks/p1-03-mcp-wait-and-result/kickoff-review-round-1.md).
