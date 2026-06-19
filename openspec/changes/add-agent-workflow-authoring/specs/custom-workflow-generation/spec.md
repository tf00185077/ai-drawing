## ADDED Requirements

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
