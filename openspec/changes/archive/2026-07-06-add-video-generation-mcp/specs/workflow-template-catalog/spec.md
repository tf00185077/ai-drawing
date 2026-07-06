## MODIFIED Requirements

### Requirement: Templates carry a machine-readable capability manifest

Each workflow template SHALL have an associated manifest containing a controlled-vocabulary set of capability tags. The manifest SHALL define both `modality` (single-valued enum: `txt2img` | `img2img` | `inpaint` | `txt2video` | `img2video`) and `model_family` (single-valued, e.g. `sdxl`, `sd15`, `anima`, or a video model family) as required fields; neither can be omitted or null, so matching never falls into an "unknown family" gray zone. The manifest can additionally define `conditioning` (set, e.g. `controlnet_pose`) and `io` (set, e.g. `text`, `image_ref`, `mask`, `first_frame`, `last_frame`, `video_ref`, `audio_ref`). A human-readable `description` can be present but SHALL NOT participate in matching decisions.

#### Scenario: Manifest exposes capability tags

- **WHEN** a client reads the manifest for the `inpaint` template
- **THEN** the manifest reports `modality=inpaint`, a non-null `model_family`, and `io` including `mask`
- **AND** any `description` text is returned as metadata only

#### Scenario: Tags are drawn from a controlled vocabulary

- **WHEN** a manifest is created or backfilled with a capability tag not in the controlled vocabulary
- **THEN** the system rejects or flags the manifest as invalid rather than silently accepting a free-form tag

#### Scenario: Missing required field is rejected

- **WHEN** a manifest omits `modality` or `model_family`
- **THEN** the system flags the manifest as invalid identifying the missing required field
- **AND** does not treat the absent field as a wildcard

#### Scenario: Text-to-video manifest validates

- **WHEN** a workflow template manifest declares `modality="txt2video"` with a non-empty `model_family`
- **THEN** template capability validation accepts the manifest
- **AND** the template appears in the lightweight capability index

#### Scenario: Image-to-video manifest validates

- **WHEN** a workflow template manifest declares `modality="img2video"` with a non-empty `model_family`
- **THEN** template capability validation accepts the manifest
- **AND** the template appears in the lightweight capability index

### Requirement: Backfill is gated on verified generation success

The system SHALL write a self-authored workflow back into the template catalog only after ComfyUI has produced at least one supported artifact and the generation has been recorded successfully. A submitted-but-unverified workflow SHALL NOT be promoted to a template.

#### Scenario: Promotion occurs only after a recorded image

- **WHEN** a self-authored custom workflow completes and its output image is recorded
- **THEN** the workflow shape is eligible for backfill into the catalog

#### Scenario: Promotion occurs only after a recorded video artifact

- **WHEN** a self-authored custom video workflow completes and its output video artifact is recorded
- **THEN** the workflow shape is eligible for backfill into the catalog with video capability tags

#### Scenario: Failed or unrecorded generation is not promoted

- **WHEN** a self-authored custom workflow fails in ComfyUI or produces no recorded artifact
- **THEN** the workflow is NOT written into the catalog

## ADDED Requirements

### Requirement: Template manifests support video IO tags

Workflow template capability manifests SHALL support controlled IO tags needed by minimal video workflows, including `first_frame`, `last_frame`, `video_ref`, and `audio_ref` in addition to existing `text`, `image_ref`, and `mask` tags.

#### Scenario: First-frame image-to-video template is matchable
- **WHEN** a template manifest declares `modality="img2video"` and `io=["text", "first_frame"]`
- **THEN** a match request requiring `modality="img2video"` and `io=["first_frame"]` returns that template as a match

#### Scenario: Missing video IO does not match
- **WHEN** a match request requires `io=["last_frame"]` and a template only declares `io=["text", "first_frame"]`
- **THEN** that template is not returned as a match

### Requirement: Verified video workflows can be saved as reusable templates

The workflow template save path SHALL allow a verified video-producing job to be promoted into the reusable template catalog with video modality and IO tags. Promotion SHALL remain gated on recorded generation success.

#### Scenario: Successful video job is eligible for template save
- **WHEN** a custom video workflow completes and records at least one video artifact
- **THEN** the agent can call the template-save operation with video capability tags
- **AND** the saved template is listed by `list_template_capabilities`

#### Scenario: Failed video job is not promotable
- **WHEN** a custom video workflow fails validation, fails execution, or completes without a recorded artifact
- **THEN** the workflow is not eligible for template promotion
- **AND** the save operation returns a structured error rather than creating a broken template

### Requirement: Template matching supports video derivation from a base workflow

The template catalog SHALL let agents discover reusable video workflow shapes by matching video modality and IO tags. A matched template provides a base workflow shape that an agent can derive from through custom workflow submission; matching SHALL NOT imply that the backend can synthesize arbitrary video workflows from prose.

#### Scenario: Agent finds an image-to-video base template
- **WHEN** an agent requests `modality="img2video"` with `io=["first_frame"]`
- **THEN** matching returns valid templates whose capability tags cover those requirements
- **AND** the agent can fetch the workflow shape and submit a derived variant through the custom video workflow path

#### Scenario: No matching video template requires caller-provided workflow
- **WHEN** no template covers the requested video modality and IO tags
- **THEN** the system reports a match miss
- **AND** the agent must provide a complete known-good workflow JSON before using `generate_video_custom_workflow`
