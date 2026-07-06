## ADDED Requirements

### Requirement: Agent training decision preflight is deterministic and non-executing
The backend SHALL provide a deterministic LoRA training decision preflight for a dataset. The preflight SHALL return `train`, `needs_review`, or `do_not_train` with reasons and SHALL NOT enqueue training.

#### Scenario: Ready dataset returns train decision
- **WHEN** metadata is valid, captions are suitable, dataset validation passes, curation has no unresolved required actions, and the dataset has enough examples
- **THEN** the preflight returns decision `train`
- **AND** the response includes dataset hash, profile hash, reasons, and suggested training parameters

#### Scenario: Reviewable issues return needs review decision
- **WHEN** the dataset has non-blocking warnings such as outliers, low-confidence caption coherence, or manual-caption curation choices awaiting approval
- **THEN** the preflight returns decision `needs_review`
- **AND** the response includes review reasons and recommended next actions

#### Scenario: Blocking issues return do not train decision
- **WHEN** the dataset has blocking issues such as missing captions, empty captions, invalid metadata, stale hashes, or too few trainable examples
- **THEN** the preflight returns decision `do_not_train`
- **AND** the response includes blocking issues and recovery actions

#### Scenario: Preflight does not enqueue training
- **WHEN** a client requests training decision preflight
- **THEN** no LoRA training job is created
- **AND** the existing explicit training start operation remains the only backend training trigger

### Requirement: Training decision suggests parameters without submitting them
The backend SHALL include suggested training parameters in a `train` or `needs_review` decision when enough metadata is available. Suggested parameters SHALL be advisory and SHALL NOT be persisted as a queued job.

#### Scenario: Suggested parameters are returned with rationale
- **WHEN** model family, dataset type, caption profile, and image count are available
- **THEN** the preflight response includes suggested parameters and rationale fields

#### Scenario: Suggested parameters do not bypass validation
- **WHEN** a client later starts training using suggested parameters
- **THEN** the backend still validates the dataset and expected hashes through the existing training start path
