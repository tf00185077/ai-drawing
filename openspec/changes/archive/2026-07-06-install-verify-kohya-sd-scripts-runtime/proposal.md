## Why

The LoRA training MCP workflow can be locally verified through dataset preparation and backend preflight, but this machine does not have Kohya `sd-scripts` installed at the configured `SD_SCRIPTS_PATH`. A separate runtime change is needed so the external training dependency can be installed/configured and the full train/register/smoke happy path can be verified without pretending that a real training run occurred.

## What Changes

- Install or point the project at a working Kohya `sd-scripts` checkout that contains `train_network.py`, `sdxl_train_network.py`, `anima_train_network.py`, and the WD Tagger script used by the watcher.
- Configure the runtime Python/accelerate environment needed by Kohya without committing secrets, generated models, or large external dependency trees to this repo.
- Run a bounded small-dataset LoRA training verification with an Anima checkpoint through the backend/MCP workflow: inspect, prepare dry-run, prepare apply, validate, start with `model_family=anima`, poll status/logs, register the produced `.safetensors`, and run a generation smoke test.
- Document the machine-local setup and verification evidence so future agents can distinguish implemented control-plane behavior from external runtime readiness.

## Capabilities

### New Capabilities

- `kohya-sd-scripts-runtime`: Machine-local Kohya sd-scripts installation/configuration and full LoRA training runtime verification.

### Modified Capabilities

- None.

## Impact

- Affected runtime dependencies: Kohya `sd-scripts`, `accelerate`, training Python environment, WD Tagger dependencies, and local model/checkpoint paths.
- Affected configuration: `SD_SCRIPTS_PATH`, optional `SD_SCRIPTS_PYTHON`, `COMFYUI_LORA_DIR`, checkpoint settings, and local `.env` values.
- Affected verification: full LoRA training happy-path runtime check using backend APIs and MCP tools with explicit trainer family selection.
- Affected API/MCP contract: `lora_train_start` accepts an explicit `model_family` selector so Anima checkpoints route to `anima_train_network.py` instead of SD1.x/SDXL trainers.
