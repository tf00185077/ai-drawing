---
name: native-interaction-card-lineage
description: "Reconcile pending sibling question cards when the same agent creates another ordinary card of the same kind on one issue."
metadata:
  type: project
  curated_on: "2026-10-31"
---

## Context

In the observed deployed Paperclip service, an agent creating an ordinary `ask_user_questions` or `request_confirmation` expires its own older pending cards of that kind on the same company issue by default. Tool-action and secret-proposal confirmations are outside this observed rule. `supersedeOnUserComment` governs a separate event; administrative expiry with no answers supplies no policy decision.

## Why

An apparently independent new question can remove the live response path for an earlier unresolved choice.

## How to apply

Check current supported behavior without creating probe cards. Group questions that must remain pending together, or resolve the earlier card before creating its same-kind successor. Read back sibling status after creation and preserve question IDs, exact proposal revisions, answers and successor linkage. Use the current delegated decision route; repair of card lineage does not approve the underlying operation.

## Evidence

- [Decision intake and native writeback](../team/channel-routing.md#delegated-decision-intake) — closest durable project route to the native same-kind interaction reconciliation record.
- [Current delegation](../GOAL.md#current-owner-completion-mandate) — authority remains separate from a card lifecycle outcome.
