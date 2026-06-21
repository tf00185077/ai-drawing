## ADDED Requirements

### Requirement: Multiple LoRAs fill loader nodes positionally

Parameter injection SHALL accept an ordered `loras` list (each `{name, strength_model, strength_clip?}`) and apply the i-th entry to the i-th `LoraLoader` / `LoraLoaderModelOnly` node in workflow-JSON order. `strength_clip` SHALL default to `strength_model`, and `LoraLoaderModelOnly` (model-only) SHALL ignore clip strength. When `loras` is omitted, the existing single-`lora` behavior SHALL be unchanged. When both are provided, `loras` SHALL take precedence.

#### Scenario: Each LoRA maps to its loader in order

- **WHEN** a workflow has two LoRA loader nodes and `loras=[A, B]` is provided
- **THEN** the first loader node's `lora_name` becomes A's name and the second's becomes B's
- **AND** each node's strengths are set from its entry (clip defaulting to model strength)

#### Scenario: Single lora still applies when loras omitted

- **WHEN** `loras` is not provided but a single `lora` is
- **THEN** the single LoRA is applied as before

#### Scenario: loras takes precedence over single lora

- **WHEN** both `loras` and a single `lora` are provided
- **THEN** the loader nodes are filled from `loras` and the single `lora` is ignored

#### Scenario: Extra loras beyond available loader nodes are ignored

- **WHEN** more `loras` are provided than there are loader nodes in the workflow
- **THEN** only as many as there are loader nodes are applied, and the rest are ignored without error
