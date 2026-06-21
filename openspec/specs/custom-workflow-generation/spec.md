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

