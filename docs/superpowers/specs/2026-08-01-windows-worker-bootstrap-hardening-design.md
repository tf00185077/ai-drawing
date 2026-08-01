# Windows Worker Bootstrap Hardening Design

## Problem

The Windows Worker installer at commit `c49828386da8f76c2b3be356f712e674e7435249` fails on a real Windows 11 upgrade in two deterministic ways:

1. `uv pip install --python <standalone-python>` refuses to modify the uv-managed interpreter because it is externally managed. The installer does not check those subprocess exit codes and continues with an incomplete runtime.
2. `uv python install` creates a version alias junction below `runtime/python`. The first managed-runtime bootstrap subsequently performs a fail-closed, no-follow inventory and raises `MIGRATION_REPARSE_POINT` for that installer-created alias.

The migration's general reparse-point rejection is a security boundary and must remain fail-closed.

## Goals

- Install dependencies into the intended uv standalone Python explicitly and fail immediately when any required dependency installation fails.
- Remove only trusted uv Python alias junctions before the managed-runtime inventory.
- Resolve and persist the concrete Python executable path before removing an alias.
- Preserve rejection of unknown, external, nested, or otherwise unsafe reparse points.
- Keep existing Worker tokens, models, cache, input, output, and rollback data intact.
- Rebuild the checked-in Windows distribution directory and ZIP from source and verify source/dist parity.

## Non-goals

- Redesigning the Worker runtime around a new virtual-environment layout.
- Relaxing the migration inventory to follow junctions or symbolic links.
- Automatically deleting arbitrary reparse points.
- Changing the Mac update coordinator or enabling automatic updates.

## Design

### Dependency installation

Every `uv pip install` invocation that targets the uv standalone interpreter will include `--system`, which is uv's explicit opt-in for modifying an interpreter outside a virtual environment. A small PowerShell helper will run required external commands and throw a stable installer error when `$LASTEXITCODE` is non-zero. ComfyUI, PyTorch, Worker, and custom-node requirements will all use this gate.

### Python path selection

After `uv python install`, the installer will enumerate candidate `python.exe` files without traversing reparse points and select one located below a concrete, non-reparse version directory. It will reject missing, ambiguous, or reparse-backed candidates. `config/python-path.txt` will contain this concrete path.

### Trusted alias normalization

Before `Initialize-ManagedWorkerLayout`, the installer will inspect only direct children of `runtime/python`. A junction may be removed only when all of these conditions hold:

- it is a directory junction, not a symbolic link or other reparse type;
- its leaf name matches the uv CPython alias naming convention;
- its target resolves beneath the same canonical `runtime/python` directory;
- the target is an existing concrete directory and is not itself a reparse point;
- the selected concrete Python executable is not beneath the alias path.

Anything outside that narrow contract remains untouched. The managed migration then runs unchanged and continues to reject all remaining reparse points.

### Failure handling

Installer failures remain terminating errors. No dependency-install error may be treated as a warning. Alias validation fails before removal if any invariant is uncertain. Setup does not start the Worker or advertise protocol 2/update capability unless managed bootstrap validation succeeds.

## Tests

- Contract tests verify all required `uv pip install` calls opt into `--system` and are exit-code gated.
- Windows PowerShell integration tests create a safe internal uv-style junction and verify normalization removes only the alias while preserving the concrete target.
- Windows integration tests verify external-target, nested-target-reparse, wrong-name, and non-junction reparse points are rejected or preserved and still cause migration failure.
- Tests verify concrete Python selection does not traverse or persist an alias path.
- Existing focused Worker gates run after the new regression tests.
- The distribution build runs, followed by byte/content parity checks and ZIP SHA-256 reporting.

## Delivery and live recovery

The source files under `worker/windows` are authoritative. The distribution build refreshes `dist/AI-Drawing-NVIDIA-Worker` and `dist/AI-Drawing-NVIDIA-Worker.zip`. After verification, the repaired package is used to rerun Setup on the current Windows host. Only after Setup reports success and the Worker is healthy will the documented `C:\AI-Drawing-Worker-Source\worker\windows\Migrate-Worker.ps1` D-drive migration be attempted.
