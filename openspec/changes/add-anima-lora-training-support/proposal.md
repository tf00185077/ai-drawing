## Why

Training an Anima LoRA through the current MCP surface is fragile because the trainer's model-file
resolution was built around SDXL's single-checkpoint shape. Anima is a diffusion-model family whose
components (diffusion model, Qwen3 text encoder, VAE, optional T5 tokenizer) live in *separate*
directories from SDXL checkpoints, and the current resolver (`_resolve_checkpoint_path`) only ever
prefixes a bare filename with the first `LORA_CHECKPOINT_DIRS` entry, never searches across
directories, and never checks existence. As a result a bare Anima filename (exactly what
`list_available_resources` returns) either resolves to the wrong directory or slips through unresolved
and fails late inside the Kohya subprocess. SDXL avoids this only because one file in one configured
directory is enough to paper over the same weakness.

Two further gaps block a full agent-driven Anima training loop: the backend smoke test builds a
checkpoint-only generation request that cannot exercise an Anima LoRA, and several dataset/smoke-test
MCP tools that the `lora-training-mcp-tools` spec already declares have drifted out of the code.

## What Changes

- Add a unified model-file resolver that accepts three input forms — absolute path, bare filename,
  and remote/HuggingFace id — and resolves bare filenames by searching a model-family-aware list of
  directories, reusing the existing generation-side config
  (`COMFYUI_DIFFUSION_MODELS_DIR` / `COMFYUI_TEXT_ENCODERS_DIR` / `COMFYUI_VAE_DIR`) instead of
  introducing parallel settings. Applies to `checkpoint` (Anima diffusion model / SDXL checkpoint) and
  to the Anima `qwen3` / `vae` / `t5` runtime paths.
- Validate checkpoint existence before enqueue for local paths and bare filenames, returning a
  structured `checkpoint_not_found` error with the `searched_dirs` list; remote/HF ids pass through,
  and an `allow_unverified_checkpoint` flag bypasses the check for edge cases. Remain resolve-then-warn,
  never hard-lock.
- Make the backend smoke test model-family-aware: for `model_family=anima`, derive an Anima generation
  request (`template=anima` + `diffusion_model` + `text_encoder` + `vae` + `lora`) from the durable
  job params, with optional per-component request overrides. Other families keep the existing
  checkpoint-only shape.
- Restore the drifted MCP tools that the spec already requires: `lora_dataset_list`,
  `lora_dataset_inspect`, and `lora_train_smoke_test` (thin, read-only-or-delegating wrappers over
  existing backend endpoints, all component parameters optional).

Non-goals: re-implementing the wider drifted dataset suite (prepare / validate / caption-assessment /
metadata / curation / agent-inspect). Those, plus a full project-wide MCP spec reconciliation, are
tracked in the follow-up change `reconcile-mcp-spec-catalog`.

## Capabilities

### New Capabilities
<!-- None. All behavior extends existing capabilities. -->

### Modified Capabilities
- `kohya-sd-scripts-runtime`: model-file paths (checkpoint / qwen3 / vae / t5) resolve flexibly across
  model-family-aware directories with HF passthrough, and checkpoint existence is validated before a
  durable job is created.
- `lora-training-workflow`: the registered-LoRA smoke test becomes model-family-aware so Anima LoRAs
  are exercised through an Anima diffusion-model generation instead of a checkpoint-only one.
- `lora-training-mcp-tools`: `lora_train_smoke_test` accepts optional Anima component overrides, and
  the already-declared `lora_dataset_list` / `lora_dataset_inspect` / `lora_train_smoke_test` tools are
  re-established in code to close spec/code drift.

## Impact

- Code: `backend/app/services/lora_trainer.py` (resolver, enqueue validation, smoke test),
  `backend/app/config.py` (reuse of component dirs for resolution), `backend/app/api/lora_train.py`
  (smoke-test request overrides), `mcp-server/mcp_server/tools/lora_train.py` (restored tools).
- Tests: `backend/tests/test_lora_trainer.py`, smoke-test coverage, MCP contract tests.
- Behavior: bare-name resolution now searches multiple directories; SDXL flows that relied on the
  first-directory-only behavior stay compatible because `LORA_CHECKPOINT_DIRS` remains the first
  search source. No breaking API changes.
