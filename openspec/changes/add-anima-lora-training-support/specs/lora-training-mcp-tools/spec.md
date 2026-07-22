## MODIFIED Requirements

### Requirement: MCP can run LoRA smoke tests
The MCP server SHALL expose `lora_train_smoke_test` to run backend smoke tests for completed jobs with
registered LoRAs. The tool SHALL accept optional Anima component overrides (`diffusion_model`,
`text_encoder`, `vae`) in addition to the existing prompt fields, all optional so that a caller may
rely on the values derived from the durable job params. The tool SHALL keep the structured JSON result
contract.

#### Scenario: Agent smoke-tests completed registered LoRA
- **WHEN** an agent calls `lora_train_smoke_test` for a completed job with `registered_lora_name`
- **THEN** the result includes `ok=true`, LoRA job id, registered LoRA name, generation job id or
  generated artifact reference, and smoke-test status

#### Scenario: Agent overrides Anima components for a smoke test
- **WHEN** an agent calls `lora_train_smoke_test` for an Anima job and supplies a `diffusion_model`,
  `text_encoder`, or `vae` override
- **THEN** the backend uses the supplied component(s) for the smoke-test generation
- **AND** derives any component not supplied from the durable job params

#### Scenario: Smoke test preconditions are enforced
- **WHEN** an agent calls `lora_train_smoke_test` for a job that is not completed or lacks a registered
  LoRA
- **THEN** the result includes `ok=false`
- **AND** the error identifies the unmet precondition
