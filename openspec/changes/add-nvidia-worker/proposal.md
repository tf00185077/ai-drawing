# Change: Add a paired NVIDIA generation worker

## Why

The Apple Silicon host remains the authoritative ai-drawing coordinator and
resource store, but selected generation jobs need to execute on a Windows 11
NVIDIA machine on the same private LAN. Operators need a one-click Windows
install without modifying an older ComfyUI installation.

## What changes

- Add explicit per-request `execution_target` selection (`local` or `worker`).
- Add a paired Worker client with bearer authentication and no silent fallback.
- Synchronize only workflow-referenced resources using SHA-256, resumable
  uploads, and atomic promotion into a size-bounded Windows cache.
- Add a Windows Worker distribution with a double-click installer, pinned
  ComfyUI/runtime manifest, private-network firewall rule, and auto-start.
- Keep ComfyUI bound to Windows localhost; expose only the authenticated Worker.

## Impact

- Backend generation schemas, queue client selection, configuration, and API.
- A new standalone Windows Worker runtime and packaging scripts.
- No automatic deletion of an existing Windows ComfyUI installation.
- No change to local generation unless a request explicitly selects `worker`.
