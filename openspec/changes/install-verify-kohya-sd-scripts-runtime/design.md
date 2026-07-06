## Context

`add-lora-training-mcp-workflow` implements the backend and MCP control plane for LoRA dataset preparation, durable training jobs, registration, logs, cancellation, and smoke testing. Local verification on 2026-07-06 showed that dataset list, inspect, dry-run prepare, apply prepare, and validate work, but `POST /api/lora-train/start` correctly stops before queueing because `SD_SCRIPTS_PATH=./sd-scripts` resolves to a missing runtime directory.

The missing pieces are external to this repo: a Kohya `sd-scripts` checkout, a compatible Python/accelerate environment, WD Tagger dependencies, usable model/checkpoint paths, and a ComfyUI LoRA target directory. These files can be large and machine-specific, so they must be installed/configured locally and not committed.

## Goals / Non-Goals

**Goals:**

- Configure this machine with a working Kohya `sd-scripts` runtime for the existing trainer.
- Verify that the configured runtime exposes `train_network.py`, `sdxl_train_network.py`, and `finetune/tag_images_by_wd14_tagger.py`.
- Run one bounded small-dataset LoRA training verification through the existing backend/MCP workflow.
- Confirm the produced `.safetensors` is registered into the configured ComfyUI LoRA directory.
- Submit one smoke-test generation through the existing backend smoke-test endpoint or MCP tool.
- Document runtime settings and verification evidence without committing generated models or secrets.

**Non-Goals:**

- Changing the backend/MCP LoRA workflow API contract.
- Vendoring Kohya `sd-scripts` or model weights into this repository.
- Running long, high-quality production training.
- Replacing WD Tagger, Kohya, or ComfyUI.

## Decisions

### Keep runtime dependencies outside git

Install or reference Kohya `sd-scripts` in a local path and configure `.env` with `SD_SCRIPTS_PATH`. Do not commit the external checkout, virtual environment, model weights, generated LoRA files, or local secrets.

Alternatives considered:

- Vendor `sd-scripts` into the repo: easier discovery, but too large and couples this project to an external training engine.
- Mock the training process: useful for unit tests, but does not satisfy runtime verification.
- Local external install: keeps the repo clean while proving the real integration.

### Verify both SD1.x and SDXL entrypoints

The runtime preflight must check for both `train_network.py` and `sdxl_train_network.py`, even if the bounded smoke run uses only one model family. The backend chooses between those scripts via `lora_sdxl`.

### Run bounded verification

Use a small dataset and conservative parameters such as one epoch, low resolution, low network dimension, and batch size one. This verifies wiring and output lifecycle without claiming model quality.

### Use existing APIs and MCP tools

The runtime check should call the implemented backend endpoints and MCP tools rather than bypassing them with direct subprocess commands. Direct commands are acceptable only as preflight diagnostics for the external runtime.

## Risks / Trade-offs

- Large dependency install can be slow or machine-specific -> Keep it in a separate follow-up change and document exact local paths.
- Training may fail due to missing GPU, incompatible Torch, or model path issues -> Capture backend job logs and structured status without changing the implemented workflow.
- Smoke test may fail because ComfyUI is not running or lacks the checkpoint -> Record this as a runtime blocker distinct from successful training/register output.
- Generated model files can pollute git status -> Keep outputs under ignored local paths and verify before committing.

## Migration Plan

1. Install or select a local Kohya `sd-scripts` checkout and compatible Python environment.
2. Update local `.env` values for `SD_SCRIPTS_PATH`, optional `SD_SCRIPTS_PYTHON`, checkpoint path, and `COMFYUI_LORA_DIR`.
3. Run preflight checks for required scripts and Python/accelerate availability.
4. Run the bounded backend/MCP LoRA workflow verification on a small dataset.
5. Preserve command output and job/log evidence in docs or OpenSpec task notes without committing generated artifacts.
6. Roll back by restoring previous local `.env` values and deleting local runtime/generated files.

## Open Questions

- Which local checkpoint should be used for the bounded runtime verification?
- Should the runtime use GPU acceleration or CPU-only mode for the verification run?
- Which ComfyUI instance/path should receive the registered LoRA on this machine?
