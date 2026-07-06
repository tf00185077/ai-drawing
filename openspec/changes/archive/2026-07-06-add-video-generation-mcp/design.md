## Context

The current `ai-drawing` MCP architecture already has most of the agent-facing control plane needed for video experimentation: agents can list resources, inspect ComfyUI node categories/schemas, retrieve workflow templates, submit arbitrary custom workflow JSON, poll generation status, inspect gallery images, and save successful workflows as templates. The gap is the product lifecycle around outputs: queue completion and gallery recording assume image artifacts, and workflow capabilities do not describe video modalities.

The requested MVP lets a Codex/GPT-5.5-style agent start from a human-provided, known-good ComfyUI video workflow, derive variants using existing node-schema and custom-workflow MCP tools, and produce a deliverable video through MCP. It does not try to solve every video-model family, node installation, or frontend UI problem in the first slice.

## Goals / Non-Goals

**Goals:**

- Preserve the existing image-generation behavior and MCP tools.
- Add the smallest backend/API/MCP artifact lifecycle needed for generated video files.
- Allow an agent to submit a ComfyUI video workflow, poll the job, receive structured terminal status, fetch the resulting video artifact, and deliver it as a file path.
- Let successful video workflow shapes be described by template capability tags and saved/reused.
- Make the distinction explicit: workflow derivation is an agent-side MCP capability; durable video artifact lifecycle is a backend/API/MCP product contract.
- Keep the MVP grounded in local ComfyUI workflows and local filesystem artifacts.

**Non-Goals:**

- No video frontend/gallery UI in the first MVP.
- No automatic custom-node installation or dependency management.
- No backend generation of a complete video graph from prose.
- No guarantee that any arbitrary video model family is installed locally.
- No partner/API video nodes requiring third-party credentials.
- No full video editing suite, timeline editor, or multi-shot orchestration.
- No migration that breaks existing `GeneratedImage`, `get_gallery_image`, or `generate_image_custom_workflow` clients.

## Decisions

### Decision 1: Add a generic `GeneratedArtifact` layer, keep image compatibility

Use a new artifact record/read path for video instead of forcing videos into `GeneratedImage`. The artifact record includes at minimum `id`, `job_id`, `artifact_type`, `gallery_path`, `mime_type`, `workflow_json`, prompt metadata, `source_node_id`, `source_node_type`, file size, and timestamps, with optional video metadata such as fps, frame count, duration, width, and height when discoverable.

Alternatives considered:
- **Reuse `GeneratedImage` with video paths**: fastest but semantically wrong and brittle for future audio/3D outputs.
- **Create `GeneratedVideo` only**: clearer for video but repeats logic and does not generalize to GIF/audio/file outputs.

Rationale: `GeneratedArtifact` is the smallest clean abstraction that supports video now and future non-image outputs later, while legacy image rows can remain untouched. Image outputs are mirrored into artifacts, but the legacy image path remains authoritative for existing callers during the MVP.

### Decision 2: Make job status artifact-aware while preserving legacy fields

`get_generation_status` returns `artifacts[]` for completed jobs. For image jobs, continue returning `image_id`/`image_path` for backward compatibility. For video jobs, return artifact entries and a `next` instruction to call `get_gallery_artifact`.

Alternatives considered:
- **Add separate video-only status endpoint**: avoids touching existing response shape, but duplicates polling semantics.
- **Replace image fields entirely**: cleaner long term, but breaks existing agents and tests.

Rationale: artifact-aware status lets one queue completion path serve image and video without disrupting current users.

### Decision 3: MVP submit path starts with custom video workflows

Add `generate_video_custom_workflow` as an MCP/API wrapper around the existing custom-workflow queue path, using video-specific naming and parameters where needed. It accepts raw workflow JSON and optional video input references, but it does not synthesize a video graph from scratch in MVP.

Alternatives considered:
- **Only reuse `generate_image_custom_workflow`**: technically possible, but the name and return semantics mislead agents and hide artifact expectations.
- **Build `generate_video` template path first**: useful later, but premature without at least one verified video template and artifact lifecycle.

Rationale: a named video custom path communicates intent and allows narrow video parameters without overloading the image tool further.

### Decision 4: Separate workflow derivation from artifact lifecycle

Agents can derive variants from a base ComfyUI video workflow by using existing MCP tools: search node types, inspect node schemas, edit workflow JSON, submit through `generate_video_custom_workflow`, inspect structured node errors, and promote verified shapes with `save_workflow_template`. The backend remains responsible for queueing, structured failures, and artifact recording, not for creative graph synthesis.

Alternatives considered:
- **Backend workflow builder for video**: easier for simple prompts but too broad and model-family-specific for the first slice.
- **No derivation path, only exact template replay**: safer but does not answer CTY's key question about agent-derived variants.

Rationale: a provided known-good template plus schema-grounded variant editing is enough to prove MCP derivation while keeping implementation bounded.

### Decision 5: Extend template tags before broad template automation

Add controlled vocabulary entries for video modalities and IO, but only require one known-good template to prove the path. Initial modalities include `txt2video` and `img2video`; IO includes `text`, `image_ref`, `first_frame`, `last_frame`, `video_ref`, and optionally `audio_ref` as future-facing vocabulary.

Alternatives considered:
- **Use free-form tags**: flexible but weakens deterministic matching.
- **Wait until many video templates exist**: delays agent reuse and successful workflow backfill.

Rationale: the existing matching design depends on exact capability tags; video needs to enter that vocabulary before template matching/backfill is reliable.

### Decision 6: Do not make node download part of the MVP

Node discovery and schema lookup are enough for deriving variants from an installed/working base template. Node download/install/restart introduces dependency, security, and stability risks and remains a separate change.

Alternatives considered:
- **Bundle node installation into video MVP**: could broaden what runs, but greatly increases failure modes.
- **Forbid derived workflows**: too restrictive; schema lookup already supports controlled derivation.

Rationale: CTY's immediate need is to know the minimal MCP tool/backend changes. A known-good base template plus artifact lifecycle is the shortest verifiable route.

## Risks / Trade-offs

- **Risk: ComfyUI history output shapes vary by video node** → Mitigation: implement extension-based artifact discovery (`mp4`, `webm`, `gif`) in addition to known `videos` output keys, and record node id/type for diagnostics.
- **Risk: A workflow completes but produces no recorded artifact** → Mitigation: mark the job `failed` with a structured `recording_error` rather than reporting success.
- **Risk: Large video files stress Discord or local delivery** → Mitigation: return local path, size, and mime type; delivery policy can decide whether to attach or summarize.
- **Risk: Video models/resources are not installed** → Mitigation: MVP accepts known-good workflows first and only lists resource directories that are actually configured.
- **Risk: Existing image clients break** → Mitigation: preserve legacy fields, old MCP tools, and image gallery APIs; add artifact paths alongside them.

## Migration Plan

1. Add the artifact table through the same idempotent local DB initialization style already used for image metadata columns.
2. Deploy artifact-aware recording while keeping `GeneratedImage` writes and `get_gallery_image` behavior unchanged.
3. Add API/MCP artifact read paths and artifact-aware status fields.
4. Add the video custom workflow tool and template vocabulary.
5. Verify a real known-good local ComfyUI video workflow end to end before marking the MVP complete.

Rollback is straightforward for the MVP because legacy image records and endpoints remain intact. If artifact recording causes runtime issues, disable the video tool and ignore artifact rows while preserving existing image generation.

## Open Questions

- Which known-good ComfyUI video workflow will CTY provide for the live verification run?
- Which video model/custom-node family will be used for the first checked-in template manifest after verification?
