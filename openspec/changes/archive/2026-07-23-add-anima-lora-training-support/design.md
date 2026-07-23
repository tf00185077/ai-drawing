## Context

The LoRA trainer's model-file handling was shaped by SDXL, where a single checkpoint file in a single
configured directory is enough. Anima is a diffusion-model family: its diffusion model lives in
`COMFYUI_DIFFUSION_MODELS_DIR`, its Qwen3 text encoder in `COMFYUI_TEXT_ENCODERS_DIR`, and its VAE in
`COMFYUI_VAE_DIR` — all separate from `COMFYUI_CHECKPOINTS_DIR`.

Current resolution logic (`backend/app/services/lora_trainer.py`):
- `_resolve_checkpoint_path` treats a bare filename by prefixing it with the *first* non-empty entry of
  `LORA_CHECKPOINT_DIRS` and returning immediately — it never searches other directories and never
  checks existence. `LORA_CHECKPOINT_DIRS` is also decoupled from the generation-side component dirs
  and is empty by default (absent from `.env.example`).
- `_validate_runtime_path` (used for `qwen3`/`vae`/`t5`) resolves a bare filename relative to the CWD,
  so a bare component filename never exists and always errors.

Net effect: a bare Anima filename — which is exactly what `list_available_resources` returns — resolves
to the wrong place or fails late inside Kohya. `smoke_test_job` compounds this by building a
checkpoint-only generation that cannot exercise an Anima LoRA. Finally, `lora_dataset_list`,
`lora_dataset_inspect`, and `lora_train_smoke_test` are declared in `lora-training-mcp-tools` but absent
from code.

A guiding constraint from the maintainer: keep the MCP surface flexible. Fixes must not lock callers
into one rigid input form or a mandatory pipeline.

## Goals / Non-Goals

**Goals:**
- Make bare-name Anima inputs resolve correctly by searching family-aware directories, reusing existing
  generation-side config.
- Fail fast and clearly on a missing local checkpoint, while letting remote references through.
- Exercise Anima LoRAs with a real Anima generation in the smoke test.
- Re-establish the three drifted MCP tools to close spec/code drift.

**Non-Goals:**
- Re-implementing the wider drifted dataset suite (prepare / validate / caption-assessment / metadata /
  curation / agent-inspect).
- Project-wide MCP spec reconciliation — tracked in `reconcile-mcp-spec-catalog`.
- Changing generation-side (`generate_image`) behavior.

## Decisions

### D1: One resolver, three input forms, family-aware search — reuse generation config
Extract a single `_resolve_model_file(name, search_dirs, *, allow_missing)` and route both the
checkpoint and the Anima component paths through it.
- **Input forms (flexibility principle P1):** absolute/separator-bearing path → resolve as-is; bare
  filename → search `search_dirs` in order, first `.exists()` wins; looks-like-HF (`/` but not local) →
  pass through.
- **Search dirs (P3, no parallel config):** built per `model_family` from existing settings —
  checkpoint(anima) = `[*LORA_CHECKPOINT_DIRS, *COMFYUI_DIFFUSION_MODELS_DIR]`, checkpoint(sd/sdxl) =
  `[*LORA_CHECKPOINT_DIRS, *COMFYUI_CHECKPOINTS_DIR]`, qwen3/t5 = `COMFYUI_TEXT_ENCODERS_DIR`, vae =
  `COMFYUI_VAE_DIR`. `.env`-provided `LORA_ANIMA_*` and absolute paths keep working.
- **Alternative rejected:** add new `LORA_ANIMA_*_DIRS` settings — duplicates config the generation side
  already owns and invites drift.
- **Backward compat:** `LORA_CHECKPOINT_DIRS` stays the first checkpoint search source, so existing SDXL
  bare-name flows resolve identically.

### D2: Existence check is resolve-then-warn, local-only, bypassable
Validate a resolved *local* checkpoint with `.exists()` in `enqueue` before creating the durable job;
on miss return structured `checkpoint_not_found` with `searched_dirs`. Remote/HF references skip the
check (P2). An `allow_unverified_checkpoint` flag threads from `lora_train_start` through the API to the
enqueue path for edge cases. Component paths (`qwen3`/`vae`/`t5`) keep their existing existence
validation, now fed by the D1 resolver so bare names work.
- **Alternative rejected:** hard-block every unresolved string — breaks legitimate HF ids and reduces
  flexibility.

### D3: Model-family-aware smoke test derived from durable job params
`smoke_test_job` reads the job's stored `params` (`model_family`, `checkpoint`, `anima_qwen3`,
`anima_vae`). For `anima` it builds `{template: "anima", diffusion_model, text_encoder, vae, lora,
prompt, negative_prompt}`; other families keep the checkpoint-only shape. The smoke-test request schema
gains optional `diffusion_model` / `text_encoder` / `vae` overrides; unset values fall back to job
params (P4).
- **Verification point:** confirm the Anima generation path treats the training `qwen3` as the
  generation `text_encoder`; validate against a real Anima workflow during implementation.

### D4: Thin MCP wrappers to close drift
Add `lora_dataset_list` → `GET /folders`, `lora_dataset_inspect(folder)` →
`GET /datasets/{folder}/agent-inspect`, `lora_train_smoke_test(job_id, prompt?, negative_prompt?,
diffusion_model?, text_encoder?, vae?)` → `POST /jobs/{job_id}/smoke-test`. All follow the existing
`_backend_result` / `_backend_error` contract; component params optional.

## Risks / Trade-offs

- **[SDXL regression from changed resolution]** → `LORA_CHECKPOINT_DIRS`-first ordering preserved;
  regression test covers SDXL bare-name resolving to the same path as today.
- **[Anima generation component mapping is unverified]** → treat as an explicit implementation
  verification step (D3); gate the smoke-test task on a real Anima workflow check before asserting done.
- **[Existence check false-negative on network/virtual mounts]** → `allow_unverified_checkpoint` bypass
  plus remote-reference exemption keep the door open.
- **[Duplicated search-dir parsing between trainer and `core/resources.py`]** → reuse the existing
  comma-split helper rather than re-implementing directory parsing.

## Migration Plan

Additive and backward compatible; no data migration. New `allow_unverified_checkpoint` defaults to
`false` and the smoke-test override fields default to unset, so existing callers are unaffected.
Rollback is a straight revert of the trainer/API/MCP changes.

## Open Questions

- ~~Does the Anima generation workflow expect the training-time `qwen3` file as its `text_encoder`, or a
  distinct CLIP?~~ **Resolved:** `backend/workflows/anima.json` wires `CLIPLoader.clip_name =
  qwen_3_06b_base.safetensors` (type `qwen_image`), and `workflow_form` maps the `text_encoder`
  parameter to `CLIPLoader.clip_name`. So the training `anima_qwen3` is the generation `text_encoder`,
  which is exactly the mapping the smoke test uses.
