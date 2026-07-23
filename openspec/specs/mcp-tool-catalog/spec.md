# mcp-tool-catalog Specification

## Purpose
Define the audited catalog of agent-facing ai-drawing MCP tools and the contract that keeps it
bidirectionally aligned with the tools actually registered in code, so hidden tools, stale names, and
phantom catalog entries fail tests before release. Covers the machine-readable response contract, LoRA
and multi-LoRA payload consistency, and keeping tool documentation in sync with the catalog.
## Requirements
### Requirement: MCP server exposes an audited tool catalog
The ai-drawing MCP server SHALL maintain a tested catalog of intended agent-facing tools that stays
bidirectionally aligned with the tools actually registered in code: the catalog SHALL contain no tool
that is not registered, and every registered agent-facing tool SHALL appear in the catalog or be
recorded as a documented intentional omission.

#### Scenario: Intended tools are registered
- **WHEN** the MCP server starts and registers its tools
- **THEN** every tool in the intended catalog is registered under its documented name
- **AND** missing or renamed tools fail tests before release

#### Scenario: Catalog contains no phantom tools
- **WHEN** the catalog audit runs
- **THEN** every tool named in the catalog resolves to a registered MCP tool
- **AND** a catalog entry with no corresponding registered tool fails the audit

#### Scenario: Intentional omissions are documented
- **WHEN** a backend endpoint is intentionally not exposed as an MCP tool
- **THEN** the omission is documented with a reason
- **AND** the catalog test does not treat it as an accidental missing tool

### Requirement: Video workflow MCP tools are visible to agents
The MCP server SHALL expose video workflow tools intended for agent use, including custom video workflow submission and video artifact retrieval.

#### Scenario: Agent submits a known-good video workflow
- **WHEN** an agent needs to run a verified low-load video workflow
- **THEN** `generate_video_custom_workflow` is visible through the MCP tool surface
- **AND** it returns a structured queued job response or a structured error

#### Scenario: Agent retrieves a video artifact
- **WHEN** a completed generation job returns video artifacts
- **THEN** `get_gallery_artifact` is visible through the MCP tool surface
- **AND** the returned payload includes artifact id, type, mime type, gallery path, local path, size, job id, and workflow metadata

### Requirement: LoRA resources are exposed consistently
The MCP server SHALL expose LoRA resources and LoRA payload fields consistently across resource, style preset, generation, and training tools.

#### Scenario: Agent lists available LoRAs
- **WHEN** an agent calls `list_available_resources`
- **THEN** the result includes `loras` as a list
- **AND** each item corresponds to an installed or indexed LoRA resource known to the backend

#### Scenario: Agent composes a style preset with LoRA fields
- **WHEN** a style preset includes a single LoRA or ordered multi-LoRA entries
- **THEN** `get_style_preset` and `compose_style_preset` preserve those fields in the machine-readable payload
- **AND** the payload can be passed to generation tools without silently dropping LoRA entries

#### Scenario: Agent forwards LoRA generation payloads
- **WHEN** an agent calls a generation or custom workflow tool with LoRA or multi-LoRA parameters
- **THEN** the MCP server forwards the supported LoRA fields to the backend
- **AND** unsupported fields return a structured validation error rather than being silently ignored

### Requirement: MCP response shapes are machine-readable
The MCP server SHALL provide machine-readable responses for agent-facing tools.

#### Scenario: Structured tool succeeds
- **WHEN** a structured MCP tool succeeds
- **THEN** it returns a JSON-compatible dictionary with `ok=true`, `tool`, and documented payload fields

#### Scenario: Structured tool fails
- **WHEN** a structured MCP tool fails due to backend, validation, runtime, or registration errors
- **THEN** it returns `ok=false`, `tool`, and an `error` object with `code`, `message`, and optional `details`

#### Scenario: Transitional string tools remain parseable or documented
- **WHEN** a tool remains string-returning for compatibility
- **THEN** tests assert whether the string is parseable JSON or intentionally human-readable
- **AND** docs mark the tool's response category

### Requirement: MCP catalog remains aligned with documentation
The project documentation SHALL list the audited MCP tools and their response category.

#### Scenario: Tool documentation is checked
- **WHEN** a tool is added, removed, or renamed
- **THEN** tests or review tasks require updating the MCP catalog documentation
- **AND** stale tool names do not remain in setup docs as active capabilities

### Requirement: MCP image generation accepts ordered multi-LoRA payloads
The MCP image generation tool SHALL expose an optional `loras` field containing ordered LoRA descriptors and SHALL forward it to the backend generation request without dropping or flattening it.

#### Scenario: Compose style preset payload can be submitted unchanged
- **GIVEN** `compose_style_preset` returns a generation payload containing `loras`
- **WHEN** an agent submits that payload through MCP `generate_image`
- **THEN** the backend receives the same ordered `loras` array
- **AND** legacy `lora`/`lora_strength` compatibility fields are not required to represent multiple LoRAs

#### Scenario: Distinct multi-LoRA workflow nodes are preserved
- **GIVEN** a multi-LoRA template has separate LoRA loader nodes
- **WHEN** a generation request supplies ordered LoRAs with different names and strengths
- **THEN** the submitted ComfyUI workflow uses the corresponding distinct LoRA name and strength per node
- **AND** it MUST NOT overwrite every LoRA loader with the first or legacy single LoRA.

### Requirement: MCP cancel job works through backend client
The MCP cancel job tool SHALL call the backend cancel/delete endpoint through a supported HTTP client method.

#### Scenario: Cancel pending job
- **GIVEN** a queued/pending generation job id
- **WHEN** the agent calls MCP `cancel_job`
- **THEN** the call returns a successful cancellation response or a structured backend error
- **AND** it MUST NOT fail because the HTTP client lacks a `delete` method.

