# lora-training-agent-handoff-runbook Specification

## Purpose
TBD - created by archiving change add-lora-training-agent-handoff-runbook. Update Purpose after archive.
## Requirements
### Requirement: Agent training handoff reports are standardized
The LoRA training handoff runbook SHALL require a pre-start report before an agent starts training a specific LoRA.

#### Scenario: Pre-start report summarizes training intent
- **WHEN** an agent is ready to ask the user to train a LoRA
- **THEN** the report includes dataset folder, dataset type, trigger token, model family, caption profile, caption suitability verdict, training decision, reasons, dataset hash, profile hash, selected training parameters, and known risks

#### Scenario: Training start waits for explicit user request
- **WHEN** the pre-start report is produced
- **THEN** the agent does not call `lora_train_start`
- **AND** training starts only after the user explicitly asks to train that specific LoRA

### Requirement: Agent training execution follows monitor register smoke-test sequence
The LoRA training handoff runbook SHALL define the explicit agent sequence for starting, monitoring, registering, and smoke-testing a user-approved LoRA training run.

#### Scenario: Approved training run is started with expected hashes
- **WHEN** the user approves training for a specific dataset and LoRA target
- **THEN** the agent starts training with selected parameters, expected dataset hash, and expected profile hash when available

#### Scenario: Running job is monitored with status and logs
- **WHEN** a training job is queued or running
- **THEN** the agent polls job status and reads bounded logs using existing LoRA MCP tools
- **AND** the agent reports failed, cancelled, or stalled states with actionable next steps

#### Scenario: Completed job is smoke-tested
- **WHEN** a training job completes and registers a LoRA output
- **THEN** the agent requests a smoke test through the existing LoRA smoke-test tool
- **AND** smoke-test failure is reported separately from training completion

### Requirement: Agent training terminal reports are standardized
The LoRA training handoff runbook SHALL require a terminal report for completed, failed, or cancelled training runs.

#### Scenario: Completed job report includes output and smoke test
- **WHEN** a training job completes
- **THEN** the terminal report includes job id, final status, output path, registered LoRA name, smoke-test status, generated artifact reference when available, and recommended next actions

#### Scenario: Failed or cancelled job report includes recovery context
- **WHEN** a training job fails or is cancelled
- **THEN** the terminal report includes job id, final status, error or cancellation reason, recent log summary, dataset hash, profile hash, and recommended recovery actions
