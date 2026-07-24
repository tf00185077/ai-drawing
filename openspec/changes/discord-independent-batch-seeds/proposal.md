## Why

Discord currently requests multiple images as one ComfyUI latent batch, so every
recorded image reports the same sampler seed. That prevents reliable per-image
traceability and reduces the requested batch diversity.

## What Changes

- Add an opt-in `batch_seed_mode="independent"` request contract for normal
  template generation while retaining `shared` as the default for every existing
  API and MCP caller.
- Expand an independent request into sequential private `batch_size=1`
  executions with unique backend-owned seeds under one public parent job ID.
- Aggregate queue status, cancellation, successful artifacts, and sanitized
  failed-member summaries at the parent level without exposing child IDs.
- Persist parent/member terminal outcomes and reconcile interrupted in-flight
  members after a Backend restart.
- Make output identity and result ordering deterministic by child ordinal.
- Opt the existing Discord generation flow into independent mode without
  changing `/draw`, batch-count controls, or `/result id:<parent-job-id>`.
- Keep custom and audited workflows on existing shared behavior and reject
  incompatible independent/fixed-seed combinations.
- Limit implementation verification to isolated fakes and repository tests; do
  not restart Backend or submit real ComfyUI/GPU work in this change phase.

## Capabilities

### New Capabilities

- `generation-batch-seed-policy`: Defines opt-in independent seed allocation,
  parent/child execution identity, compatibility restrictions, deterministic
  artifact identity, and unchanged Discord result lookup.

### Modified Capabilities

- `queue-job-completion`: Extends terminal-state guarantees to aggregate
  independent batches, including sibling continuation, durable mixed outcomes,
  restart reconciliation, atomic capacity reservation, and parent cancellation.

## Impact

- Backend request schema and generation API response shaping.
- In-process generation queue identity, capacity, cancellation, completion, and
  failure handling.
- SQLAlchemy models plus one Alembic migration for durable batch/member state.
- Artifact naming, metadata, recording, and deterministic result ordering.
- Discord HTTP client payload and mixed-result presentation.
- Focused and full backend/Discord test suites plus OpenSpec validation.
