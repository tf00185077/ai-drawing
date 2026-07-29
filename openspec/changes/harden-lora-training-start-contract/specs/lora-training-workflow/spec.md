## MODIFIED Requirements

### Requirement: Dataset validation blocks unsafe training starts
The backend SHALL validate every dataset before training and return structured errors and warnings. Public Training Start SHALL require the current expected dataset and profile hashes, SHALL reject unknown request fields, and SHALL reject invalid datasets before creating or launching work.

#### Scenario: Valid approved dataset passes Start validation
- **WHEN** a dataset has enough trainable image/caption pairs, each caption contains the normalized trigger token, both supplied approval hashes match, and the declared model family matches the dataset profile
- **THEN** Start validation succeeds
- **AND** the durable queued job records the normalized trigger token, dataset hash, and profile hash

#### Scenario: Missing captions fail validation
- **WHEN** one or more trainable images have no matching `.txt` caption
- **THEN** validation returns `ok=false`
- **AND** includes blocking errors identifying the affected image paths
- **AND** no training subprocess is launched

#### Scenario: Missing approval hash is rejected
- **WHEN** a public Start request omits `expected_dataset_hash` or `expected_profile_hash`
- **THEN** the backend returns a field-level request-validation failure
- **AND** no durable training job is created

#### Scenario: Stale dataset or profile hash is rejected
- **WHEN** a client starts training with an expected dataset or profile hash that no longer matches the dataset
- **THEN** the backend returns a conflict-style `dataset_hash_mismatch` or `profile_hash_mismatch` failure
- **AND** includes the corresponding current hash so the client can re-inspect and rerun preflight

#### Scenario: Unknown Start field is rejected
- **WHEN** a Start request contains an unrecognized or misspelled field
- **THEN** the backend returns HTTP 422 identifying the extra field
- **AND** does not silently apply a configured default for the intended field

### Requirement: Dataset locks prevent watcher and training races
The backend SHALL coordinate dataset preparation, validation, watcher caption writes, and training with per-dataset locks and hash checks. The worker SHALL acquire the training lock before authoritative profile/dataset validation and SHALL keep it until the training critical section ends.

#### Scenario: Preparation holds a dataset lock
- **WHEN** dataset preparation is applying caption changes
- **THEN** concurrent preparation, validation-for-start, or training start for the same folder is rejected or waits according to the API timeout
- **AND** the response identifies the dataset as locked when it cannot proceed

#### Scenario: Watcher does not overwrite locked caption edits
- **WHEN** the watcher detects a new image in a folder that is locked for preparation or training
- **THEN** watcher caption generation does not overwrite in-flight caption edits
- **AND** the watcher retries or defers according to the backend lock policy

#### Scenario: Document mutation routes respect the training lock
- **WHEN** upload, caption edit, batch prefix, or LLM caption generation targets a dataset locked for training
- **THEN** the mutation returns a structured `dataset_locked` conflict
- **AND** no image or caption is partially changed

#### Scenario: Worker validates after acquiring training lock
- **WHEN** a queued job is dequeued
- **THEN** the worker acquires the dataset training lock before resolving the final profile hash, validating captions, and checking the dataset hash
- **AND** launches sd-scripts only if all locked checks pass

#### Scenario: Dataset changes while job is queued
- **WHEN** image bytes, captions, dataset membership, or the profile changes after enqueue but before the worker obtains the training lock
- **THEN** the locked final validation marks the job failed with the corresponding structured mismatch or validation code
- **AND** durable status retains the structured current-hash details
- **AND** the worker does not launch sd-scripts for that job

### Requirement: LoRA training API and trainer schema are aligned
The backend SHALL keep LoRA training API request schemas and trainer enqueue parameters aligned. The Start request SHALL reject unknown fields and SHALL forward every accepted field, including `batch_size` and both approval hashes, to the trainer service.

#### Scenario: Accepted Start fields reach enqueue
- **WHEN** a valid `TrainStartRequest` includes `batch_size`, `expected_dataset_hash`, and `expected_profile_hash`
- **THEN** the API forwards those exact values to `lora_trainer.enqueue`
- **AND** the queued job records their effective values

#### Scenario: Removed or misspelled field fails closed
- **WHEN** Start receives a field absent from `TrainStartRequest`
- **THEN** request validation returns HTTP 422
- **AND** the trainer service is not called

### Requirement: Dataset profiles never trigger automatic training
The backend SHALL treat `.lora-dataset.json` and all dataset discovery operations as descriptive metadata. Profile loading, validation, discovery, inspection, decision preflight, and trigger checks SHALL NOT enqueue a LoRA training job.

#### Scenario: Auto train defaults to false
- **WHEN** a dataset profile omits `auto_train`
- **THEN** the normalized profile reports `auto_train=false`

#### Scenario: Profile inspection does not start training
- **WHEN** a client lists, inspects, validates, or runs decision preflight for dataset profile metadata
- **THEN** no LoRA training job is created
- **AND** training remains available only through an explicit approved training Start request

#### Scenario: Trigger check is discovery-only
- **WHEN** a client runs the legacy trigger-check operation
- **THEN** the response may report eligible candidates and `should_trigger`
- **AND** the operation does not call enqueue or create durable training jobs

### Requirement: Training decision suggests parameters without submitting them
The backend SHALL include suggested training parameters in a `train` or `needs_review` decision when enough metadata is available. Suggested parameters SHALL be advisory, SHALL include the exact dataset/profile hashes inspected by preflight, and SHALL NOT be persisted as a queued job.

#### Scenario: Suggested parameters are returned with rationale
- **WHEN** model family, dataset type, caption profile, and image count are available
- **THEN** the preflight response includes suggested parameters and rationale fields
- **AND** the suggested Start payload includes `expected_dataset_hash` and `expected_profile_hash`

#### Scenario: Suggested parameters do not bypass validation
- **WHEN** a client later starts training using suggested parameters
- **THEN** the backend performs preliminary validation and repeats authoritative validation under the worker's dataset lock
- **AND** stale dataset/profile hashes prevent subprocess launch

#### Scenario: Family conflict is not suggested as ready
- **WHEN** the configured default training family differs from the dataset profile family
- **THEN** preflight returns `needs_review` with `model_family_mismatch`
- **AND** does not provide a ready-to-submit default checkpoint/family combination

## ADDED Requirements

### Requirement: Training dataset paths use the shared root-contained resolver
Every Training Start and worker dataset lookup SHALL use the same canonical resolver as dataset discovery and inspection. The resolver SHALL accept only dataset folders whose resolved targets remain strictly below `lora_train_dir`.

#### Scenario: Relative contained folder is accepted
- **WHEN** Start names an existing relative dataset folder whose resolved path remains below `lora_train_dir`
- **THEN** enqueue and the worker resolve the same canonical directory
- **AND** validation, durable job identity, duplicate detection, and output naming use one root-relative POSIX locator

#### Scenario: Absolute or traversal path is rejected
- **WHEN** Start names an absolute path or a path containing traversal that would escape `lora_train_dir`
- **THEN** the backend returns structured `invalid_dataset_folder`
- **AND** no external directory is inspected or queued

#### Scenario: Symlink escape is rejected
- **WHEN** a dataset path below `lora_train_dir` resolves through a symlink to a target outside the root
- **THEN** the shared resolver returns `invalid_dataset_folder`
- **AND** no training job is created or subprocess launched

### Requirement: Training approval identity is durable
Every newly created LoRA training job SHALL persist both the approved dataset hash and approved profile hash as first-class job identity fields and expose them through job status.

#### Scenario: Approved Start creates durable identity
- **WHEN** a valid Start request creates a queued job
- **THEN** the persistent job stores `dataset_hash` and `profile_hash`
- **AND** job status returns both values after enqueue, execution, and terminal completion

#### Scenario: Existing job lacks profile hash
- **WHEN** an existing pre-migration job has no profile hash
- **THEN** database initialization and status serialization keep the historical job readable with `profile_hash=null`
- **AND** the missing historical value does not satisfy the approval requirement for a new run

### Requirement: Bundled LoRA training client uses approved hashes
The bundled LoRA training page SHALL run decision preflight before submitting each Start request and SHALL submit the exact dataset and profile hashes returned by that preflight.

#### Scenario: Frontend starts a ready dataset
- **WHEN** a user starts a selected dataset and decision preflight returns `train`
- **THEN** the frontend submits `expected_dataset_hash` and `expected_profile_hash` with the selected Start parameters
- **AND** carries preflight-selected family/runtime parameters that the minimal UI cannot represent
- **AND** preserves an explicitly selected `batch_size`

#### Scenario: Frontend preflight requires review or blocks training
- **WHEN** decision preflight returns `needs_review`, `do_not_train`, or an error
- **THEN** the frontend does not call the Start endpoint for that dataset
- **AND** displays the decision or structured failure to the user
