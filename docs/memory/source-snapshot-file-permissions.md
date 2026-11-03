---
name: source-snapshot-file-permissions
description: "Bind source and packaging identities separately, preserving numeric permissions and current nonwrite authority through reconstruction and rollback."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

Git regular-file modes retain executable classes rather than original numeric POSIX permissions. A byte-correct source round trip can therefore pass while changing permissions. Separately frozen packaging metadata can repair that loss without changing the product Git tree. An operation write projection also differs from the complete product and from preserved current authority.

## Why

Matching hashes or Git trees cannot establish metadata preservation, and an old package preimage can incorrectly classify newer memory as drift or an unwanted file.

## How to apply

Bind exact product commit/tree, packaging controls, selected paths, original numeric modes and byte preimages separately. Reconstruct original metadata before scratch verification; verify bytes, modes and original absences after both apply and rollback. Keep write-path drift refusal while preserving current nonwrite authority and explicit assembly exceptions. Never normalize canonical files to satisfy an older package. Numeric-mode evidence for selected regular files does not certify ACLs, xattrs, ownership or Windows behavior. For private checkpoints, distinguish restrictive storage modes from original-metadata reconstruction in the explicitly authorized restore-check location; verify actual reconstruction under the current uid rather than counting a sidecar as restore success.

## Evidence

- [Source-kit and policy records](../PROGRESS.md#company-preparation-and-next-step) — closest durable routes to the original permission audit, repaired kits and separate metadata-representation decision.
- [Preservation boundary](../../AGENTS.md#safety-and-scope) — unrelated dirty work and runtime data remain protected.
