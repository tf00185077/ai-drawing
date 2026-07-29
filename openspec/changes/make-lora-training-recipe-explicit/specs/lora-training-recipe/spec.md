## ADDED Requirements

### Requirement: Training recipes are versioned canonical objects
Every new LoRA training Start SHALL include a `recipe` object. The recipe
compiler SHALL recognize schema version `lora-training-recipe/v1` and SHALL
return one canonical requested-recipe shape before enqueue.

#### Scenario: Canonical recipe is accepted
- **WHEN** Start receives a v1 recipe object with canonical field names
- **THEN** the backend parses it as `lora-training-recipe/v1`
- **AND** returns the canonical requested recipe in Start/job status

#### Scenario: Recipe container is missing
- **WHEN** Start omits the `recipe` container
- **THEN** no durable job is created
- **AND** the error directs the caller to decision preflight

#### Scenario: Legacy flat training fields are submitted
- **WHEN** Start receives removed top-level training fields instead of `recipe`
- **THEN** it returns `legacy_training_fields_removed`
- **AND** identifies field names without echoing their values

### Requirement: Recipe input is broad and output is strict
Recipe parsing SHALL accept documented equivalent input forms while emitting
one typed canonical object. It SHALL resolve aliases before unknown-field
checking, SHALL reject contradictory aliases, and SHALL NOT silently ignore
unknown fields.

#### Scenario: Parseable recipe forms normalize identically
- **WHEN** equivalent recipes are supplied as an object or JSON-object string using documented aliases and lossless numeric/boolean strings
- **THEN** they produce the same canonical requested recipe
- **AND** their effective recipes and recipe hashes are equal

#### Scenario: Partial recipe is completed visibly
- **WHEN** a requested recipe omits optional recipe leaves
- **THEN** the compiler materializes every training-affecting effective value
- **AND** records each omitted value's `preflight_policy`, `server_policy`, or `derived` source

#### Scenario: Conflicting aliases are rejected
- **WHEN** two accepted aliases target one canonical field with different values
- **THEN** compilation returns `recipe_field_conflict`
- **AND** no durable job is created

#### Scenario: Trigger token has one canonical field
- **WHEN** a caller uses `class_tokens` or `instance_token`
- **THEN** requested output normalizes it to `dataset.trigger_token`
- **AND** effective output derives native dataset `class_tokens` from the approved normalized token

#### Scenario: Unknown recipe field receives repair guidance
- **WHEN** a recipe contains an unrecognized or misspelled field after alias normalization
- **THEN** compilation returns `recipe_validation_failed`
- **AND** the issue includes canonical location, accepted forms, a safe closest-field suggestion when available, and a next-step hint
- **AND** submitted values are not echoed

### Requirement: Effective recipes are complete before enqueue
The backend SHALL compile requested recipe, safe policy, derived values, and
server-owned constants into an immutable effective recipe before creating a
durable queued job. No dataset-TOML or sd-scripts argv value SHALL fall through
to an unrecorded global or upstream default.

#### Scenario: New job has no unresolved training value
- **WHEN** a valid partial recipe starts training
- **THEN** the queued job already stores a complete effective recipe
- **AND** every training-affecting leaf has a recorded source

#### Scenario: Settings change after enqueue
- **WHEN** global LoRA settings change after a job is queued
- **THEN** the job's effective recipe, dataset TOML, and sd-scripts argv remain unchanged

#### Scenario: Server-owned constants are visible
- **WHEN** gradient checkpointing, caption shuffle/extension, save format, or launcher CPU-thread count is server-owned
- **THEN** the effective recipe/status names its value and source
- **AND** the value is not present only as an invisible code constant

### Requirement: Text Encoder training is explicit opt-in
The v1 recipe SHALL always train the family denoiser and SHALL train Text
Encoder LoRA modules only when `scope.train_text_encoder=true`. Omission SHALL
resolve to false.

#### Scenario: SD family defaults to UNet-only
- **WHEN** an SD1.5 or SDXL recipe omits or disables Text Encoder training
- **THEN** effective scope reports `denoiser_kind=unet` and `train_text_encoder=false`
- **AND** exact argv includes `--network_train_unet_only`

#### Scenario: Anima defaults to DiT-only
- **WHEN** an Anima recipe omits or disables Text Encoder training
- **THEN** effective scope reports `denoiser_kind=dit` and `train_text_encoder=false`
- **AND** exact argv includes the upstream `--network_train_unet_only` flag without calling the denoiser a UNet in public output

#### Scenario: Text Encoder is explicitly enabled
- **WHEN** a compatible recipe sets `train_text_encoder=true`
- **THEN** effective scope reports denoiser plus Text Encoder
- **AND** argv omits `--network_train_unet_only`

#### Scenario: Text Encoder cache conflicts with training
- **WHEN** `train_text_encoder=true` and `cache_text_encoder_outputs=true`
- **THEN** compilation returns `incompatible_training_recipe`
- **AND** no durable job or subprocess is created

#### Scenario: Untrusted network module is rejected
- **WHEN** a recipe names a network module outside the server-owned registry for its model family
- **THEN** compilation returns `unsupported_network_module` with allowed identifiers
- **AND** no arbitrary module import, durable job, or subprocess is created

### Requirement: Optimization, data, cache, and execution controls are explicit
The recipe SHALL explicitly represent gradient accumulation, optimizer and
arguments, scheduler and arguments, warmup, seed, mixed precision,
overall and per-component learning rates, data-loader workers, persistent
workers, save cadence, all five bucket fields, latent cache, Text Encoder
output cache, and disk-cache intent.

#### Scenario: Explicit controls reach native artifacts
- **WHEN** a recipe supplies distinct valid values for all v1 controls
- **THEN** the effective recipe preserves their canonical values
- **AND** the dataset TOML and exact argv contain their corresponding native settings

#### Scenario: Component learning rates are complete
- **WHEN** a caller omits per-component rates or supplies one Text Encoder rate
- **THEN** effective output derives the denoiser rate and the family-required Text Encoder rate count from the overall or supplied rate
- **AND** exact argv records those explicit native values without an upstream learning-rate fallback

#### Scenario: Text Encoder learning-rate count is invalid
- **WHEN** an explicit Text Encoder learning-rate list does not match the trained family component count
- **THEN** compilation returns `recipe_validation_failed` with the expected count
- **AND** no durable job or subprocess is created

#### Scenario: Bucket invariants fail closed
- **WHEN** bucket minimum exceeds maximum, a bound is incompatible with bucket step, or bucket values are invalid
- **THEN** compilation returns a field-level `recipe_validation_failed`
- **AND** no TOML, durable job, or subprocess is created

#### Scenario: Persistent workers require workers
- **WHEN** persistent data-loader workers are requested with zero workers
- **THEN** compilation returns `incompatible_training_recipe`
- **AND** identifies both conflicting fields

#### Scenario: Disk cache expands only enabled cache kinds
- **WHEN** `cache_to_disk=true`
- **THEN** argv includes each native disk-cache flag only for its enabled cache kind
- **AND** effective recipe exposes the expanded latent/text cache-to-disk booleans

#### Scenario: Final-only saving is explicit
- **WHEN** `save_every_n_epochs=0`
- **THEN** effective recipe reports final-only saving
- **AND** argv omits `--save_every_n_epochs`

### Requirement: Safe defaults are platform and family aware
Omitted recipe values SHALL be resolved by a deterministic documented policy
using model family, resolution, and sanitized runtime capability. Unknown
capability SHALL choose conservative values and SHALL NOT be represented as
verified support.

#### Scenario: MPS or unknown runtime uses conservative suggestion
- **WHEN** execution capability is MPS or unknown and the caller omits batch and precision
- **THEN** effective batch is 1
- **AND** effective Kohya mixed precision is `no`
- **AND** field sources identify the safe policy

#### Scenario: High-memory family avoids batch four default
- **WHEN** family is Anima or SDXL, or resolution is at least 1024, and batch is omitted
- **THEN** effective batch is 1
- **AND** the compiler does not copy an unqualified global batch 4

#### Scenario: Unsupported explicit runtime precision is rejected
- **WHEN** a caller explicitly requests MPS fp16/bf16 without verified compatible runtime capability
- **THEN** compilation returns `unsupported_runtime_precision`
- **AND** suggests precision `no` or runtime verification

#### Scenario: Capability inspection is unavailable
- **WHEN** the configured trainer runtime cannot be inspected
- **THEN** compilation/status records `platform=unknown` and evidence `unavailable`
- **AND** does not claim CUDA, MPS, or mixed-precision support

### Requirement: Random seed is materialized once
The requested seed SHALL distinguish fixed from random intent. A random seed
SHALL be materialized exactly once before hashing and durable job creation.
Canonical requested output SHALL carry mode, materialized value, and source so
an exact preflight Start payload preserves intent and omission provenance
without redrawing.

#### Scenario: Fixed seed is preserved
- **WHEN** the caller supplies a valid seed integer
- **THEN** requested seed is canonicalized as fixed mode with that integer and caller source
- **AND** effective seed contains that integer
- **AND** recipe hash input, argv, and status use the same value

#### Scenario: Random seed is stable after compilation
- **WHEN** seed is omitted, null, or the documented `random` alias
- **THEN** requested recipe records random mode, one materialized integer, and the caller/policy source
- **AND** effective recipe and canonical Start payload carry that same integer
- **AND** Start, queue delay, and worker launch do not draw another seed

### Requirement: Recipe identity is deterministic and semantic
The backend SHALL compute `recipe_hash` as SHA-256 over canonical recipe schema
version, approved dataset/profile identity, effective semantic recipe, and
resolved component identities/verification states. Ephemeral job and output
paths and the transport-only expected hash SHALL be excluded.

#### Scenario: Key order does not change recipe hash
- **WHEN** two equivalent canonical recipes differ only in input key order or accepted aliases
- **THEN** they produce the same recipe hash

#### Scenario: Semantic value changes recipe hash
- **WHEN** dataset/profile identity, model/component identity, scope, seed, optimizer, bucket, cache, or another effective training value changes
- **THEN** recipe hash changes

#### Scenario: Job-specific path does not change recipe hash
- **WHEN** the same semantic recipe is queued under a different job id, log path, or output namespace
- **THEN** recipe hash remains the same

#### Scenario: Stale preflight recipe is rejected
- **WHEN** a preflight Start payload supplies `expected_recipe_hash` and current compilation produces a different hash
- **THEN** Start returns `recipe_hash_mismatch`
- **AND** no durable job, TOML, or subprocess is created

### Requirement: Recipe and execution evidence are durable
Every new v1 job SHALL durably store recipe schema version/hash, requested and
effective recipe, field sources, computed step plan, component identities, and
execution evidence. Historical rows SHALL remain readable with null v1 fields.

#### Scenario: Queued status exposes recipe identity
- **WHEN** a v1 Start creates a queued job
- **THEN** job status returns recipe version/hash, requested/effective recipe, requested/effective scope, field sources, step plan, and component verification evidence

#### Scenario: Worker persists exact execution before launch
- **WHEN** the locked worker is ready to launch sd-scripts
- **THEN** it persists exact argv, dataset-TOML content/hash, sanitized launcher/runtime identity, and sd-scripts revision or explicit unavailable evidence
- **AND** launches that exact argv

#### Scenario: Unverified component is auditable
- **WHEN** a permitted component verification bypass is used
- **THEN** component identity and recipe hash record the bypass and unverified state
- **AND** status does not present the component as verified

#### Scenario: Historical job remains readable
- **WHEN** a pre-v1 row has no recipe/evidence columns populated
- **THEN** status returns null v1 fields and the legacy params projection
- **AND** database initialization does not corrupt or reject the row

### Requirement: Step relationships are explicit
The effective recipe SHALL include a deterministic step plan derived from
approved image count, repeats, batch, gradient accumulation, epochs, and the
single-process execution policy. Warmup ratios SHALL resolve to a persisted
integer optimizer-step count from that plan.

#### Scenario: Step plan is calculated before queue
- **WHEN** a dataset and effective recipe are valid
- **THEN** status records train examples, batches per epoch, optimizer steps per epoch, epochs, and total optimizer steps
- **AND** records the formula inputs used

#### Scenario: Accumulation changes optimizer steps
- **WHEN** only gradient accumulation changes
- **THEN** the step plan and recipe hash reflect the changed optimizer-step relationship

#### Scenario: Ratio warmup becomes exact steps
- **WHEN** requested warmup uses ratio mode
- **THEN** effective warmup steps equal the ceiling of total optimizer steps multiplied by the ratio
- **AND** status, recipe hash, and exact argv use that resolved integer
