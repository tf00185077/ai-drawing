# Windows Worker Update Minimal Health Validation Design

## Goal

Make Windows Worker updates validate only the conditions required for a safe
version switch. The updater must not duplicate resource planning, download the
complete ComfyUI object catalog, or reject an otherwise healthy candidate based
on speculative model/resource checks.

Resource and model errors belong to actual ComfyUI task execution. They are not
an update, activation, or general submission gate.

## Problem

The first Mac-to-Windows update of candidate commit
`3240b6c11c649fbd1f51e1eccd54b3e34ddfac39` reached isolated validation and
failed before activation with `WORKER_CONTRACT_FAILED`. The production release
remained healthy and unchanged.

An isolated manual run subsequently proved that the candidate supplied:

- a ready ComfyUI server;
- an authenticated protocol 2 Worker;
- the exact target source commit;
- update capability 1;
- a successful empty resource plan; and
- a successful required-node preflight.

The updater nevertheless performs redundant validation: it downloads and
parses the complete `/object_info` response with a shorter timeout than the
Worker's preflight, then calls the Worker's required-node preflight as well. It
also calls an empty resource plan that cannot prove whether a future task's
resources will be usable. Transport failures are collapsed into the generic
`WORKER_CONTRACT_FAILED`, while staged process output is discarded.

## Required Activation Contract

Candidate validation keeps only these gates:

1. Candidate ComfyUI `/system_stats` becomes reachable within the bounded cold
   start budget.
2. `/system_stats` reports a CUDA device with a non-empty GPU name.
3. Candidate Worker authenticated `/v1/worker/status` becomes reachable.
4. Worker status reports:
   - integer `protocol_version == 2`;
   - integer `update_capability == 1`;
   - `source_commit` exactly equal to the requested target commit; and
   - `comfyui == "ready"`.
5. A single authenticated `/v1/workflows/preflight` call for the fixed required
   node set reports `ready == true` and no missing node types.

Activation, production health verification, rollback, request correlation,
crash recovery, source trust, and privileged updater boundaries remain
unchanged.

## Removed Validation

The updater no longer:

- requests or parses ComfyUI `/object_info` directly;
- calls `/v1/resources/plan` during staged or production update validation;
- infers candidate validity from speculative model/resource availability; or
- checks the same required node set in both direct updater code and Worker
  preflight.

General task submission must not use resource-plan results as a blocking gate.
Tasks are submitted to ComfyUI, and genuine missing-model/resource errors are
reported from ComfyUI through the existing Worker/Backend error path.

The resource-plan API may remain available for informational or explicit
operator use, but it is not invoked implicitly by update activation or normal
task submission.

## Validation Sequence

```text
start candidate ComfyUI
  -> wait for /system_stats
  -> require CUDA
start candidate Worker
  -> authenticated /status
  -> require protocol, commit, capability, comfyui ready
  -> one required-node preflight
  -> activate candidate
  -> verify production using the same minimal contract
  -> ready, or rollback on failure
```

Readiness polling is phase-aware. A cold ComfyUI start is not treated as a
Worker contract violation. Each request remains bounded, and the overall
validation deadline remains finite.

## Errors and Diagnostics

Failures use the narrowest safe stage code available:

- `COMFYUI_START_TIMEOUT`
- `CUDA_VALIDATION_FAILED`
- `WORKER_START_TIMEOUT`
- `WORKER_STATUS_INVALID`
- `WORKER_PREFLIGHT_FAILED`

Private diagnostics may record the failed stage, process exit code, and
redacted stdout/stderr tail. Public state continues to expose only stable safe
codes. Tokens, authorization headers, pairing contents, environment secrets,
and response bodies that may contain secrets are never persisted.

## Testing

Tests must prove that:

- update validation never calls `/object_info`;
- update validation never calls `/v1/resources/plan`;
- ordinary task submission is not blocked by resource planning;
- cold-start polling remains bounded but does not fail on the former short
  object-info timeout;
- missing CUDA still rejects activation;
- invalid protocol, capability, source commit, or ComfyUI status still rejects
  activation;
- missing required nodes still reject activation through the single Worker
  preflight;
- production validation and rollback use the same minimal contract;
- diagnostics are stage-specific and secret-safe; and
- existing update correlation, recovery, and rollback tests remain green.

## Out of Scope

- Installing optional Triton, SageAttention, ONNX, or OpenGL packages.
- Treating optional custom-node import warnings as activation failures.
- Changing Git trust, updater ownership, token storage, or scheduled-task
  privilege.
- Automatically enabling `NVIDIA_WORKER_AUTO_UPDATE`.
- Retrying the failed update before this design is implemented and deployed.
