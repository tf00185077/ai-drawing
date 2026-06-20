## ADDED Requirements

### Requirement: Persist the submitted workflow on each generated image

The system SHALL store the final ComfyUI workflow (the prompt dict actually submitted to ComfyUI) on each recorded image as `workflow_json`, in addition to the existing denormalized metadata columns.

#### Scenario: Workflow stored after a successful generation

- **WHEN** a job completes and its image is recorded
- **THEN** the `GeneratedImage` record stores the submitted workflow as `workflow_json`
- **AND** the existing columns (checkpoint, lora, prompt, seed, steps, cfg, ...) remain populated for querying and display

### Requirement: Persist gallery-relative source references

The system SHALL store the gallery-relative `source_image` and `source_mask` paths used by a generation, because the persisted workflow embeds only ephemeral ComfyUI input filenames.

#### Scenario: img2img source recorded

- **WHEN** a generation is submitted with a subject `image` (and optionally a `mask`)
- **THEN** the record stores `source_image` (and `source_mask`) as the original gallery-relative paths

#### Scenario: txt2img leaves source references empty

- **WHEN** a generation has no subject image or mask
- **THEN** `source_image` and `source_mask` are null on the record

### Requirement: Rerun reproduces the stored workflow exactly

`gallery_rerun` SHALL reproduce an image by re-submitting its stored `workflow_json` through the custom path, re-uploading `source_image`/`source_mask` from the gallery and re-injecting the fresh uploaded filenames into the workflow's `LoadImage`/`LoadImageMask` nodes before submission.

#### Scenario: Custom workflow reproduced faithfully

- **WHEN** rerun is requested for an image that has `workflow_json`
- **THEN** the stored workflow is submitted via the custom path
- **AND** any `source_image`/`source_mask` are re-uploaded and re-injected so the graph references valid input files

#### Scenario: Seed reused for precise reproduction

- **WHEN** an image with a stored workflow is rerun
- **THEN** the seed baked into `workflow_json` is reused unchanged
- **AND** no new random seed is generated

### Requirement: Legacy records fall back to column reconstruction

For records that have no `workflow_json` (created before this capability), `gallery_rerun` SHALL fall back to the existing behavior of reconstructing a flat params dict from the denormalized columns and submitting through the template path.

#### Scenario: Old record without stored workflow

- **WHEN** rerun is requested for a record whose `workflow_json` is null
- **THEN** rerun reconstructs params from the stored columns and submits through the template path as before
