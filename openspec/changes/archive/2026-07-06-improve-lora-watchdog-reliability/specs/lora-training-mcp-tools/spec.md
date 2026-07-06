## ADDED Requirements

### Requirement: MCP can assess LoRA dataset caption suitability
The MCP server SHALL expose `lora_dataset_caption_assess` so an agent can request the backend dataset caption suitability assessment directly. The tool result SHALL remain structured JSON and SHALL treat `not_suitable` as a successful assessment result, not as a transport error.

#### Scenario: Agent assesses caption suitability
- **WHEN** an agent calls `lora_dataset_caption_assess` with a dataset folder and optional trigger token
- **THEN** the result includes `ok=true`, the tool name, caption coverage counts, trigger-token coverage when available, common tags, rare tags, coherence metrics, warnings, recommendations, verdict, and reasons

#### Scenario: Backend assessment errors stay structured
- **WHEN** the backend rejects the assessment request because the folder is invalid or missing
- **THEN** the MCP result includes `ok=false`
- **AND** includes `error.code`, `error.message`, and structured backend details when available
