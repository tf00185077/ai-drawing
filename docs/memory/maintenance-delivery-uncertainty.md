---
name: maintenance-delivery-uncertainty
description: "Keep remote delivery uncertainty and persistent history visible through drain receipts, retries and rollback."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

Completed-delivery ledgers suppress recorded duplicates but do not enumerate active or uncertain sends. External acceptance can precede a receipt, and local persistence can fail after sending. A timed worker join is not proof of exit; a successful drain response may still retain uncertainty. A ledger/checkpoint pair can detect a stale single-file restore, while a coherent whole-root rewind can restore that pair and still lose evidence of later remote effects.

## Why

Treating clean-looking local state as proof of no remote effect can duplicate delivery or release an unsafe maintenance hold.

## How to apply

Inspect the persistence-aware typed close/drain result and actual worker/child closure. Retain missing, corrupt or inconsistent history as unknown/held on the receipt itself; HTTP success or later status reconciliation cannot certify an earlier zero. Bind the actual single writer, ledger and cwd. An adopted new gate cannot certify an older process.

Preserve the exact legacy no-resend hold and local closure/checkpoint/restore/data guards in current authority. Retry, replay, force-resend or old-ledger restore cannot release unresolved outcomes. Require positive reconciliation or a separately authorized exact disposition. Use an externally trusted checkpoint or approved recovery decision when whole-root rollback could rewind local evidence; never equate a locally consistent pair with external delivery proof.

## Evidence

- [Current maintenance, close-receipt and legacy-hold records](../PROGRESS.md#company-preparation-and-next-step) — closest durable routes to the retained Bot assessment, counterexamples, repaired receipt and delegated policy.
- [Current data and recovery boundaries](../../AGENTS.md#safety-and-scope) — preserve records and reconcile uncertain submission identity before retry.
