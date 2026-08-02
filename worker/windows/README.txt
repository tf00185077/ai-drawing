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
Cancellation publishes `cancelled` before the cancel response returns. Process
exit and output capture may finish later, but cannot change that terminal state.

PowerShell 5.1 text transport
-----------------------------

The Worker starts the fixed system Windows PowerShell 5.1 executable with a
fixed ASCII bootstrap. The bootstrap sets console input/output to strict UTF-8,
then reads the caller's script from standard input. The submitted script is not
placed in process arguments and no temporary script file is created. Standard
output and standard error are returned separately using strict UTF-8.

This is a Unicode text-stream API, not an arbitrary binary-stream API. A script
that must move byte-exact binary data should encode it as text (for example,
Base64) and decode it at its destination.

Generation behavior
-------------------

Ordinary generation is sent directly to ComfyUI at `/prompt`. It does not use
`/v1/resources/plan`, `/v1/workflows/preflight`, resource planning, or managed
updater coordination. ComfyUI directly returns missing-resource, node, and
capacity errors to the caller.

The live Worker has no managed update, managed restart, resource-plan/content,
or workflow-preflight HTTP routes. Update, repair, and restart actions are
ordinary scripts submitted through the open PowerShell command routes. Backend
startup does not launch the retired managed-update coordinator, and legacy
update state cannot block `/prompt`.

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
