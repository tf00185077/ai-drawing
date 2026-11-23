---
name: windows-worker-offline-test-limits
description: "Recognize the CREATE_NO_WINDOW host limitation before interpreting mocked Worker process checks as Windows evidence."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

The inspected Worker constructs its process with `subprocess.CREATE_NO_WINDOW`. On the recorded macOS Python environment that constant was absent, so fake-process checks failed before their factories ran. An explicitly stubbed offline runner could exercise those mocks while the real Windows PowerShell check remained skipped.

## Why

A host-specific Python limitation can hide a useful source regression; a test-only replacement still cannot verify Windows execution or stream behavior.

## How to apply

When Worker QA is authorized, retain the unmodified host result separately from any stubbed run. Verify that selected mocks intercept process creation before using a test-only constant, and keep real-Windows skips explicit. Recheck the selected interpreter and source. Leave production code unchanged merely to accommodate the stub; reconcile installed state and operating authority through the Windows authority before host work.

## Evidence

- [Worker process construction](../../worker/windows/powershell_control.py) — use of the Windows-only creation flag.
- [Worker process checks](../../backend/tests/test_worker_powershell_control.py) — fake-process coverage and the Windows-only skip.
- [Windows authority](../windows-worker.md#owner-report) — installed-state evidence and current execution limits.
