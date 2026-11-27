---
name: native-handoff-retirement
description: "Retire withdrawn blocked Paperclip handoffs through the authorized native cancellation path without admitting stale work."
metadata:
  type: project
  captured_on: "2026-11-27"
  curated_on: "2026-11-27"
---

## Context

In the local Paperclip deployment checked on 2026-11-27, an agent's status change
from `blocked` checks existing prerequisite readiness before applying proposed
edge edits. Cancellation can therefore return 409 for unresolved blockers even
when the same payload requests an empty blocker list. The dedicated tree-control
preview and cancellation routes require Board access.

## Why

Removing a prerequisite can admit the withdrawn assignment. Repeating the same
status write does not resolve the readiness or authority boundary.

## How to apply

Withdraw the obsolete card's operative description and current plan while keeping
its hold. Under existing owner authorization, relay retirement to the authorized
Hermes Board operator through the established notify path. The operator previews
the cancellation scope, cancels only the intended stale cards, and reads back
`cancelled` with no old execution run. Native cancellation can retain prerequisite
edges, descriptions and plan revisions. Do not change credentials or permissions
after a Board-access denial. Recheck the installed API when its behavior changes.

Keep worktrees, records and attachments. Cancellation is administrative retirement;
it grants no product acceptance and resets no rejection history.

## Evidence

- [Fresh continuation request](../requests/2026-11-27-fresh-producer-continuation.md)
  — closest project authority for preserving and withdrawing old handoffs.
- [Verified native retirement](/AID/issues/AID-217#comment-7186ed24-9210-4fa9-9aa4-b400e35b40b7)
  — API behavior and readback live in the local Paperclip service, outside this repository.
