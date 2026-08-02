AI-Drawing Windows Worker: open PowerShell control
===================================================

Security boundary
-----------------

TCP port 8791 accepts unauthenticated arbitrary PowerShell from any host that
can reach it. Treat network access to this port as full control of the Windows
account running the existing `AI-Drawing NVIDIA Worker` scheduled task. This is
an intentional high-risk open-control interface, not a paired or token-authenticated
service.

Commands run as the Windows account configured for that existing scheduled
task. They do not automatically run as SYSTEM. Pairing and token files are
legacy compatibility artifacts and are ignored by open-control Worker requests.

Open control uses the existing Worker listener on port 8791 only. It does not
enable WinRM, SSH, SMB, RDP, VNC, or any additional Windows listener. Restrict
who can reach port 8791 before enabling this interface.

The Worker exposes these unauthenticated command routes:

* `POST /v1/powershell/commands` submits a script and optional working directory.
* `GET /v1/powershell/commands/{command_id}` reads its lifecycle record.
* `POST /v1/powershell/commands/{command_id}/cancel` requests cancellation.

Command records and active-process state live only in Worker memory. They are
lost when the Worker restarts; a previous command ID then cannot be recovered.

Generation behavior
-------------------

Ordinary generation is sent directly to ComfyUI at `/prompt`. It does not use
`/v1/resources/plan`, `/v1/workflows/preflight`, resource planning, or managed
updater coordination. ComfyUI directly returns missing-resource, node, and
capacity errors to the caller.

One-time enablement
-------------------

Open Windows PowerShell 5.1 as Administrator and run exactly:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& "D:\code\ai-drawing\worker\windows\Enable-Open-PowerShell-Control.ps1" `
    -ExpectedCommit "<40-character commit shown after the final push>"
```

The angle-bracket value is documentation notation, not executable code. In the
final operator handoff, replace it with the actual 40-character commit shown
after the final push.

The deployment script fetches `origin/main`, requires `HEAD == origin/main`,
and requires the supplied `-ExpectedCommit` to match both. These are its only
deployment version checks. It copies the two open-control Worker files into the
installed current runtime and restarts the existing Worker scheduled task; it
does not create another service, listener, or updater workflow.
