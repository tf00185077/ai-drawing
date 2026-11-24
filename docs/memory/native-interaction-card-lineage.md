---
name: native-interaction-card-lineage
description: "In Paperclip, a new question card expires the same agent's older pending card of the same kind on the same issue."
metadata:
  type: project
  curated_on: "2026-11-24"
---

## Context

When an agent creates an `ask_user_questions` or `request_confirmation` card, Paperclip expires that agent's older pending card of the same kind on the same issue. The earlier question can no longer be answered.

## Why

Agents that ask several questions in separate cards lose all but the last answer.

## How to apply

Put questions that must stay open into one card, or wait for the earlier answer before asking again.

## Evidence

- [Team guide](../team/README.md) — closest project document; the behavior lives in the local Paperclip service
