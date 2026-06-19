## ADDED Requirements

### Requirement: Custom workflow forwards ComfyUI validation errors for self-correction

When a custom workflow submitted through `generate_image_custom_workflow` is rejected by ComfyUI `/prompt` validation, the system SHALL relay ComfyUI's `node_errors` to the caller as a structured, agent-parseable error identifying the offending node(s) and reason, rather than failing opaquely. The system SHALL NOT implement an independent pre-submission graph validator for this path.

#### Scenario: Node errors surfaced as structured data

- **WHEN** a custom workflow references a node input that ComfyUI rejects at `/prompt` validation
- **THEN** the tool result reports `ok=false` with the ComfyUI `node_errors` mapped to node id, node type, and error reason
- **AND** the result is shaped so the agent can correct the workflow and resubmit

#### Scenario: Unknown node type reported by node, not swallowed

- **WHEN** a custom workflow contains a `class_type` that does not exist on the live ComfyUI instance
- **THEN** the error identifies the offending node and indicates the node type is unknown
- **AND** the job is not left in an opaque failed state without diagnostics

#### Scenario: Valid workflow is unaffected

- **WHEN** a custom workflow passes ComfyUI validation
- **THEN** generation proceeds as before and no validation-error payload is returned
