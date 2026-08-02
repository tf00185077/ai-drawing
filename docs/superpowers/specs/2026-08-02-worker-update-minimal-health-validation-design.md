# Windows Worker Update Minimal Health Validation Design

## Goal

Make Windows Worker updates validate only the conditions required for a safe
version switch. The updater must not duplicate resource planning, download the
complete ComfyUI object catalog, or reject an otherwise healthy candidate based
on speculative model/resource checks.

Resource planning is not an update or activation gate. Normal Worker submission
still scans workflow resource references and transfers resources that are not
present with a valid verification record. Model usability errors beyond that
transfer-integrity boundary belong to actual ComfyUI execution.

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

The updater never invokes the resource-plan API. Normal task submission retains
resource scanning, planning, and missing-file transfer because those operations
move referenced content from Mac to Windows; they are not candidate-runtime
health checks.

## Resource Verification Lifecycle

The Mac scans each submitted workflow for referenced resources and uses its
local digest cache to build content-addressed manifests without repeatedly
hashing unchanged local files. The Worker resource plan treats its verification
sidecar as the only trusted proof of a transferred file:

- A destination file is reusable only when its sidecar exists, parses, and
  matches the destination size, modification time, and requested SHA-256.
- A missing, malformed, or mismatched sidecar makes the resource missing. The
  Worker does not hash the existing destination to self-heal the record; the Mac
  retransmits and replaces it.
- A missing destination causes any stale sidecar for that destination to be
  removed before the resource is reported missing.
- Transfer completion hashes the completed partial file exactly once. Only a
  matching digest permits atomic promotion and sidecar creation.
- Digest mismatch removes the partial file and leaves no verification sidecar.
- LRU eviction removes the destination and its corresponding sidecar as one
  logical operation. A later submission therefore retransmits and re-verifies
  the resource.

Resource planning does not attempt to predict whether ComfyUI can semantically
use a model. Genuine loader/model errors are returned by ComfyUI after prompt
submission.

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
- ordinary task submission retains resource scan, plan, and missing transfer;
- a valid sidecar avoids rehashing an unchanged Worker resource;
- missing or invalid sidecars trigger retransmission without Windows-side
  self-healing hashes;
- missing destinations and LRU eviction remove stale sidecars;
- failed transfer digest validation leaves no sidecar;
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

## Windows PowerShell Compatibility

All shipped PowerShell and operator commands target the installed Windows
PowerShell 5.1 Desktop runtime, not PowerShell 7. Requirements are:

- use syntax documented for Windows PowerShell 5.1;
- avoid ambiguous .NET overload binding when a native PowerShell operator or an
  explicitly typed overload is available;
- use `-split '=', 2` for two-part environment parsing;
- quote `Start-Process` arguments according to its 5.1 behavior, where argument
  arrays are joined into one command line;
- treat scheduled-task start as asynchronous and verify terminal task/service
  state separately;
- execute parser and runtime smoke tests through real
  `powershell.exe -NoProfile -NonInteractive`, including paths containing
  spaces and non-ASCII characters; and
- verify commands against Microsoft documentation before adding them to the
  package README or operator instructions.

Authoritative references:

- [Microsoft about_Split for Windows PowerShell 5.1](https://learn.microsoft.com/de-at/powershell/module/microsoft.powershell.core/about/about_split?view=powershell-5.1)
- [Microsoft Start-Process for Windows PowerShell 5.1](https://learn.microsoft.com/hr-hr/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1)
- [Microsoft ScheduledTasks module](https://learn.microsoft.com/de-de/powershell/module/scheduledtasks/?view=windowsserver2016-ps)
- [Microsoft Get-NetTCPConnection](https://learn.microsoft.com/fr-fr/powershell/module/nettcpip/get-nettcpconnection?view=windowsserver2025-ps)
