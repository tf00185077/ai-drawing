# lora-training-workflow Specification

## Purpose
TBD - created by archiving change add-lora-training-mcp-workflow. Update Purpose after archive.
## Requirements
### Requirement: Dataset folders are discoverable and inspectable
The backend SHALL expose LoRA dataset discovery for folders under `lora_train_dir`, including trainable image counts, caption coverage, dataset hash, lock state, and detected trigger-token consistency.

#### Scenario: List datasets with summary fields
- **WHEN** a client requests the LoRA dataset list
- **THEN** the response includes each dataset folder under `lora_train_dir`
- **AND** each item includes image count, caption count, missing caption count, dataset hash, and lock state

#### Scenario: Inspect one dataset with file-level details
- **WHEN** a client inspects a dataset folder
- **THEN** the response includes image/caption pairs, missing captions, current caption text or caption path metadata, detected trigger-token candidates, dataset hash, and validation summary

### Requirement: Dataset preparation supports dry-run, apply, backup, and restore
The backend SHALL prepare LoRA captions with deterministic trigger-token normalization and optional AI-assisted cleanup. Preparation SHALL support dry-run without writes, apply with backup creation, and restore from a previous backup.

#### Scenario: Dry-run previews deterministic trigger-token changes
- **WHEN** a client prepares a dataset with `dry_run=true` and a requested trigger token
- **THEN** no caption files are modified
- **AND** the response includes the normalized trigger token, proposed per-file changes, counts of changed/unchanged captions, and dataset hash before changes

#### Scenario: Apply writes normalized captions with backup
- **WHEN** a client prepares a dataset with `dry_run=false`
- **THEN** the backend creates a restorable backup before modifying captions
- **AND** every trainable caption begins with the normalized trigger token exactly once
- **AND** the response includes the backup id, dataset hash before changes, and dataset hash after changes

#### Scenario: AI-assisted cleanup is deterministic after post-filtering
- **WHEN** AI-assisted cleanup is requested and an AI caption provider is configured
- **THEN** the backend applies deterministic caption filtering and trigger-token normalization after AI output
- **AND** the final proposed or written captions remain comma-separated caption text

#### Scenario: Restore reverts an applied preparation
- **WHEN** a client restores a dataset using a valid backup id
- **THEN** caption files are restored from that backup
- **AND** the response includes the restored dataset hash

### Requirement: Dataset validation blocks unsafe training starts
The backend SHALL validate a dataset before training and return structured errors and warnings. Training start SHALL reject invalid datasets.

#### Scenario: Valid dataset passes preflight
- **WHEN** a dataset has enough trainable image/caption pairs and each caption contains the normalized trigger token
- **THEN** validation returns `ok=true`
- **AND** includes image count, caption count, normalized trigger token, dataset hash, and no blocking errors

#### Scenario: Missing captions fail validation
- **WHEN** one or more trainable images have no matching `.txt` caption
- **THEN** validation returns `ok=false`
- **AND** includes blocking errors identifying the affected image paths

#### Scenario: Stale dataset hash is rejected
- **WHEN** a client validates or starts training with an `expected_dataset_hash` that no longer matches the dataset
- **THEN** the backend returns a conflict-style failure
- **AND** includes the current dataset hash so the client can re-inspect or re-validate

### Requirement: Dataset locks prevent watcher and training races
The backend SHALL coordinate dataset preparation, validation, watcher caption writes, and training with per-dataset locks and hash checks.

#### Scenario: Preparation holds a dataset lock
- **WHEN** dataset preparation is applying caption changes
- **THEN** concurrent preparation, validation-for-start, or training start for the same folder is rejected or waits according to the API timeout
- **AND** the response identifies the dataset as locked when it cannot proceed

#### Scenario: Watcher does not overwrite locked caption edits
- **WHEN** the watcher detects a new image in a folder that is locked for preparation or training
- **THEN** watcher caption generation does not overwrite in-flight caption edits
- **AND** the watcher retries or defers according to the backend lock policy

### Requirement: LoRA training jobs are durable and queryable by job id
The backend SHALL persist every LoRA training job with job id, folder, status, stage, progress, current epoch, total epochs, log path, log tail metadata, output path, registered LoRA name, error, dataset hash, parameters, and timestamps.

#### Scenario: Training start creates a persistent queued job
- **WHEN** a client starts training for a validated dataset
- **THEN** the backend returns a `job_id`
- **AND** a persistent job record is created with status `queued`, dataset hash, normalized trigger token, and submitted parameters

#### Scenario: Running job exposes progress and stage
- **WHEN** the Kohya subprocess emits parseable epoch or step output
- **THEN** the backend updates the job progress, current epoch, total epochs, and stage in persistent storage

#### Scenario: Completed job remains queryable after worker restart
- **WHEN** a training job reaches a terminal status
- **THEN** querying by `job_id` returns the terminal status, output or error fields, timestamps, and log metadata even after the process restarts

#### Scenario: Failed job records structured error
- **WHEN** training fails before output registration
- **THEN** the job is marked `failed`
- **AND** the job stores an error message and recent log tail for diagnosis

### Requirement: Training logs are persisted and retrievable
The backend SHALL write each LoRA training job's stdout and stderr to a per-job log file and expose bounded log retrieval.

#### Scenario: Log tail returns recent output
- **WHEN** a client requests logs for a job with a line limit
- **THEN** the response includes at most that many recent log lines
- **AND** indicates whether earlier output was truncated

#### Scenario: Missing log is reported without hiding job state
- **WHEN** a job exists but its log file cannot be read
- **THEN** the log endpoint returns a structured error for log retrieval
- **AND** job status remains queryable from persistent job state

### Requirement: LoRA training jobs can be cancelled
The backend SHALL support cancellation for queued and running LoRA training jobs.

#### Scenario: Queued job is cancelled before subprocess start
- **WHEN** a client cancels a queued job
- **THEN** the job is removed from the execution queue
- **AND** the persistent job status becomes `cancelled`

#### Scenario: Running job termination is tracked
- **WHEN** a client cancels a running job
- **THEN** the backend requests subprocess termination
- **AND** the persistent job status becomes `cancelled` after the process exits
- **AND** dataset locks and worker slots are released

#### Scenario: Cancelling a terminal job is idempotent
- **WHEN** a client cancels a completed, failed, or already-cancelled job
- **THEN** the backend returns the existing terminal state without starting new work

### Requirement: Successful LoRA outputs are registered for ComfyUI
The backend SHALL register successful `.safetensors` LoRA outputs into the configured ComfyUI LoRA directory and record the registered LoRA name on the job.

#### Scenario: Output file is registered atomically
- **WHEN** training succeeds and a `.safetensors` output is found
- **THEN** the backend copies or links it into the ComfyUI LoRA directory using an atomic completion step
- **AND** records `output_path` and `registered_lora_name` on the job

#### Scenario: Registration failure preserves training output
- **WHEN** training succeeds but registration fails
- **THEN** the job records the output path and registration error
- **AND** the failure is visible in job status without deleting the trained file

### Requirement: Registered LoRAs can be smoke-tested through generation
The backend SHALL provide a smoke test operation for a completed LoRA training job that submits a generation using the registered LoRA and records the generation result through the existing generation/recording path.

#### Scenario: Smoke test starts generation for a registered LoRA
- **WHEN** a client requests a smoke test for a completed job with a registered LoRA
- **THEN** the backend submits a generation request using that LoRA and the normalized trigger token
- **AND** returns the generation job id or recorded artifact reference

#### Scenario: Smoke test failure is attached to the LoRA job
- **WHEN** smoke test generation fails or cannot be submitted
- **THEN** the LoRA job remains completed if training and registration succeeded
- **AND** the smoke test error is recorded separately on the job status

### Requirement: LoRA training API and trainer schema are aligned
The backend SHALL keep LoRA training API request schemas and trainer enqueue parameters aligned so start requests do not reference removed fields.

#### Scenario: Start request does not read missing generate-after field
- **WHEN** a valid `TrainStartRequest` without `generate_after` is submitted
- **THEN** the API does not raise an attribute error for `generate_after`
- **AND** the request is validated and queued or rejected for dataset-specific reasons only

### Requirement: Watchdog caption generation is reliable and conservative
The backend SHALL generate watchdog captions only after target image files are stable and only when a watched folder contains images with missing or stale same-name `.txt` captions. The watcher SHALL react to created, modified, and moved image events and SHALL NOT start automatic LoRA training.

#### Scenario: Watcher waits for stable image files
- **WHEN** a watched image event arrives while the image size or modification time is still changing
- **THEN** the watcher waits until the image remains stable before invoking WD Tagger
- **AND** WD Tagger is not invoked on a partially written image

#### Scenario: Watcher handles created modified and moved images
- **WHEN** a supported image file is created, modified, or moved into a watched dataset folder
- **THEN** the watcher schedules caption evaluation for that image's parent folder

#### Scenario: Current manual captions are preserved
- **WHEN** a same-name `.txt` file exists and is newer than or equal to the image file
- **THEN** the watcher treats that caption as current
- **AND** the watcher does not overwrite the current caption by default

#### Scenario: Folder is skipped when captions are current
- **WHEN** every supported image in a target folder has a current same-name `.txt` file
- **THEN** the watcher does not invoke WD Tagger for that folder

#### Scenario: Unreadable images produce structured status
- **WHEN** a watched image cannot be read or is detected as invalid before captioning
- **THEN** the watcher records a structured dataset-local status entry with an error code, message, image path, size, and mtime
- **AND** the unchanged invalid image is not retried indefinitely

#### Scenario: Watchdog does not auto-train
- **WHEN** watchdog caption generation finishes or records a captioning status error
- **THEN** no LoRA training job is enqueued unless a client explicitly calls the training API

### Requirement: Dataset captions can be assessed for training suitability
The backend SHALL expose a deterministic dataset caption suitability assessment for a folder under `lora_train_dir`. The assessment SHALL use local image and `.txt` caption data only and SHALL return a verdict of `suitable`, `needs_review`, or `not_suitable` with reasons.

#### Scenario: Assessment returns caption coverage counts
- **WHEN** a client assesses a dataset folder
- **THEN** the response includes `image_count`, `txt_count`, `missing_txt_count`, and `empty_txt_count`
- **AND** the response includes the dataset hash

#### Scenario: Assessment reports trigger-token coverage
- **WHEN** the assessment request includes a trigger token or a trigger token is configured
- **THEN** the response includes the normalized trigger token, covered caption count, total caption count, and coverage ratio

#### Scenario: Assessment reports tag coherence metrics
- **WHEN** captions contain comma-separated tags
- **THEN** the response includes common tags, rare tags, unique tag count, repeated tag count, singleton ratio, repeated-tag ratio, average tags per caption, and mean pairwise tag-set similarity

#### Scenario: Assessment warns about scattered captions
- **WHEN** captions are dominated by one-off tags or have too few repeated tags across images
- **THEN** the response includes warnings or recommendations indicating over-fragmented tags or insufficient repeated identity/style tags
- **AND** the verdict is not `suitable`

#### Scenario: Missing or empty captions block suitability
- **WHEN** one or more images have missing or empty `.txt` captions
- **THEN** the response includes warnings or reasons identifying the caption coverage issue
- **AND** the verdict is `not_suitable`

#### Scenario: Assessment is local and deterministic
- **WHEN** a client requests caption suitability assessment
- **THEN** the backend computes the result without calling an external LLM or starting LoRA training

### Requirement: Dataset metadata profiles are persisted locally
The backend SHALL recognize a dataset-local `.lora-dataset.json` metadata profile for folders under `lora_train_dir`. The profile SHALL support dataset type, trigger token, caption profile, model family, protected tags, removable tags, and `auto_train`.

#### Scenario: Missing profile uses conservative defaults
- **WHEN** a dataset folder does not contain `.lora-dataset.json`
- **THEN** dataset discovery still includes the folder
- **AND** the returned profile summary uses conservative defaults including `auto_train=false`

#### Scenario: Valid profile is returned with profile hash
- **WHEN** a dataset folder contains a valid `.lora-dataset.json`
- **THEN** dataset inspection includes the normalized profile fields
- **AND** the response includes a `profile_hash` separate from the dataset image/caption hash

#### Scenario: Malformed profile is reported structurally
- **WHEN** `.lora-dataset.json` cannot be parsed or violates the profile schema
- **THEN** dataset discovery and inspection return structured profile validation errors
- **AND** image/caption discovery for the dataset remains available when the folder itself is valid

### Requirement: Dataset profiles never trigger automatic training
The backend SHALL treat `.lora-dataset.json` as descriptive dataset metadata. Profile loading, validation, discovery, or inspection SHALL NOT enqueue a LoRA training job.

#### Scenario: Auto train defaults to false
- **WHEN** a dataset profile omits `auto_train`
- **THEN** the normalized profile reports `auto_train=false`

#### Scenario: Profile inspection does not start training
- **WHEN** a client lists, inspects, or validates dataset profile metadata
- **THEN** no LoRA training job is created
- **AND** training remains available only through an explicit training start request

### Requirement: Dataset metadata can be managed through backend APIs
The backend SHALL expose explicit get, update, and validate operations for `.lora-dataset.json` metadata profiles under `lora_train_dir`.

#### Scenario: Metadata get returns normalized profile state
- **WHEN** a client requests metadata for a valid dataset folder
- **THEN** the response includes the normalized profile, profile validation status, and `profile_hash`

#### Scenario: Metadata update rejects stale profile hash
- **WHEN** a client updates metadata with an `expected_profile_hash` that does not match the current profile
- **THEN** the backend rejects the update with a conflict-style failure
- **AND** the response includes the current `profile_hash`

#### Scenario: Metadata validate does not write files
- **WHEN** a client validates proposed dataset metadata
- **THEN** the backend returns structured errors, warnings, and normalized values
- **AND** `.lora-dataset.json` is not modified

### Requirement: Agent inspection composes profile and suitability signals
The backend SHALL provide an agent inspection response for a dataset that combines profile status, dataset hash, profile hash, caption suitability summary, trigger-token coverage, and existing validation signals.

#### Scenario: Agent inspection summarizes a dataset
- **WHEN** a client requests agent inspection for a valid dataset folder
- **THEN** the response includes dataset identity, profile summary, profile validation messages, caption suitability verdict, reasons, recommendations, dataset hash, and profile hash

#### Scenario: Agent inspection remains side-effect free
- **WHEN** a client requests agent inspection
- **THEN** the backend does not modify captions or metadata
- **AND** no LoRA training job is created

