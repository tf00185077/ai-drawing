## Context

The first hardening batch made dataset/profile approval explicit and closed the
dataset validation race, but a Start request still describes only part of the
training operation. `_TrainJob` and `params_json` contain the current subset;
dataset TOML and sd-scripts argv add late global settings and hard-coded flags;
the rest comes from the installed sd-scripts revision. A historical
Backend-managed Anima run proves the danger: `networks.lora_anima` created both
Qwen3 Text Encoder and DiT LoRA modules because no explicit denoiser-only flag
was present.

The local Windows workspace has no sd-scripts checkout, while production
evidence came from another machine. The design therefore distinguishes
semantic recipe compilation from runtime evidence, records unavailable
evidence honestly, and leaves the real bounded initialization probe to the
fourth batch.

The project's MCP rule is "寬進嚴出": LLM callers get forgiving parsing and
repair guidance, while the server emits one stable canonical shape and never
silently ignores ambiguous input.

## Goals / Non-Goals

**Goals:**

- Replace scattered Start knobs with one versioned requested recipe.
- Compile partial, parseable input into a complete effective recipe before any
  durable job is created.
- Make denoiser-only the default and Text Encoder training an explicit opt-in.
- Make every value affecting dataset TOML or sd-scripts argv visible,
  validated, durable, hashable, and queryable.
- Give preflight, Backend Start, MCP Start, bundled transport, status, and the
  handoff runbook one parity-tested recipe contract.
- Record exact execution evidence without claiming that source-level tests are
  a real trainer probe.

**Non-Goals:**

- Restart reconciliation, durable executor ownership, process-group
  cancellation, resume state, or power assertions (third batch).
- Unique artifact namespaces, deterministic artifact ownership, registration
  terminal states, or smoke-test reconciliation (third batch).
- A complete frontend recipe editor, expanded dataset MCP tools, live MCP
  reload proof, or a real bounded trainer initialization probe (fourth batch).
- Arbitrary raw command fragments or shell strings. Broad input applies to
  typed recipe values and documented aliases, not command injection.

## Decisions

### 1. Public Start uses one required versioned recipe object

`folder`, `expected_dataset_hash`, and `expected_profile_hash` remain top-level.
All model and training controls move into `recipe`.

The canonical requested shape is:

```json
{
  "schema_version": "lora-training-recipe/v1",
  "expected_recipe_hash": null,
  "model": {
    "family": "anima",
    "checkpoint": "model locator",
    "allow_unverified_checkpoint": false,
    "network_module": "networks.lora_anima",
    "network_dim": 32,
    "network_alpha": 16,
    "anima": {
      "qwen3": "text encoder locator",
      "vae": "vae locator or null",
      "t5_tokenizer_path": "tokenizer locator or null"
    }
  },
  "scope": {
    "train_text_encoder": false
  },
  "dataset": {
    "trigger_token": "sks",
    "resolution": 1024,
    "batch_size": 1,
    "keep_tokens": 1,
    "num_repeats": 8,
    "enable_bucket": true,
    "bucket_no_upscale": true,
    "min_bucket_reso": 256,
    "max_bucket_reso": 2048,
    "bucket_reso_steps": 64
  },
  "optimization": {
    "epochs": 8,
    "learning_rate": "1e-4",
    "denoiser_learning_rate": null,
    "text_encoder_learning_rates": null,
    "gradient_accumulation_steps": 1,
    "optimizer_type": "AdamW",
    "optimizer_args": [],
    "lr_scheduler": "constant",
    "lr_scheduler_args": [],
    "warmup": {"mode": "steps", "value": 0},
    "seed": {
      "mode": "random",
      "value": 1700000001,
      "source": "preflight_policy"
    },
    "mixed_precision": "no"
  },
  "caching": {
    "cache_latents": true,
    "cache_text_encoder_outputs": true,
    "cache_to_disk": true
  },
  "execution": {
    "max_data_loader_n_workers": 0,
    "persistent_data_loader_workers": false,
    "save_every_n_epochs": 1
  }
}
```

Start requires the `recipe` container but permits a partial requested recipe.
Preflight may be called with no recipe hints. In both cases the compiler
materializes a complete effective recipe before enqueue. The canonical
requested record remains normalized but partial so omitted caller intent is
auditable.

Alternative considered: add every field as another flat Start/MCP argument.
Rejected because the tool would approach forty independent parameters and
would recreate parity drift.

Alternative considered: persist preflight state and Start with a short
`recipe_id`. Deferred because expiry, restart, ownership, and idempotency add a
new durable lifecycle outside this batch.

### 2. Broad input is normalization, never silent omission

Backend recipe parsing is the single authority. MCP forwards the raw recipe and
normalizes only transport forms needed before HTTP serialization.

Accepted forms include:

- a JSON object or a string containing one JSON object;
- `1`, `"1"`, `"v1"`, and the canonical schema-version spelling;
- documented snake/camel aliases such as `batch`, `batchSize`,
  `gradient_accumulation`, `workers`, `optimizer`, `scheduler`, and
  `save_cadence`;
- legacy `class_tokens`/`instance_token` as aliases for canonical
  `dataset.trigger_token`; effective dataset output derives the native
  `class_tokens` value from that one approved token;
- family-native learning-rate aliases such as `unet_lr`, `dit_lr`, and
  `text_encoder_lr`, normalized to family-neutral denoiser/Text Encoder fields;
- numeric and boolean strings when conversion is lossless;
- a fixed integer, `null`, `"random"`, an omitted seed, or the canonical
  `{mode, value}` seed envelope;
- optimizer/scheduler args as a mapping, a list of `key=value` strings, or one
  parseable string;
- `trainable_scope="denoiser_only"` as an alias for
  `train_text_encoder=false`, and
  `denoiser_and_text_encoder` as the true form.

Aliases are resolved before unknown-field checking. Two aliases that target the
same canonical field with different values return `recipe_field_conflict`.
Unknown fields return `recipe_validation_failed` with canonical location,
accepted forms, a closest-field suggestion when available, and a next-step
hint. Submitted values, URLs, arbitrary exception context, and environment
secrets are not echoed.

This keeps agent input forgiving while remaining fail-closed for typos.

### 3. One compiler produces requested, effective, and field-source records

A focused recipe module owns:

1. tolerant parsing into `RequestedTrainingRecipeV1`;
2. deterministic policy resolution into `EffectiveTrainingRecipeV1`;
3. cross-field validation;
4. semantic hashing;
5. step-plan calculation;
6. dataset TOML and command specifications.

Every effective leaf has a source:

- `caller` — explicitly supplied after alias normalization;
- `preflight_policy` — chosen by the deterministic family/platform policy;
- `server_policy` — a documented server-owned constant;
- `derived` — calculated from other canonical values.

The durable requested record preserves omission and intent; the effective
record contains no unresolved `null` for a field that affects training.
Compiler output is immutable once the job is queued. Worker launch cannot
re-read training defaults from global settings.

Alternative considered: keep resolving values in `enqueue()`,
`_write_dataset_config()`, and `_run_training_subprocess()`. Rejected because
late resolution is the current cause of drift.

### 4. Scope is family-neutral and Text Encoder is opt-in

The public scope has one capability in v1: `train_text_encoder`. The denoiser is
always trained. Effective scope expands to:

```json
{
  "denoiser_kind": "dit",
  "train_denoiser": true,
  "train_text_encoder": false,
  "native_scope_flag": "--network_train_unet_only",
  "verification_status": "source_contract"
}
```

`denoiser_kind` is `unet` for SD1.5/SDXL and `dit` for Anima. The inherited
Kohya flag name remains `network_train_unet_only`, but output and reports never
mislabel an Anima DiT as a UNet.

`train_text_encoder=false` emits `--network_train_unet_only`.
`train_text_encoder=true` omits it and requires
`cache_text_encoder_outputs=false`. The conflicting combination returns
`incompatible_training_recipe` before durable job creation. Unknown family,
unsupported canonical scope, or contradictory aliases return a structured
scope error rather than being ignored.

Runtime module/optimizer log proof remains `unverified` until the fourth-batch
bounded probe. Source contract and runtime proof are distinct status fields.

### 5. Safe policy is deterministic and capability-aware

The compiler receives a sanitized execution-capability snapshot. Platform may
come from an explicit config override or a bounded inspection of the configured
trainer Python; failure produces `platform=unknown`, not a guessed CUDA/MPS
claim.

Safe omitted-value policy:

- Text Encoder training is false.
- Batch is 1 for MPS, unknown platform, Anima, SDXL, or resolution at least
  1024. A verified CUDA SD1.5 runtime below 1024 may use the configured batch,
  bounded to the public range.
- Mixed precision is `no` for MPS, CPU, or unknown capability. A verified CUDA
  runtime may use the normalized configured precision.
- An explicit MPS `fp16`/`bf16` request is accepted only when the inspected
  trainer runtime reports compatible Torch/Accelerate capability; otherwise it
  returns `unsupported_runtime_precision`.
- Gradient accumulation is 1; workers are 0 and non-persistent unless the
  caller explicitly requests supported values.
- Optimizer is `AdamW`, scheduler is `constant`, scheduler/optimizer args are
  empty, and warmup is zero steps.
- Overall learning rate is the fallback for every trained component. Effective
  output always expands a denoiser learning rate and, when Text Encoder
  training is enabled, one Text Encoder rate for SD1.5/Anima or two for SDXL.
  A scalar Text Encoder rate expands to the family count; an explicit list must
  match it.
- Bucketing is enabled with no upscale, step 64, minimum 256, and maximum
  `max(1024, resolution * 2)`.
- Latent caching is enabled. Text-encoder output caching is enabled by default
  for denoiser-only SDXL/Anima and disabled otherwise. Disk caching is enabled
  only for cache kinds that are enabled.
- Anima defaults to 8 repeats and 8 epochs. Existing deterministic image-count
  epoch policy remains for SD1.5/SDXL.
- Save cadence is one epoch unless explicitly set to 0 for final-only.

These are project policies, not claimed upstream defaults. Preflight returns
the values and their sources, so an agent can override them within validated
ranges.

### 6. Validation is cross-field and repair-guided

The compiler validates:

- positive dimensions, epochs, repeats, accumulation, and network sizes;
- nonnegative workers and save cadence;
- nonempty, numeric learning-rate strings;
- family-compatible Text Encoder learning-rate counts;
- warmup step/ratio mode and range;
- bucket `min <= max`, positive step, divisibility, and compatibility with
  resolution;
- `cache_to_disk` expansion only for enabled cache kinds;
- Text Encoder/cache incompatibility;
- persistent workers requiring workers greater than zero;
- model-family requirements and dataset-profile family agreement;
- network module membership in the server-owned trusted family registry;
- MPS/runtime precision capability;
- trigger-token aliases resolving to one normalized approval token;
- local component identity and `allow_unverified_checkpoint` evidence.

`network_module` is a typed selector, not an arbitrary Python import escape.
Each family has a server-owned trusted module registry; an unknown module
returns `unsupported_network_module` with allowed identifiers before job
creation.

Errors use stable codes, a human message, `hint`, and redacted structured
details. Repairable omission is compiled; contradictory or unsafe input is
rejected.

### 7. Seed intent and materialization travel together

Canonical requested output represents seed as `{mode, value, source}`. A fixed
integer normalizes to `{"mode":"fixed","value":N,"source":"caller"}`. An
omitted, null, or `"random"` input normalizes to random mode, with source
retaining whether intent came from caller, preflight policy, or direct-Start
server policy. Its `value` is drawn once with a cryptographically strong
bounded generator during recipe compilation. The effective recipe contains
the same integer.

Preflight embeds that canonical seed envelope in its exact Start payload, so
Start preserves random intent and reuses the materialized integer rather than
drawing again. Direct Start with an unresolved random form materializes once
before hashing and durable job creation. The same integer appears in recipe
hash input, argv, status, and later artifact evidence.

### 8. Recipe hash covers semantic training identity

Canonical JSON uses UTF-8, sorted keys, and compact separators. `recipe_hash`
is SHA-256 over:

- recipe schema version;
- approved dataset/profile hashes;
- canonical effective recipe;
- resolved component identities and verification states.

Job id, timestamps, log path, output path, registration alias, exact
machine-specific argv paths, and transport-only `expected_recipe_hash` are
excluded. Any semantic scope, seed, model, dataset, optimizer, bucket, or cache
change therefore changes the hash, while JSON key order does not.

Preflight writes its preview hash into `recipe.expected_recipe_hash` in the
exact Start payload. Start recompiles from current approval/component/runtime
evidence and returns `recipe_hash_mismatch` before job creation when the
supplied expectation differs. Direct Start may omit the expectation and is
validated against current evidence without a stale-preflight comparison.

### 9. Durable recipe and execution evidence use additive columns

New nullable `lora_training_jobs` columns are:

- `recipe_schema_version`;
- `recipe_hash`;
- `recipe_json` — requested/effective recipes, field sources, step plan, and
  component identities;
- `execution_evidence_json` — exact argv, dataset-config content/hash, launcher
  identity, sanitized runtime versions/platform, and sd-scripts revision.

Historical rows remain readable with these fields null and retain legacy
`params`. Every new v1 job must have recipe version/hash/envelope before it
becomes queued.

Status exposes typed top-level recipe fields and retains `params` as a
read-only legacy projection during migration. Evidence entries always include
`status=verified|unavailable|unverified` plus a reason; absence is never
presented as verification.

Component identity uses requested locator, resolved locator, file size/mtime,
cached SHA-256 when available, and verification/bypass state. A bypass is part
of the hash and audit record.

### 10. Exact TOML and argv are built from effective recipe only

Dataset TOML generation receives the effective dataset section and emits all
five bucket fields plus the existing caption/repeat fields. Command building is
a pure function returning an argv list, not a shell string.

Before `Popen`, while the training lock is held, the worker:

1. repeats dataset/profile approval validation;
2. writes the deterministic TOML;
3. builds argv exclusively from the immutable effective recipe;
4. captures sanitized execution evidence and sd-scripts revision;
5. persists exact argv/TOML evidence;
6. launches that exact argv.

Native flags include scope, accumulation, workers, optimizer and args,
scheduler and args, warmup, seed, cache variants, precision, and save cadence.
`cache_to_disk` expands into the enabled native disk-cache flags. A zero save
cadence omits `--save_every_n_epochs`.

Computed step plan records image count, repeats, batches per epoch,
accumulation, optimizer steps per epoch, epochs, and total optimizer steps.
For the single-process policy:

- `train_examples = image_count * num_repeats`;
- `batches_per_epoch = ceil(train_examples / batch_size)`;
- `optimizer_steps_per_epoch = ceil(batches_per_epoch /
  gradient_accumulation_steps)`;
- `total_optimizer_steps = optimizer_steps_per_epoch * epochs`.

Step-mode warmup uses its integer value. Ratio-mode warmup is
`ceil(total_optimizer_steps * ratio)`. The resolved integer is stored in the
effective recipe and passed to `--lr_warmup_steps`.

### 11. Preflight returns an exact Start payload

Decision preflight accepts optional broad recipe hints. For `decision=train`,
it returns:

- canonical requested recipe;
- complete effective preview and field sources;
- recipe hash preview using current dataset/model identity;
- `start_payload` containing folder, both approval hashes, and the canonical
  requested recipe with random seed already materialized and
  `expected_recipe_hash` set to the preview hash.

The payload recipe contains normalized caller hints, not a copy of every
policy-filled effective leaf. Caller omissions therefore remain omissions when
Start recompiles and re-derives field sources. The compiler-owned seed envelope
is the sole inserted materialization needed to prevent a second random draw.

The bundled frontend submits `start_payload` and may overwrite only controls it
actually exposes before rerunning preflight. It does not gain the complete
recipe editor in this batch.

Start compiles and verifies the payload again. A dataset/profile/component
change, or a runtime-capability change that alters the effective recipe or
invalidates a safety assertion, returns a structured mismatch/error rather
than silently changing the recipe.

### 12. MCP output is strict and stable

`lora_train_start` accepts only folder, both approval hashes, and the broad
`recipe` transport. `lora_training_decision_preflight` accepts folder,
approval hints, and optional broad recipe hints.

MCP does not duplicate semantic alias, coercion, or cross-field rules. It
forwards the broad recipe transport to the Backend compiler and relays the
Backend's canonical result or redacted structured error. A rejected validation
request may reach Backend HTTP, but it creates no job, enqueue, TOML, or
subprocess side effect.

Known removed flat MCP argument names are recognized only by the protocol
validation wrapper and mapped to `legacy_training_fields_removed`; their
values are discarded. They are not advertised as supported tool parameters,
accepted by the tool function, or translated into a recipe.

Success returns canonical recipe version/hash, requested/effective scope, field
sources, warnings, and durable job identity. Failure always returns:

```json
{
  "ok": false,
  "tool": "lora_train_start",
  "error": {
    "code": "recipe_validation_failed",
    "message": "training recipe is invalid",
    "hint": "apply the suggested field correction and rerun preflight",
    "details": {"issues": []}
  }
}
```

All LoRA MCP tools keep the same `ok/tool/error` envelope. List/status/log
outputs remain stable even for historical jobs without v1 recipe fields.

### 13. Migration is fail-closed and actionable

Backend Start rejects legacy top-level training knobs with
`legacy_training_fields_removed`, listing field names but not values and
pointing to decision preflight. MCP accepts recipe transport aliases but does
not silently rebuild an old flat Start payload.

The bundled frontend, MCP docs, setup guide, and handoff runbook migrate in the
same change. The first-batch approval hashes remain mandatory.

Rollback can restore the old application code; additive nullable columns remain
unused safely. New v1 jobs remain readable as generic historical rows through
`params`/JSON even if older code does not interpret the new fields.

## Risks / Trade-offs

- **Broad parsing could hide typos** → Resolve only documented aliases, then
  reject unknowns with closest-field suggestions.
- **A partial recipe could recreate hidden defaults** → Every omission has a
  named policy source and every effective leaf is returned and persisted.
- **Runtime capability inspection can fail** → Use conservative batch 1 /
  precision `no`, mark evidence unavailable, and never claim verified support.
- **Exact model hashing can be expensive** → Reuse the file-digest cache and
  record stat/unverified evidence when hashing is unavailable.
- **Upstream sd-scripts flags can change** → Record revision and exact argv;
  source tests validate the target contract, while real compatibility proof
  remains the fourth-batch bounded probe.
- **Breaking flat callers** → Ship Backend, MCP, bundled transport, docs, and
  structured migration errors together.
- **Recipe/status payloads grow** → Keep one canonical envelope and bounded
  evidence; never embed logs or environment values.

## Migration Plan

1. Add recipe schemas/compiler and RED tests without changing Start.
2. Add additive durable recipe columns and historical-row compatibility.
3. Compile preflight hints and return canonical `start_payload`.
4. Switch Backend Start, enqueue, TOML, argv, and status to v1 recipe.
5. Switch MCP and bundled frontend transport; add migration errors for flat
   callers.
6. Update handoff/docs and run schema/parity/command/persistence tests.
7. Run strict OpenSpec, Backend/MCP/Frontend suites, and an offline command
   fixture matrix. Do not claim real trainer scope verification.

## Source References

- [Kohya Anima network training guide](https://github.com/kohya-ss/sd-scripts/blob/main/docs/anima_train_network.md)
  for DiT/Text Encoder scope, cache incompatibility, and Text Encoder learning
  rate behavior.
- [Kohya advanced network training guide](https://github.com/kohya-ss/sd-scripts/blob/main/docs/train_network_advanced.md)
  for network scope and component learning-rate semantics.
- [Kohya dataset configuration guide](https://github.com/kohya-ss/sd-scripts/blob/main/docs/config_README-en.md)
  for dataset TOML and bucket controls.
- [Accelerate runtime source](https://github.com/huggingface/accelerate/blob/main/src/accelerate/accelerator.py)
  and [1.11.0 release notes](https://github.com/huggingface/accelerate/releases/tag/v1.11.0)
  for capability-dependent MPS mixed-precision handling.

## Open Questions

No blocking design questions remain. The exact production sd-scripts revision,
real module/optimizer log assertions, and artifact metadata comparison require
the fourth-batch bounded runtime probe and are explicitly reported as
unverified in this batch.
