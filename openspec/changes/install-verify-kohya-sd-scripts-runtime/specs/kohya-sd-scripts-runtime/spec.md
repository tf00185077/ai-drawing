## ADDED Requirements

### Requirement: Kohya sd-scripts runtime is configured locally
The project runtime SHALL be configured with a local Kohya `sd-scripts` checkout and training Python environment that the existing backend trainer can invoke.

#### Scenario: Required Kohya scripts are present
- **WHEN** the runtime preflight resolves `SD_SCRIPTS_PATH`
- **THEN** that path contains `train_network.py`
- **AND** it contains `sdxl_train_network.py`
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

#### Scenario: Small dataset trains through backend workflow
- **WHEN** a small LoRA dataset is inspected, prepared with dry-run, applied, and validated through the backend or MCP workflow
- **THEN** `lora_train_start` can queue a durable job
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
