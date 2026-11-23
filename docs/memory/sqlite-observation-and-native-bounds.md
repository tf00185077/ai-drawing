---
name: sqlite-observation-and-native-bounds
description: "Keep WAL observations unknown when incomplete, and require connection-bound native limits before treating fixture SQL as an operational profile."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

Read-only or immutable SQLite main-file access does not by itself establish a consistent WAL observation. The reviewed operational reader/executor source refuses before database access; its isolated derivation is separate from an executable profile. Native fetch and materialization occur before Python serialization or validation, while a main-page cap omits other native and later-file effects.

## Why

A harmless-looking query or bounded returned JSON can still lack the consistency and full effect coverage required by the operation.

## How to apply

Inspect whether a proposed status route reconciles durable state before classifying it as read-only. Use only the approved reader/projection; validate its typed fields before a bounded observation. Preserve unknown for WAL/journal activity, changing files, failed projection or locator errors. Do not invent discarded responses, infer absence from failed empty output or silently refill reads.

For a future admitted DB profile, bind required limits, readback and lifetime to the same actual connection, schema and complete WAL/SHM/journal/temp/write coverage. Keep refusal and synthetic evidence within their tested scope; missing mechanisms are specific proof gaps, not a general SQLite impossibility or permission to enable fixture SQL with a caller-supplied safe flag.

## Evidence

- [Lifecycle observation limits](../training-status.md#lifecycle-source-milestone-and-unresolved-historical-jobs).
- [Reader/refusal and finite-observation records](../PROGRESS.md#company-preparation-and-next-step) — closest durable routes to the isolated DB review and stopped preflight observations.
