## ADDED Requirements

### Requirement: MCP can curate LoRA dataset captions safely
The MCP server SHALL expose dataset curation tools for dry-run, apply, and rollback while preserving the structured JSON result contract.

#### Scenario: Agent dry-runs curation
- **WHEN** an agent calls the curation tool in dry-run mode
- **THEN** the result includes proposed per-file caption changes, blocked manual edits, outlier flags, dataset hash, profile hash, and summary counts
- **AND** no caption files are modified

#### Scenario: Agent applies reviewed curation
- **WHEN** an agent calls the curation tool in apply mode with matching expected hashes
- **THEN** the result includes backup id, changed files, skipped files, manually overwritten files, and updated dataset hash

#### Scenario: Agent rolls back curation
- **WHEN** an agent calls the curation tool with a rollback backup id
- **THEN** the result includes restored files and restored dataset hash

#### Scenario: Manual overwrite protection is visible to the agent
- **WHEN** curation would change manual captions without explicit approval
- **THEN** the result reports review-required or blocked edits structurally
- **AND** the MCP server does not treat the blocked edits as a transport error when the backend request succeeds
