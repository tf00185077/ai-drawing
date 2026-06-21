## ADDED Requirements

### Requirement: Catalog is stored as a lightweight index plus per-preset detail

The system SHALL store the style preset catalog as a lightweight `index` of entries (each with at least `id`, `name`, and available profile names) plus a separate full recipe per preset. Listing presets SHALL read only the index and SHALL NOT load full preset bodies.

#### Scenario: Listing reads only the index

- **WHEN** a client lists style presets
- **THEN** the response is built from the index entries (id, name, profiles, summary resource refs)
- **AND** full preset bodies (base/negative prompt, default params, profile bodies) are not loaded to produce the list

#### Scenario: Detail is loaded per preset on demand

- **WHEN** a client requests or composes a specific preset by id
- **THEN** only that preset's full recipe is loaded, not the whole catalog

### Requirement: Reindex rebuilds the index and the read path self-heals

The system SHALL provide a reindex operation that rebuilds the index from the per-preset detail files. If the index is missing when the catalog is read, the system SHALL rebuild it rather than failing.

#### Scenario: Reindex reflects added or edited presets

- **WHEN** a preset detail file is added or edited and reindex is run
- **THEN** the index entries match the current set of preset files

#### Scenario: Missing index self-heals on read

- **WHEN** the index is absent but preset detail files exist
- **THEN** a list request rebuilds the index from the detail files and returns the current presets

### Requirement: Validation reports index and detail drift

`validate_style_presets` SHALL report drift between the index and the per-preset detail files, in addition to the existing resource and note checks.

#### Scenario: Detail file without an index entry is reported

- **WHEN** a preset detail file exists with no corresponding index entry (or an index entry references a missing detail file)
- **THEN** validation reports the drift as data rather than silently ignoring it
