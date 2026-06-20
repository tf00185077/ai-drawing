## ADDED Requirements

### Requirement: Presets can be authored from supplied fields

The system SHALL provide a create operation that writes a new style preset from supplied fields: the machine recipe under the per-preset detail layer and a human note, then refreshes the index so the preset is listable. `id` and `name` SHALL be required.

#### Scenario: Create writes both layers and indexes

- **WHEN** a client creates a preset with an `id`, `name`, and recipe fields
- **THEN** the system writes the machine recipe as the preset's detail file
- **AND** writes a human note whose frontmatter `preset_id` equals the `id`
- **AND** the new preset appears in a subsequent listing

#### Scenario: Created preset passes note validation

- **WHEN** a preset is created with its note
- **THEN** validation finds the note present with matching frontmatter `preset_id` (no `note_path` / `note_preset_id` diagnostics for that preset)

### Requirement: Create does not clobber an existing preset by default

The create operation SHALL refuse to overwrite an existing preset of the same `id` unless an explicit overwrite flag is set.

#### Scenario: Duplicate id is rejected

- **WHEN** a client creates a preset whose `id` already has a detail file and overwrite is not set
- **THEN** the system rejects the request and does not modify the existing files

#### Scenario: Overwrite replaces when explicitly requested

- **WHEN** a client creates a preset with an existing `id` and overwrite is set
- **THEN** the system replaces the recipe and reindexes

### Requirement: Create reports referenced-resource validity without blocking

The create operation SHALL return the created preset's resource validation result, reporting missing referenced resources as data rather than refusing creation.

#### Scenario: Missing resource is reported, not blocking

- **WHEN** a preset references a checkpoint or LoRA that is not installed
- **THEN** the preset is still created
- **AND** the response reports the missing resource so the caller can fix it later
