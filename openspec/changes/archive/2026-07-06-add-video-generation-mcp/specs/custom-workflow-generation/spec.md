## ADDED Requirements

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
