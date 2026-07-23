## ADDED Requirements

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
