## ADDED Requirements

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
