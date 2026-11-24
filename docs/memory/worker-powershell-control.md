---
name: worker-powershell-control
description: "How the Windows worker's PowerShell control behaves: text-only UTF-8, memory-only records, no managed updates, deployment checks."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

The worker runs Windows PowerShell 5.1 with a fixed UTF-8 bootstrap and passes the script on stdin; stdout and stderr return separately as strict UTF-8 text. Command records live only in worker memory and are lost on restart. The worker has no managed update, restart, resource-plan or preflight routes; updates and restarts are ordinary scripts sent through the command routes. `Enable-Open-PowerShell-Control.ps1 -ExpectedCommit <sha>` requires `HEAD` and `origin/main` to equal that commit, copies the control files into the installed runtime and restarts the scheduled task. The routes are unauthenticated.

## Why

Binary output is corrupted by the text stream, old command IDs vanish after a restart, and agents look for update endpoints that no longer exist.

## How to apply

Base64-encode binary data in scripts. Read a command's result before the worker restarts. Update the worker by submitting scripts. Keep port 8791 reachable only from the Backend host.

## Evidence

- `worker/windows/powershell_control.py`
- `worker/windows/Enable-Open-PowerShell-Control.ps1`
- [Windows worker](../windows-worker.md)
