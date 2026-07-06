## Why

The completed watchdog reliability step makes captions safer, but agents still lack a durable dataset profile that records how a LoRA dataset is intended to be interpreted. A local `.lora-dataset.json` profile gives Hermes/OpenClaw a stable source of truth for trigger token, dataset type, caption policy, model family, and the fact that training is manual-only by default.

## What Changes

- Add a dataset-local metadata profile file named `.lora-dataset.json`.
- Define schema fields for dataset type, trigger token, caption profile, model family, protected tags, removable tags, and `auto_train=false` by default.
- Surface profile presence, validity, warnings, and profile hash through existing dataset discovery/inspection behavior without replacing the archived caption suitability assessment.
- Treat missing profiles as valid discoverable datasets with conservative defaults.
- Preserve the manual-training contract: metadata can describe a dataset, but it MUST NOT enqueue training.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `lora-training-workflow`: Add dataset metadata profile persistence and default semantics.

## Impact

- Affected backend areas: dataset discovery/inspection services, LoRA training schemas, tests around profile parsing and defaulting.
- Affected data files: `.lora-dataset.json` stored inside each dataset folder under `lora_train_dir`.
- Prerequisite: archived change `2026-07-06-improve-lora-watchdog-reliability` and current `lora-training-workflow` requirements for dataset discovery, inspection, and caption suitability assessment.
