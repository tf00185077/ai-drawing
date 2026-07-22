## MODIFIED Requirements

### Requirement: MCP server exposes an audited tool catalog
The ai-drawing MCP server SHALL maintain a tested catalog of intended agent-facing tools that stays
bidirectionally aligned with the tools actually registered in code: the catalog SHALL contain no tool
that is not registered, and every registered agent-facing tool SHALL appear in the catalog or be
recorded as a documented intentional omission.

#### Scenario: Intended tools are registered
- **WHEN** the MCP server starts and registers its tools
- **THEN** every tool in the intended catalog is registered under its documented name
- **AND** missing or renamed tools fail tests before release

#### Scenario: Catalog contains no phantom tools
- **WHEN** the catalog audit runs
- **THEN** every tool named in the catalog resolves to a registered MCP tool
- **AND** a catalog entry with no corresponding registered tool fails the audit

#### Scenario: Intentional omissions are documented
- **WHEN** a backend endpoint is intentionally not exposed as an MCP tool
- **THEN** the omission is documented with a reason
- **AND** the catalog test does not treat it as an accidental missing tool
