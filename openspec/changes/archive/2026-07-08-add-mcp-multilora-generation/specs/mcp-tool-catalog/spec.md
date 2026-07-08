## ADDED Requirements

### Requirement: MCP image generation accepts ordered multi-LoRA payloads
The MCP image generation tool SHALL expose an optional `loras` field containing ordered LoRA descriptors and SHALL forward it to the backend generation request without dropping or flattening it.

#### Scenario: Compose style preset payload can be submitted unchanged
- **GIVEN** `compose_style_preset` returns a generation payload containing `loras`
- **WHEN** an agent submits that payload through MCP `generate_image`
- **THEN** the backend receives the same ordered `loras` array
- **AND** legacy `lora`/`lora_strength` compatibility fields are not required to represent multiple LoRAs

#### Scenario: Distinct multi-LoRA workflow nodes are preserved
- **GIVEN** a multi-LoRA template has separate LoRA loader nodes
- **WHEN** a generation request supplies ordered LoRAs with different names and strengths
- **THEN** the submitted ComfyUI workflow uses the corresponding distinct LoRA name and strength per node
- **AND** it MUST NOT overwrite every LoRA loader with the first or legacy single LoRA.

### Requirement: MCP cancel job works through backend client
The MCP cancel job tool SHALL call the backend cancel/delete endpoint through a supported HTTP client method.

#### Scenario: Cancel pending job
- **GIVEN** a queued/pending generation job id
- **WHEN** the agent calls MCP `cancel_job`
- **THEN** the call returns a successful cancellation response or a structured backend error
- **AND** it MUST NOT fail because the HTTP client lacks a `delete` method.
