---
name: windows-worker-offline-test-limits
description: Worker tests fail on macOS/Linux because subprocess.CREATE_NO_WINDOW only exists on Windows.
metadata:
  type: project
---

`worker/windows/` builds processes with `subprocess.CREATE_NO_WINDOW`, which is undefined outside Windows. On macOS/Linux, tests that fake process creation fail before their mocks run.

**How to apply:** stub the constant in tests run off Windows, and report those as mocked results. Real PowerShell behavior is only verified on Windows.
