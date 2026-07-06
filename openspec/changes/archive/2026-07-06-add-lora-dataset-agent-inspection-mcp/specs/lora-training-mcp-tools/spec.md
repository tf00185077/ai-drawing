## ADDED Requirements

### Requirement: MCP can manage LoRA dataset metadata profiles
The MCP server SHALL expose structured tools for reading, validating, and updating `.lora-dataset.json` metadata profiles through the backend.

#### Scenario: Agent reads dataset metadata
- **WHEN** an agent calls `lora_dataset_metadata_get` with a dataset folder
- **THEN** the result includes `ok=true`, normalized profile fields, profile validation status, and `profile_hash`

#### Scenario: Agent validates proposed metadata without writing
- **WHEN** an agent calls `lora_dataset_metadata_validate` with proposed profile fields
- **THEN** the result includes validation errors, warnings, normalized values, and no file write side effects

#### Scenario: Agent updates metadata with conflict protection
- **WHEN** an agent calls `lora_dataset_metadata_update` with an expected profile hash
- **THEN** the result includes the updated profile and new `profile_hash`
- **AND** stale profile hashes return `ok=false` with a structured conflict error

### Requirement: MCP can provide agent-ready dataset inspection
The MCP server SHALL expose `lora_dataset_agent_inspect` to compose backend dataset inspection, profile validation, and caption suitability summary for Hermes/OpenClaw review.

#### Scenario: Agent inspection returns combined review signals
- **WHEN** an agent calls `lora_dataset_agent_inspect` for a dataset folder
- **THEN** the result includes profile summary, profile validation messages, caption suitability verdict, reasons, recommendations, trigger-token coverage, dataset hash, and profile hash

#### Scenario: Agent inspection does not start training
- **WHEN** an agent calls `lora_dataset_agent_inspect`
- **THEN** no LoRA training job is enqueued
- **AND** `not_suitable` and `needs_review` verdicts are returned as structured payload outcomes when backend transport succeeds
