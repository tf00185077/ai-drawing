## Why

LoRA dataset caption generation currently depends on a create-only watchdog event and runs the WD tagger without proving image files are fully written or that captions actually need regeneration. Agents also need a deterministic way to judge caption suitability before asking Hermes to train, because image/caption counts alone do not show whether tags are coherent enough to produce a useful LoRA.

## What Changes

- Harden the dataset watchdog so it reacts to created, moved, and modified image events, waits for stable image files, and only invokes WD Tagger when a folder has missing or stale captions.
- Preserve newer or manually edited `.txt` files by default; a caption file newer than its image is treated as current.
- Detect unreadable or corrupt image files and surface structured watchdog status under the dataset folder instead of crashing or retrying indefinitely.
- Add a backend caption suitability assessment for one dataset folder with counts, trigger-token coverage, tag frequency, rare tags, dispersion/coherence metrics, warnings, recommendations, and a verdict.
- Expose the assessment to agents through MCP if feasible while keeping all suitability logic deterministic and local.
- Explicitly do not add automatic LoRA training or new training triggers in this change.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `lora-training-workflow`: Watchdog caption generation reliability and backend dataset caption suitability assessment.
- `lora-training-mcp-tools`: Agent-facing MCP access to dataset caption suitability assessment.

## Impact

- Affected backend modules: `backend/app/services/watcher.py`, `backend/app/services/lora_dataset.py` or a new assessment service, `backend/app/schemas/lora_train.py`, `backend/app/api/lora_train.py`, and focused backend tests.
- Affected MCP modules: `mcp-server/mcp_server/tools/lora_train.py`, `mcp-server/mcp_server/tool_catalog.py`, and MCP tests if the assessment tool is added.
- Runtime behavior remains manual-training-first: no automatic training is added, and existing training APIs continue to require explicit calls.
