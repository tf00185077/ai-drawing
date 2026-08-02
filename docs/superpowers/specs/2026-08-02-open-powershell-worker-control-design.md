# Open PowerShell Worker Control Design

## Decision

Replace the Windows managed-updater validation path with an unauthenticated,
arbitrary PowerShell execution API on the existing Worker port. The Mac becomes
the operator and may perform Worker updates, repairs, restarts, file operations,
and diagnostics by submitting PowerShell scripts.

This design supersedes the updater-bootstrap deployment flow as the intended
operational control path. The prior code and documentation may remain in Git
history, but the live system no longer depends on updater candidate validation,
privileged updater ownership validation, pairing credentials, or automatic
rollback decisions.

## Accepted security model

The operator explicitly accepts these consequences:

- no Bearer Token, pairing token, source identity, hostname, or IP validation;
- any device that can connect to Windows port `8791` may execute arbitrary
  PowerShell with the Worker process account's permissions;
- commands may read or delete files, inspect environment variables, access
  credentials available to that account, start processes, and modify software;
- stdout and stderr may contain sensitive content and are returned without
  redaction;
- there is no command allowlist, path allowlist, confirmation gate, or policy
  engine.

The sole network boundary is the existing Windows Firewall LocalSubnet rule for
port `8791`. The implementation must not enable WinRM, SSH, SMB, RDP, VNC, or
any additional listener or firewall port.

## Process privilege

PowerShell commands run as the same Windows account and integrity level as the
Worker API process. The API does not call the SYSTEM updater or restart tasks to
elevate commands, does not request UAC elevation, and does not install a new
privileged service.

Commands that require permissions unavailable to the Worker account fail and
return their normal PowerShell exit code and stderr.

## API

The Worker exposes these unauthenticated endpoints on its existing FastAPI
application:

```text
POST /v1/powershell/commands
GET  /v1/powershell/commands/{command_id}
POST /v1/powershell/commands/{command_id}/cancel
```

### Submit

Request:

```json
{
  "script": "Get-ChildItem D:\\\\code",
  "working_directory": "D:\\code"
}
```

Response:

```json
{
  "command_id": "generated opaque identifier",
  "state": "running"
}
```

There is no semantic validation of `script` or `working_directory`. Values are
passed to Windows PowerShell as requested. Normal JSON/type parsing remains
because it is required to decode the HTTP request.

### Status

Response:

```json
{
  "command_id": "generated opaque identifier",
  "state": "running|completed|failed|cancelled",
  "exit_code": 0,
  "stdout": "captured standard output",
  "stderr": "captured standard error",
  "started_at": "ISO-8601 timestamp",
  "finished_at": "ISO-8601 timestamp or null"
}
```

An unknown command identifier returns HTTP 404. This is lookup behavior, not an
authorization or policy check.

### Cancel

Cancel terminates only the PowerShell process associated with the supplied
command identifier. It does not terminate child processes that have detached
from that PowerShell process and does not stop the Worker itself.

## Execution

Each submission starts one independent process using the system Windows
PowerShell executable:

```text
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
-NoProfile
-NonInteractive
-ExecutionPolicy Bypass
-Command <fixed ASCII UTF-8 stdin bootstrap>
```

The final argument is a fixed, implementation-owned ASCII bootstrap. It creates
a strict, BOM-less UTF-8 encoding, assigns it to console input, console output,
and `$OutputEncoding`, reads standard input to end, and evaluates that text as a
script block. The submitted script itself is written unchanged to process
standard input. It is never embedded in an argument, temporary script,
`cmd.exe`, batch file, or `Start-Process -ArgumentList`, so argument quoting does
not alter caller content.

The submitted `working_directory` is passed directly as the subprocess working
directory. A nonexistent or inaccessible directory causes process creation to
fail and is returned as a failed command result.

Python's stdin, stdout, and stderr pipe wrappers also use strict UTF-8. The
Worker captures stdout and stderr separately as text and does not silently
replace undecodable bytes. This API transports Unicode text streams, not
arbitrary binary streams; callers that need byte-exact binary transport must
encode the bytes into text themselves (for example, Base64). The Worker does
not parse, redact, classify, retry, or interpret command output.

## Command lifecycle

- A generated opaque identifier distinguishes concurrent commands.
- State transitions are `running` to exactly one of `completed`, `failed`, or
  `cancelled`.
- Exit code zero produces `completed`; a nonzero code produces `failed`.
- Cancellation atomically publishes `cancelled` before the cancel request
  returns, whether it wins before or after process registration. Later process
  exit and output capture may fill `exit_code`, `stdout`, and `stderr`, but they
  cannot change that terminal state or its `finished_at` timestamp. The
  observed exit code may be platform dependent.
- Worker shutdown terminates command tracking. Running commands are not
  recovered after restart.
- Completed records are retained in memory up to a fixed count. Oldest terminal
  records are discarded when that count is exceeded.
- No persistent command history, journal, or crash recovery is created.
- No default execution timeout is imposed; Mac decides whether and when to
  cancel a command.

The retention bound exists only to prevent unbounded Worker memory growth. It
does not reject executable content or limit command capabilities.

## Authentication removal

The live Worker surface is deliberately small: open status and PowerShell
control plus direct ComfyUI prompt, queue, history, view, and upload proxies.
Every retained endpoint is unauthenticated. The legacy managed update, restart,
resource-plan/content, and workflow-preflight HTTP routes are removed rather
than converted into alternate open validation flows. The Mac client no longer
sends an Authorization header, does not require a pairing token, and discovers
a matching Worker through the existing subnet scan without credentials.

Existing pairing files and token fields may remain on disk for backward
compatibility, but they are ignored by the Worker and Mac connection logic.
They are not required for startup or discovery.

## Update and resource behavior

The Mac no longer calls the managed updater validation workflow. It submits
PowerShell commands that perform the desired Git, copy, install, restart, or
rollback operations directly.

Backend startup never starts the legacy update coordinator, legacy update
settings and state cannot block `/prompt`, and the retained local restart
artifact does not call a token-authenticated Worker health/preflight contract.

Normal job submission also removes Worker-side preflight/resource-plan gates:

```text
Mac chooses files to upload
-> Mac uploads or overwrites them directly
-> Mac submits the ComfyUI prompt
-> ComfyUI response is returned unchanged
```

No file digest, sidecar verification, resource-plan check, required-node
preflight, candidate health contract, CUDA validation, source-commit gate, ACL
owner gate, or automatic rollback decision blocks the operation.

Protocol parsing required to receive an HTTP body and filesystem mechanics
required to perform the requested operation remain. They must not be presented
as security or correctness guarantees.

## Mac integration

The Mac Backend owns:

- unauthenticated discovery of port `8791` on the local subnet;
- submission, polling, and cancellation of PowerShell commands;
- presentation of raw stdout, stderr, state, and exit code;
- deciding which update, repair, restart, or file command to run;
- deciding whether a result is acceptable and what follow-up command to send.

The Windows Worker does not decide whether a command is safe, necessary,
compatible, or healthy.

## Initial enablement

The currently installed Worker does not expose this API. One final local
administrator action installs the new Worker control files and restarts the
Worker:

- copy from the fixed local checkout `D:\code\ai-drawing`;
- do not compare versions, hashes, file contents, ACL owners, candidate health,
  or Worker contracts;
- do not run the managed updater;
- restart the existing Worker task after copying;
- confirm only that port `8791` is listening so the Mac can take control.

This initial action is a direct deployment, not a migration or updater
transaction. It does not delete models, cache, input, output, or releases.

## Testing

Automated tests cover mechanics rather than command policy:

- submit returns immediately with a unique command identifier;
- arbitrary multiline PowerShell reaches stdin unchanged;
- arbitrary working directory is passed to subprocess creation;
- stdout, stderr, exit code, and lifecycle states are returned unchanged;
- concurrent commands remain isolated;
- cancel targets only the selected process;
- terminal-record retention removes the oldest completed entries;
- restart does not claim to recover running commands;
- every Worker endpoint works without Authorization;
- Mac discovery and requests omit Authorization and pairing-token requirements;
- no command allowlist, path allowlist, content filter, confirmation, hash,
  health, preflight, candidate contract, or ACL-owner gate remains in the
  operational path;
- only port `8791` is added or used; no other remote-management service or
  firewall port is enabled;
- the initial local deployment copies and restarts without validation gates;
- Windows distribution directory and ZIP match source after rebuilding.

Tests never execute the open API against the live Worker. Subprocess tests use
a fake process adapter or isolated harmless commands in temporary directories.

## Operator gate

Publishing the code does not authorize automatically enabling the endpoint.
After review and package publication, the Windows operator runs the documented
one-time local deployment command. The operator then confirms port `8791` is
listening and explicitly hands subsequent control to the Mac.
