---
name: native-interaction-card-lineage
description: "Ordinary Paperclip question and confirmation cards supersede the same agent's older pending cards of that kind."
metadata:
  type: project
  curated_on: "2026-11-26"
---

## Context

By default, an agent creating an `ask_user_questions` or ordinary `request_confirmation` card expires that agent's older pending card of the same kind on the same issue. Creating a confirmation for a tool action or secret proposal does not take this supersession path. The expired card can no longer be answered.

## Why

Agents that ask several questions in separate cards lose all but the last answer.

## How to apply

Put questions that must stay open into one card, or wait for the earlier answer before asking again.

## Evidence

- [Team guide](../team/README.md) — closest project document; the behavior lives in the local Paperclip service's `server/src/services/issue-thread-interactions.ts`, outside this repository.
