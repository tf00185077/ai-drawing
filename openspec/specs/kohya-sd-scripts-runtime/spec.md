# kohya-sd-scripts-runtime Specification

## Purpose
TBD - created by archiving change install-verify-kohya-sd-scripts-runtime. Update Purpose after archive.
## Requirements
### Requirement: Kohya sd-scripts runtime is configured locally
The project runtime SHALL be configured with a local Kohya `sd-scripts` checkout and training Python environment that the existing backend trainer can invoke.

#### Scenario: Required Kohya scripts are present
- **WHEN** the runtime preflight resolves `SD_SCRIPTS_PATH`
- **THEN** that path contains `train_network.py`
- **AND** it contains `sdxl_train_network.py`
- **AND** it contains `anima_train_network.py`
- **AND** it contains `anima_train.py`
- **AND** it contains `library/anima_train_utils.py`
- **AND** it contains `finetune/tag_images_by_wd14_tagger.py`

#### Scenario: Training launcher is available
- **WHEN** the runtime preflight resolves the configured training Python environment
- **THEN** `accelerate launch` can be invoked by the backend trainer command path
- **AND** the check does not require committing the external virtual environment to this repository

### Requirement: Runtime configuration remains local and non-secret
The project SHALL keep machine-local runtime values and generated model artifacts out of committed source control.

#### Scenario: Local configuration uses environment values
- **WHEN** Kohya and ComfyUI runtime paths are configured
- **THEN** they are loaded from local environment values such as `.env`
- **AND** committed examples contain placeholders rather than machine-specific secrets or model paths

#### Scenario: Generated training artifacts are not committed
- **WHEN** the runtime verification creates logs, checkpoints, LoRA outputs, or temporary files
- **THEN** those artifacts remain in ignored local paths or are removed before commit

### Requirement: Full LoRA training happy path is verified against real runtime
The project SHALL verify the implemented LoRA workflow against a real bounded Kohya training run instead of a mocked completion.

#### Scenario: Anima model routes through Anima trainer
- **WHEN** `lora_train_start` is called with `model_family=anima`
- **THEN** the backend validates `anima_train_network.py` under `SD_SCRIPTS_PATH`
- **AND** the backend validates a configured or request-provided Qwen3 text encoder path before creating a durable job
- **AND** the durable job params record `model_family=anima`
- **AND** the durable job params record `trainer_script=anima_train_network.py`
- **AND** the durable job params record the resolved `network_module`
- **AND** the default resolved `network_module` is `networks.lora_anima` unless the request explicitly provides a different `network_module`
- **AND** the durable job params record the resolved Anima Qwen3 path and any resolved Anima VAE or T5 tokenizer path
- **AND** the launched command includes `--qwen3` and includes `--vae` when an Anima VAE path is configured or provided
- **AND** the launched command includes `--network_module networks.lora_anima` unless the request explicitly provides a different `network_module`
- **AND** the backend does not launch `train_network.py` or `sdxl_train_network.py` for that job

#### Scenario: Unsupported trainer family is rejected
- **WHEN** `lora_train_start` is called with a `model_family` outside `sd15`, `sdxl`, or `anima`
- **THEN** the backend returns a structured `unsupported_model_family` error
- **AND** it does not create or queue a durable training job

#### Scenario: Small dataset trains through backend workflow
- **WHEN** a small LoRA dataset is inspected, prepared with dry-run, applied, and validated through the backend or MCP workflow
- **THEN** `lora_train_start` can queue a durable Anima job with `model_family=anima`
- **AND** polling status and logs shows the job moving through training stages
- **AND** the job reaches a terminal status based on the real Kohya subprocess result

#### Scenario: Successful output registers with ComfyUI
- **WHEN** the bounded training job completes and produces a `.safetensors` output
- **THEN** the backend registers the output into the configured ComfyUI LoRA directory
- **AND** the durable job status records `output_path` and `registered_lora_name`

#### Scenario: Registered LoRA smoke test is submitted
- **WHEN** a completed job has `registered_lora_name`
- **THEN** the smoke-test operation submits a generation using that LoRA and the normalized trigger token
- **AND** the durable job status records the smoke-test generation job id or a structured smoke-test error

### Requirement: Model file paths resolve flexibly across model directories
The backend SHALL resolve every training model-file input — the `checkpoint` (Anima diffusion model or
SD/SDXL checkpoint) and the Anima `qwen3`, `vae`, and `t5_tokenizer` paths — through a single resolver
that accepts three input forms without forcing the caller to pre-compute absolute paths: an absolute or
separator-bearing path, a bare filename, or a remote/HuggingFace id. The resolver SHALL search a
model-family-aware list of directories for bare filenames and SHALL reuse the existing
generation-side configuration rather than introducing parallel settings.

#### Scenario: Absolute path is used as given
- **WHEN** a model-file input contains a path separator, a Windows drive letter, or a leading `/`
- **THEN** the resolver returns the resolved absolute path unchanged
- **AND** does not prepend any search directory

#### Scenario: Bare filename resolves by searching family-aware directories
- **WHEN** a model-file input is a bare filename with no path separator
- **THEN** the resolver searches each configured directory in order and returns the first directory in
  which the file exists
- **AND** for an Anima `checkpoint` the search order includes `LORA_CHECKPOINT_DIRS` followed by
  `COMFYUI_DIFFUSION_MODELS_DIR`
- **AND** for an SD/SDXL `checkpoint` the search order includes `LORA_CHECKPOINT_DIRS` followed by
  `COMFYUI_CHECKPOINTS_DIR`
- **AND** for an Anima `qwen3` the search includes `COMFYUI_TEXT_ENCODERS_DIR`, for `vae`
  `COMFYUI_VAE_DIR`, and for `t5_tokenizer` `COMFYUI_TEXT_ENCODERS_DIR`

#### Scenario: Remote or HuggingFace id passes through
- **WHEN** a model-file input contains `/` but is not a local filesystem path
- **THEN** the resolver returns it unchanged so a remote/HuggingFace reference still loads

### Requirement: Checkpoint existence is validated before a durable job is created
The backend SHALL verify that a resolved local `checkpoint` exists before creating or queueing a
durable training job, returning a structured error instead of failing late inside the Kohya
subprocess. The check SHALL remain flexible: it applies only to local paths and bare filenames, remote
references are exempt, and an explicit override allows bypassing it.

#### Scenario: Missing local checkpoint is rejected with searched directories
- **WHEN** `lora_train_start` resolves a local or bare-filename `checkpoint` that does not exist in any
  searched directory
- **THEN** the backend returns a structured `checkpoint_not_found` error
- **AND** the error details include the `searched_dirs` list
- **AND** no durable training job is created or queued

#### Scenario: Remote checkpoint skips the existence check
- **WHEN** the resolved `checkpoint` is a remote/HuggingFace reference rather than a local path
- **THEN** the backend does not perform a filesystem existence check
- **AND** allows the job to proceed

#### Scenario: Existence check can be explicitly bypassed
- **WHEN** `lora_train_start` is called with `allow_unverified_checkpoint=true`
- **THEN** the backend skips the checkpoint existence check
- **AND** proceeds to create the durable job

