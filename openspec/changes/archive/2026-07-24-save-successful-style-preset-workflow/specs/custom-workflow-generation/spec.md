## ADDED Requirements

### Requirement: Server-owned saved workflow submission can bypass parameter injection

The backend SHALL provide a narrowly scoped queue path for a saved style-preset workflow that submits the parsed graph verbatim. This path SHALL be distinct from the caller-supplied custom-workflow request whose prompt defaults and optional overrides are intentionally applied.

#### Scenario: Existing custom workflow behavior remains unchanged

- **WHEN** a caller uses `generate_image_custom_workflow`
- **THEN** its existing prompt and explicit-override semantics remain unchanged
- **AND** the new verbatim path does not weaken validation or alter that public contract

#### Scenario: Verbatim path makes no graph mutations

- **WHEN** the backend retests a server-owned saved style-preset graph
- **THEN** the object submitted to ComfyUI is deeply equal to the saved parsed graph
- **AND** no default prompt or runtime override is applied

#### Scenario: Queue lifecycle remains shared

- **WHEN** a verbatim saved graph is queued
- **THEN** it uses the existing job status, completion recording, artifact, and structured ComfyUI node-error lifecycle

#### Scenario: Verbatim submit failure cannot block the queue

- **WHEN** ComfyUI submission raises an HTTP status error, returns no `prompt_id`, or raises another exception
- **THEN** the verbatim job becomes terminal `failed` with structured status
- **AND** the running slot is released
- **AND** the next pending job can proceed
