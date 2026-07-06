# lora-training-mcp-tools Specification

## Purpose
TBD - created by archiving change add-lora-training-mcp-workflow. Update Purpose after archive.
## Requirements
### Requirement: MCP LoRA tools return structured JSON results
The MCP server SHALL return JSON-serializable dictionaries for LoRA dataset and training tools instead of human-readable status strings. Every tool result SHALL include `ok`, `tool`, and either payload fields or an `error` object with `code`, `message`, and optional `details`.

#### Scenario: Successful tool result is machine-readable
- **WHEN** a LoRA MCP tool succeeds
- **THEN** the result includes `ok=true`
- **AND** includes the tool name and documented payload fields without requiring text parsing

#### Scenario: Failed tool result is machine-readable
- **WHEN** a LoRA MCP tool fails because the backend returns validation, conflict, not-found, or execution errors
- **THEN** the result includes `ok=false`
- **AND** includes `error.code`, `error.message`, and any structured backend details available

### Requirement: MCP can list LoRA datasets
The MCP server SHALL expose `lora_dataset_list` to list available LoRA training datasets from the backend.

#### Scenario: Agent lists datasets before choosing work
- **WHEN** an agent calls `lora_dataset_list`
- **THEN** the result includes dataset folders, image counts, caption counts, missing caption counts, dataset hashes, and lock states

### Requirement: MCP can inspect one LoRA dataset
The MCP server SHALL expose `lora_dataset_inspect` for detailed dataset inspection by folder.

#### Scenario: Agent inspects dataset files and trigger tokens
- **WHEN** an agent calls `lora_dataset_inspect` with a folder
- **THEN** the result includes file-level image/caption information, detected trigger-token candidates, dataset hash, and validation summary

#### Scenario: Invalid folder is rejected safely
- **WHEN** an agent calls `lora_dataset_inspect` with a folder outside `lora_train_dir`
- **THEN** the result includes `ok=false`
- **AND** the error identifies the folder as invalid or not found without exposing unrelated filesystem paths

### Requirement: MCP can prepare LoRA datasets
The MCP server SHALL expose `lora_dataset_prepare` with dry-run/apply options, requested trigger token, optional AI cleanup flag, and optional backup restore operation.

#### Scenario: Agent dry-runs caption preparation
- **WHEN** an agent calls `lora_dataset_prepare` with `dry_run=true`
- **THEN** the result includes normalized trigger token, proposed changes, unchanged count, changed count, dataset hash before changes, and no backup id

#### Scenario: Agent applies caption preparation
- **WHEN** an agent calls `lora_dataset_prepare` with `dry_run=false`
- **THEN** the result includes backup id, dataset hash before changes, dataset hash after changes, normalized trigger token, and changed count

#### Scenario: Agent restores a preparation backup
- **WHEN** an agent calls `lora_dataset_prepare` with a restore backup id
- **THEN** the result reports restored files and the restored dataset hash

### Requirement: MCP can validate LoRA datasets before training
The MCP server SHALL expose `lora_dataset_validate` to run backend preflight validation before training.

#### Scenario: Agent validates a prepared dataset
- **WHEN** an agent calls `lora_dataset_validate` with folder, trigger token, and optional expected dataset hash
- **THEN** the result includes `ok`, normalized trigger token, dataset hash, counts, warnings, and blocking errors

#### Scenario: Validation conflict is visible to the agent
- **WHEN** backend validation fails because the expected dataset hash is stale
- **THEN** the MCP result includes `ok=false`, conflict error code, and the current dataset hash in details

### Requirement: MCP can start LoRA training
The MCP server SHALL expose `lora_train_start` to start a backend-managed LoRA training job with folder, normalized trigger token, expected dataset hash, checkpoint, epochs, and supported training parameters.

#### Scenario: Agent starts training after validation
- **WHEN** an agent calls `lora_train_start` with a valid dataset and expected hash
- **THEN** the result includes `ok=true`, `job_id`, status `queued`, stage, dataset hash, and normalized trigger token

#### Scenario: Start rejects invalid or racing datasets
- **WHEN** backend training start rejects the dataset due to validation errors, lock conflict, or stale hash
- **THEN** the MCP result includes `ok=false`
- **AND** includes structured error details that allow the agent to inspect, prepare, or validate again

### Requirement: MCP can query LoRA training job status
The MCP server SHALL expose `lora_train_job_status` to query a specific LoRA training job by `job_id`.

#### Scenario: Agent polls running job status
- **WHEN** an agent calls `lora_train_job_status` for a running job
- **THEN** the result includes status, stage, progress, current epoch, total epochs, log tail metadata, folder, dataset hash, and timestamps

#### Scenario: Agent reads terminal job status
- **WHEN** an agent calls `lora_train_job_status` for a completed, failed, or cancelled job
- **THEN** the result includes terminal status, output path or error, registered LoRA name when available, and smoke-test fields when available

### Requirement: MCP can read LoRA training logs
The MCP server SHALL expose `lora_train_logs` to retrieve bounded logs for a LoRA training job.

#### Scenario: Agent requests recent log lines
- **WHEN** an agent calls `lora_train_logs` with a `job_id` and line limit
- **THEN** the result includes recent log lines, log path metadata, and a truncation flag

#### Scenario: Log retrieval failure does not hide job status
- **WHEN** the backend cannot read the log file for an existing job
- **THEN** the MCP result includes `ok=false` with a log-specific error
- **AND** the agent can still call `lora_train_job_status` for persistent job state

### Requirement: MCP can cancel LoRA training jobs
The MCP server SHALL expose `lora_train_cancel` to cancel queued or running LoRA training jobs.

#### Scenario: Agent cancels queued or running job
- **WHEN** an agent calls `lora_train_cancel` for a cancellable job
- **THEN** the result includes `ok=true`, `job_id`, and resulting status

#### Scenario: Agent cancels a terminal job
- **WHEN** an agent calls `lora_train_cancel` for a terminal job
- **THEN** the result includes `ok=true`
- **AND** returns the existing terminal status without changing output records

### Requirement: MCP can run LoRA smoke tests
The MCP server SHALL expose `lora_train_smoke_test` to run backend smoke tests for completed jobs with registered LoRAs.

#### Scenario: Agent smoke-tests completed registered LoRA
- **WHEN** an agent calls `lora_train_smoke_test` for a completed job with `registered_lora_name`
- **THEN** the result includes `ok=true`, LoRA job id, registered LoRA name, generation job id or generated artifact reference, and smoke-test status

#### Scenario: Smoke test preconditions are enforced
- **WHEN** an agent calls `lora_train_smoke_test` for a job that is not completed or lacks a registered LoRA
- **THEN** the result includes `ok=false`
- **AND** the error identifies the unmet precondition

### Requirement: MCP can assess LoRA dataset caption suitability
The MCP server SHALL expose `lora_dataset_caption_assess` so an agent can request the backend dataset caption suitability assessment directly. The tool result SHALL remain structured JSON and SHALL treat `not_suitable` as a successful assessment result, not as a transport error.

#### Scenario: Agent assesses caption suitability
- **WHEN** an agent calls `lora_dataset_caption_assess` with a dataset folder and optional trigger token
- **THEN** the result includes `ok=true`, the tool name, caption coverage counts, trigger-token coverage when available, common tags, rare tags, coherence metrics, warnings, recommendations, verdict, and reasons

#### Scenario: Backend assessment errors stay structured
- **WHEN** the backend rejects the assessment request because the folder is invalid or missing
- **THEN** the MCP result includes `ok=false`
- **AND** includes `error.code`, `error.message`, and structured backend details when available

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

### Requirement: MCP can curate LoRA dataset captions safely
The MCP server SHALL expose dataset curation tools for dry-run, apply, and rollback while preserving the structured JSON result contract.

#### Scenario: Agent dry-runs curation
- **WHEN** an agent calls the curation tool in dry-run mode
- **THEN** the result includes proposed per-file caption changes, blocked manual edits, outlier flags, dataset hash, profile hash, and summary counts
- **AND** no caption files are modified

#### Scenario: Agent applies reviewed curation
- **WHEN** an agent calls the curation tool in apply mode with matching expected hashes
- **THEN** the result includes backup id, changed files, skipped files, manually overwritten files, and updated dataset hash

#### Scenario: Agent rolls back curation
- **WHEN** an agent calls the curation tool with a rollback backup id
- **THEN** the result includes restored files and restored dataset hash

#### Scenario: Manual overwrite protection is visible to the agent
- **WHEN** curation would change manual captions without explicit approval
- **THEN** the result reports review-required or blocked edits structurally
- **AND** the MCP server does not treat the blocked edits as a transport error when the backend request succeeds

### Requirement: MCP can run LoRA training decision preflight
The MCP server SHALL expose `lora_training_decision_preflight` so an agent can request the backend training decision without starting training.

#### Scenario: Agent receives train decision
- **WHEN** an agent calls `lora_training_decision_preflight` for a ready dataset
- **THEN** the result includes `ok=true`, decision `train`, reasons, dataset hash, profile hash, suggested parameters, and next actions

#### Scenario: Agent receives review or do not train decision
- **WHEN** an agent calls `lora_training_decision_preflight` for a dataset with warnings or blocking issues
- **THEN** the result includes `ok=true`, decision `needs_review` or `do_not_train`, reasons, blocking issues when present, and recommended next actions

#### Scenario: Decision preflight does not call training start
- **WHEN** an agent calls `lora_training_decision_preflight`
- **THEN** the MCP server does not call `lora_train_start`
- **AND** no backend LoRA training job is enqueued

