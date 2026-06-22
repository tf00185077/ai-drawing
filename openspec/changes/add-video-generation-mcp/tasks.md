## 1. Generic Artifact Lifecycle

- [x] 1.1 Add a `GeneratedArtifact` model/table or equivalent artifact persistence layer with job id, artifact type, gallery-relative path, mime type, source node id/type, file size, workflow JSON, prompt metadata, and optional video metadata.
- [x] 1.2 Add an idempotent local DB initialization/migration path so SQLite creates the artifact table without changing existing `GeneratedImage` rows.
- [x] 1.3 Implement artifact type and MIME detection for `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.mp4`, and `.webm`.
- [x] 1.4 Extend ComfyUI history/output parsing to collect image, video, and file artifacts from completed prompt outputs, including extension-based detection for video nodes with inconsistent output keys.
- [x] 1.5 Copy recorded video artifacts into the configured project gallery with job-id-safe filenames and record the final gallery-relative path.
- [x] 1.6 Mark jobs as `failed` with a structured recording error when ComfyUI reports success but no supported output artifact can be recorded.

## 2. Backend API and Status Contract

- [x] 2.1 Add artifact response schemas for artifact summary/detail, including id, artifact type, mime type, gallery path, local path or URL, size, job id, and workflow metadata.
- [x] 2.2 Add `GET /api/gallery/artifacts/{artifact_id}` for recorded artifact lookup with structured not-found behavior.
- [x] 2.3 Extend generation status responses to include `artifacts[]` for completed jobs.
- [x] 2.4 Preserve legacy `image_id` and `image_path` fields for completed image jobs and keep `get_gallery_image` compatibility.
- [x] 2.5 Add backend tests for completed video status, artifact lookup, unknown artifact lookup, recording failure, and legacy image status compatibility.

## 3. MCP Video Workflow Tools

- [x] 3.1 Add `get_gallery_artifact(artifact_id)` MCP tool returning stable JSON with artifact type, mime type, gallery path, local path, file size, job id, and workflow metadata.
- [x] 3.2 Add `generate_video_custom_workflow` MCP tool as a video-named wrapper over the custom workflow queue path; it accepts supplied ComfyUI workflow JSON and returns a normal queued job id.
- [x] 3.3 Support optional video input references for `generate_video_custom_workflow`: `image`, `first_frame`, `last_frame`, and `video_ref`, with safe gallery/input-root path handling and no injection for omitted values.
- [x] 3.4 Ensure MCP `get_generation_status` includes artifact-aware `next` instructions for completed video jobs.
- [x] 3.5 Add MCP tests for queued video custom workflow submission, completed video artifact retrieval, artifact-aware status, and structured not-found errors.

## 4. Workflow Derivation and Template Capabilities

- [x] 4.1 Extend controlled template capability vocabulary with video modalities `txt2video` and `img2video`.
- [x] 4.2 Extend controlled IO tags with `first_frame`, `last_frame`, `video_ref`, and `audio_ref`.
- [x] 4.3 Update `validate_template_capabilities` and `match_workflow_template` tests to cover video modalities and IO tags.
- [x] 4.4 Allow `save_workflow_template` to promote successful video jobs that recorded at least one supported artifact.
- [x] 4.5 Document the agent-side derivation loop: start from a known-good video workflow, inspect schemas with MCP tools, submit a derived workflow through `generate_video_custom_workflow`, inspect structured failures, and save verified shapes.
- [ ] 4.6 Add or document one minimal video template manifest only after a real local ComfyUI video workflow has been verified.

## 5. MVP Guardrails and Resource Inventory

- [x] 5.1 Add optional video resource categories to `list_available_resources` only for directories that are configured and discoverable locally.
- [x] 5.2 Return empty arrays for absent video resource categories rather than failing the resource listing.
- [x] 5.3 Document that automatic node download/installation, partner/API video nodes, frontend video browsing, and backend prose-to-video-graph synthesis are out of scope for this MVP.

## 6. Verification

- [x] 6.1 Run backend unit tests covering artifact recording, status serialization, gallery artifact API behavior, and image compatibility.
- [ ] 6.2 Run MCP server tests covering new tools and artifact-aware status responses.
- [ ] 6.3 Validate OpenSpec with `openspec validate add-video-generation-mcp --strict` and `openspec validate --all`.
- [ ] 6.4 Run one low-load local ComfyUI video job end to end with a known-good workflow: submit via `generate_video_custom_workflow`, poll with `get_generation_status`, confirm `artifacts[]`, retrieve via `get_gallery_artifact`, verify the local file exists, and free ComfyUI memory.
- [ ] 6.5 Confirm existing image generation and `get_gallery_image` still pass their current tests.

## 7. Agent Assignment

- [ ] 7.1 Preferred implementation agent: Codex using GPT-5.5.
- [ ] 7.2 When assigning to an external agent, provide change id `add-video-generation-mcp` and require it to follow proposal, design, specs, and tasks before editing implementation code.
