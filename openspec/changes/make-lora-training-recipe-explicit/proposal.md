## Why

LoRA Start currently exposes only part of the recipe and lets the remaining
scope, optimizer, scheduler, seed, bucket, cache, worker, and save behavior fall
through to global settings or sd-scripts defaults. This makes a queued job
impossible to reproduce or audit and has already allowed Backend-managed Anima
training to include Text Encoder modules when the intended scope was DiT-only.

**Execution order:** 2/4

**Previous batch:** `harden-lora-training-start-contract`

**Next batch:** `harden-lora-training-runtime-lifecycle`

## What Changes

- **BREAKING** Replace the public Start collection of top-level training knobs
  with a required, versioned `recipe` object. Folder and the two approval hashes
  remain top-level approval identity.
- Apply the MCP rule "寬進嚴出": accept parseable recipe objects, JSON-object
  strings, documented aliases, numeric/boolean string forms, and partial
  requested recipes; emit one canonical typed recipe or a stable repair-guided
  error. Unknown or misspelled fields are never silently ignored.
- Compile every requested recipe into a complete effective recipe before
  durable job creation. Every omitted value records its policy source; no
  effective field may fall through to an invisible sd-scripts default.
- Make Text Encoder training an explicit opt-in. The safe default is
  `train_text_encoder=false`, compiled to denoiser-only training (UNet for
  SD1.5/SDXL, DiT for Anima).
- Expose and validate gradient accumulation, data-loader workers, save cadence,
  optimizer/scheduler/warmup, seed, bucket, and cache behavior.
- Extend decision preflight to accept recipe hints and return an exact canonical
  Start payload using family-, resolution-, platform-, and runtime-aware safe
  policies.
- Persist requested and effective recipes, field sources, recipe schema version,
  deterministic recipe hash, exact sd-scripts argv, dataset-config evidence,
  runtime environment/revision, resolved component identities, verification
  evidence, and computed optimizer-step relationships.
- Update Backend, MCP, the bundled transport adapter, and the agent handoff
  contract together so the versioned recipe has one parity-tested shape.
- Keep restart reconciliation, process-group cancellation, per-job artifact
  ownership, registration/smoke lifecycle, expanded dataset MCP tools, complete
  frontend controls, live MCP reload evidence, and real bounded trainer probes
  in their already ordered later batches.

## Capabilities

### New Capabilities

- `lora-training-recipe`: Versioned requested/effective recipe compilation,
  validation, hashing, provenance, platform policy, and execution evidence.

### Modified Capabilities

- `lora-training-workflow`: Start, preflight, durable job status, dataset TOML,
  and sd-scripts execution use the canonical effective recipe.
- `lora-training-mcp-tools`: MCP Start and preflight accept broad recipe input
  and return strict canonical recipe/error envelopes.
- `lora-training-agent-handoff-runbook`: Pre-start, Start, monitoring, and
  terminal reports carry recipe version/hash and requested/effective scope.

## Impact

- Backend schemas, API routing, recipe compilation, training decision,
  trainer command construction, durable job model/migrations, and job status.
- MCP LoRA tool signatures, input normalization, validation errors, parity
  tests, and documentation.
- Bundled frontend transport must submit the canonical preflight recipe, without
  adding the complete recipe-control UI reserved for the fourth batch.
- Existing direct Start callers must migrate from top-level training fields to
  `recipe`; structured migration errors point callers to decision preflight.
- The change depends on the completed, unarchived
  `harden-lora-training-start-contract` approval-hash and lock contract.
