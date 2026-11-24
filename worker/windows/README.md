# AI-Drawing Windows Worker

Runs next to ComfyUI on a same-LAN Windows machine. Setup, endpoints and Backend settings: [docs/windows-worker.md](../../docs/windows-worker.md). Behavior details: [worker PowerShell control](../../docs/memory/worker-powershell-control.md).

## Security boundary

Port 8791 accepts unauthenticated PowerShell from any host that can reach it, run as the Windows account of the `AI-Drawing NVIDIA Worker` scheduled task. Keep the port reachable only from the Backend host on the private LAN. No other listener (WinRM, SSH, SMB, RDP, VNC) is enabled.

## Command lifecycle

- `POST /v1/powershell/commands` submits a script and optional working directory.
- `GET /v1/powershell/commands/{command_id}` reads its record.
- `POST /v1/powershell/commands/{command_id}/cancel` cancels it; `cancelled` is final once returned.

Records live in worker memory and are lost on restart.

## PowerShell 5.1 text transport

Scripts are passed on stdin to Windows PowerShell 5.1 with strict UTF-8; stdout and stderr return separately as text. Base64-encode binary data.

## Generation behavior

Generation goes straight to ComfyUI `/prompt`; ComfyUI returns missing-resource, node and capacity errors. Updates and restarts are ordinary scripts sent through the command routes.

## One-time enablement

In Windows PowerShell 5.1 as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& "<repo>\worker\windows\Enable-Open-PowerShell-Control.ps1" -ExpectedCommit "<40-character commit on origin/main>"
```

The script requires `HEAD` and `origin/main` to equal `-ExpectedCommit`, copies the control files into the installed runtime and restarts the scheduled task.
