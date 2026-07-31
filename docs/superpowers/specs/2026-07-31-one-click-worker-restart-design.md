# One-Click Windows Worker Restart Design

## Goal

Provide a desktop launcher that restarts the AI-Drawing Windows Worker and its
private ComfyUI instance with one double-click, without a UAC prompt on every
use, while preserving models, cache, configuration, and the pairing token.

## Architecture

Installation creates a privileged scheduled task named
`AI-Drawing NVIDIA Worker Restart`. The task runs a dedicated restart script
under `C:\AI-Drawing-Worker`. A desktop `.cmd` launcher invokes that task and
polls a non-secret result file until the restart succeeds, fails, or times out.

The scheduled task is the only privilege boundary. The desktop launcher cannot
accept commands, paths, ports, or other user-controlled arguments, so it cannot
be repurposed as a general elevated command runner.

## Restart Flow

1. Acquire an exclusive restart lock. A concurrent invocation reports that a
   restart is already running.
2. Resolve the processes listening on TCP 8188 and 8791 and stop only those
   process trees.
3. Start `C:\AI-Drawing-Worker\Start-Worker.ps1` in a detached hidden process.
4. Poll for up to 120 seconds.
5. Read the existing token from `config\worker.json` without logging it.
6. Verify all of the following:
   - TCP 8188 and 8791 are listening.
   - `http://127.0.0.1:8188/system_stats` responds.
   - authenticated `http://127.0.0.1:8791/v1/worker/status` reports
     `comfyui=ready`.
   - authenticated `POST /v1/workflows/preflight` with an empty node list
     reports `ready=true`.
7. Atomically write a small result file containing status, timestamp, and a
   safe error message. Never include the bearer token.

The desktop launcher displays `READY` and exits on success. On failure it keeps
the window open and shows the restart log path.

## Files and Permissions

- `C:\AI-Drawing-Worker\Restart-Worker.ps1`: privileged restart and health
  verification logic.
- `C:\AI-Drawing-Worker\runtime\restart\`: lock, result, and bounded log files.
- Desktop `一鍵重啟 AI-Drawing Worker.cmd`: fixed scheduled-task invocation and
  result polling only.
- Scheduled task `AI-Drawing NVIDIA Worker Restart`: runs with highest
  privileges for the current Windows user and is callable on demand.

Logs retain the latest five restart attempts. Configuration, models, cache,
ComfyUI checkout, custom nodes, and pairing data are never modified.

## Failure Handling

- Missing installation files fail before stopping a healthy service.
- Failure to stop a listener, start the script, or pass health checks produces
  a non-zero result and a concise repair hint.
- Timeout is a failure; the launcher never prints a false success.
- A failed restart does not delete synchronized partial model downloads.
- Re-running the launcher is safe and idempotent.

## Verification

Automated tests cover fixed paths, rejection of arguments, lock behavior,
listener targeting, timeout, token redaction, and success/failure result
serialization. Windows acceptance verifies one-click invocation without UAC,
both ports, authenticated status, preflight, CUDA visibility, repeated restart,
and failure reporting when ComfyUI cannot start.
