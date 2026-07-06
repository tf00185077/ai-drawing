## Context

The archived workflow already supports basic dataset preparation with dry-run/apply/backup/restore and trigger normalization. The remaining architecture needs a higher-level curation workflow that agents can use after inspection to clean noisy captions, normalize trigger usage, flag outliers, and protect human-written captions. This change must build on preparation rather than duplicate it.

## Goals / Non-Goals

**Goals:**

- Produce deterministic curation plans before any caption write.
- Apply only reviewed plans with dataset/profile hash checks.
- Backup all changed files and support rollback.
- Preserve manual captions unless the request explicitly approves targeted overwrites.
- Expose curation through MCP for Hermes/OpenClaw.

**Non-Goals:**

- Do not call an external LLM for caption rewriting.
- Do not automatically decide that a curated dataset is trainable.
- Do not start LoRA training.
- Do not remove the existing dataset prepare endpoint/tool.

## Decisions

1. **Represent curation as a plan.**
   - Dry-run returns a plan with per-file operations, reasons, before/after captions, outlier flags, and risk markers.
   - Apply accepts the reviewed plan identity or equivalent expected hashes.

2. **Use metadata policy as input.**
   - Trigger token, protected tags, and removable tags come from `.lora-dataset.json` unless the request explicitly overrides them.
   - Alternative considered: require all policy fields in every request. Rejected because agents need persistent reusable dataset intent.

3. **Protect manual captions by default.**
   - Captions newer than their images or marked as protected/manual by metadata are not changed automatically.
   - The apply request must list approved manual-caption files or set an explicit override field with per-file reporting.

4. **Flag outliers, do not delete them.**
   - Curation can flag captions/images that diverge strongly from shared tags or expected trigger coverage.
   - Removing images is left to a human or later explicit workflow.

## Risks / Trade-offs

- Conservative manual-caption protection can leave noisy captions unchanged -> return clear blocked edits and suggested manual review steps.
- A plan can become stale if captions change -> require expected dataset/profile hashes before apply.
- No LLM cleanup limits semantic rewriting -> this keeps the first curation layer deterministic and testable.

## Migration Plan

- Additive backend and MCP operations.
- Existing preparation remains available.
- Rollback removes curation endpoints/tools and any plan cache while backups created by applied runs remain restorable.

## Open Questions

- None. Image removal and LLM-assisted rewrite workflows are out of scope for this change.
