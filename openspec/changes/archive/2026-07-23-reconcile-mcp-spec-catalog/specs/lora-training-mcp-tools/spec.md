## REMOVED Requirements

### Requirement: MCP can prepare LoRA datasets
**Reason**: The MCP surface was intentionally trimmed to the decision-and-train loop; dataset
preparation stays on the backend HTTP API and was never re-implemented as an MCP tool.
**Migration**: Call the backend endpoint `POST /api/lora-train/datasets/prepare` (and
`POST /api/lora-train/datasets/restore` for backup restore) directly.

### Requirement: MCP can validate LoRA datasets before training
**Reason**: Dataset validation is available through the backend HTTP API and the decision preflight;
it is not a standalone MCP tool.
**Migration**: Call `POST /api/lora-train/datasets/validate`, or use the `lora_training_decision_preflight`
MCP tool which runs backend validation as part of its decision.

### Requirement: MCP can assess LoRA dataset caption suitability
**Reason**: Caption suitability assessment stays on the backend HTTP API; no `lora_dataset_caption_assess`
MCP tool exists.
**Migration**: Call `POST /api/lora-train/datasets/caption-assessment` directly.

### Requirement: MCP can manage LoRA dataset metadata profiles
**Reason**: Dataset metadata profile read/validate/update stays on the backend HTTP API; the
`lora_dataset_metadata_get` / `lora_dataset_metadata_validate` / `lora_dataset_metadata_update` MCP tools
were never implemented.
**Migration**: Use the backend metadata endpoints under
`GET|PUT /api/lora-train/datasets/{folder}/metadata` and
`POST /api/lora-train/datasets/{folder}/metadata/validate`.

### Requirement: MCP can provide agent-ready dataset inspection
**Reason**: Consolidated into the `lora_dataset_inspect` MCP tool, which composes the backend
agent-inspection endpoint (profile summary, caption suitability, dataset/profile hashes) under a single
name. A separate `lora_dataset_agent_inspect` tool is redundant.
**Migration**: Call the `lora_dataset_inspect` MCP tool (backed by
`GET /api/lora-train/datasets/{folder}/agent-inspect`).

### Requirement: MCP can curate LoRA dataset captions safely
**Reason**: Deterministic dataset curation (dry-run/apply/rollback) stays on the backend HTTP API; no
curation MCP tool exists.
**Migration**: Call `POST /api/lora-train/datasets/curate` directly for plan/apply/rollback.
