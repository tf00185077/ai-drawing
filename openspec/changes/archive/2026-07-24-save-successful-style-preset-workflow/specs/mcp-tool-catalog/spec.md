## ADDED Requirements

### Requirement: MCP exposes explicit successful-workflow save intent

The MCP server SHALL expose `save_successful_workflow_as_style_preset` as the single agent-facing intent for promoting a successfully generated image workflow into a style preset. Its documentation SHALL instruct agents not to call it automatically and to call it only after an explicit user save request.

#### Scenario: Loose source and keyword inputs are forwarded

- **WHEN** an agent supplies an image id, prefixed image/artifact/job locator, or completed job id plus string-or-list positive and negative keywords
- **THEN** the MCP tool forwards the short locator and keyword values to the backend
- **AND** it does not transfer or modify the large workflow graph

#### Scenario: Save success has a stable response

- **WHEN** the backend saves the graph
- **THEN** the MCP response is parseable JSON containing `ok=true`, `tool`, canonical preset/profile, canonical source, relative workflow path, normalized keyword arrays, and `retest_required=true`
- **AND** it does not contain the source generation's full prompts or workflow JSON

#### Scenario: Save failure is repairable

- **WHEN** the backend rejects the save request
- **THEN** MCP returns `ok=false`, the tool name, and an error object with `code`, `message`, and `hint`

### Requirement: MCP exposes verbatim saved-workflow retest intent

The MCP server SHALL expose `test_saved_style_preset_workflow` so an agent can queue the backend-owned saved graph without passing workflow JSON or prompt overrides.

#### Scenario: Retest returns queued job identity

- **WHEN** an agent calls the tool for a preset/profile with a saved graph
- **THEN** the response includes `ok=true`, the tool name, generation `job_id`, and queued status
- **AND** instructs the caller to poll `get_generation_status`

#### Scenario: Tools remain in the audited catalog

- **WHEN** the MCP server registers tools
- **THEN** both successful-workflow save and saved-workflow retest names are present in the intended tool catalog
- **AND** catalog regression tests fail if either is removed or renamed
