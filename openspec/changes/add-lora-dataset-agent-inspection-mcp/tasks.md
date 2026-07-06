## 1. Backend Metadata Operations

- [ ] 1.1 Add API/schema tests for metadata get, validate, update, missing profile defaults, malformed profile errors, and stale `profile_hash` conflicts.
- [ ] 1.2 Implement backend profile get/update/validate operations using the metadata profile service from `add-lora-dataset-metadata-profiles`.
- [ ] 1.3 Add an agent inspection response that composes profile summary, profile validation, caption suitability summary, dataset hash, profile hash, and existing validation signals.

## 2. MCP Tools

- [ ] 2.1 Add MCP tests for metadata get/update/validate success and structured backend error forwarding.
- [ ] 2.2 Add MCP tests for agent inspection output with valid, missing, and invalid metadata profiles.
- [ ] 2.3 Implement `lora_dataset_metadata_get`, `lora_dataset_metadata_update`, `lora_dataset_metadata_validate`, and `lora_dataset_agent_inspect` with catalog entries.

## 3. Verification

- [ ] 3.1 Run focused backend LoRA dataset API tests and MCP LoRA tool tests.
- [ ] 3.2 Run `openspec validate add-lora-dataset-agent-inspection-mcp` and `git diff --check`.
