# Windows worker

A worker lets the Backend run ComfyUI jobs on another Windows machine on the same LAN. The worker is a small FastAPI service next to that machine's ComfyUI.

## Status

**Built:** a worker service that proxies a remote ComfyUI; Backend client with optional LAN discovery and hostname/protocol validation; `execution_target=worker` on generation.

**Verified in a real run:** nothing. The worker has never been installed successfully on the owner's machine.

**Gaps:**
- One worker URL only; no registry, heartbeat or scheduling.
- No check that the worker runs the same project version, nodes and models.
- PowerShell control routes have no authentication.
- Queue limits block parallel workers (see [Architecture → Known limitations](ARCHITECTURE.md#known-limitations-to-optimize)).
- Large updater/migration code for retired APIs.

Overall project state: [CURRENT.md](CURRENT.md).

## How it works

```
Backend ──HTTP :8791──► worker.py ──loopback──► ComfyUI :8188 (on the worker host)
```

- The Backend sends a job with `execution_target=worker` to the worker instead of local ComfyUI.
- The worker forwards `/prompt`, `/queue`, `/history/{prompt_id}`, `/view` and `/upload/image` to its local ComfyUI.
- Results are fetched back by the Backend and stored in its Gallery.
- A failed worker job is reported, not retried on local ComfyUI.

## Worker endpoints

Source: `worker/windows/worker.py`.

| Endpoint | Purpose |
|---|---|
| `GET /v1/worker/status` | Status, hostname, protocol version |
| `POST /prompt`, `GET /queue`, `GET /history/{id}`, `GET /view`, `POST /upload/image` | ComfyUI proxy |
| `POST /v1/powershell/commands` | Run a PowerShell script |
| `GET /v1/powershell/commands/{id}` | Command status and output |
| `POST /v1/powershell/commands/{id}/cancel` | Cancel a command |

**The PowerShell routes have no authentication.** Anyone who can reach port 8791 can run commands as the worker's Windows account. Keep the port reachable only from the Backend host on the private LAN.

Worker settings: `AI_DRAWING_COMFYUI_URL` (default `http://127.0.0.1:8188`, must be loopback). The worker listens on `0.0.0.0:8791`.

## Backend settings

In `.env` / `backend/app/config.py`:

| Setting | Purpose |
|---|---|
| `NVIDIA_WORKER_URL` | Worker base URL, e.g. `http://192.168.1.20:8791` |
| `NVIDIA_WORKER_TIMEOUT` | Request timeout (seconds) |
| `NVIDIA_WORKER_HOSTNAME` | Expected worker hostname; checked against `/v1/worker/status` |
| `NVIDIA_WORKER_PROTOCOL_VERSION` | Expected protocol version (default 2) |
| `NVIDIA_WORKER_DISCOVERY_ENABLED` | Scan the LAN when the worker URL stops answering (default off) |
| `NVIDIA_WORKER_DISCOVERY_CIDR` | `/24` range to scan |

Discovery runs only on connection errors, scans the CIDR on port 8791 and accepts exactly one host whose hostname and protocol match. The found URL is cached in memory until the Backend restarts.

`setup`/`reconfigure` drop these keys from `.env`; re-add them afterwards.

Backend source: `backend/app/services/nvidia_worker.py`, `backend/app/api/workers.py`.

## Read-only status visibility

The accepted `GET /api/workers/status` response extends the existing
`configured`, `reachable`, `status`, failed `error_type` and successful nested
`worker` fields. It adds normalized configured `url`, `expected_hostname`
(null when unset), `expected_protocol_version`, current `hostname`,
`protocol_version`, `resolved_url` and `last_error`. It introduces no new route
or control capability. See [MCP health and worker discovery](mcp.md#health-and-configured-worker).

A successful current `health()` client probe accepts the existing identity
validation before reporting its actual selected endpoint as `resolved_url`.
That endpoint may differ from configuration after existing discovery/cache.
URL-only success can have no hostname. Failed probes retain configuration,
set status unavailable and a safe current error, and clear observed identity
and resolved URL; an old runtime cache remains distinct from this observation.
Success sets `last_error` null. There is no persistent error history.

MCP `list_workers` returns empty only for a successfully read unconfigured
Backend response, one configured entry even when unavailable, or a common
error when Backend configuration cannot be read/validated. MCP `health` keeps
Backend, Backend-local ComfyUI and worker entries on partial/outage reads.
These tools issue existing GET/status requests only. Backend discovery may
perform its existing private-LAN probes; it sends no generation or control.
Reachability proves neither remote ComfyUI nor model/node parity, generation
readiness, source version or artifact access. This source change has offline
route/client/registered-tool checks; deployment and real worker operation
remain unverified. The [p1-04 acceptance](tasks/p1-04-mcp-health-and-workers/acceptance.md)
records the independent exact-commit PASS and source integration.

## Install (current scripts)

Scripts in `worker/windows/`:

| Script | Purpose |
|---|---|
| `Setup.cmd`, `Install-Worker.ps1`, `WorkerInstall.ps1` | Install the worker runtime and scheduled task |
| `Start-Worker.ps1` | Start ComfyUI on loopback and the worker on port 8791 |
| `Restart-Worker.ps1`, `Uninstall-Worker.cmd` | Restart, uninstall |
| `Enable-Open-PowerShell-Control.ps1` | Deploy the PowerShell control files to an installed worker |
| `Migrate-Worker.ps1`, `Deploy-UpdaterBootstrap.ps1`, `updater/` | Legacy updater and migration (to be removed) |

`scripts/build-windows-worker.py` builds the `dist/AI-Drawing-NVIDIA-Worker` package. Worker Python dependencies: `worker/windows/requirements.txt`.

## Known limits

- One worker URL only; no registry or load balancing.
- No check that the worker runs the same project commit, custom nodes and models.
- Worker command records live in memory and are lost on restart.
- Tests that create processes use `subprocess.CREATE_NO_WINDOW`, which exists only on Windows.
