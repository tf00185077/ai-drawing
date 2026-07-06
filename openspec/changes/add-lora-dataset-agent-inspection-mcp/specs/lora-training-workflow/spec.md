## ADDED Requirements

### Requirement: Dataset metadata can be managed through backend APIs
The backend SHALL expose explicit get, update, and validate operations for `.lora-dataset.json` metadata profiles under `lora_train_dir`.

#### Scenario: Metadata get returns normalized profile state
- **WHEN** a client requests metadata for a valid dataset folder
- **THEN** the response includes the normalized profile, profile validation status, and `profile_hash`

#### Scenario: Metadata update rejects stale profile hash
- **WHEN** a client updates metadata with an `expected_profile_hash` that does not match the current profile
- **THEN** the backend rejects the update with a conflict-style failure
- **AND** the response includes the current `profile_hash`

#### Scenario: Metadata validate does not write files
- **WHEN** a client validates proposed dataset metadata
- **THEN** the backend returns structured errors, warnings, and normalized values
- **AND** `.lora-dataset.json` is not modified

### Requirement: Agent inspection composes profile and suitability signals
The backend SHALL provide an agent inspection response for a dataset that combines profile status, dataset hash, profile hash, caption suitability summary, trigger-token coverage, and existing validation signals.

#### Scenario: Agent inspection summarizes a dataset
- **WHEN** a client requests agent inspection for a valid dataset folder
- **THEN** the response includes dataset identity, profile summary, profile validation messages, caption suitability verdict, reasons, recommendations, dataset hash, and profile hash

#### Scenario: Agent inspection remains side-effect free
- **WHEN** a client requests agent inspection
- **THEN** the backend does not modify captions or metadata
- **AND** no LoRA training job is created
