## Context

LoRA training crosses four trust boundaries: an agent calls MCP, MCP forwards a backend request, the backend turns the request into a durable job, and a worker later resolves the dataset and launches sd-scripts. The current boundaries do not share one strict contract:

- Preflight suggests `batch_size`, while MCP Start cannot submit it.
- `TrainStartRequest` ignores unknown fields and makes approval hashes optional.
- MCP converts list-shaped FastAPI 422 details into a generic string.
- Dataset APIs use `lora_dataset.resolve_dataset_dir()`, while trainer Start uses an unchecked `(base / folder).resolve()`.
- Enqueue validation is conditional and occurs before the worker obtains the dataset lock; the worker checks only the dataset hash before locking and does not verify the profile hash.
- `trigger_check()` can call `enqueue()` directly, bypassing explicit user approval.

This change is intentionally the first of four batches. It hardens the existing Start surface before later changes expand the effective training recipe, lifecycle handling, artifact semantics, or frontend.

## Goals / Non-Goals

**Goals:**

- Make one preflight result the versioned approval artifact for a training start.
- Reject omitted/stale dataset or profile hashes, unknown fields, unsafe dataset paths, and declared model-family/profile conflicts before sd-scripts starts.
- Keep MCP, Backend Start, and preflight suggestions aligned for all fields the backend already supports, including `batch_size`.
- Preserve field-level backend validation information across MCP.
- Ensure the worker performs final validation while holding the same dataset lock that remains held during training.
- Remove every non-explicit auto-enqueue path.
- Add deterministic contract, path, lock-order, and error propagation tests.

**Non-Goals:**

- Adding trainable-scope, bucket, cache, optimizer, scheduler, warmup, seed, gradient-accumulation, worker, or save-cadence controls.
- Defining an immutable effective recipe or recipe hash.
- Adding cross-process locks, restart reconciliation, process-group cancellation, unique artifact namespaces, registration terminal states, or smoke-test reconciliation.
- Expanding the MCP dataset-management surface or redesigning the frontend.
- Adding the full frontend controls/status experience; only the minimal preflight handshake required by the breaking Start contract is included.
- Inferring a checkpoint's architecture by parsing model weights. This batch verifies declared/configured family consistency only.

## Decisions

### 1. Preflight returns the complete approval payload

For a startable decision, `suggested_params.params` will contain both `expected_dataset_hash` and `expected_profile_hash` plus every backend-supported Start field selected by preflight. `lora_train_start` and `TrainStartRequest` will accept both hashes and `batch_size`.

Both hashes are required for public Start. A missing hash produces a field-level 422 before enqueue; a stale hash produces a structured conflict (`dataset_hash_mismatch` or `profile_hash_mismatch`) with expected and current values.

Alternative considered: keep hashes optional for direct/manual callers. Rejected because it preserves the exact bypass that lets a caller train data the user did not approve. Callers must run preflight again after any dataset/profile change.

### 2. Backend request validation is the authoritative public field set

`TrainStartRequest` will use Pydantic `ConfigDict(extra="forbid")`. MCP will expose the same public fields, subject only to explicit aliases already accepted by the backend. A regression test will compare:

1. the `lora_train_start` callable signature,
2. `TrainStartRequest.model_fields`, and
3. keys emitted in a complete preflight suggestion.

The test will use a small explicit allowlist only for transport/default differences and will fail when a new backend field is added without updating MCP and preflight.

Alternative considered: duplicate hand-maintained field lists in documentation. Rejected because they drift without failing CI.

### 3. MCP preserves list-shaped validation details

The MCP backend-error normalizer will treat FastAPI's list-shaped `detail` as structured validation data:

```json
{
  "ok": false,
  "tool": "lora_train_start",
  "status_code": 422,
  "error": {
    "code": "request_validation_failed",
    "message": "backend request validation failed",
    "details": {
      "validation_errors": [
        {"loc": ["body", "batch_size"], "msg": "...", "type": "..."}
      ]
    }
  }
}
```

Dictionary-shaped application errors keep their existing `code`, `message`, and `details`. Secret-bearing unexpected input values must not be copied into MCP errors; validation entries retain location, message, type, and safe constraint context only.

FastMCP argument validation for this tool follows the same rule. Missing required
arguments are converted into a normal structured tool result before the SDK can
emit a text-only protocol error, and submitted values are omitted.

Alternative considered: return FastAPI's payload unchanged. Rejected because MCP tools require a stable `error` envelope and raw validation entries can echo submitted values.

### 4. Dataset identity and family are checked from one resolver

Trainer code will stop constructing dataset paths itself. Enqueue and worker code will call `lora_dataset.resolve_dataset_dir(folder)`, which rejects absolute paths, traversal, and symlink escapes after canonical resolution. Immediately after resolution, enqueue derives one root-relative POSIX locator and uses it for validation, durable job identity, duplicate checks, and output names, so equivalent slash and backslash inputs cannot diverge.

Preflight derives the family from the dataset profile. If the configured default training family conflicts with that profile, preflight returns `needs_review`, omits a ready-to-start default checkpoint, and emits a structured `model_family_mismatch` warning. At Start, the requested/resolved family must equal the locked dataset profile family or the request fails before job creation/launch. This does not claim to inspect model weights; checkpoint identity verification is a later recipe/runtime concern.

Alternative considered: maintain a second trainer-specific containment check. Rejected because two resolvers already drifted and would continue to do so.

### 5. Validation is preliminary at enqueue and authoritative under the worker lock

The public Start flow is:

1. Pydantic rejects missing hashes and unknown fields.
2. The API calls `enqueue()` with the two hashes and supported fields.
3. `enqueue()` resolves the dataset through the shared resolver, performs a fast preliminary inspection/validation, resolves runtime inputs, creates a durable queued job containing both approval hashes, and returns `job_id`.
4. When dequeued, the worker acquires `dataset_lock(folder, owner=training:<job_id>)`.
5. While holding the lock, it resolves the directory again, inspects the profile, verifies `expected_profile_hash`, runs complete dataset validation with `expected_dataset_hash`, verifies the declared family, and only then marks the job running and launches sd-scripts.
6. The same lock remains held until subprocess termination and output handling leave the training critical section.

This two-stage validation provides fast request feedback while the lock-held validation closes the queue-delay race. A stale queued job becomes `failed` with a structured hash/validation code and never launches a subprocess.

Upload, manual caption edit, batch prefix, LLM captioning, and watcher WD Tagger
writes use the same per-dataset lock. A watcher event that loses the lock race is
deferred through bounded exponential-backoff retries instead of being dropped.

Alternative considered: hold a thread lock from HTTP Start until a queued job eventually runs. Rejected because it would lock the dataset while unrelated jobs wait and cannot survive process boundaries.

### 6. Profile approval is durable

Add nullable `profile_hash` to `LoraTrainingJob`, include it in startup's additive SQLite column migration, `_TrainJob`, durable serialization, job status, and params/audit data. Existing rows remain readable with `profile_hash=null`; only new Start requests must supply it.

Locked worker failures also retain structured `error_details`, including current
dataset/profile hashes, so a queued approval race remains recoverable from
durable status rather than logs alone. The structured details use a nullable,
additively migrated `error_details_json` column so historical rows remain
readable.

Alternative considered: store the profile hash only in `params_json`. Rejected because hashes are first-class job identity/status fields and callers must not parse an opaque recipe dictionary to audit approval.

### 7. Trigger check is discovery-only

`trigger_check()` will return candidates and `should_trigger`, but it will never call `enqueue()`. The explicit Start endpoint remains the only training trigger and therefore the only way to satisfy the two-hash approval contract.

Alternative considered: have trigger check run preflight and auto-start ready datasets. Rejected because project specs require explicit user training intent.

### 8. Bundled frontend performs the same preflight handshake

Before its existing Start call, the LoRA training page will call decision preflight for each selected folder. It will proceed only on `decision=train`, merge the returned `expected_dataset_hash` and `expected_profile_hash` into the user-selected Start payload, and display a useful error for `needs_review`, `do_not_train`, or failed preflight. This is a compatibility migration for the strict endpoint, not the later frontend redesign.

Preflight-selected family/runtime fields are used as defaults for controls the
minimal page cannot represent (notably Anima), while fields selected in the
existing form remain authoritative. The exact top-level approval hashes always
override suggestion copies.

Alternative considered: exempt the bundled frontend from required hashes. Rejected because the backend cannot distinguish a trusted bundled caller from any other HTTP client.

## Risks / Trade-offs

- **Existing callers receive 422 after deployment** → Update MCP, frontend/backend callers, the runbook, and tests in the same change; error details state that preflight must be rerun.
- **Queued jobs can fail after initially returning 202** → This is intentional when data changes during queue delay; status and logs retain the current hashes and recovery action.
- **Configured family metadata can be wrong** → Treat it as a declared compatibility boundary, not proof of checkpoint contents; full component identity verification belongs to the effective-recipe batch.
- **Pydantic 422 data may contain submitted values** → MCP sanitizes entries and does not copy the `input` field.
- **SQLite schema changes are additive only** → Add a nullable column using the project's existing startup migration mechanism; rollback code may leave the unused column in place safely.
- **Thread locks do not protect multiple backend processes** → Document single-worker safety for this batch; cross-process locking is explicitly scheduled for the lifecycle hardening batch.

## Migration Plan

1. Add failing schema, MCP error, parity, path, hash, family, and lock-order tests.
2. Add the nullable `profile_hash` model field and SQLite startup migration.
3. Extend preflight, Backend Start, durable job, and MCP Start with both hashes and `batch_size`.
4. Make request extras forbidden and sanitize/preserve 422 validation details.
5. Replace trainer path construction with the shared resolver and move authoritative checks inside the worker lock.
6. Remove trigger-check auto-enqueue.
7. Adapt the bundled LoRA training page to preflight and submit both approval hashes.
8. Update the handoff runbook and `docs/PROGRESS.md`.
9. Run focused backend/MCP tests under Python 3.11, frontend checks, then the full backend and MCP suites.

Rollback may restore the prior API/MCP code while leaving the nullable `profile_hash` database column. No destructive data migration is required. Queued jobs created under the new contract remain queryable; operators should cancel them before rolling back if the old worker cannot deserialize new params.

## Open Questions

None for this batch. Cross-process dataset locking, checkpoint-content identity, and expanded recipe controls are deliberately assigned to later OpenSpec changes.
