## MODIFIED Requirements

### Requirement: Registered LoRAs can be smoke-tested through generation
The backend SHALL provide a smoke test operation for a completed LoRA training job that submits a
generation using the registered LoRA and records the generation result through the existing
generation/recording path. The submitted generation SHALL match the trained model family: for
`model_family=anima` the backend SHALL build a diffusion-model-family request (Anima template with
`diffusion_model`, `text_encoder`, and `vae` components derived from the durable job params) rather
than a checkpoint-only request, and SHALL allow those components to be overridden per request.

#### Scenario: Smoke test starts generation for a registered LoRA
- **WHEN** a client requests a smoke test for a completed job with a registered LoRA
- **THEN** the backend submits a generation request using that LoRA and the normalized trigger token
- **AND** returns the generation job id or recorded artifact reference

#### Scenario: Anima smoke test uses diffusion-model components
- **WHEN** a smoke test is requested for a completed job whose params record `model_family=anima`
- **THEN** the backend submits an Anima generation using the diffusion model, text encoder, and VAE
  derived from the job params (or from per-request overrides when provided)
- **AND** does not submit a checkpoint-only request for that job

#### Scenario: Non-Anima smoke test keeps the checkpoint shape
- **WHEN** a smoke test is requested for a completed job whose family is `sd15` or `sdxl`
- **THEN** the backend submits a checkpoint-based generation using the registered LoRA as before

#### Scenario: Smoke test failure is attached to the LoRA job
- **WHEN** smoke test generation fails or cannot be submitted
- **THEN** the LoRA job remains completed if training and registration succeeded
- **AND** the smoke test error is recorded separately on the job status
