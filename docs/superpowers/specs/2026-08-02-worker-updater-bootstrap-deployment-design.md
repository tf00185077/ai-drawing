# Windows Worker Updater Bootstrap Deployment Design

## Problem

The installed scheduled task executes the fixed bootstrap at
`C:\ProgramData\AI-Drawing-Worker\UpdaterBootstrap.ps1`, which imports the
updater package already installed under the managed Worker root. A candidate
release contains newer updater code, but that code cannot participate in the
validation that decides whether the same candidate may activate. This creates
a bootstrap boundary: updater fixes in a candidate cannot repair the updater
performing that candidate's installation.

The observed production installation proves this boundary. Its installed
`runtime.py`, `windows_runtime.py`, `cli.py`, and `state.py` differ from the
current repository versions, while the scheduled task continues to launch the
installed updater. The candidate therefore fails before activation with the
old updater's generic `WORKER_CONTRACT_FAILED` result.

## Goal

Provide a one-time, administrator-run, transactional deployment path that
updates only the privileged updater package and fixed bootstrap. Preserve the
running production Worker, ComfyUI, models, shared files, pairing state, and
managed releases. A failed bootstrap deployment must restore the previously
installed updater.

## Non-goals

- Do not reinstall or migrate the Worker.
- Do not activate a candidate release.
- Do not submit or retry a remote update request.
- Do not enable automatic updates.
- Do not stop the production Worker or ComfyUI.
- Do not validate updater contents file-by-file.
- Do not calculate or compare file SHA values or other content digests.
- Do not introduce a permanent dual-slot updater architecture.

## Trusted source and version boundary

The deployment command is the tracked script in `D:\code\ai-drawing`. It
accepts a mandatory `-ExpectedCommit` argument and requires all of the
following before staging:

- the repository root resolves exactly to `D:\code\ai-drawing`;
- the active branch is `main`;
- the configured `origin` URL is the expected AI Drawing repository;
- `HEAD` equals `origin/main`;
- `HEAD` equals `-ExpectedCommit`;
- tracked files are clean.

Untracked files are allowed and are neither read nor copied. Git commit
identity is the only content-version boundary. There is no per-file manifest,
file hash, archive hash, or source-to-staging content comparison.

## Components

### `Deploy-UpdaterBootstrap.ps1`

A new Windows PowerShell 5.1-compatible entrypoint performs preflight,
staging, switch, smoke validation, and rollback. It must require an elevated
administrator session and use literal, canonical paths throughout.

### Fixed source set

The transaction copies only:

- `worker\windows\updater\` as the updater Python package;
- `worker\windows\UpdaterBootstrap.ps1` as the ProgramData bootstrap.

The script does not enumerate or consume untracked repository content. It
rejects reparse points in source, staging, installed updater, backup, and
ProgramData-owned paths.

### Secure staging and backup

Staging and backup directories live under a dedicated updater-owned directory
inside the managed Worker root. They are created with the existing
`WorkerSecurity.ps1` primitives and protected with SYSTEM ownership and the
existing updater ACL contract.

Only one transaction may run at a time. A fixed lock owned by this deployment
flow prevents concurrent bootstrap deployments.

## Transaction

1. Verify elevation, PowerShell 5.1 compatibility, trusted repository state,
   Worker ownership marker, installed updater tree, ProgramData tree, and
   absence of reparse points.
2. Stop only the `AI-Drawing Worker Updater` scheduled task and poll until it
   is no longer running. Do not stop the NVIDIA Worker task or ComfyUI.
3. Copy the fixed source set into secure staging.
4. Confirm only structural requirements: required files and package modules
   exist and all staged paths satisfy the no-reparse policy. Do not hash or
   compare file contents.
5. Move the currently installed updater and ProgramData bootstrap to the
   transaction backup.
6. Move the staged updater into the installed updater path and install the
   staged ProgramData bootstrap.
7. Reapply and assert the updater ACL contract on installed and ProgramData
   trees.
8. Run smoke validation with the updater-owned Python:
   - import the updater modules required by the scheduled entrypoint;
   - load the fixed updater configuration;
   - execute managed activation recovery and require exit code zero.
9. Confirm the scheduled task action still invokes the fixed ProgramData
   bootstrap using Windows PowerShell with the required non-interactive
   arguments.
10. Write a non-sensitive transaction result and print
    `UPDATER_BOOTSTRAP_READY`.

The deployment never starts an update. A later Mac smoke must use a new request
ID while `NVIDIA_WORKER_AUTO_UPDATE=false` remains in effect.

## Failure and rollback

Any failure after backup begins triggers rollback:

- remove the failed newly installed updater and bootstrap;
- restore the previous updater and ProgramData bootstrap from backup;
- reapply and assert their protected ACLs;
- run the previous updater import/config smoke;
- leave the production Worker and ComfyUI untouched;
- preserve the backup and a private diagnostic result for inspection.

Public output uses stable error codes and stage names. It must not print
tokens, `updater.env` contents, authorization headers, response bodies, or raw
exception text that may contain protected paths or values. If rollback itself
cannot be proven, the terminal result is `UPDATER_BOOTSTRAP_RECOVERY_REQUIRED`
and no remote update may be attempted.

## Successful cleanup

Remove staging and the transaction lock after success. Retain the immediately
previous updater backup until one later remote update smoke reaches a healthy
terminal state. The backup is small because it contains updater code and the
bootstrap only; it contains no models, virtual environments, releases, cache,
input, or output data.

## Testing

Tests run through the system Windows PowerShell 5.1 executable and cover:

- parser compatibility and paths containing spaces and non-ASCII characters;
- elevation rejection;
- repository path, branch, origin, `HEAD == origin/main`, mandatory
  `-ExpectedCommit`, and tracked-dirty rejection;
- allowance and non-consumption of untracked files;
- reparse-point and invalid ownership/ACL rejection;
- updater-task stop polling without touching Worker or ComfyUI tasks;
- structural staging validation without any file digest operations;
- successful directory switch, ACL repair, import/config/recovery smoke, and
  fixed scheduled-task action validation;
- rollback at every post-backup failure boundary;
- recovery-required behavior when rollback validation fails;
- secret-safe public diagnostics;
- source/distribution/ZIP parity after rebuilding the Windows package.

The test suite must also assert that the deployment script contains no
`Get-FileHash`, SHA, digest-manifest, or equivalent per-file content comparison
gate. Git commit comparison remains required.

## Operator flow

After the reviewed package is published, the Windows operator runs the new
script once from an elevated Windows PowerShell 5.1 session and supplies the
published exact commit. Only after `UPDATER_BOOTSTRAP_READY` and a healthy
production Worker are confirmed may the Mac submit one new remote update
request. Previously failed request IDs are never reused.
