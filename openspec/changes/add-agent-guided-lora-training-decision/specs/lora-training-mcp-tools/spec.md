## ADDED Requirements

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
