## ADDED Requirements

### Requirement: Presets support an ordered multi-LoRA list

A style preset SHALL be able to declare an ordered `loras` list (each `{name, strength_model, strength_clip?}`) in addition to the single `lora`/`lora_strength` field. Composition SHALL emit the list as `generation.loras` so it flows to generation, and creation SHALL accept it.

#### Scenario: Compose carries the multi-LoRA list

- **WHEN** a preset with a `loras` list is composed
- **THEN** the resulting `generation` payload includes that `loras` list
- **AND** the single-LoRA path still works for presets that use only `lora`

#### Scenario: Created preset persists its loras

- **WHEN** a preset is created with a `loras` list
- **THEN** the stored recipe records the list and it appears when the preset is fetched
