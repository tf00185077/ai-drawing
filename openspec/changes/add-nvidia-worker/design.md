# Design

## Topology

The Mac runs the coordinator, Gallery, database, Presets, and authoritative
model library. Windows runs an isolated Worker and a pinned ComfyUI checkout.
The Worker binds to a private-LAN address while ComfyUI binds only to localhost.

## Selection and failure

Every supported generation request may set `execution_target` to `local` or
`worker`. The default is `local`. The target is copied into the durable
in-memory queue item and the same client is used for submit, status, history,
input upload, and artifact retrieval. A worker error terminates the job and is
never retried on the local engine.

## Pairing and transport

The first release uses an operator-generated bearer token stored in protected
configuration on both machines. Worker endpoints require the token except for
the loopback health endpoint and a deliberately minimal pairing-status probe.
ComfyUI is never exposed directly to the LAN.

## Resource synchronization

Before `/prompt`, the coordinator extracts known ComfyUI loader resources from
the final graph. It resolves each name within configured authoritative roots,
computes SHA-256, asks the Worker which digests are absent, and uploads missing
content in chunks. A partial file is never visible as a model. The Worker
verifies size and digest, then atomically promotes it into the matching ComfyUI
model directory. Cache eviction is LRU, excludes active resources, and stops
before the configured free-space reserve.

## Versioning

`worker-manifest.json` pins the Worker protocol, Python, PyTorch CUDA index,
ComfyUI tag/commit, and custom-node revisions. Setup installs into
`C:\AI-Drawing-Worker` by default and refuses to overwrite unrelated content.
Updates stage and validate a replacement before switching. Existing ComfyUI
folders are reported only; cleanup is a separate confirmed operation.

## Network

Setup requires an elevated Windows terminal, verifies that the active network
profile is Private, creates a narrowly scoped inbound firewall rule for the
Worker port, and registers an auto-start scheduled task. It does not change the
router, enable port forwarding, or expose ComfyUI port 8188.
