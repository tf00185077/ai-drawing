## ADDED Requirements

### Requirement: Dataset metadata profiles are persisted locally
The backend SHALL recognize a dataset-local `.lora-dataset.json` metadata profile for folders under `lora_train_dir`. The profile SHALL support dataset type, trigger token, caption profile, model family, protected tags, removable tags, and `auto_train`.

#### Scenario: Missing profile uses conservative defaults
- **WHEN** a dataset folder does not contain `.lora-dataset.json`
- **THEN** dataset discovery still includes the folder
- **AND** the returned profile summary uses conservative defaults including `auto_train=false`

#### Scenario: Valid profile is returned with profile hash
- **WHEN** a dataset folder contains a valid `.lora-dataset.json`
- **THEN** dataset inspection includes the normalized profile fields
- **AND** the response includes a `profile_hash` separate from the dataset image/caption hash

#### Scenario: Malformed profile is reported structurally
- **WHEN** `.lora-dataset.json` cannot be parsed or violates the profile schema
- **THEN** dataset discovery and inspection return structured profile validation errors
- **AND** image/caption discovery for the dataset remains available when the folder itself is valid

### Requirement: Dataset profiles never trigger automatic training
The backend SHALL treat `.lora-dataset.json` as descriptive dataset metadata. Profile loading, validation, discovery, or inspection SHALL NOT enqueue a LoRA training job.

#### Scenario: Auto train defaults to false
- **WHEN** a dataset profile omits `auto_train`
- **THEN** the normalized profile reports `auto_train=false`

#### Scenario: Profile inspection does not start training
- **WHEN** a client lists, inspects, or validates dataset profile metadata
- **THEN** no LoRA training job is created
- **AND** training remains available only through an explicit training start request
