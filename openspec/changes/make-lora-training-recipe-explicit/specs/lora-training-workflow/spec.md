## MODIFIED Requirements

### Requirement: Dataset validation blocks unsafe training starts
The backend SHALL validate every dataset and compile/validate the versioned
recipe before training. Public Start SHALL require the current expected dataset
and profile hashes plus a recipe container, SHALL reject unknown top-level or
recipe fields after documented alias normalization, and SHALL reject invalid
datasets/recipes before creating or launching work.

#### Scenario: Valid approved recipe passes Start validation
- **WHEN** a dataset has enough valid image/caption pairs, both approval hashes match, family matches the profile, and the requested recipe compiles successfully
- **THEN** Start validation succeeds
- **AND** the durable queued job records approval identity, normalized trigger token, recipe version/hash, and complete effective recipe

#### Scenario: Missing captions fail validation
- **WHEN** one or more trainable images have no matching `.txt` caption
- **THEN** validation returns `ok=false`
- **AND** includes blocking errors identifying affected image paths
- **AND** no durable job or subprocess is created

#### Scenario: Missing approval hash or recipe is rejected
- **WHEN** a public Start request omits either approval hash or the recipe container
- **THEN** the backend returns a field-level request/recipe validation failure
- **AND** no durable training job is created

#### Scenario: Stale dataset or profile hash is rejected
- **WHEN** Start uses an expected dataset/profile hash that no longer matches
- **THEN** it returns `dataset_hash_mismatch` or `profile_hash_mismatch`
- **AND** includes the corresponding current hash for re-inspection/preflight

#### Scenario: Invalid recipe is rejected before persistence
- **WHEN** recipe values are contradictory, unsupported, or unsafe for the approved family/runtime
- **THEN** Start returns a stable structured recipe error with repair guidance
- **AND** no durable job, TOML, or subprocess is created

#### Scenario: Unknown Start or recipe field fails closed
- **WHEN** Start contains an unrecognized top-level field or an unrecognized recipe field after alias normalization
- **THEN** validation identifies the field and accepted canonical form
- **AND** does not silently apply a default for the intended field

### Requirement: LoRA training jobs are durable and queryable by job id
The backend SHALL persist every LoRA training job with job id, folder, status,
stage, progress, epochs, log metadata, output/registration/error fields,
dataset/profile approval identity, recipe version/hash/envelope, execution
evidence, smoke fields, and timestamps. New jobs SHALL be queryable from typed
status without parsing logs; historical jobs SHALL remain readable.

#### Scenario: Training start creates persistent queued recipe
- **WHEN** a client starts training for a validated dataset and recipe
- **THEN** the backend returns a job id and creates a queued row
- **AND** the row already contains dataset/profile hashes, normalized trigger token, requested/effective recipe, field sources, step plan, component identities, schema version, and recipe hash

#### Scenario: Running job exposes exact execution
- **WHEN** the locked worker builds the dataset TOML and sd-scripts command
- **THEN** it persists exact argv/TOML and sanitized runtime/revision evidence before launch
- **AND** running status returns that evidence with progress and epoch fields

#### Scenario: Completed job remains queryable after worker restart
- **WHEN** a training job reaches a terminal status
- **THEN** querying by job id returns terminal output/error/timestamps/log metadata
- **AND** preserves the immutable recipe and execution evidence

#### Scenario: Failed job records structured error
- **WHEN** validation, command preparation, launch, or the training subprocess fails before output registration
- **THEN** the job is marked failed according to the existing lifecycle contract
- **AND** stores structured error details and retains recipe/execution evidence

#### Scenario: Historical job has no v1 recipe
- **WHEN** a pre-migration row lacks v1 recipe columns
- **THEN** status returns null v1 fields and legacy params
- **AND** the historical row remains readable

### Requirement: LoRA training API and trainer schema are aligned
Backend Start, preflight Start payload, trainer enqueue, and the MCP Start SHALL
use the same top-level approval fields and one
`lora-training-recipe/v1` object. Recipe compilation SHALL be the only path from
requested values to effective trainer fields.

#### Scenario: Canonical Start reaches enqueue
- **WHEN** a valid Start contains folder, both approval hashes, and a v1 recipe
- **THEN** the API forwards the recipe without dropping any canonical section
- **AND** enqueue receives the compiler output rather than independently resolving defaults

#### Scenario: Preflight payload validates as Start
- **WHEN** preflight returns `decision=train` with a canonical `start_payload`
- **THEN** the payload validates directly through Backend and MCP Start schemas
- **AND** no field translation or hidden default is required

#### Scenario: Removed flat field fails with migration guide
- **WHEN** Start uses a former top-level training field
- **THEN** it returns `legacy_training_fields_removed`
- **AND** trainer enqueue is not called

#### Scenario: Recipe parity regression is detected
- **WHEN** Backend, MCP, preflight, or trainer changes a recipe field, type, alias, default source, or requiredness
- **THEN** automated parity tests fail unless the canonical contract is updated together

### Requirement: Training decision suggests parameters without submitting them
Decision preflight SHALL accept optional broad recipe hints and compile them
with current dataset/profile/model/runtime evidence. A `train` decision SHALL
include an exact canonical Start payload, effective preview, field sources, and
recipe hash; preflight SHALL remain non-executing.

#### Scenario: Suggested recipe is returned with rationale
- **WHEN** metadata, family, runtime policy, and requested hints are sufficient
- **THEN** preflight returns canonical requested/effective recipe, field sources, step plan, hash preview, and rationale
- **AND** `start_payload` contains folder, exact approval hashes, and the versioned recipe carrying the expected preview hash

#### Scenario: Broad hints are normalized
- **WHEN** preflight receives documented recipe aliases or partial hints
- **THEN** it returns the strict canonical recipe shape
- **AND** explains policy-filled values without hiding them

#### Scenario: Start payload preserves caller omission
- **WHEN** preflight compiles a partial recipe hint
- **THEN** effective preview contains every policy-filled leaf
- **AND** `start_payload.recipe` retains normalized caller omissions and only inserts compiler-owned transport metadata plus the materialized seed envelope

#### Scenario: Malformed hint produces request repair guidance
- **WHEN** requested hints contain an unknown field, invalid coercion, or alias conflict
- **THEN** preflight returns `recipe_validation_failed` or `recipe_field_conflict` with redacted field guidance
- **AND** does not enqueue or silently translate the submitted intent

#### Scenario: Parseable unsafe hint produces a blocking decision
- **WHEN** requested hints parse but conflict with family, runtime capability, scope, cache, or another safety invariant
- **THEN** preflight returns structured issues with `needs_review` or `do_not_train`
- **AND** does not enqueue or silently weaken the requested recipe

#### Scenario: Suggested recipe does not bypass Start validation
- **WHEN** a client later submits `start_payload`
- **THEN** Start repeats dataset/profile/family/runtime/recipe validation
- **AND** stale approval, component identity, or safety-relevant capability evidence prevents subprocess launch

#### Scenario: Preflight does not persist a job
- **WHEN** any decision preflight is requested
- **THEN** no LoRA training job is created
- **AND** only explicit Start may enqueue

### Requirement: Bundled LoRA training client uses approved hashes
The bundled LoRA training page SHALL run decision preflight before each Start
and SHALL submit the exact current approval hashes and canonical recipe
transport returned by preflight. This batch SHALL migrate transport without
claiming a complete recipe-control UI.

#### Scenario: Frontend starts a ready canonical recipe
- **WHEN** decision preflight returns `train`
- **THEN** the frontend submits its canonical `start_payload`
- **AND** preserves only supported user overrides by rerunning preflight before Start

#### Scenario: Frontend does not rebuild recipe defaults
- **WHEN** the minimal page cannot represent a recipe field
- **THEN** it carries the preflight canonical value unchanged
- **AND** does not reconstruct that value from frontend defaults

#### Scenario: Frontend preflight requires review or blocks training
- **WHEN** decision is `needs_review`, `do_not_train`, or recipe validation fails
- **THEN** the frontend does not call Start
- **AND** displays the structured decision/error
