# Mac-Managed Windows Worker Updates Design

## Goal

Allow the Mac Backend to detect that its paired Windows Worker was built from a
different `origin/main` commit and automatically update the complete Windows
Worker runtime without Windows-side confirmation. Updates include Worker code,
Python, CUDA PyTorch, ComfyUI, custom nodes, and their dependencies while
preserving configuration, tokens, models, cache, partial transfers, inputs, and
outputs.

The first release trusts the private home LAN and continues using the existing
HTTP bearer-token channel. It does not add HTTPS, certificate pinning, or a
second update token.

## Source and Runtime Boundaries

The Windows source repository and deployed runtime remain separate:

```text
D:\code\ai-drawing
    Git source repository used only while preparing an update

D:\code\AI-Drawing-Worker
    deployed, independently runnable Worker environment
```

Normal generation never reads the source repository. The deployed Worker keeps
working if the source checkout is absent or temporarily unusable. During an
update, an independent updater obtains an exact Git commit and constructs a new
release without modifying the source checkout's branch, index, tracked files,
or untracked files.

## Local Updater Configuration

A stable bootstrap outside the replaceable runtime owns updater configuration:

```text
C:\ProgramData\AI-Drawing-Worker\
├─ UpdaterBootstrap.ps1
└─ updater.env
```

`updater.env` contains:

```env
AI_DRAWING_PROJECT_ROOT=D:\code\ai-drawing
AI_DRAWING_WORKER_ROOT=D:\code\AI-Drawing-Worker
AI_DRAWING_WORKER_REMOTE=origin
AI_DRAWING_WORKER_BRANCH=main
```

The bootstrap accepts no paths, URLs, branches, commands, or installer
arguments from the Mac request. It loads the local file and validates that:

- all paths are absolute local drive paths, not UNC paths;
- project root is a Git repository whose configured remote matches the
  installer-recorded expected repository;
- Worker root contains the installer ownership marker;
- project and Worker roots are distinct and neither contains the other;
- remote and branch use the locally configured allowlisted values;
- the configuration file is not stored in Git and is readable only by the
  required Windows identities.

Mac `.env` contains only the existing URL/token plus the feature flag:

```env
NVIDIA_WORKER_URL=http://WINDOWS_IP:8791
NVIDIA_WORKER_TOKEN=...
NVIDIA_WORKER_AUTO_UPDATE=true
```

## Versioned Runtime Layout

The migrated Worker root uses immutable releases and shared mutable data:

```text
D:\code\AI-Drawing-Worker\
├─ config\
│  └─ worker.json
├─ shared\
│  ├─ models\
│  ├─ cache\
│  ├─ partial\
│  ├─ input\
│  └─ output\
├─ releases\
│  ├─ <previous-commit>\
│  └─ <current-commit>\
│     ├─ app\
│     ├─ python\
│     ├─ ComfyUI\
│     ├─ worker-manifest.json
│     └─ release-state.json
├─ current\                 directory junction to one release
├─ updater\
│  ├─ request.json
│  ├─ status.json
│  └─ logs\
└─ tools\
   └─ Restart-Worker.ps1
```

Each release contains its own Python, CUDA PyTorch, ComfyUI source, custom
nodes, and Worker application. ComfyUI model/input/output locations are linked
to `shared`, so release creation and rollback never copy or delete large model
data. The launch path always resolves through `current`.

## Initial C-to-D Migration

Migration from `C:\AI-Drawing-Worker` is a one-time transaction:

1. Validate the current Worker, Token, CUDA runtime, ComfyUI, model directories,
   cache, and partial files and record non-secret inventory hashes/counts.
2. Stop Worker and ComfyUI.
3. Build the first release under the D-drive layout and copy mutable data into
   `shared`, verifying sizes and digests without changing the C-drive source.
4. Create release-local links to shared data and a `current` junction.
5. update scheduled tasks, firewall-independent launch scripts, the one-click
   restart tool, Python path, and ownership markers.
6. Start through `current` and verify authenticated status, workflow preflight,
   ComfyUI object info, and CUDA.
7. Rename the C-drive installation to a dated backup only after all checks pass.

Migration failure restores the original C-drive launch configuration and
restarts the original Worker. The backup is not automatically deleted.

## Update API and Capability Contract

Worker status advertises exact compatibility information:

```json
{
  "protocol_version": 2,
  "worker_version": "0.3.0",
  "source_commit": "40-character-git-sha",
  "update_capability": 1,
  "update_state": "idle"
}
```

The authenticated update endpoint accepts only:

```http
POST /v1/admin/update
Authorization: Bearer <existing-worker-token>
Content-Type: application/json

{"target_commit":"40-character-git-sha"}
```

It validates syntax, serializes a fixed request file, and invokes the
on-demand, highest-privilege `AI-Drawing Worker Updater` scheduled task. The
Worker process never installs or overwrites itself. The updater is a separate
process anchored by the ProgramData bootstrap.

Status is available from:

```text
GET /v1/admin/update/status
```

When the Worker is temporarily offline, the Mac treats connection failure as
expected only after it has received an update request ID. After restart, it
resumes polling and correlates the same request ID from persisted status.

## Git Trust and Build Rules

The Mac derives its exact commit with `git rev-parse HEAD`. Automatic update is
allowed only when that commit is the Mac repository's current `origin/main`.

The Windows updater:

1. acquires a global OS update mutex;
2. runs `git fetch <configured-remote> <configured-branch>` in the configured
   source repository;
3. resolves the fetched remote branch to a full SHA;
4. requires exact equality with `target_commit`;
5. exports that commit into a new staging directory without checking it out in
   the user's working tree;
6. builds and validates the Windows Worker distribution from the exported
   source.

The request cannot select another repository, branch, remote, path, command,
or commit that is not the fetched `origin/main` head. Commit SHA is recorded in
the release state and Worker status.

## Update State Machine

Only one update may run at a time. The updater persists request ID, target
commit, timestamps, current stage, stable error code, and safe message.

```text
queued
→ fetching
→ staging
→ installing
→ validating
→ activating
→ restarting
→ ready
```

Terminal alternatives are:

```text
rejected
failed_before_activation
rolled_back
recovery_required
```

Duplicate requests for the active target return the existing request ID.
Requests for a different target while an update runs return `409
worker_updating`. Generation and new resource-plan requests also return `409
worker_updating`; already-written partial content remains in shared storage.

## Staging and Validation

Before activation, staging must prove:

- fetched commit equals the requested and configured remote-branch head;
- manifest schema, protocol version, runtime pins, and custom-node revisions are
  valid;
- Python installation succeeds;
- CUDA-index PyTorch is installed and `torch.cuda.is_available()` is true;
- GPU device name is available;
- pinned ComfyUI and custom-node revisions are exact;
- required Python requirements install successfully;
- Worker contract tests pass against the staged app;
- ComfyUI starts on staging-only loopback ports and responds to `/system_stats`
  and `/object_info`;
- staged Worker responds to authenticated status, resource plan, and workflow
  preflight on a staging-only loopback port;
- no config, token, model, cache, partial, input, or output data was written
  inside the immutable release.

External programs must have their exit codes checked. A non-zero Git, uv, pip,
Python, ComfyUI, or health-check result fails staging and cannot activate.

## Activation and Rollback

Activation is deliberately short:

1. record the previous release and junction target;
2. stop production Worker and ComfyUI;
3. atomically replace `current` with a junction to the staged release;
4. start through the stable launch script;
5. verify production ports, authenticated status, exact source commit,
   preflight, ComfyUI, and CUDA.

If production validation fails, the updater stops the failed release, restores
the previous junction, starts the previous release, and verifies recovery. A
successful recovery records `rolled_back`. Failed recovery records
`recovery_required` and preserves every release, staging directory, request,
and log for manual repair.

The updater retains the current and immediately previous successful releases.
It removes older releases only after a later release has completed production
validation. It never removes shared data. On power loss, `current` still points
to the last fully activated release; an incomplete staging directory is never
launched.

## Mac Backend Automation

The Mac performs the compatibility check at Backend startup and immediately
before Worker-targeted submission:

1. read local full commit SHA and verify it equals local `origin/main`;
2. obtain Worker status;
3. if source commits match, continue normally;
4. if they differ and auto-update is enabled, submit the update request;
5. poll persisted status for up to 30 minutes, tolerating the expected restart
   outage;
6. require `ready`, matching source commit, protocol compatibility, and
   successful preflight;
7. retry the original generation submission once.

The Backend never retries indefinitely and never falls back to local generation
after the user selected Worker execution. Startup update runs in a managed
background task so local Backend, local ComfyUI, and the Bot remain available.
A Worker-targeted request waits for that same task rather than launching a
second update.

## Authentication and Logging

Per the accepted threat model, update endpoints reuse the current Worker bearer
token over private-LAN HTTP. No Windows password, administrator credential, or
GitHub password crosses the API. The public Git remote requires no credential.

Tokens remain in local configuration and authorization headers. They are never
accepted in URLs or command-line arguments and are excluded from request files,
status files, logs, subprocess output, exception serialization, and API error
bodies. Logs contain request ID, commit, stage, timestamps, stable error codes,
and redacted messages only.

## Error Contract

Errors use stable codes and repair hints, including:

- `UPDATE_ALREADY_RUNNING`
- `TARGET_COMMIT_INVALID`
- `MAC_COMMIT_NOT_ORIGIN_MAIN`
- `WINDOWS_REMOTE_HEAD_MISMATCH`
- `UPDATER_CONFIG_INVALID`
- `SOURCE_REPOSITORY_INVALID`
- `INSUFFICIENT_DISK_SPACE`
- `RUNTIME_INSTALL_FAILED`
- `CUDA_VALIDATION_FAILED`
- `COMFYUI_VALIDATION_FAILED`
- `WORKER_CONTRACT_FAILED`
- `ACTIVATION_FAILED_ROLLED_BACK`
- `RECOVERY_REQUIRED`

Errors identify the failed stage and next safe action without exposing secrets
or arbitrary subprocess command lines.

## Testing and Acceptance

Unit tests cover env parsing, canonical-path validation, Git remote/commit
validation, request schema, idempotency, state transitions, lock behavior,
redaction, retention, and stable errors.

Integration tests use temporary Git repositories and fake runtimes to cover
fetch/export, exact-commit enforcement, staging, shared-data isolation, atomic
junction switching, duplicate requests, failed activation, successful rollback,
failed rollback, and recovery after an interrupted update.

Backend tests cover startup detection, pre-submit detection, one managed update
task, expected Worker outage, 30-minute timeout, successful revalidation,
single retry, and fail-closed behavior.

Windows real-host acceptance covers:

- C-to-D migration with token/model/cache/partial preservation;
- a complete main-to-new-main runtime update;
- Python, CUDA PyTorch, ComfyUI, and custom-node pin changes;
- duplicate requests;
- network interruption during fetch;
- package-install and staged-health failures;
- production-health failure and rollback;
- reboot during staging and recovery from `current`;
- Mac Backend startup auto-update;
- automatic update immediately before generation;
- successful post-update prompt ID and retrieved Gallery image.

Acceptance requires a Mac commit mismatch to trigger and complete an unattended
Windows update, followed by a successful Worker generation, with no Windows
confirmation and no loss or disclosure of preserved data.
