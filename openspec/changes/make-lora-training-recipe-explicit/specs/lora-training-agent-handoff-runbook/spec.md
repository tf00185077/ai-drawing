## MODIFIED Requirements

### Requirement: Agent training handoff reports are standardized
The LoRA training handoff runbook SHALL require a pre-start report for a
specific LoRA that presents dataset/profile approval identity and the complete
canonical recipe preview before explicit training intent.

#### Scenario: Pre-start report summarizes recipe intent
- **WHEN** an agent is ready to ask the user to train a LoRA
- **THEN** the report includes dataset folder/type, trigger token, model family, caption profile/suitability, decision/reasons, dataset/profile hashes, recipe schema version/hash preview, requested/effective scope, optimizer/scheduler/warmup, seed, batch/accumulation/repeats/epochs/step plan, bucket/cache, workers, save cadence, component verification, runtime capability, and known risks

#### Scenario: Policy values are distinguished from user values
- **WHEN** preflight filled omitted recipe leaves
- **THEN** the report identifies caller, preflight policy, server policy, and derived sources
- **AND** does not present a policy choice as an explicit user selection

#### Scenario: Training start waits for explicit user request
- **WHEN** the pre-start report is produced
- **THEN** the agent does not call Start
- **AND** training starts only after explicit user intent for that dataset/recipe

### Requirement: Agent training execution follows monitor register smoke-test sequence
The LoRA training handoff runbook SHALL define Start/monitor/register/smoke
sequence using the current approval hashes and canonical recipe payload while
retaining the existing terminal lifecycle boundaries.

#### Scenario: Approved recipe is started exactly
- **WHEN** the user approves a specific reported recipe
- **THEN** the agent submits the exact canonical preflight Start payload
- **AND** does not reconstruct omitted values, redraw random seed, or substitute Backend defaults

#### Scenario: Running recipe is monitored
- **WHEN** a job is queued or running
- **THEN** the agent polls job status and bounded logs
- **AND** compares durable recipe version/hash, effective scope, step plan, and execution evidence with the approved report

#### Scenario: Completed job is smoke-tested
- **WHEN** training completes and registers a LoRA output
- **THEN** the agent requests the existing smoke test
- **AND** reports smoke failure separately from training completion

### Requirement: Agent training terminal reports are standardized
The handoff runbook SHALL require terminal reports to preserve recipe identity,
effective scope, execution evidence, and existing output/error fields.

#### Scenario: Completed report includes recipe evidence
- **WHEN** a v1 job completes
- **THEN** the report includes job/final status, output, registered LoRA, smoke status/artifact, recipe version/hash, effective scope, effective seed, optimizer-step plan, exact argv/revision evidence status, and recommended next actions

#### Scenario: Failed or cancelled report includes recipe context
- **WHEN** a v1 job fails or is cancelled
- **THEN** the report includes job/final status, structured reason, recent log summary, approval hashes, recipe version/hash, requested/effective scope, execution evidence available before failure, and recovery actions

#### Scenario: Historical report does not invent evidence
- **WHEN** a historical job lacks v1 recipe/evidence
- **THEN** the report labels those fields unavailable
- **AND** uses legacy params only as historical context

## ADDED Requirements

### Requirement: Agent recipe recovery is explicit
The handoff runbook SHALL define repair branches for recipe parsing,
cross-field, runtime capability, approval, and legacy-field failures. An agent
SHALL NOT silently weaken scope, caching, precision, or another recipe value to
force Start success.

#### Scenario: Parse or alias failure stops Start
- **WHEN** Start/preflight returns `recipe_validation_failed` or `recipe_field_conflict`
- **THEN** the agent reports canonical location, code/message/hint, accepted forms, and suggested field
- **AND** retries only after explicitly applying a non-ambiguous correction

#### Scenario: Scope or cache conflict requires review
- **WHEN** recipe compilation returns `incompatible_training_recipe`
- **THEN** the agent reports the conflicting requested fields
- **AND** does not disable Text Encoder training or cache implicitly

#### Scenario: Runtime precision is unsupported
- **WHEN** compilation returns `unsupported_runtime_precision`
- **THEN** the agent reports capability evidence and the conservative option
- **AND** does not substitute precision until the user approves changed intent or a new preflight policy payload

#### Scenario: Legacy fields require migration
- **WHEN** Start returns `legacy_training_fields_removed`
- **THEN** the agent reruns decision preflight and presents the canonical recipe
- **AND** does not translate the old payload invisibly
