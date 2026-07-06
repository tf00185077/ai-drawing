## MODIFIED Requirements

### Requirement: LoRA resources are exposed consistently
The MCP server SHALL expose LoRA resources, LoRA payload fields, and supported LoRA input-schema fields consistently across resource, style preset, generation, and training tools.

#### Scenario: Agent lists available LoRAs
- **WHEN** an agent calls `list_available_resources`
- **THEN** the result includes `loras` as a list
- **AND** each item corresponds to an installed or indexed LoRA resource known to the backend

#### Scenario: Agent composes a style preset with LoRA fields
- **WHEN** a style preset includes a single LoRA or ordered multi-LoRA entries
- **THEN** `get_style_preset` and `compose_style_preset` preserve those fields in the machine-readable payload
- **AND** the payload can be passed to generation tools without silently dropping LoRA entries

#### Scenario: Agent forwards LoRA generation payloads
- **WHEN** an agent calls a generation or custom workflow tool with LoRA or multi-LoRA parameters
- **THEN** the MCP server forwards the supported LoRA fields to the backend
- **AND** unsupported fields return a structured validation error rather than being silently ignored

#### Scenario: Supported tools expose LoRA input-schema fields
- **WHEN** an agent inspects the MCP tool catalog for `generate_image`, `generate_image_custom_workflow`, `generate_video_custom_workflow`, or `create_style_preset`
- **THEN** each tool's input schema exposes the ordered `loras` field
- **AND** the generation tools also expose the backward-compatible single `lora` and `lora_strength` fields
