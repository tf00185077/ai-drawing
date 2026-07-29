## MODIFIED Requirements

### Requirement: MCP LoRA tools return structured JSON results
The MCP server SHALL return stable JSON-serializable dictionaries for every
LoRA tool. Every result SHALL include `ok`, `tool`, and either typed payload
fields or an `error` object containing `code`, `message`, `hint`, and optional
redacted `details`.

#### Scenario: Successful tool result is machine-readable
- **WHEN** a LoRA MCP tool succeeds
- **THEN** the result includes `ok=true` and the exact tool name
- **AND** returns documented canonical payload fields without text parsing

#### Scenario: Failed tool result is repair-guided
- **WHEN** a LoRA MCP tool receives validation, conflict, not-found, runtime, or execution failure
- **THEN** it returns `ok=false` with stable code/message/hint/details
- **AND** details identify the next repair step when one is known

#### Scenario: Error output is redacted
- **WHEN** protocol, Pydantic, Backend, or recipe validation includes submitted input, URLs, arbitrary exception context, or environment values
- **THEN** MCP output omits those values
- **AND** retains only safe locations, types, constraints, accepted forms, and field suggestions

### Requirement: MCP can start LoRA training
The MCP server SHALL expose `lora_train_start` with top-level folder, current
dataset/profile approval hashes, and a required broad `recipe` transport. It
SHALL forward one versioned recipe to Backend Start and SHALL return canonical
recipe identity/status.

#### Scenario: Agent starts from canonical preflight payload
- **WHEN** an agent calls Start with the exact preflight folder, hashes, and recipe
- **THEN** the result includes `ok=true`, job/status/stage, approval hashes, recipe version/hash, and requested/effective scope

#### Scenario: Agent supplies parseable broad recipe
- **WHEN** recipe is an object or JSON-object string containing documented aliases, coercible scalar forms, or partial requested sections
- **THEN** MCP/Backend normalize it through the single recipe compiler
- **AND** the success result returns the strict canonical recipe/effective output

#### Scenario: Start rejects invalid or racing input
- **WHEN** Backend rejects validation, lock, stale hash, family, runtime capability, or recipe conflict
- **THEN** MCP returns `ok=false` with the exact stable backend/recipe code
- **AND** includes redacted repair guidance without retrying implicitly

#### Scenario: Legacy flat Start receives migration guidance
- **WHEN** an agent calls Start using removed top-level training knobs
- **THEN** the MCP protocol validation wrapper returns `legacy_training_fields_removed`
- **AND** directs the agent to decision preflight and versioned recipe
- **AND** omits the removed values and does not invoke the Start tool function

### Requirement: MCP can query LoRA training job status
The MCP server SHALL expose `lora_train_job_status` for durable job state,
including typed recipe and execution evidence for v1 jobs and compatible null
fields for historical jobs.

#### Scenario: Agent polls running recipe
- **WHEN** an agent queries a queued/running v1 job
- **THEN** status includes stage/progress/epochs/timestamps and approval identity
- **AND** includes recipe version/hash, requested/effective recipe/scope, field sources, step plan, component identities, and available exact execution evidence

#### Scenario: Agent reads terminal recipe
- **WHEN** an agent queries a terminal v1 job
- **THEN** status includes terminal output/error/registration/smoke fields
- **AND** preserves immutable recipe and execution evidence

#### Scenario: Agent reads historical job
- **WHEN** a historical job has no v1 recipe
- **THEN** MCP returns the job with v1 fields null and legacy params intact
- **AND** does not treat missing historical evidence as verified

### Requirement: MCP can run LoRA training decision preflight
The MCP server SHALL expose `lora_training_decision_preflight` with folder,
optional approval hints, and optional broad recipe hints. It SHALL return the
Backend decision plus canonical recipe preview and exact Start payload without
enqueuing.

#### Scenario: Agent receives train decision and Start payload
- **WHEN** a dataset and compiled recipe are ready
- **THEN** result includes decision `train`, reasons/actions, approval hashes, canonical requested/effective recipe, field sources, step plan, recipe hash preview, and exact `start_payload`
- **AND** the payload recipe carries that preview as `expected_recipe_hash`

#### Scenario: Agent supplies partial or aliased hints
- **WHEN** an agent submits a partial recipe object or documented aliases
- **THEN** preflight accepts parseable intent
- **AND** emits one strict canonical recipe with visible policy sources

#### Scenario: Agent receives review or block decision
- **WHEN** dataset, family, runtime, or recipe has warning/blocking issues
- **THEN** result includes `needs_review` or `do_not_train` with structured issues and next actions
- **AND** does not start training

#### Scenario: Decision preflight does not call Start
- **WHEN** an agent calls decision preflight
- **THEN** MCP does not call `lora_train_start`
- **AND** no Backend training job is created

### Requirement: MCP and Backend Start fields remain aligned
The project SHALL enforce automated parity between MCP Start, Backend Start,
and decision-preflight Start payloads. Their public top level SHALL contain
only folder, expected dataset hash, expected profile hash, and the nested
versioned recipe, except for documented transport-only differences.

#### Scenario: Batch size is nested without disappearing
- **WHEN** the parity test inspects the v1 public Start contract
- **THEN** `batch_size` exists at canonical `recipe.dataset.batch_size` in Backend, MCP, and preflight output
- **AND** both approval hashes remain required top-level fields

#### Scenario: Recipe contract changes
- **WHEN** a canonical recipe field, type, alias, requiredness rule, or output identity changes
- **THEN** parity tests fail until Backend, MCP, and preflight are updated together

## ADDED Requirements

### Requirement: MCP recipe aliases are documented and conflict safe
The MCP recipe transport SHALL publish accepted canonical fields and aliases.
Alias normalization SHALL be deterministic, and ambiguity SHALL fail before
any Backend Start side effect.

#### Scenario: Equivalent aliases have one meaning
- **WHEN** an agent uses one documented alias for a canonical recipe field
- **THEN** advertised/tool documentation identifies the canonical output field
- **AND** the result uses only the canonical field

#### Scenario: Alias conflict has no side effect
- **WHEN** an agent supplies two aliases with different values for one field
- **THEN** MCP returns `recipe_field_conflict`
- **AND** Backend validation creates no durable job and performs no enqueue

#### Scenario: Typo receives closest safe suggestion
- **WHEN** an unknown key has one unambiguous close canonical field
- **THEN** the error suggests that field name without copying the submitted value
- **AND** the agent can repair and retry explicitly
