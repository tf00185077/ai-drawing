# Video Generation MCP MVP Design

Date: 2026-06-22

Source input: CTY approved this as a non-interactive brainstorming/design run. No follow-up questions are required for this phase.

Preferred implementation agent note: Codex GPT-5.5.

## Context

`ai-drawing` is agent-first: MCP tools drive FastAPI, which drives ComfyUI and records outputs. The current system already has the control-plane pieces needed for workflow experimentation: agents can search ComfyUI node types, inspect node schemas, list and match workflow template capabilities, submit custom workflow JSON, poll job status, and save successful workflow shapes as reusable templates.

The missing piece for video is not primarily graph authoring. The product contract is still image-shaped: completed jobs expose image ids/paths, gallery retrieval is image-oriented, and template capability tags only describe image modalities.

## Approved Direction

The smallest useful MVP is an MCP workflow that can run a known-good ComfyUI video graph and return a durable generated artifact. It must prove:

- An agent can submit a base video workflow or a derived variant through MCP.
- The backend can poll the normal queue lifecycle and detect produced video files.
- Completed status returns `artifacts[]`.
- MCP can retrieve the artifact through `get_gallery_artifact`.
- Existing image behavior and `get_gallery_image` stay compatible.

## Key Boundary

Workflow derivation and product artifact lifecycle are separate concerns.

Workflow derivation capability: If CTY provides a base ComfyUI video template and the required custom nodes/models are already installed, an agent can derive variants by using node search/schema MCP tools, editing the workflow JSON, submitting it through `generate_video_custom_workflow`, inspecting structured failures, and saving verified shapes with video capability tags. This does not require the backend to synthesize a video graph from a prose prompt.

Product-level video artifact lifecycle: The backend/API/MCP contract must record, expose, and retrieve non-image outputs. This requires a generic artifact record such as `GeneratedArtifact`, `artifacts[]` in status responses, and `get_gallery_artifact`. Without this lifecycle, a video workflow could run but the agent would not have a stable product contract for delivery.

## MVP Scope

In scope:

- Add `GeneratedArtifact` or equivalent generic artifact persistence.
- Detect and record at least `.mp4`, `.webm`, `.gif`, and existing image outputs from completed ComfyUI jobs.
- Return completed job `artifacts[]` while preserving legacy `image_id` and `image_path` for image jobs.
- Add backend artifact lookup and MCP `get_gallery_artifact`.
- Add MCP `generate_video_custom_workflow` as a video-named wrapper around the custom workflow queue path.
- Extend workflow template capability vocabulary with `txt2video`, `img2video`, and video IO tags such as `first_frame`, `last_frame`, `video_ref`, and `audio_ref`.
- Verify end to end with one known-good local ComfyUI video workflow.

Out of scope for the first MVP:

- Frontend video gallery UI.
- Automatic ComfyUI custom-node installation or restart orchestration.
- Third-party video APIs or partner nodes requiring credentials.
- Full video editing, multi-shot orchestration, or timeline state.
- Guaranteeing arbitrary video model families are installed locally.
- Replacing existing image gallery APIs or MCP tools.

## Considered Approaches

Recommended: Add the generic artifact lifecycle plus a video-named custom workflow MCP tool. This is the smallest route that produces a real deliverable video while fitting the current queue, custom workflow, and template catalog architecture.

Alternative: Treat video as workflow derivation only and keep using `generate_image_custom_workflow`. This would prove graph execution but leave artifact delivery ambiguous and keep misleading image-oriented tool names.

Alternative: Build a full product video system first, including UI, model management, node installation, and rich video metadata. This is more complete but too broad for the MVP and would obscure the core MCP contract CTY asked to validate.

## Verification Standard

The implementation is not complete until a known-good local ComfyUI video workflow is run through MCP end to end: submit through `generate_video_custom_workflow`, poll `get_generation_status`, observe `artifacts[]`, fetch the video with `get_gallery_artifact`, verify the local file exists and has a video MIME type, then confirm existing image generation and `get_gallery_image` tests still pass.
