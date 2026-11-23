# Windows worker

A worker lets the Backend run ComfyUI jobs on another Windows machine on the same LAN. The worker is a small FastAPI service next to that machine's ComfyUI.

Status and gaps: [STATUS.md](STATUS.md#3-lan-windows-workers). No worker has been installed successfully yet; the design is planned for rework in Phase 3 ([roadmap](roadmap/ROADMAP.md)).

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
