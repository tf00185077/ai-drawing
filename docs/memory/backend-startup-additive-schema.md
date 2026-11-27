---
name: backend-startup-additive-schema
description: "Inspect the whole database schema delta when relaunching current Backend source against an older SQLite database."
metadata:
  type: project
  captured_on: "2026-11-24"
  curated_on: "2026-11-25"
---

## Context

Backend `init_db` registers the ORM models, calls `Base.metadata.create_all` and adds missing nullable columns from `_ADDITIVE_COLUMNS`. Launching current source can therefore create registered tables and add columns outside the feature being exercised, including training/reservation schema during an image-generation check.

## Why

Equal values selected through the old column list prove preservation of those values, not unchanged schema or a complete runtime inventory. An operator relying on that narrower check can miss changes made by normal startup.

## How to apply

Preserve a private prelaunch snapshot, then compare the complete table/column schema and all preexisting values after relaunch. Record added columns, null/default state, new table counts and their existing-source cause. Keep schema deltas separate from row-value preservation claims. Publish redacted schema/aggregate/hash receipts rather than the private database or historical row contents. Do not restart, roll back or edit data merely to correct an inventory omission.

## Evidence

- [Database startup](../../backend/app/db/database.py): `init_db`, `_ADDITIVE_COLUMNS` and `Base.metadata.create_all`.
- [p1-00a review round 1](../tasks/p1-00a-mac-runtime-and-retrieval/review-round-1.md#findings): independent schema and old-value preservation audits.
