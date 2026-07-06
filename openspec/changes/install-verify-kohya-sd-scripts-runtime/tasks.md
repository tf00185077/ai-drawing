## 1. Runtime Installation and Configuration

- [ ] 1.1 Install or select a local Kohya `sd-scripts` checkout outside committed source control.
- [ ] 1.2 Create or select a compatible training Python environment with `accelerate` available to the backend trainer command path.
- [ ] 1.3 Configure local `.env` values for `SD_SCRIPTS_PATH`, optional `SD_SCRIPTS_PYTHON`, `COMFYUI_LORA_DIR`, and the checkpoint used for bounded verification.
- [ ] 1.4 Verify required runtime files exist: `train_network.py`, `sdxl_train_network.py`, and `finetune/tag_images_by_wd14_tagger.py`.

## 2. Bounded LoRA Runtime Verification

- [ ] 2.1 Prepare a small local LoRA dataset that is safe to train and is not committed as a new large artifact.
- [ ] 2.2 Run the existing dataset workflow through backend APIs or MCP tools: inspect, dry-run prepare, apply prepare, and validate.
- [ ] 2.3 Start one bounded training job with minimal safe parameters and capture the returned durable `job_id`.
- [ ] 2.4 Poll job status and logs until the real Kohya subprocess reaches a terminal state.
- [ ] 2.5 Confirm a successful job records `output_path`, registers a `.safetensors` into `COMFYUI_LORA_DIR`, and records `registered_lora_name`.
- [ ] 2.6 Run the LoRA smoke-test operation for the completed registered job and record the generation job id or structured smoke-test error.

## 3. Evidence and Cleanup

- [ ] 3.1 Document the runtime preflight commands, bounded training command/API sequence, job id, log path, and smoke-test result.
- [ ] 3.2 Verify generated models, logs, virtual environments, and local path configuration are not accidentally staged for commit.
- [ ] 3.3 Run `openspec validate install-verify-kohya-sd-scripts-runtime --strict` after recording evidence.
