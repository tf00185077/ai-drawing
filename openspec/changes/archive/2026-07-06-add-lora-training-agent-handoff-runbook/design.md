## Context

The existing LoRA training MCP tools can start, monitor, cancel, inspect logs, and smoke-test training jobs. The decision preflight determines whether training is appropriate. The missing piece is the standard agent handoff: what Hermes reports to the user before training, which explicit action starts training, how monitoring proceeds, and what final report is produced.

## Goals / Non-Goals

**Goals:**

- Define a standard pre-training report.
- Define the user-confirmed start, monitor, registration, smoke-test, and terminal reporting sequence.
- Make hash values, selected parameters, risks, and next actions visible in the handoff.
- Keep all training starts explicit and attributable to the user's request.

**Non-Goals:**

- Do not add new automatic training triggers.
- Do not duplicate backend training job implementation.
- Do not require production code in this planning change.
- Do not modify application docs unless a later apply step chooses to add a helper template.

## Decisions

1. **Represent the handoff as an OpenSpec capability.**
   - The runbook is primarily a contract for agents and future helper templates.
   - Alternative considered: modify application docs immediately. Rejected because the user requested OpenSpec-only docs for this pass.

2. **Require a pre-start report before training.**
   - The report includes dataset identity, metadata profile, caption suitability, decision result, hashes, suggested parameters, selected parameters, risks, and the exact LoRA target.
   - The report is complete enough for the user to approve or reject the specific training run.

3. **Use existing MCP tools for execution.**
   - Start uses `lora_train_start`.
   - Monitoring uses `lora_train_job_status` and `lora_train_logs`.
   - Completion uses registered output fields and `lora_train_smoke_test`.

4. **Record terminal outcomes.**
   - Final report includes job id, status, output path, registered LoRA name, smoke-test result, failure details, and recommended next steps.

## Risks / Trade-offs

- A runbook-only change depends on agent discipline -> make the requirements explicit and testable through future prompt or helper tests.
- Reports can become verbose -> standardize required fields and allow concise summaries.
- Dataset state can change between decision and start -> the runbook requires expected dataset/profile hashes at start.

## Migration Plan

- Archive creates a main OpenSpec capability documenting the runbook.
- Future implementation can add helper templates or tests without changing backend contracts.
- Rollback removes the new runbook capability only.

## Open Questions

- None. Concrete helper-template location can be chosen during implementation if Hermes wants one.
