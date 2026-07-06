## 1. Backend Decision Preflight

- [ ] 1.1 Add tests for `train`, `needs_review`, and `do_not_train` decisions using metadata, caption suitability, validation errors, curation status, and dataset/profile hash scenarios.
- [ ] 1.2 Implement a deterministic decision service that composes profile validation, caption assessment, dataset validation, curation status, and training constraints.
- [ ] 1.3 Return reasons, blocking issues, warnings, next actions, suggested parameters, dataset hash, and profile hash without side effects.

## 2. API And MCP Access

- [ ] 2.1 Add backend API tests proving decision preflight does not enqueue training and handles invalid folders structurally.
- [ ] 2.2 Add MCP tests for decision preflight success payloads, backend errors, and `do_not_train` as a successful assessment outcome.
- [ ] 2.3 Implement `lora_training_decision_preflight` or equivalent MCP tool and catalog entry.

## 3. Verification

- [ ] 3.1 Run focused backend decision tests and MCP LoRA decision tests.
- [ ] 3.2 Run `openspec validate add-agent-guided-lora-training-decision` and `git diff --check`.
