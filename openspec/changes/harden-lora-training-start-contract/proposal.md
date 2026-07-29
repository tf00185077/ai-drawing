## Why

The agent-facing LoRA training start path is not fail-closed: preflight can suggest `batch_size` but MCP cannot submit it, unknown backend fields are silently ignored, approval hashes are optional or incomplete, and training start does not share the dataset API's root-contained resolver or perform its final validation while holding the dataset lock. These gaps can silently fall back to expensive defaults or enqueue work against a dataset other than the one the user approved.

**Execution order:** 1/4

**Previous batch:** None

**Next batch:** `make-lora-training-recipe-explicit`

## What Changes

- **BREAKING** Require every public LoRA training start request to carry the preflight-approved `expected_dataset_hash` and `expected_profile_hash`, and reject missing or stale approval hashes before a durable job is created.
- Add `batch_size` to `lora_train_start` and add an automated parity assertion between MCP Start fields, backend Start fields, and preflight suggested fields.
- **BREAKING** Configure LoRA Start request validation to reject unknown fields instead of ignoring misspellings.
- Preserve FastAPI/Pydantic field-level 422 validation entries in MCP structured error details.
- Make preflight suggestions carry both approval hashes and refuse to present a ready-to-start checkpoint/model-family pairing when the configured training family conflicts with the dataset profile.
- Make Training Start use the same root-contained dataset resolver as discovery, inspection, preparation, and validation.
- Acquire the per-dataset training lock before the final profile-hash check, dataset validation, and dataset-hash check, and keep the lock through subprocess execution.
- Remove the legacy `trigger_check()` auto-enqueue side effect so discovery never bypasses the explicit preflight, approval, and Start contract.
- Adapt the bundled LoRA training page to run decision preflight and submit its two hashes before calling the now-strict Start endpoint, without redesigning the page.
- Add regression tests for MCP/backend/preflight parity, unknown fields, structured 422 propagation, absolute/traversal/symlink paths, stale hashes, and lock-before-final-validation ordering.
- Update the LoRA training handoff runbook and progress record to reflect the required two-hash approval contract.
- Keep full trainable-scope, bucket/cache, optimizer/scheduler/seed/save-cadence recipe controls out of this batch; they will be specified in the next OpenSpec change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lora-training-mcp-tools`: Make MCP Start faithfully expose the backend-supported start contract and preserve field-level backend validation failures.
- `lora-training-workflow`: Make Start fail closed on unknown fields, approved dataset/profile versions, model-family conflicts, unsafe dataset paths, and validation races.
- `lora-training-agent-handoff-runbook`: Require agents to submit the exact dataset and profile hashes shown in the user-approved pre-start report.

## Impact

- Backend request/schema, API, dataset resolver/locking, training decision, and trainer enqueue code under `backend/app/`.
- MCP LoRA tool signature and backend-error normalization under `mcp-server/mcp_server/tools/lora_train.py`.
- Backend and MCP contract, workflow, path-safety, and handoff tests.
- The existing LoRA training page and its TypeScript request/decision types; broader frontend feature parity remains out of scope.
- `docs/lora-training-agent-handoff-runbook.md` and `docs/PROGRESS.md`.
- Existing callers that start training without both approval hashes or that send unknown fields will receive structured validation failures and must run preflight first.
