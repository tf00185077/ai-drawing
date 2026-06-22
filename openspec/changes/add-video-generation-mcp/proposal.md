## Why

`ai-drawing` already lets agents inspect ComfyUI nodes, submit arbitrary custom workflow JSON, poll jobs, and retrieve gallery images, but the product contract is still image-only: completed jobs surface `image_id`/`image_path`, gallery records are `GeneratedImage`, and template capabilities only cover image modalities. To support video as an MCP-first workflow, the smallest useful MVP is an artifact lifecycle that lets an agent submit a known-good ComfyUI video workflow or derived variant, poll it, retrieve the saved video file, and deliver it.

## What Changes

- Add a generic generation artifact layer that can record and return video outputs in addition to images, without breaking existing `GeneratedImage` and `get_gallery_image` callers.
- Extend ComfyUI history/output collection to discover video-like artifacts (`mp4`, `webm`, `gif`, and ComfyUI video output entries) from completed prompts, copy them into the project gallery, and persist metadata such as artifact type, path, mime type, node id/type, workflow JSON, and optional fps/frame/duration fields when available.
- Add MCP/API read path for completed artifacts: `get_gallery_artifact` plus generation-status `artifacts[]`, while preserving legacy `image_id`/`image_path` for image jobs.
- Add MCP/API submit path for the MVP: `generate_video_custom_workflow`, a video-named wrapper around the existing custom workflow queue path that accepts supplied workflow JSON, optional video-oriented input references, and returns a normal job id.
- Extend workflow template capabilities with video modalities and IO tags so a reusable video template can be matched, derived from, and saved after a successful run.
- Add minimal video resource inventory fields only where the backend can reliably list local files; do not require a full model-management UI for MVP.
- Keep the first MVP scoped to local ComfyUI workflows and local artifact delivery. Partner/API video nodes, automatic node installation, backend graph synthesis from prose, and front-end video browsing are non-goals for the first slice.

## Capabilities

### New Capabilities
- `video-generation-artifacts`: Records, exposes, and delivers generated video artifacts from ComfyUI jobs through backend APIs and MCP tools.

### Modified Capabilities
- `custom-workflow-generation`: Custom workflow submission can be used for video graphs and returns terminal status with `artifacts[]`, including video artifacts and structured failures.
- `workflow-template-catalog`: Template capability vocabulary and matching support video modalities/IO so reusable video workflows can be cataloged and selected by agents.

## Impact

- Backend core: ComfyUI history/output parsing, queue completion, gallery copying, recording layer, and job status serialization.
- Backend DB: add a `GeneratedArtifact` table or equivalent artifact records while keeping existing image records backward-compatible.
- Backend schemas/API: add artifact response schemas, `GET /api/gallery/artifacts/{id}`, and optionally `POST /api/generate/video/custom`.
- MCP server: add `get_gallery_artifact`, `generate_video_custom_workflow` if a separate tool is chosen, and artifact-aware status responses.
- Workflow templates: add controlled capability tags for `txt2video`, `img2video`, and minimal video IO/resource tags.
- Verification: add unit tests for artifact extraction/recording, MCP tests for video status/gallery paths using mocked ComfyUI history/output, and one real end-to-end run with a known-good local ComfyUI video workflow before calling the MVP complete.
- Preferred implementation agent metadata: codex gpt-5.5.
