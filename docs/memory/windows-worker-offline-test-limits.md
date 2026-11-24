---
name: windows-worker-offline-test-limits
description: "Worker tests fail off Windows because subprocess.CREATE_NO_WINDOW exists only on Windows."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

`worker/windows/` creates processes with `subprocess.CREATE_NO_WINDOW`, which is undefined on macOS and Linux, so tests that fake process creation fail before their mocks run.

## Why

Suites must pass on both macOS and Windows; these failures look like real defects on the Mac.

## How to apply

Stub the constant in tests run off Windows and report those results as mocked. Real PowerShell behavior is verified only on Windows.

## Evidence

- `worker/windows/powershell_control.py`
