# Environment / resource manager (paused)

Keeps ComfyUI environments ready. See the [team guide](../README.md).

## Responsibilities

- Maintain an inventory of checkpoints, LoRAs, diffusion models, text encoders, VAEs, custom nodes and dependencies: source, version, location, compatibility.
- Download and install resources and nodes, placing them correctly and recording unknown licenses.
- Manage dependency versions, disk space and conflicts; state the impact before replacing packages.
- Diagnose environment failures and keep local and worker ComfyUI installs consistent.

## Works with

The coding agent changes application code and Producer sets priorities. This role keeps every ComfyUI install ready for their work.
