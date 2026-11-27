---
name: windows-worker-offline-test-limits
description: "Off-Windows tests that reach worker process creation need a stub for the Windows-only subprocess.CREATE_NO_WINDOW constant."
metadata:
  type: project
  curated_on: "2026-11-25"
---

## Context

The PowerShell command manager evaluates `subprocess.CREATE_NO_WINDOW` before invoking its process factory. The constant is absent on macOS and Linux, so a fake factory alone cannot exercise that process-creation path there.

## Why

Without a stub, a test reaches the platform-constant error before its fake process runs.

## How to apply

Stub the constant only for off-Windows tests that need the process-creation path, and report fake-process results as mocked. Keep real PowerShell integration checks Windows-only.

## Evidence

- [PowerShell command manager](../../worker/windows/powershell_control.py) — constant evaluated in `_run_command`.
- [Worker control tests](../../backend/tests/test_worker_powershell_control.py) — fake process factory and Windows-only real PowerShell check.
