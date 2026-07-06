## 1. Runbook Contract

- [ ] 1.1 Review existing MCP training tools and decision preflight outputs to confirm required report fields are available.
- [ ] 1.2 Define a pre-start handoff report template in the implementation artifacts or agent prompt layer selected during apply.
- [ ] 1.3 Ensure the report requires dataset hash, profile hash, decision, reasons, selected parameters, risks, and explicit user training intent.

## 2. Training Execution Handoff

- [ ] 2.1 Define the explicit sequence for `lora_train_start`, `lora_train_job_status`, `lora_train_logs`, registration review, and `lora_train_smoke_test`.
- [ ] 2.2 Add tests or checklist validation proving the handoff never starts training before explicit user approval.
- [ ] 2.3 Define failure, cancellation, and stale-hash recovery steps for the agent.

## 3. Terminal Reporting

- [ ] 3.1 Define the terminal report fields for completed, failed, and cancelled jobs.
- [ ] 3.2 Include smoke-test outcome, generated artifact reference, registered LoRA name, logs/error summary, and recommended next actions.

## 4. Verification

- [ ] 4.1 Run `openspec validate add-lora-training-agent-handoff-runbook`.
- [ ] 4.2 Run `openspec validate --all` and `git diff --check`.
