## 1. Recipe transport and canonical schemas

- [x] 1.1 Add RED cases in `backend/tests/test_lora_training_recipe.py` for object and JSON-object-string input, schema-version aliases, documented field aliases, lossless scalar coercions, optimizer/scheduler argument forms, scalar/list component learning rates, and partial requested recipes.
- [x] 1.2 Add RED cases in `backend/tests/test_lora_training_recipe.py` for alias conflicts, unknown or misspelled fields, invalid coercions, non-object JSON, submitted-value redaction, and stable `code/message/hint/details` errors.
- [x] 1.3 Define the v1 requested/effective recipe, field-source, component-identity, capability, execution-evidence, and step-plan models in `backend/app/schemas/lora_train.py`, with unknown fields forbidden after normalization.
- [x] 1.4 Implement the tolerant transport parser and alias normalizer in `backend/app/services/lora_training_recipe.py`, then make the tests from 1.1 and 1.2 pass without duplicating semantic normalization in MCP.

## 2. Deterministic recipe compilation

- [x] 2.1 Add RED table tests for the SD1.5, SDXL, and Anima scope/component-learning-rate matrix; Text Encoder opt-in; cache/scope incompatibility; trusted family network modules; family/resolution/platform batch policy; conservative unknown/MPS precision; worker invariants; bucket invariants; and save cadence.
- [x] 2.2 Implement requested-to-effective compilation and per-leaf `caller`, `preflight_policy`, `server_policy`, or `derived` source tracking in `backend/app/services/lora_training_recipe.py`, including visible server-owned constants.
- [x] 2.3 Add RED tests proving canonical seed output preserves fixed/random mode, source, and one materialized value; Start never redraws a preflight seed; canonical key order and accepted aliases do not change the hash; semantic changes do change it; and ephemeral paths/transport expected hash do not affect it.
- [x] 2.4 Add RED tests for the documented single-process step-plan formula using approved image count, repeats, batch size, gradient accumulation, and epochs, including ceiling behavior and ratio-to-step warmup resolution.
- [x] 2.5 Implement seed materialization, canonical JSON hashing, resolved component identity input, and deterministic step-plan calculation, then make tasks 2.3 and 2.4 pass.

## 3. Dataset TOML, argv, and runtime evidence builders

- [x] 3.1 Add RED offline fixture tests in `backend/tests/test_lora_training_recipe_execution.py` for exact dataset TOML and argv across SD1.5, SDXL, and Anima, covering all bucket fields, denoiser-only scope, Text Encoder opt-in, overall/component learning rates, accumulation, workers, optimizer/scheduler/warmup, seed, caches, precision, and final-only saving.
- [x] 3.2 Refactor `backend/app/services/lora_trainer.py` so pure TOML and argv builders consume only an immutable effective recipe and return data/argv rather than reading late training defaults or building a shell string.
- [x] 3.3 Add RED tests that mutation of global settings after compilation cannot change the queued recipe, TOML, or argv.
- [x] 3.4 Implement sanitized trainer-capability, launcher/runtime version, sd-scripts revision, and component-identity evidence collection with explicit `verified`, `unverified`, or `unavailable` status and no secret/environment leakage.

## 4. Durable recipe and evidence persistence

- [x] 4.1 Add RED migration and model tests in `backend/tests/test_database_init.py` and `backend/tests/test_lora_training_recipe_persistence.py` for the four additive nullable columns, idempotent initialization, and historical rows with null v1 fields.
- [x] 4.2 Add `recipe_schema_version`, `recipe_hash`, `recipe_json`, and `execution_evidence_json` to `backend/app/db/models.py` and the additive migration map in `backend/app/db/database.py`.
- [x] 4.3 Add RED persistence/status tests proving a new queued row already contains requested/effective recipes, field sources, step plan, component identities, schema version, and hash while retaining legacy `params` only as a read-only projection.
- [x] 4.4 Update `backend/app/services/lora_trainer.py` and `backend/app/schemas/lora_train.py` serialization so v1 status is typed, historical status remains readable, and missing evidence is never represented as verified.

## 5. Decision preflight contract

- [x] 5.1 Add RED cases in `backend/tests/test_lora_training_decision.py` for no hints, partial/aliased hints, preserved caller omissions, policy rationale, structured invalid-hint outcomes, no job creation, random-seed intent/source/materialization, and exact canonical `start_payload`.
- [x] 5.2 Integrate the single recipe compiler into `backend/app/services/lora_training_decision.py` and the preflight request/response schemas so a `train` result returns requested/effective recipes, field sources, step plan, recipe-hash preview, runtime/component evidence, and exact folder/hash/recipe Start payload.
- [x] 5.3 Add a parity test proving every `decision=train` `start_payload` carries the preview as `recipe.expected_recipe_hash`, validates through the Backend Start model unchanged, and rejects stale approval/component or safety-relevant capability evidence when Start recompiles it.

## 6. Backend Start, queue, and locked worker

- [x] 6.1 Add RED API/contract cases in `backend/tests/test_lora_start_contract.py`, `backend/tests/test_lora_training_start_safety.py`, and `backend/tests/test_lora_start_contract_parity.py` for required recipe, forbidden unknown top-level fields, actionable legacy-flat-field errors, recipe conflicts, approval races, and zero durable/subprocess side effects on rejection.
- [x] 6.2 Replace public flat training knobs with folder, both approval hashes, and required broad recipe transport in `backend/app/schemas/lora_train.py` and `backend/app/api/lora_train.py`; compile once before creating the immutable queued job.
- [x] 6.3 Update `backend/app/services/lora_trainer.py` enqueue and worker handoff to carry compiler output rather than resolve training defaults again, preserving the first-batch lock and approval revalidation behavior.
- [x] 6.4 Add RED worker tests proving exact TOML/argv and sanitized evidence are persisted while the lock is held before `Popen`, and that the launched argv is byte-for-byte the persisted argv.
- [x] 6.5 Implement the pre-launch evidence persistence path and make the offline three-family command matrix pass without claiming a real trainer initialization result.

## 7. MCP broad-input/strict-output transport

- [x] 7.1 Add RED direct-tool cases in `mcp-server/tests/test_lora_train_tools.py` for recipe object/string transport, aliases/coercions/partial input, canonical success, Backend alias/field/runtime errors, redaction, legacy migration guidance, and historical null-v1 status.
- [x] 7.2 Change `mcp-server/mcp_server/tools/lora_train.py` so Start and decision preflight forward the broad recipe transport to the Backend authority and always return the stable `ok/tool/error` envelope or strict canonical success payload.
- [x] 7.3 Add protocol/catalog cases in `mcp-server/tests/test_server.py` and `mcp-server/tests/test_tool_catalog.py` proving advertised LoRA tool fields and descriptions document accepted recipe forms, preserve both approval hashes, expose no hidden flat training defaults, and map known removed protocol arguments to a redacted `legacy_training_fields_removed` result without invoking the tool function.
- [x] 7.4 Extend Backend/MCP parity tests so any drift in canonical field names, types, requiredness, aliases, error codes, or output recipe identity fails automatically.

## 8. Bundled frontend transport migration

- [x] 8.1 Add RED cases in `frontend/src/pages/LoraTrain.test.tsx` proving Start submits the exact preflight `start_payload`, does not reconstruct unseen recipe defaults, reruns preflight after a supported override, and blocks Start for review/error decisions.
- [x] 8.2 Add v1 recipe, evidence, and exact Start-payload types to `frontend/src/types/api.ts`; migrate `frontend/src/pages/LoraTrain.tsx` to carry the canonical payload while retaining the current limited controls.
- [x] 8.3 Run `npm test -- src/pages/LoraTrain.test.tsx` and `npm run build` from `frontend`, correcting only transport/type regressions in this batch.

## 9. Operator and agent documentation

- [x] 9.1 Update `docs/mcp-setup.md` with the canonical LoRA recipe container, accepted broad forms/aliases, strict output/error envelope, migration error, and a preflight-to-Start example.
- [x] 9.2 Update `docs/lora-training-agent-handoff-runbook.md` with recipe version/hash, field sources, requested/effective scope, exact Start payload use, monitoring evidence, and explicit repair branches.
- [x] 9.3 Update `docs/setup-guide.md` with runtime-capability and execution-evidence meanings, clearly labeling unavailable source/runtime proof and deferring the real bounded trainer probe.

## 10. Verification and project record

- [ ] 10.1 Run the focused Backend recipe, decision, Start, persistence, trainer, worker-lock, and parity tests; run the focused MCP LoRA/server/catalog tests; retain the exact commands and results.
- [ ] 10.2 Run `pytest backend/tests/ mcp-server/tests/ -x -q`, `npm test`, and `npm run build`; separate any pre-existing unrelated failure from regressions introduced by this change.
- [ ] 10.3 Run `openspec validate make-lora-training-recipe-explicit --strict`, an offline SD1.5/SDXL/Anima command-fixture matrix, and `git diff --check`; do not report a live MCP reload or real trainer probe.
- [ ] 10.4 Perform a focused review for hidden defaults, duplicated MCP normalization, unredacted values, semantic hash omissions, historical-row compatibility, and accidental third/fourth-batch scope, then correct every confirmed finding.
- [ ] 10.5 Update `docs/PROGRESS.md` with the completed second-batch scope, verification evidence, known unrelated failures, and explicitly deferred third/fourth-batch gaps.
