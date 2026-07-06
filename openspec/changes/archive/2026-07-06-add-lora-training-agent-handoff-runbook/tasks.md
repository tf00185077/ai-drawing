## 1. Runbook Contract

- [x] 1.1 Review existing MCP training tools and decision preflight outputs to confirm required report fields are available.
- [x] 1.2 Define a pre-start handoff report template in the implementation artifacts or agent prompt layer selected during apply.
- [x] 1.3 Ensure the report requires dataset hash, profile hash, decision, reasons, selected parameters, risks, and explicit user training intent.

## 2. Training Execution Handoff

- [x] 2.1 Define the explicit sequence for `lora_train_start`, `lora_train_job_status`, `lora_train_logs`, registration review, and `lora_train_smoke_test`.
- [x] 2.2 Add tests or checklist validation proving the handoff never starts training before explicit user approval.
- [x] 2.3 Define failure, cancellation, and stale-hash recovery steps for the agent.

## 3. Terminal Reporting

- [x] 3.1 Define the terminal report fields for completed, failed, and cancelled jobs.
- [x] 3.2 Include smoke-test outcome, generated artifact reference, registered LoRA name, logs/error summary, and recommended next actions.

## 4. Verification

- [x] 4.1 Run `openspec validate add-lora-training-agent-handoff-runbook`.
- [x] 4.2 Run `openspec validate --all` and `git diff --check`.
