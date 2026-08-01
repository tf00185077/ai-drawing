# Windows Worker Direct-to-D Clean Install Design

## Goal

Replace the current Windows Worker with a clean managed installation rooted at
`D:\code\AI-Drawing-Worker`. Generate a new Worker token and pairing file. Do
not preserve any existing Worker models, cache, input, output, runtime, token,
or rollback copy from C drive.

## Scope and safety boundary

The operation is intentionally destructive and has no C-drive rollback. It may
delete only these verified Worker-owned targets:

- `C:\AI-Drawing-Worker`
- `C:\AI-Drawing-Worker-Source`
- `C:\ProgramData\AI-Drawing-Worker`
- `D:\code\AI-Drawing-Worker` left by failed migration attempts
- the three fixed AI-Drawing Worker scheduled tasks
- the fixed `AI-Drawing NVIDIA Worker` firewall rule
- obsolete `AI-Drawing-NVIDIA-Worker-fixed-*` ZIPs and extracted directories in
  the current user's Downloads directory

The operation must not delete or modify `D:\code\ai-drawing`, unrelated files
under `D:\code`, or any directory whose ownership marker and expected layout
cannot be verified. It must enumerate and report destructive targets and their
sizes before deletion. It must stop the fixed tasks and exact 8188/8791 listener
processes before removing the owned roots.

## Architecture

The installer receives one canonical managed root rather than installing to C
and relocating afterward. For this installation the root is fixed to
`D:\code\AI-Drawing-Worker`. All path derivation for config, releases, shared
data, updater runtime, launchers, firewall configuration, scheduled tasks, and
ProgramData updater metadata uses that canonical root.

The managed layout remains:

```text
D:\code\AI-Drawing-Worker
├── config
├── releases\<source-commit>
├── current -> releases\<source-commit>
├── shared\models
├── shared\cache
├── shared\partial
├── shared\input
├── shared\output
├── updater
└── updater-runtime
```

`C:\ProgramData\AI-Drawing-Worker` remains a small privileged control-plane
directory. It contains no models or generated images and records the D-drive
Worker root for updater/restart operations.

## Installation flow

1. Build and verify the direct-to-D distribution from the local `main` source.
2. As Administrator, inventory the exact deletion targets, validate ownership,
   and display their sizes.
3. Stop the fixed Worker, updater, and restart tasks and the exact listeners on
   ports 8188 and 8791.
4. Unregister the fixed tasks and firewall rule.
5. Remove the verified C-drive Worker roots, the failed D target, and obsolete
   Worker packages. No old model, cache, input, output, token, pairing file, or
   migration backup is retained.
6. Securely create the D managed root and the ProgramData control root.
7. Generate a cryptographically random new Worker token and write a new config
   and pairing file without printing the token.
8. Install the pinned Python runtime, CUDA PyTorch packages, ComfyUI, custom
   nodes, updater runtime, and the first versioned release directly under D.
9. Register Worker/restart/updater tasks whose actions and fixed environment
   resolve the D root.
10. Start the Worker and run the health gate.

## Health and completion gate

Installation is successful only when all of the following hold:

- the Worker scheduled task remains running;
- ComfyUI listens on loopback port 8188 and `/system_stats` reports CUDA;
- Worker listens on port 8791 and rejects an unauthenticated status request;
- an authenticated status request reports protocol 2, the expected source
  commit, ComfyUI ready, update capability, and restart capability;
- PyTorch reports CUDA available and identifies the NVIDIA GPU;
- `current` is a verified junction to the expected D release;
- ProgramData updater configuration names the D Worker root;
- no old C Worker root or source checkout remains;
- the new pairing file exists and the token is never printed or committed.

The Mac operator must import the new pairing file. The previous pairing is
expected to stop working.

## Failure handling

Because the user explicitly chose a destructive clean install, failure does not
restore the old C Worker. The installer must preserve the failed D installation
and its logs for diagnosis, report a specific stage/error code, and avoid
re-running destructive cleanup on retries. A retry resumes or repairs only the
verified D-owned root.

## Testing

Tests must cover:

- every installed path derives from the D root and no production launcher or
  task action retains `C:\AI-Drawing-Worker`;
- destructive cleanup accepts only the exact ownership-marked targets and
  rejects reparse points, unexpected owners, unexpected paths, and the
  development repository;
- a new token is generated and the previous token is not copied;
- tasks and ProgramData configuration point to D;
- CUDA packages are installed last and the CUDA activation gate is mandatory;
- clean-install retries do not repeat broad deletion;
- the distribution directory and ZIP match source bytes;
- a Windows end-to-end harness reaches the D-root health contract.

## Out of scope

- Preserving any current models, cache, input, output, logs, token, pairing, or
  rollback data.
- Repairing or continuing the existing C-to-D migration transaction.
- Changing the Mac Backend auto-update policy before the new Worker passes live
  verification.
