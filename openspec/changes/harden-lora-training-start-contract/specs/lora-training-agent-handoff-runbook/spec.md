## MODIFIED Requirements

### Requirement: Agent training execution follows monitor register smoke-test sequence
The LoRA training handoff runbook SHALL define the explicit agent sequence for starting, monitoring, registering, and smoke-testing a user-approved LoRA training run. Start SHALL submit the exact dataset and profile hashes shown in the approved pre-start report.

#### Scenario: Approved training run is started with exact expected hashes
- **WHEN** the user approves training for a specific dataset, profile, LoRA target, and parameter set
- **THEN** the agent calls `lora_train_start` with selected parameters, `expected_dataset_hash`, and `expected_profile_hash` from that report
- **AND** includes `batch_size` when it was selected or suggested

#### Scenario: Approval evidence is incomplete
- **WHEN** the approved pre-start report lacks a dataset hash or profile hash
- **THEN** the agent does not call `lora_train_start`
- **AND** reruns inspection and decision preflight before requesting approval again

#### Scenario: Running job is monitored with status and logs
- **WHEN** a training job is queued or running
- **THEN** the agent polls job status and reads bounded logs using existing LoRA MCP tools
- **AND** the agent reports failed, cancelled, or stalled states with actionable next steps

#### Scenario: Completed job is smoke-tested
- **WHEN** a training job completes and registers a LoRA output
- **THEN** the agent requests a smoke test through the existing LoRA smoke-test tool
- **AND** smoke-test failure is reported separately from training completion

## ADDED Requirements

### Requirement: Agent treats Start validation failures as approval invalidation
The handoff runbook SHALL instruct agents to stop rather than repair-and-retry automatically when Start reports a stale hash, family mismatch, unsafe dataset path, or missing approval field.

#### Scenario: Start reports stale approval hash
- **WHEN** `lora_train_start` returns `dataset_hash_mismatch` or `profile_hash_mismatch`
- **THEN** the agent reruns inspection and decision preflight
- **AND** emits a new pre-start report and waits for a new explicit user approval

#### Scenario: Start reports missing field or family mismatch
- **WHEN** `lora_train_start` returns field-level 422 validation or `model_family_mismatch`
- **THEN** the agent reports the exact structured field/error details
- **AND** does not retry with an implicit backend default
