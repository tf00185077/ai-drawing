## ADDED Requirements

### Requirement: Style preset catalog exposes named creator recipes

The system SHALL load a structured style preset catalog and expose named presets to backend clients and MCP tools. Each preset SHALL include a stable `id`, display `name`, resource references, prompt components, optional profiles, and optional human note metadata.

#### Scenario: List presets returns lightweight entries

- **WHEN** a client lists style presets
- **THEN** the response includes each preset's `id`, `name`, available profile names, and summary metadata
- **AND** the response does not require reading Obsidian or Markdown files at request time

#### Scenario: Get preset returns full recipe

- **WHEN** a client requests a known preset by `preset_id`
- **THEN** the response includes its resource references, base prompt, negative prompt, default generation parameters, profiles, and note metadata

#### Scenario: Unknown preset returns structured not found

- **WHEN** a client requests a preset id that is not in the catalog
- **THEN** the system returns a structured not-found error

### Requirement: Catalog validation checks referenced resources and notes

The system SHALL validate preset resource references against the currently available ComfyUI resources and workflow templates. The system SHALL also validate project-local note references when a preset defines `note_path`.

#### Scenario: Valid preset reports available resources and note metadata

- **WHEN** a preset references installed checkpoint, LoRA, workflow template, optional diffusion-family components, and a note whose frontmatter `preset_id` matches the catalog `id`
- **THEN** validation marks that preset as valid
- **AND** includes the checked resource names in the result

#### Scenario: Missing model is reported without hiding the preset

- **WHEN** a preset references a checkpoint, LoRA, diffusion model, text encoder, VAE, or workflow template that is not installed
- **THEN** validation marks that preset as invalid
- **AND** lists every missing resource by resource type and name
- **AND** listing presets still returns the preset so the user can repair the catalog

#### Scenario: Missing note path is reported without hiding the preset

- **WHEN** a preset defines `note_path` but that Markdown file does not exist under the project
- **THEN** validation marks that preset as invalid
- **AND** includes a diagnostic with resource type `note_path`

#### Scenario: Note frontmatter id must match catalog id

- **WHEN** a preset defines `note_path` and the Markdown frontmatter `preset_id` differs from the catalog `id`
- **THEN** validation marks that preset as invalid
- **AND** includes a diagnostic with resource type `note_preset_id`

### Requirement: Preset composition produces a generate_image-compatible payload

The system SHALL compose a style preset with a user `content_prompt` into a final generation payload that can be passed to the existing `generate_image` MCP tool and backend generation endpoint.

#### Scenario: Default profile composition

- **WHEN** a client composes preset `creator-a` with `content_prompt="a girl in a raincoat"`
- **THEN** the response includes a `generation` object containing the preset resources, default params, final `prompt`, and final `negative_prompt`
- **AND** the final `prompt` includes the preset base prompt and the user content prompt in deterministic order

#### Scenario: Named profile modifies prompt content

- **WHEN** a client composes a preset with `profile="portrait"`
- **THEN** the profile prompt prefix and suffix are merged with the preset base prompt and user content prompt
- **AND** profile-level generation params override preset-level defaults only for fields explicitly set by that profile

#### Scenario: Unknown profile returns structured error

- **WHEN** a client composes a known preset with an unknown profile name
- **THEN** the system returns a structured error that includes the available profile names

### Requirement: Presets support checkpoint and diffusion-family templates

The system SHALL support both traditional checkpoint-based presets and diffusion-model-family presets through the same composition interface.

#### Scenario: Checkpoint preset composes traditional resources

- **WHEN** a preset defines `checkpoint`, optional `lora`, `lora_strength`, and a workflow `template`
- **THEN** composition includes those fields in the `generation` payload for `generate_image`

#### Scenario: Diffusion-family preset composes component resources

- **WHEN** a preset defines `template`, `diffusion_model`, `text_encoder`, and `vae`
- **THEN** composition includes those fields in the `generation` payload for `generate_image`
- **AND** omitted diffusion component fields preserve the workflow template's embedded values

### Requirement: Preset use is optional and manual generation remains supported

The style preset catalog SHALL not replace direct manual resource selection. Callers SHALL be able to generate images by passing checkpoint, LoRA, prompt, and other parameters directly to `generate_image` without selecting a preset.

#### Scenario: User manually specifies checkpoint and LoRA

- **WHEN** a user asks to generate with an explicit checkpoint and LoRA instead of a preset
- **THEN** the agent can validate those names with available resources
- **AND** the final generation request is submitted through `generate_image` without requiring a preset id

### Requirement: MCP tools return agent-friendly JSON for preset operations

The MCP server SHALL expose preset list, detail, validation, and composition operations as stable JSON strings suitable for agent parsing.

#### Scenario: MCP compose returns next action

- **WHEN** an agent calls the preset composition MCP tool successfully
- **THEN** the returned JSON includes `ok=true`, the selected `preset_id`, the selected `profile`, the composed `generation` payload, and a `next` instruction to call `generate_image` with that payload

#### Scenario: MCP validation returns repairable diagnostics

- **WHEN** an agent calls the preset validation MCP tool
- **THEN** the returned JSON includes per-preset validity and missing-resource diagnostics
- **AND** invalid presets are represented as data rather than as an unhandled tool failure
