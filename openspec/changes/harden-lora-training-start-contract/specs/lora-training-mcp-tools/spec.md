## MODIFIED Requirements

### Requirement: MCP can start LoRA training
The MCP server SHALL expose `lora_train_start` to start a backend-managed LoRA training job with the complete backend-supported public Start contract, including folder, normalized trigger token, expected dataset hash, expected profile hash, checkpoint, epochs, `batch_size`, and other supported training parameters. The two expected hashes SHALL be required approval evidence.

#### Scenario: Agent starts training after approved preflight
- **WHEN** an agent calls `lora_train_start` with a valid dataset, the current expected dataset/profile hashes, and supported parameters including `batch_size`
- **THEN** MCP forwards every supplied supported field unchanged to Backend Start
- **AND** the result includes `ok=true`, `job_id`, status `queued`, stage, dataset hash, profile hash, and normalized trigger token

#### Scenario: Start rejects missing approval hashes
- **WHEN** an agent calls `lora_train_start` without either `expected_dataset_hash` or `expected_profile_hash`
- **THEN** the call returns `ok=false`
- **AND** the structured validation details identify each missing field
- **AND** protocol-level validation does not echo any submitted input value
- **AND** no durable training job is created

#### Scenario: Start rejects invalid or racing datasets
- **WHEN** Backend Start rejects the dataset due to unsafe path, validation errors, lock conflict, stale dataset/profile hash, or declared model-family conflict
- **THEN** the MCP result includes `ok=false`
- **AND** includes structured error details that allow the agent to inspect the dataset and rerun decision preflight

### Requirement: MCP can run LoRA training decision preflight
The MCP server SHALL expose `lora_training_decision_preflight` so an agent can request the backend training decision without starting training. For a startable decision, the suggested Start parameters SHALL include both approval hashes and every parameter selected by preflight that Backend Start supports.

#### Scenario: Agent receives train decision
- **WHEN** an agent calls `lora_training_decision_preflight` for a ready dataset whose declared profile family matches the configured training family
- **THEN** the result includes `ok=true`, decision `train`, reasons, dataset hash, profile hash, suggested parameters, and next actions
- **AND** `suggested_params.params` includes `expected_dataset_hash` and `expected_profile_hash`

#### Scenario: Agent receives review or do not train decision
- **WHEN** an agent calls `lora_training_decision_preflight` for a dataset with warnings or blocking issues
- **THEN** the result includes `ok=true`, decision `needs_review` or `do_not_train`, reasons, blocking issues when present, and recommended next actions

#### Scenario: Configured family conflicts with dataset profile
- **WHEN** the dataset profile declares a model family different from the configured default training family
- **THEN** preflight does not return a ready-to-submit default checkpoint pairing
- **AND** returns decision `needs_review` with a structured `model_family_mismatch` warning

#### Scenario: Decision preflight does not call training start
- **WHEN** an agent calls `lora_training_decision_preflight`
- **THEN** the MCP server does not call `lora_train_start`
- **AND** no backend LoRA training job is enqueued

## ADDED Requirements

### Requirement: MCP preserves field-level Backend Start validation
The MCP server SHALL convert FastAPI/Pydantic request-validation failures into the stable MCP error envelope without flattening field-level validation entries or echoing submitted input values.

#### Scenario: Backend returns list-shaped 422 details
- **WHEN** Backend Start returns HTTP 422 with list-shaped validation details
- **THEN** MCP returns `ok=false`, `status_code=422`, and `error.code=request_validation_failed`
- **AND** `error.details.validation_errors` preserves each safe `loc`, `msg`, `type`, and constraint context entry
- **AND** submitted `input` values are omitted

#### Scenario: Backend returns application error dictionary
- **WHEN** Backend Start returns a dictionary-shaped error with `code`, `message`, and `details`
- **THEN** MCP preserves those fields in its existing structured error envelope

### Requirement: MCP and Backend Start fields remain aligned
The project SHALL enforce automated parity between the MCP `lora_train_start` parameters, Backend `TrainStartRequest` fields, and fields emitted by a complete preflight suggestion, except for a documented minimal allowlist of transport-only differences.

#### Scenario: Supported Start field is added
- **WHEN** a developer adds a public Backend Start field
- **THEN** the contract-parity test fails until MCP forwarding and preflight behavior are explicitly aligned or the field is documented as an allowed difference

#### Scenario: Current Start contract includes batch size and approval hashes
- **WHEN** the parity test inspects the current public Start contract
- **THEN** `batch_size`, `expected_dataset_hash`, and `expected_profile_hash` are present in Backend Start, MCP Start, and complete preflight suggested parameters
