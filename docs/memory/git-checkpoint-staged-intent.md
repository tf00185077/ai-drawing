---
name: git-checkpoint-staged-intent
description: "Preserve unrelated staged intent across a Git baseline change and reconcile separate ref/index publication."
metadata:
  type: project
  curated_on: "2026-11-06"
---

## Context

Moving a Git baseline ref can change the staged delta even when the raw index and working files are unchanged. The reviewed isolated checkpoint design prepared a new index from the candidate's baseline changes and compared unrelated staged deltas against their respective baselines.

## Why

Preserving index bytes alone can turn baseline changes into staged inverse changes, misrepresenting work that was already staged.

## How to apply

Before an authorized Git checkpoint, require the prepared index's staged object/mode delta against the new baseline to equal the original unrelated staged delta against the old baseline. Refuse staged overlap with the candidate's changed paths and unsupported index states. Preserve working bytes, numeric modes and absences separately from tracking/status labels.

Ref and index publish separately. Pin both identities and retain cooperative writer exclusion through process-interruption recovery. Preserve ambiguous state for exact authorized reconciliation rather than blindly restoring the old index or rewinding the ref. Require independent acceptance of the exact transaction/recovery procedure; source-composition acceptance does not establish procedure safety or power-loss durability.

## Evidence

- [Retained Git checkpoint delivery and independent review](../PROGRESS.md#m1--image-request-and-revision-through-mcpthe-existing-ui-active) — routes to the frozen engineering proof, independent composition/procedure verdicts and Producer assessment.
- [Repository reconciliation boundary](../checkpoints/2026-11-03-source-design.md#repository-reconciliation) — Git history, working-file application and runtime adoption are separate.
