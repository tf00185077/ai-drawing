## 1. Unified model-file resolver (TDD)

- [x] 1.1 Add tests in `backend/tests/test_lora_trainer.py` for `_resolve_model_file`: absolute path unchanged; bare filename resolves to first existing dir across a family-aware list; HF-style id (`org/model`) passes through; missing bare name returns/reports `searched_dirs`.
- [x] 1.2 Implement `_resolve_model_file(name, search_dirs, *, allow_missing)` in `backend/app/services/lora_trainer.py`, replacing the first-dir-only logic in `_resolve_checkpoint_path`.
- [x] 1.3 Build family-aware checkpoint search dirs: anima = `LORA_CHECKPOINT_DIRS` + `COMFYUI_DIFFUSION_MODELS_DIR`; sd15/sdxl = `LORA_CHECKPOINT_DIRS` + `COMFYUI_CHECKPOINTS_DIR`. Reuse the existing comma-split dir helper.
- [x] 1.4 Route `_validate_runtime_path` (qwen3/vae/t5) through `_resolve_model_file` with the component dirs (text_encoders / vae) so bare component filenames resolve instead of failing on CWD.
- [x] 1.5 Add a regression test proving an SDXL bare filename resolves to the same path as the previous behavior.

## 2. Checkpoint existence preflight

- [x] 2.1 Add tests: missing local checkpoint → `checkpoint_not_found` with `searched_dirs`, no job created; remote/HF checkpoint skips the check; `allow_unverified_checkpoint=true` bypasses.
- [x] 2.2 In `enqueue`, validate a resolved local checkpoint exists before creating the durable job; raise structured `TrainerServiceError("checkpoint_not_found", …, {"searched_dirs": [...]})`.
- [x] 2.3 Thread `allow_unverified_checkpoint` from `TrainStartRequest` (schema) → `lora_train.enqueue` → validation.
- [x] 2.4 Add `allow_unverified_checkpoint` to the `lora_train_start` MCP tool and `sdxl`/anima params passthrough (no behavior change when unset).

## 3. Model-family-aware smoke test

- [x] 3.1 Add tests: an anima job builds `{template:"anima", diffusion_model, text_encoder, vae, lora}` from job params; sd15/sdxl keeps checkpoint-only; per-request component override wins over job params.
- [x] 3.2 Update `smoke_test_job` in `backend/app/services/lora_trainer.py` to branch on `params.model_family` and derive the anima generation request from stored params.
- [x] 3.3 Add optional `diffusion_model` / `text_encoder` / `vae` fields to the smoke-test request schema (`backend/app/schemas/lora_train.py`) and pass them through `backend/app/api/lora_train.py`.
- [x] 3.4 Verify against a real Anima workflow that the training `qwen3` maps to the generation `text_encoder` (resolve design Open Question) before marking this group done.

## 4. Restore drifted MCP tools

- [x] 4.1 Add `lora_dataset_list` MCP tool → `GET /datasets` (richer image/caption/hash/lock summary), following the `_backend_result` / `_backend_error` contract.
- [x] 4.2 Add `lora_dataset_inspect(folder)` MCP tool → `GET /datasets/{folder}/agent-inspect`.
- [x] 4.3 Add `lora_train_smoke_test(job_id, prompt?, negative_prompt?, diffusion_model?, text_encoder?, vae?)` MCP tool → `POST /jobs/{job_id}/smoke-test`.
- [x] 4.4 Add MCP contract tests for the three tools (success + structured error shapes) in `mcp-server/tests/`.
- [x] 4.5 Register the three tools in `tool_catalog.py` so the catalog audit test covers them.

## 5. Verification

- [x] 5.1 Run `backend/tests/test_lora_trainer.py` and the MCP tool tests; confirm all pass.
- [x] 5.2 Update `.env.example` to document the reused component dirs for Anima training and note `LORA_CHECKPOINT_DIRS` is optional now that generation dirs are searched.
- [x] 5.3 Update `docs/PROGRESS.md` per project rule.
- [x] 5.4 Run `openspec validate add-anima-lora-training-support --strict` and fix any issues.
