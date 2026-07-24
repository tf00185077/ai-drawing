## ADDED Requirements

### Requirement: Independent seed mode is explicit and backward compatible

The normal generation request SHALL support
`batch_seed_mode` values `shared` and `independent`, with `shared` as the
default. Shared mode SHALL preserve one normal ComfyUI batch using the caller's
original batch size and existing seed behavior.

#### Scenario: Omitted mode preserves shared generation

- **WHEN** a caller submits normal template generation without
  `batch_seed_mode`
- **THEN** the Backend enqueues one execution with the original `batch_size`
- **AND** no independent child expansion occurs

#### Scenario: Explicit shared mode preserves fixed seeds

- **WHEN** a caller submits `batch_seed_mode="shared"` with an explicit or fixed
  seed
- **THEN** the request remains valid under the existing shared-seed contract

### Requirement: Independent mode accepts only backend-owned random template seeds

The Backend SHALL accept independent mode only for normal template generation
whose seed is implicit or random. It SHALL reject incompatible seed selection
and immutable workflow execution with a validation response before enqueue.

#### Scenario: Independent random template request is accepted

- **WHEN** a caller submits normal template generation with
  `batch_seed_mode="independent"`, `batch_size=4`, and implicit or random seed
  selection
- **THEN** the Backend accepts the request for independent child expansion

#### Scenario: Independent fixed seed is rejected

- **WHEN** independent mode is combined with `seed_mode="fixed"`
- **THEN** the Backend rejects the request with HTTP 422

#### Scenario: Independent workflow-default seed is rejected

- **WHEN** independent mode is combined with `seed_mode="workflow_default"`
- **THEN** the Backend rejects the request with HTTP 422

#### Scenario: Independent explicit seed is rejected

- **WHEN** independent mode includes an explicit caller seed
- **THEN** the Backend rejects the request with HTTP 422

#### Scenario: Independent custom or audited workflow is rejected

- **WHEN** independent mode is requested for a custom, immutable, or audited
  workflow execution path
- **THEN** the Backend rejects the request before any work is enqueued

### Requirement: Independent batches use unique private child executions

The Backend SHALL allocate one public parent job ID and one private execution
per requested image. Every child SHALL have a distinct execution ID, a unique
backend-owned seed within the parent, `batch_size=1`, and a stable zero-based
ordinal. Child execution IDs SHALL NOT be exposed by public status/result APIs.

#### Scenario: Four-image request creates four distinct seeds

- **WHEN** Discord submits an independent request with `batch_size=4`
- **THEN** the Backend creates four private child executions
- **AND** all four child seeds are distinct
- **AND** each child workflow has latent `batch_size=1`

#### Scenario: Parent ID is the only public identity

- **WHEN** an independent request is accepted and later queried
- **THEN** submission, queue status, job status, gallery records, and artifacts
  expose the same public parent job ID
- **AND** no private child execution ID is returned

### Requirement: Independent artifacts are collision-free and deterministic

Every successful independent member SHALL be recorded under the public parent
ID with its actual seed. Destination filenames SHALL incorporate the parent and
child ordinal, artifact metadata SHALL include `batch_index` and seed while
preserving `source_node_type`, and public results SHALL order artifacts by child
ordinal then artifact order.

#### Scenario: Repeated ComfyUI source names do not overwrite siblings

- **WHEN** four successful children report the same ComfyUI source filename
- **THEN** the Gallery contains four distinct destination paths
- **AND** every `GeneratedImage.job_id` equals the parent ID
- **AND** every recorded image seed matches its submitted child workflow

#### Scenario: Completed artifacts have deterministic ordering

- **WHEN** member artifacts become available in a different completion or
  database order
- **THEN** job status returns them in child ordinal then artifact order
- **AND** exposes additive `batch_index` and seed metadata when available

#### Scenario: Preview-only child is not a successful member

- **WHEN** an independent child reaches terminal history with only
  `PreviewImage` output
- **THEN** that child is recorded failed with a bounded reason
- **AND** no preview artifact is recorded or returned for the parent
- **AND** later siblings continue

### Requirement: Discord uses independent seeds without command changes

Discord SHALL preserve the existing batch count control, one acknowledgement
job ID, and `/result id:<parent-job-id>` input while adding independent mode to
the final normal generation request.

#### Scenario: Discord four-image payload opts into independent mode

- **WHEN** a Discord user requests four images
- **THEN** style composition retains `overrides.batch_size=4`
- **AND** the final generation payload contains
  `batch_seed_mode="independent"`

#### Scenario: Result returns requested SaveImage files and no previews

- **WHEN** all four independent members complete successfully and `/result`
  queries the parent
- **THEN** Discord downloads and returns all four `SaveImage` files
- **AND** excludes all `PreviewImage` artifacts
- **AND** does not require or display child IDs

#### Scenario: Independent preview cannot use legacy Gallery fallback

- **WHEN** an independent parent has no valid `SaveImage` artifacts
- **THEN** Discord does not query the legacy filename-prefix Gallery fallback
- **AND** no preview is delivered

#### Scenario: Mixed result returns successes and a concise warning

- **WHEN** three of four members succeed and one fails
- **THEN** Discord returns the three successful `SaveImage` files first
- **AND** reports successful and failed counts plus the failed child ordinal and
  sanitized reason
