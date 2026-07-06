## ADDED Requirements

### Requirement: Dataset curation plans preview caption changes
The backend SHALL provide a deterministic dataset curation plan operation that previews caption edits before any file is modified.

#### Scenario: Dry-run curation writes no captions
- **WHEN** a client requests a curation dry-run for a dataset
- **THEN** no caption or metadata files are modified
- **AND** the response includes dataset hash, profile hash, per-file proposed changes, reasons, blocked edits, outlier flags, and summary counts

#### Scenario: Curation plan normalizes trigger and tag policy
- **WHEN** metadata or request policy specifies a trigger token, protected tags, or removable tags
- **THEN** the curation plan proposes trigger normalization and removable tag cleanup
- **AND** protected tags are preserved in proposed captions

#### Scenario: Curation flags outliers without deleting files
- **WHEN** an image/caption pair has unusually low shared-tag overlap or missing trigger coverage
- **THEN** the curation plan flags the pair for review
- **AND** the backend does not delete or move the image

### Requirement: Dataset curation applies with backup and rollback
The backend SHALL apply reviewed curation plans only with conflict checks and restorable backups.

#### Scenario: Apply creates backup before caption writes
- **WHEN** a client applies a curation plan with matching expected dataset and profile hashes
- **THEN** the backend creates a backup before modifying captions
- **AND** the response includes backup id, changed files, skipped files, dataset hash before changes, and dataset hash after changes

#### Scenario: Stale curation apply is rejected
- **WHEN** captions or metadata changed after the curation plan was produced
- **THEN** the backend rejects apply with a conflict-style failure
- **AND** the response includes current dataset hash or profile hash values

#### Scenario: Rollback restores a curation backup
- **WHEN** a client rolls back an applied curation backup
- **THEN** captions are restored from that backup
- **AND** the response includes restored files and the restored dataset hash

### Requirement: Manual captions are protected during curation
The backend SHALL NOT silently overwrite manual captions during curation.

#### Scenario: Manual captions are skipped by default
- **WHEN** a curation plan would change a caption identified as manual or newer than its image
- **THEN** the plan marks the edit as blocked or review-required by default
- **AND** apply does not modify that caption without explicit approval

#### Scenario: Explicit manual overwrite is reported per file
- **WHEN** a client explicitly approves overwriting selected manual captions
- **THEN** apply modifies only the approved manual caption files
- **AND** the response identifies each manually overwritten file
