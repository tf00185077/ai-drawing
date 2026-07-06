# custom-workflow-generation

## Purpose

Submitting an arbitrary ComfyUI workflow JSON for generation through the `generate_image_custom_workflow` MCP tool and the backend `/api/generate/custom` endpoint. Defines the parameter channels the tool exposes (prompt, subject image, mask, model components, sampler params), the "override only when provided" injection semantics that respect the submitted JSON, and the gallery→ComfyUI upload of reference/mask images. This is the single flexible entry point intended to cover txt2img, img2img, ControlNet, and inpaint scenarios.
## Requirements
### Requirement: Custom workflow accepts a subject image for img2img

The `generate_image_custom_workflow` MCP tool SHALL accept an `image` parameter referencing a gallery-relative path, and the backend SHALL upload it to ComfyUI and inject the uploaded filename into the subject `LoadImage` node of the submitted workflow.

#### Scenario: Subject image forwarded to the workflow

- **WHEN** the tool is called with `image="2026-03-08/subject.png"` and a workflow containing a `LoadImage` node
- **THEN** the backend uploads the gallery file to ComfyUI
- **AND** the first `LoadImage` node's `image` input is replaced with the uploaded filename before submission

#### Scenario: Subject path outside the gallery is rejected

- **WHEN** the `image` path resolves outside the configured `gallery_dir`
- **THEN** the path is treated as not found and is not injected into the workflow

### Requirement: Custom workflow accepts an inpaint mask

The tool SHALL accept a `mask` parameter referencing a gallery-relative image, and the backend SHALL upload it and inject the uploaded filename into the `LoadImageMask` node's `image` input.

#### Scenario: Mask forwarded to the inpaint mask node

- **WHEN** the tool is called with `mask="2026-03-08/mask.png"` and a workflow containing a `LoadImageMask` node
- **THEN** the backend uploads the mask and sets that node's `image` input to the uploaded filename

#### Scenario: Subject and mask coexist without collision

- **WHEN** both `image` and `mask` are provided to an inpaint workflow
- **THEN** the subject is injected into the `LoadImage` node and the mask into the `LoadImageMask` node, because they are distinct `class_type`s

### Requirement: Custom workflow exposes model-component and batch parameters

The tool SHALL accept `batch_size`, `diffusion_model`, `text_encoder`, and `vae` parameters and forward each to the backend only when provided, so diffusion-model-family (e.g. Anima) custom workflows can be parameterized.

#### Scenario: Diffusion-model components forwarded when provided

- **WHEN** the tool is called with `diffusion_model`, `text_encoder`, and `vae` values
- **THEN** the backend injects them into the `UNETLoader`, `CLIPLoader`, and `VAELoader` nodes respectively

#### Scenario: Omitted components leave the workflow untouched

- **WHEN** `diffusion_model` / `text_encoder` / `vae` are omitted
- **THEN** the corresponding loader nodes keep the filenames already present in the submitted workflow

### Requirement: Parameter injection overrides only caller-provided values

For custom workflows, `apply_params` SHALL write `steps`, `cfg`, and `seed` into `KSampler` nodes only when the caller explicitly provides those values; when omitted, the values already present in the submitted workflow JSON SHALL be preserved.

#### Scenario: Omitted sampler params preserve workflow JSON

- **WHEN** a custom workflow whose `KSampler` has `steps=30`, `cfg=5.5` is submitted without `steps` or `cfg`
- **THEN** the submitted prompt retains `steps=30` and `cfg=5.5`

#### Scenario: Multi-sampler workflow keeps independent values

- **WHEN** a custom workflow contains two `KSampler` nodes with different `steps`/`cfg` and the caller omits both
- **THEN** each `KSampler` retains its own original `steps`/`cfg` values

#### Scenario: Provided params override the workflow

- **WHEN** the caller passes `steps=12`
- **THEN** every targeted `KSampler` node's `steps` input becomes `12`

### Requirement: Template-path generation keeps default sampler behavior

`generate_image` (template-path) generation SHALL preserve existing behavior: when `steps` or `cfg` is omitted they default to `20` and `7.0`, and an omitted `seed` is randomized and recorded.

#### Scenario: Template defaults applied when omitted

- **WHEN** `generate_image` is called without `steps`, `cfg`, or `seed`
- **THEN** the submitted workflow uses `steps=20`, `cfg=7.0`, and a randomly generated seed that is recorded for the job

### Requirement: Inpaint workflow template is available

The backend SHALL provide an `inpaint` workflow template composed of a subject `LoadImage`, a `LoadImageMask`, and a `VAEEncodeForInpaint` feeding the `KSampler`, retrievable via the workflow-templates endpoints and listed among available templates.

#### Scenario: Inpaint template listed and retrievable

- **WHEN** a client lists workflow templates
- **THEN** `inpaint` appears in the list
- **AND** fetching `inpaint` returns a valid ComfyUI workflow JSON containing `LoadImageMask` and `VAEEncodeForInpaint` nodes

### Requirement: Custom workflow forwards ComfyUI validation errors for self-correction

When a custom workflow submitted through `generate_image_custom_workflow` is rejected by ComfyUI `/prompt` validation, the system SHALL relay ComfyUI's `node_errors` to the caller as a structured, agent-parseable error (node id, node type, reason) via the job's generation status, rather than failing opaquely. Because submission is asynchronous (queued), the rejection SHALL be recorded as a terminal `failed` job state — not retried — and exposed when the caller queries that job's status. The system SHALL NOT implement an independent pre-submission graph validator for this path.

#### Scenario: Node errors surfaced as structured data

- **WHEN** a custom workflow is rejected by ComfyUI `/prompt` validation
- **THEN** querying the job's generation status reports `ok=false`, status `failed`, and the ComfyUI `node_errors` mapped to node id, node type, and reason
- **AND** the result is shaped so the agent can correct the workflow and resubmit

#### Scenario: Rejected job is terminal, not retried

- **WHEN** a custom workflow is rejected by ComfyUI
- **THEN** the job is recorded as `failed` and is not re-queued for retry
- **AND** the queue is not blocked by the rejected job

#### Scenario: Node type falls back to the submitted workflow

- **WHEN** ComfyUI's `node_errors` for an offending node omits its `class_type`
- **THEN** the structured error fills the node type from the submitted workflow's node definition
- **AND** the job is not left in an opaque failed state without diagnostics

#### Scenario: Valid workflow is unaffected

- **WHEN** a custom workflow passes ComfyUI validation
- **THEN** generation proceeds as before and no validation-error payload is returned

### Requirement: Custom workflow generation supports video workflows

The custom workflow generation path SHALL accept a ComfyUI workflow JSON that produces a video artifact and SHALL process it through the same queue lifecycle as image custom workflows. The system SHALL NOT require a separate pre-built backend template for MVP video generation when the caller supplies the full workflow JSON.

#### Scenario: Agent submits a custom video workflow
- **WHEN** an agent submits a valid custom workflow JSON whose graph saves a video output
- **THEN** the backend queues the workflow and returns a normal generation job id
- **AND** the job can be polled through the existing generation status flow

#### Scenario: Video workflow validation errors remain structured
- **WHEN** ComfyUI rejects a submitted video workflow during `/prompt` validation
- **THEN** the job status reports `failed` with structured `node_errors`
- **AND** the result is shaped so the agent can inspect the offending node and resubmit a corrected workflow

#### Scenario: Backend does not synthesize a graph from prose
- **WHEN** an agent wants to generate video in the MVP
- **THEN** the agent supplies a complete ComfyUI workflow JSON or a derived variant of one
- **AND** the backend does not attempt to construct a full video workflow from a natural-language request

### Requirement: MCP exposes an explicit custom video generation tool

The MCP server SHALL expose a video-named custom generation operation, `generate_video_custom_workflow`, that accepts a workflow JSON string and video-oriented parameters while reusing the backend custom workflow queue path. The tool SHALL return a job id and instruct the caller to poll status.

#### Scenario: MCP custom video tool returns queued job
- **WHEN** an agent calls `generate_video_custom_workflow` with a valid workflow JSON
- **THEN** the response includes `ok=true`, the generation job id, and status `queued`
- **AND** the response tells the agent to call `get_generation_status`

#### Scenario: Image custom workflow tool remains available
- **WHEN** an existing agent calls `generate_image_custom_workflow`
- **THEN** the existing tool remains available and continues to support image workflows without requiring video-specific parameters

### Requirement: Agents can derive variants from a provided video workflow

The MCP workflow shall support agent-side video workflow derivation by accepting modified workflow JSON based on a known-good source workflow. The system SHALL rely on existing node search/schema tools and structured ComfyUI errors to help the agent make safe edits, rather than adding a separate backend video graph builder in the MVP.

#### Scenario: Derived workflow variant is submitted
- **WHEN** an agent starts from a known-good video workflow, changes schema-valid node inputs, and calls `generate_video_custom_workflow`
- **THEN** the backend queues the derived workflow as a normal custom workflow job
- **AND** generation status reports completion or structured failure using the same lifecycle as the base workflow

#### Scenario: Node schema discovery grounds derivation
- **WHEN** an agent needs to alter a video workflow node type
- **THEN** it can use existing node search and schema MCP tools to inspect available inputs before submitting the derived workflow
- **AND** the video MVP does not require automatic node download or installation

### Requirement: Video custom workflow accepts video input references

The video custom workflow tool SHALL support optional input references needed by common video workflows, including at least `image`, `first_frame`, `last_frame`, and `video_ref` as gallery-relative paths. The backend SHALL inject only the references that are provided and SHALL leave the submitted workflow unchanged for omitted references.

#### Scenario: First frame is injected when provided
- **WHEN** `first_frame` is provided and the submitted workflow contains a compatible image-loading node selected for first-frame input
- **THEN** the backend uploads or references the gallery image and replaces that node's image input before submission

#### Scenario: Omitted video inputs preserve workflow JSON
- **WHEN** `first_frame`, `last_frame`, and `video_ref` are omitted
- **THEN** the workflow keeps any embedded input filenames already present in the submitted JSON

#### Scenario: Video reference outside gallery is rejected
- **WHEN** a provided `video_ref` resolves outside the configured gallery or input asset root
- **THEN** the backend rejects the path as not found or unsafe
- **AND** does not inject it into the workflow

