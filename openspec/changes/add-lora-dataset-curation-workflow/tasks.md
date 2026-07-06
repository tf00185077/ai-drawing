## 1. Backend Curation Plans

- [ ] 1.1 Add service tests for dry-run plans covering trigger normalization, protected tags, removable tags, duplicate tags, noisy tags, outlier flags, and no-write behavior.
- [ ] 1.2 Implement deterministic curation plan generation using metadata profile policy and current caption suitability metrics.
- [ ] 1.3 Include per-file before/after captions, operation reasons, manual-protection status, outlier flags, dataset hash, and profile hash in plan responses.

## 2. Apply And Rollback

- [ ] 2.1 Add API tests for apply with backup creation, stale hash rejection, manual-caption protection, explicit manual overwrite approval, and rollback.
- [ ] 2.2 Implement curation apply with expected dataset/profile hashes, restorable backups, and per-file result reporting.
- [ ] 2.3 Implement rollback by backup id without overwriting newer manual edits unless explicitly approved.

## 3. MCP Access

- [ ] 3.1 Add MCP tests for curation dry-run, apply, rollback, stale hash errors, and manual-caption protection errors.
- [ ] 3.2 Implement `lora_dataset_curate` or equivalent curation MCP entrypoints with structured results and catalog metadata.

## 4. Verification

- [ ] 4.1 Run focused backend curation tests and MCP LoRA curation tests.
- [ ] 4.2 Run `openspec validate add-lora-dataset-curation-workflow` and `git diff --check`.
