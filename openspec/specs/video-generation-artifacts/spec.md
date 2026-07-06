# video-generation-artifacts Specification

## Purpose
TBD - created by archiving change add-video-generation-mcp. Update Purpose after archive.
## Requirements
### Requirement: Generated artifacts are persisted generically

The system SHALL persist generated non-image outputs using a generic artifact record such as `GeneratedArtifact`. Each artifact record SHALL include at minimum artifact id, job id, artifact type, gallery-relative path, mime type, creation timestamp, and enough workflow/prompt metadata to inspect the generation later.

#### Scenario: Video artifact record contains delivery metadata
- **WHEN** a completed job produces a video file
- **THEN** the system records an artifact with the job id, artifact type, mime type, gallery-relative path, and creation timestamp
- **AND** the artifact detail includes a local path or URL that an MCP client can use to deliver the file

#### Scenario: Artifact persistence does not replace image rows
- **WHEN** an image job completes after artifact support is added
- **THEN** existing `GeneratedImage` persistence still occurs
- **AND** artifact persistence does not require existing image callers to change tools

### Requirement: Completed jobs expose generated video artifacts

The system SHALL record generated video outputs from completed ComfyUI jobs as gallery artifacts, including at minimum artifact id, job id, artifact type, gallery-relative path, mime type, and creation timestamp. The system SHALL preserve the submitted workflow JSON and prompt metadata for faithful inspection and rerun diagnostics.

#### Scenario: MP4 output is recorded as a video artifact
- **WHEN** a ComfyUI job completes with an `.mp4` output file
- **THEN** the backend copies the file into the configured project gallery
- **AND** records an artifact with `artifact_type="video"`, a `video/mp4` mime type, the job id, and the gallery-relative path

#### Scenario: WEBM output is recorded as a video artifact
- **WHEN** a ComfyUI job completes with a `.webm` output file
- **THEN** the backend copies the file into the configured project gallery
- **AND** records an artifact with `artifact_type="video"` and a `video/webm` mime type

#### Scenario: Completed video job without an artifact is a recording failure
- **WHEN** ComfyUI reports a prompt complete but the backend cannot find any image, video, or file artifact to record
- **THEN** the job is marked `failed`
- **AND** the status response includes a structured recording error instead of reporting success

### Requirement: Generation status returns artifacts for completed jobs

The generation status endpoint and MCP status tool SHALL return an `artifacts` array for completed jobs. Each artifact entry SHALL include id, artifact type, path, and mime type. Existing image-oriented fields SHALL remain available for backward compatibility when the completed job produced an image.

#### Scenario: Completed video job returns artifact list
- **WHEN** an agent queries generation status for a completed video job
- **THEN** the response includes `status="completed"`
- **AND** includes an `artifacts` array containing the generated video artifact
- **AND** the `next` instruction directs the agent to call `get_gallery_artifact`

#### Scenario: Status artifact entry is sufficient for routing
- **WHEN** a completed job status includes an artifact entry
- **THEN** each entry includes artifact id, artifact type, mime type, and gallery-relative path
- **AND** the agent can choose `get_gallery_artifact` without relying on image-only fields

#### Scenario: Existing image status remains backward compatible
- **WHEN** an agent queries generation status for a completed image job
- **THEN** the response still includes the existing `image_id` and `image_path` fields
- **AND** also includes the same output in the `artifacts` array

### Requirement: MCP can retrieve a recorded gallery artifact

The MCP server SHALL expose `get_gallery_artifact(artifact_id)` to retrieve metadata and a local file path or URL for any recorded gallery artifact, including video. The tool SHALL return stable, agent-friendly JSON.

#### Scenario: Retrieve video artifact by id
- **WHEN** an agent calls `get_gallery_artifact` with the id of a recorded video artifact
- **THEN** the response includes `ok=true`, artifact id, artifact type, mime type, gallery-relative path, local path, and any available workflow metadata
- **AND** the local path points to a file that exists on disk

#### Scenario: Unknown artifact returns structured not found
- **WHEN** an agent calls `get_gallery_artifact` with an id that does not exist
- **THEN** the response returns a structured not-found error
- **AND** the error is represented as data rather than an unhandled exception

### Requirement: Artifact records preserve image workflow compatibility

The system SHALL add artifact recording in a way that does not require existing image callers to migrate immediately. Existing gallery image APIs and MCP `get_gallery_image` SHALL continue to work for previously supported image jobs.

#### Scenario: Existing image gallery lookup still works
- **WHEN** an image job completes after artifact support is added
- **THEN** `get_gallery_image` can still retrieve the image by its image id
- **AND** existing image gallery API consumers do not need to call `get_gallery_artifact`

### Requirement: Video artifact verification uses a real ComfyUI workflow

The MVP SHALL NOT be considered complete until a known-good local ComfyUI video workflow has been submitted through MCP and its produced video artifact has been retrieved through the artifact read path.

#### Scenario: Known-good video workflow completes end to end
- **WHEN** CTY provides a known-good ComfyUI video workflow whose required nodes and models are installed locally
- **THEN** an agent can submit it through MCP, poll completion, observe a video artifact in `artifacts[]`, retrieve it with `get_gallery_artifact`, and verify the local file exists

#### Scenario: Missing live workflow keeps implementation incomplete
- **WHEN** unit tests pass but no known-good local ComfyUI video workflow has been run through the MCP artifact path
- **THEN** the MVP remains unverified for release

