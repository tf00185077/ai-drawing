## 1. Lock Down the Public Start Contract

- [x] 1.1 Add failing backend schema/API tests proving `expected_dataset_hash` and `expected_profile_hash` are required, `batch_size` is forwarded unchanged, and unknown Start fields return 422 without calling enqueue.
- [x] 1.2 Add failing MCP tests proving `lora_train_start` exposes and forwards `batch_size` plus both hashes and sanitizes list-shaped Backend 422 details into `error.details.validation_errors`.
- [x] 1.3 Add a failing contract-parity test comparing `TrainStartRequest.model_fields`, the `lora_train_start` signature, and a complete preflight suggestion with a documented minimal allowlist.
- [x] 1.4 Update `TrainStartRequest` to forbid extra fields and require both approval hashes; update the API-to-enqueue forwarding contract until the backend tests pass.
- [x] 1.5 Update MCP `lora_train_start` forwarding and backend-error normalization until the MCP and parity tests pass without including submitted `input` values in errors.

## 2. Persist Dataset and Profile Approval Identity

- [x] 2.1 Add failing database initialization and job serialization tests for a nullable `lora_training_jobs.profile_hash` column and `profile_hash` in durable job status.
- [x] 2.2 Add the `profile_hash` model field and the project's additive SQLite startup migration so existing databases and historical rows remain readable.
- [x] 2.3 Carry `expected_profile_hash` through `_TrainJob`, persistent creation, params/audit serialization, status responses, and Backend/MCP response schemas.
- [x] 2.4 Run the focused database and durable LoRA job tests under Python 3.11 and confirm all approval identity assertions pass.

## 3. Make Preflight Produce a Startable, Family-Safe Payload

- [x] 3.1 Add failing decision service/API tests proving complete suggestions contain both hashes and all Backend-supported preflight-selected Start fields, including `batch_size`.
- [x] 3.2 Add failing tests for a dataset-profile/configured-family conflict returning `needs_review`, `model_family_mismatch`, and no ready default checkpoint pairing.
- [x] 3.3 Update preflight suggestion and decision logic to emit the two-hash approval payload and conservative family-conflict result.
- [x] 3.4 Run focused decision, MCP preflight, and parity tests under Python 3.11 and confirm they pass.

## 4. Unify Dataset Resolution and Close the Validation Race

- [x] 4.1 Add failing Start/enqueue tests for absolute paths, traversal, and a symlink below `lora_train_dir` that resolves outside the root; assert `invalid_dataset_folder` and no durable job.
- [x] 4.2 Replace trainer-specific path joining with `lora_dataset.resolve_dataset_dir()` in enqueue and worker paths and translate `DatasetServiceError` into the existing structured trainer error envelope.
- [x] 4.3 Add failing worker-order tests that instrument lock acquisition, profile-hash verification, full dataset validation, hash verification, and subprocess launch.
- [x] 4.4 Move authoritative profile/dataset/family checks inside the worker-held dataset lock, retain preliminary enqueue validation for fast feedback, and ensure stale queued jobs fail without launching subprocesses.
- [x] 4.5 Add regression tests proving the training lock remains held during subprocess execution and is released for completed, failed, and cancelled jobs.
- [x] 4.6 Run focused dataset, trainer, workflow API, watcher-lock, and MCP error tests under Python 3.11.

## 5. Remove Automatic Enqueue Bypasses

- [x] 5.1 Add a failing `trigger_check()` test proving eligible candidates are reported without calling `enqueue()` or creating durable jobs.
- [x] 5.2 Remove the legacy auto-enqueue branch from `trigger_check()` while preserving `should_trigger` and candidate discovery responses.
- [x] 5.3 Search production code for every direct `lora_trainer.enqueue()` call and add an assertion/test proving the explicit Start API is the only public training trigger.

## 6. Migrate the Bundled Frontend and Agent Handoff

- [x] 6.1 Extend frontend LoRA request/decision TypeScript types with required approval hashes and the structured preflight response used by the page.
- [x] 6.2 Add frontend tests for ready, needs-review, do-not-train, and failed preflight paths, including preservation of the selected `batch_size`.
- [x] 6.3 Update the LoRA training page to preflight every selected folder, call Start only for `decision=train`, submit both hashes, and display actionable decision/error text for skipped folders.
- [x] 6.4 Update `docs/lora-training-agent-handoff-runbook.md` and its machine-readable contract so Start submits both hashes directly and no longer describes profile hash as preflight-only verification.
- [x] 6.5 Update runbook contract tests for the exact submitted fields and stale/missing-hash recovery behavior.

## 7. Verification and Project Record

- [x] 7.1 Run `openspec validate harden-lora-training-start-contract --strict` and fix every proposal/design/spec consistency or scenario-format error.
- [x] 7.2 Run focused backend and MCP LoRA suites with the project-required Python 3.11 runtime and record the exact pass counts.
- [x] 7.3 Run frontend typecheck/tests/build and confirm the strict Start migration has no compile or request-flow regressions.
- [x] 7.4 Run `pytest backend/tests/ mcp-server/tests/ -x -q` under Python 3.11 and resolve any regression caused by the breaking contract.
- [x] 7.5 Update `docs/PROGRESS.md` with the completed first-batch behavior, verification commands/results, breaking caller migration, and the next OpenSpec batch (`make-lora-training-recipe-explicit`).

## 8. Independent Review Corrections

- [x] 8.1 Add a real stdio protocol regression test and return redacted structured MCP results for missing Start hashes without weakening the advertised required schema.
- [x] 8.2 Include image bytes in dataset approval identity and reject rooted slash/backslash dataset locators.
- [x] 8.3 Preserve worker mismatch details durably and hold the dataset lock through output registration and terminal handling.
- [x] 8.4 Preserve structured frontend Start failures and merge preflight-selected family/runtime values while keeping user-selected fields authoritative.
- [x] 8.5 Expand the handoff recovery contract for field 422, family mismatch, and unsafe paths without implicit repair or retry.
- [x] 8.6 Coordinate watcher, upload, caption edit, batch prefix, and LLM caption writes with the same dataset lock used by training.
- [x] 8.7 Canonicalize equivalent relative dataset locators before validation/persistence and defer watcher captioning through bounded lock retries.
- [x] 8.8 Rerun strict OpenSpec validation and all final Backend, MCP, Frontend, typecheck, build, and combined regression checks.
