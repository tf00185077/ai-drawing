## 1. Runtime Installation and Configuration

- [x] 1.1 Install or select a local Kohya `sd-scripts` checkout outside committed source control.
- [x] 1.2 Create or select a compatible training Python environment with `accelerate` available to the backend trainer command path.
- [x] 1.3 Configure local `.env` values for `SD_SCRIPTS_PATH`, optional `SD_SCRIPTS_PYTHON`, `COMFYUI_LORA_DIR`, and the checkpoint used for bounded verification.
- [x] 1.4 Verify required runtime files exist: `train_network.py`, `sdxl_train_network.py`, `anima_train_network.py`, `anima_train.py`, `library/anima_train_utils.py`, and `finetune/tag_images_by_wd14_tagger.py`.

Evidence / blocker (2026-07-06):

```text
$ git clone --depth 1 https://github.com/kohya-ss/sd-scripts.git sd-scripts
Cloning into 'sd-scripts'...
fatal: unable to access 'https://github.com/kohya-ss/sd-scripts.git/': Could not resolve host: github.com

$ test -e sd-scripts && find sd-scripts -maxdepth 2 -print | head -20 || echo 'sd-scripts directory absent after failed clone'
sd-scripts directory absent after failed clone

$ find /Users/tf00185088 /Volumes/AI-Drawing-16T -maxdepth 6 \( -iname '*sd-scripts*' -o -iname '*kohya*' -o -iname '*lora*train*' \) 2>/dev/null | head -120
# No Kohya sd-scripts checkout or archive was found; output only listed this repo's LoRA code/docs.

$ lora_train/kohya-runtime-venv/bin/python - <<'PY'
import sys
import accelerate
print('sys.executable=', sys.executable)
print('accelerate=', getattr(accelerate, '__version__', 'unknown'))
PY
sys.executable= /Users/tf00185088/Desktop/ai-drawing/lora_train/kohya-runtime-venv/bin/python
accelerate= 1.14.0

$ lora_train/kohya-runtime-venv/bin/accelerate launch --help
accelerate_launch_rc=0
usage: accelerate <command> [<args>] launch [-h] [--config_file CONFIG_FILE]

$ PYTHONPATH=backend backend/.venv/bin/python - <<'PY'
from pathlib import Path
from app.config import get_settings
s=get_settings()
python_exe = s.sd_scripts_python
acc_path = Path(python_exe).resolve().parent / 'accelerate'
print('sd_scripts_python=', python_exe)
print('sibling_accelerate_exists=', acc_path.exists())
print('sd_scripts_path=', s.sd_scripts_path)
print('comfyui_lora_dir=', s.comfyui_lora_dir)
print('lora_default_checkpoint=', s.lora_default_checkpoint)
print('lora_checkpoint_dirs=', s.lora_checkpoint_dirs)
PY
sd_scripts_python= /Users/tf00185088/Desktop/ai-drawing/lora_train/kohya-runtime-venv/bin/python
sibling_accelerate_exists= True
sd_scripts_path= /Users/tf00185088/Desktop/ai-drawing/sd-scripts
comfyui_lora_dir= /Volumes/AI-Drawing-16T/ai-drawing/models/loras
lora_default_checkpoint= v1-5-pruned-emaonly.ckpt
lora_checkpoint_dirs= /Volumes/AI-Drawing-16T/ai-drawing/models/checkpoints

$ printf 'sd-scripts path: '; test -d /Users/tf00185088/Desktop/ai-drawing/sd-scripts && echo present || echo missing
sd-scripts path: missing
missing train_network.py
missing sdxl_train_network.py
missing finetune/tag_images_by_wd14_tagger.py
```

Local `.env` is ignored by git and now contains:

```text
SD_SCRIPTS_PATH=/Users/tf00185088/Desktop/ai-drawing/sd-scripts
SD_SCRIPTS_PYTHON=/Users/tf00185088/Desktop/ai-drawing/lora_train/kohya-runtime-venv/bin/python
COMFYUI_LORA_DIR=/Volumes/AI-Drawing-16T/ai-drawing/models/loras
LORA_DEFAULT_CHECKPOINT=v1-5-pruned-emaonly.ckpt
LORA_CHECKPOINT_DIRS=/Volumes/AI-Drawing-16T/ai-drawing/models/checkpoints
```

Secondary registration blocker observed under the current agent sandbox:

```text
$ ls -ld /Volumes/AI-Drawing-16T/ai-drawing/models/checkpoints/v1-5-pruned-emaonly.ckpt /Volumes/AI-Drawing-16T/ai-drawing/models/loras
-rw-------  1 tf00185088  staff  4265380512 Jun  1 19:39 /Volumes/AI-Drawing-16T/ai-drawing/models/checkpoints/v1-5-pruned-emaonly.ckpt
drwxr-xr-x  25 tf00185088  staff  800 Jul  3 18:56 /Volumes/AI-Drawing-16T/ai-drawing/models/loras
loras writable=no
```

Resolved runtime preflight evidence (2026-07-06):

```text
$ for f in train_network.py sdxl_train_network.py anima_train_network.py anima_train.py library/anima_train_utils.py finetune/tag_images_by_wd14_tagger.py; do if test -f "sd-scripts/$f"; then printf 'present %s\n' "$f"; else printf 'missing %s\n' "$f"; fi; done
present train_network.py
present sdxl_train_network.py
present anima_train_network.py
present anima_train.py
present library/anima_train_utils.py
present finetune/tag_images_by_wd14_tagger.py

$ lora_train/kohya-runtime-venv/bin/python sd-scripts/anima_train_network.py --help >/tmp/anima_train_network_help.txt
anima_train_network_help_rc=0

$ rg -- '--(pretrained_model_name_or_path|dataset_config|output_dir|output_name|network_module|network_dim|network_alpha|mixed_precision)' /tmp/anima_train_network_help.txt
[--pretrained_model_name_or_path PRETRAINED_MODEL_NAME_OR_PATH]
[--output_dir OUTPUT_DIR]
[--output_name OUTPUT_NAME]
[--mixed_precision {no,fp16,bf16}] [--full_fp16]
[--dataset_config DATASET_CONFIG]
[--network_module NETWORK_MODULE]
[--network_dim NETWORK_DIM]
[--network_alpha NETWORK_ALPHA]
--pretrained_model_name_or_path PRETRAINED_MODEL_NAME_OR_PATH
--output_dir OUTPUT_DIR
--output_name OUTPUT_NAME
--mixed_precision {no,fp16,bf16}
--dataset_config DATASET_CONFIG
--network_module NETWORK_MODULE
--network_dim NETWORK_DIM
--network_alpha NETWORK_ALPHA
```

## 2. Bounded LoRA Runtime Verification

- [x] 2.1 Prepare a small local LoRA dataset that is safe to train and is not committed as a new large artifact.
- [x] 2.2 Run the existing dataset workflow through backend APIs or MCP tools: inspect, dry-run prepare, apply prepare, and validate.
- [x] 2.3 Start one bounded Anima training job with minimal safe parameters, `model_family=anima`, and capture the returned durable `job_id`.
- [x] 2.4 Poll job status and logs until the real Kohya subprocess reaches a terminal state.
- [x] 2.5 Confirm a successful job records `output_path`, registers a `.safetensors` into `COMFYUI_LORA_DIR`, and records `registered_lora_name`.
- [x] 2.6 Run the LoRA smoke-test operation for the completed registered job and record the generation job id or structured smoke-test error.

Evidence / blocker (2026-07-06):

```text
$ PYTHONPATH=backend backend/.venv/bin/python <create-small-dataset-script>
/Users/tf00185088/Desktop/ai-drawing/lora_train/runtime_kohya_smoke_20260706
images= 10 captions= 10

$ POST /api/lora-train/datasets/runtime_kohya_smoke_20260706?trigger_token=kohyaruntimeprobe
status_code= 200
image_count=10 caption_count=10 missing_caption_count=0
dataset_hash=29dfd29014779e2b2b1644a79f3d6bf50ee4b2977df8da29f03635616c3311de
validation.ok=false
validation.errors[0].code=missing_trigger_token

$ POST /api/lora-train/datasets/prepare dry_run=true
status_code= 200
ok=true normalized_trigger_token=kohyaruntimeprobe changed_count=10 unchanged_count=0
dataset_hash_before=29dfd29014779e2b2b1644a79f3d6bf50ee4b2977df8da29f03635616c3311de

$ POST /api/lora-train/datasets/prepare dry_run=false expected_dataset_hash=29dfd...
status_code= 200
ok=true changed_count=10 backup_id=20260706T130310Z-974779d4
dataset_hash_after=7521a2277e6dbc1f179f2e249b112b1cb1321752f15a78a45984748d0cabae02

$ POST /api/lora-train/datasets/validate expected_dataset_hash=7521...
status_code= 200
ok=true image_count=10 caption_count=10 missing_caption_count=0 errors=[]

$ POST /api/lora-train/start epochs=1 resolution=256 batch_size=1 network_dim=4 network_alpha=4 mixed_precision=fp32
status_code= 400
detail.code=sd_scripts_path_missing
detail.message=sd_scripts_path does not exist: /Users/tf00185088/Desktop/ai-drawing/sd-scripts
detail.details.expected_script=train_network.py
```

At that point, no durable `job_id` was created because backend trainer preflight rejected the missing `sd-scripts` checkout before queueing.

Additional evidence / code fix (2026-07-06):

```text
Hermes installed/cloned Kohya sd-scripts at:
/Users/tf00185088/Desktop/ai-drawing/sd-scripts

Using lora_train/kohya-runtime-venv/bin/python:
train_network.py --help                         -> exit 0
sdxl_train_network.py --help                    -> exit 0
finetune/tag_images_by_wd14_tagger.py --help    -> exit 0

Bounded backend job queued:
job_id=02de69a8-d81e-4410-a87d-d8f06c41fc4f

The job failed before useful training because the backend emitted:
--mixed_precision fp32

Current Kohya argparse accepts only:
no, fp16, bf16

Observed error:
train_network.py: error: argument --mixed_precision: invalid choice: 'fp32' (choose from 'no', 'fp16', 'bf16')
```

Backend compatibility fix: API/config callers may still request `mixed_precision=fp32` for full precision, and may also request Kohya-native `no`; command construction now maps the Kohya CLI value to `--mixed_precision no` while durable job params preserve `mixed_precision` and add `kohya_mixed_precision`.

Additional Anima failure evidence / code fix (2026-07-06):

```text
Hermes used Anima checkpoint:
/Volumes/AI-Drawing-16T/ai-drawing/models/checkpoints/icerealisticAnima_icerealisticAnima.safetensors

Failed backend job:
job_id=a6de8666-53ca-4708-ae0c-ad35a3aebef1

Current backend command incorrectly routed the Anima checkpoint through SD1.x:
train_network.py ... --pretrained_model_name_or_path ...icerealisticAnima... --mixed_precision no ...

Observed terminal log tail:
KeyError: 'time_embed.0.weight'

Hermes safetensors key inspection:
icerealisticAnima_icerealisticAnima.safetensors -> model.diffusion_model.blocks.*; no time_embed.0.weight; no SD1 input_blocks
anima_baseV10.safetensors -> net.blocks.*
anima_baseV10_txt.safetensors -> model.layers.* / model.embed_tokens.weight
```

Backend/API/MCP compatibility fix: `lora_train_start` now accepts `model_family` with supported values `sd15`, `sdxl`, and `anima`. `sd15` launches `train_network.py`, `sdxl` launches `sdxl_train_network.py`, and `anima` launches `anima_train_network.py`. The legacy `sdxl` boolean remains supported when `model_family` is absent. Durable job params now record `model_family`, `trainer_script`, `mixed_precision`, and `kohya_mixed_precision`; unsupported families return structured `unsupported_model_family` without creating a job.

Additional Anima runtime-args failure evidence / code fix (2026-07-06):

```text
Hermes submitted live bounded Anima job:
job_id=7ce220f7-fc13-47e6-9858-a63000ebf81f

Backend correctly launched:
anima_train_network.py ... --mixed_precision no ...

Observed terminal failure:
ValueError: Either qwen3_tokenizer or qwen3_path must be provided

Root cause:
The backend command lacked anima_train_network.py's required --qwen3 path and did not expose Anima-specific runtime paths in API/config/MCP.
```

Backend/API/MCP compatibility fix: `lora_train_start` now accepts Anima runtime paths as `anima_qwen3`/`anima_vae`/`anima_t5_tokenizer_path` (API also accepts `qwen3`/`vae`/`t5_tokenizer_path` aliases). Config defaults are `LORA_ANIMA_QWEN3`, `LORA_ANIMA_VAE`, and optional `LORA_ANIMA_T5_TOKENIZER_PATH`. For `model_family=anima`, backend validates the resolved qwen3 path before creating a durable job and returns structured 400 `anima_qwen3_missing` if absent or missing. Durable job params record `anima_qwen3`, `anima_vae`, and `anima_t5_tokenizer_path`; the launched Anima command appends `--qwen3 <path>`, `--vae <path>` when configured/provided, and `--t5_tokenizer_path <path>` when configured/provided. Source inspection shows `--qwen_image_vae_2d` is an optional Qwen-Image VAE performance/memory path, not required for the provided VAE weights, so this fix does not force it.

Additional Anima network-module failure evidence / code fix (2026-07-06):

```text
Hermes submitted live bounded Anima jobs:
job_id=d3854dd0-8321-4dab-8664-c946c1a1debc
job_id=569deb43-2a0a-4f00-8803-c5cb61b1f060

Backend correctly selected:
anima_train_network.py ... --qwen3 ... --vae ...

Observed terminal failure:
ValueError: optimizer got an empty parameter list

Root cause:
The backend still emitted `--network_module networks.lora` for model_family=anima.
Installed sd-scripts contains `networks/lora_anima.py`; source inspection shows Anima-specific target modules in
`networks/lora_anima.py` (`ANIMA_TARGET_REPLACE_MODULE`, `ANIMA_ADAPTER_TARGET_REPLACE_MODULE`, Qwen3 text encoder
targets) and `networks/network_base.py` Anima arch config.
```

Backend/API/MCP compatibility fix: for `model_family=anima`, backend now resolves the default `network_module` to `networks.lora_anima`; `sd15` and `sdxl` continue to resolve to `networks.lora`. `TrainStartRequest`, `/api/lora-train/start`, and MCP `lora_train_start` now accept an explicit `network_module` override. Durable job params record the resolved `network_module`, and command construction consumes that resolved value for `--network_module`.

Next Hermes live bounded Anima run should use:

```text
model_family=anima
checkpoint=/Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/anima_baseV10.safetensors
anima_qwen3=/Volumes/AI-Drawing-16T/ai-drawing/models/text_encoders/qwen_3_06b_base.safetensors
anima_vae=/Volumes/AI-Drawing-16T/ai-drawing/models/vae/qwen_image_vae.safetensors
network_module=networks.lora_anima
```

Prefer `anima_baseV10.safetensors` as the Anima DiT/diffusion model candidate for the next run; do not reuse `icerealisticAnima_icerealisticAnima.safetensors` unless further source inspection proves that wrapper is the correct trainer input.

Command-construction/API validation for this fix:

```text
$ backend/.venv/bin/python -m pytest backend/tests/test_lora_trainer.py backend/tests/test_lora_train_workflow_api.py -x -q
35 passed, 2 warnings in 0.21s

$ (cd mcp-server && .venv/bin/python -m pytest tests/test_lora_train_tools.py -x -q)
8 passed in 0.20s
```

Final live bounded Anima verification (2026-07-06):

```text
Prepared clean dataset:
folder=runtime_anima_smoke_clean_20260706
trigger_token=animacleanprobe
prepare.changed_count=10
prepare.backup_id=20260706T145825Z-675fd436
validated dataset_hash=184a5d9fd27d46f046af9d4f718b75e4f2b82871c96ee5faec4c18569428051f

POST /api/lora-train/start
model_family=anima
checkpoint=/Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/anima_baseV10.safetensors
anima_qwen3=/Volumes/AI-Drawing-16T/ai-drawing/models/text_encoders/qwen_3_06b_base.safetensors
anima_vae=/Volumes/AI-Drawing-16T/ai-drawing/models/vae/qwen_image_vae.safetensors
network_module=networks.lora_anima
mixed_precision=fp32 -> kohya_mixed_precision=no

job_id=0b1c0988-83ad-469f-a5bf-6a8fd9273b4f
status=completed
stage=completed
progress=1.0
current_epoch=1
total_epochs=1
trainer_script=anima_train_network.py
network_module=networks.lora_anima
output_path=/Users/tf00185088/Desktop/ai-drawing/lora_train/output/runtime_anima_smoke_clean_20260706.safetensors
registered_lora_name=runtime_anima_smoke_clean_20260706.safetensors
registered_lora_path=/Volumes/AI-Drawing-16T/ai-drawing/models/loras/runtime_anima_smoke_clean_20260706.safetensors
registered_lora_size=33201416
registration_error=null

Log evidence:
Loaded DiT model from /Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/anima_baseV10.safetensors, missing keys: 0, unexpected keys: 0
import network module: networks.lora_anima
create LoRA for Text Encoder 1: 196 modules
create LoRA for Anima DiT: 280 modules
total optimization steps: 3
saving checkpoint: /Users/tf00185088/Desktop/ai-drawing/lora_train/output/runtime_anima_smoke_clean_20260706.safetensors
Registered LoRA: runtime_anima_smoke_clean_20260706.safetensors -> /Volumes/AI-Drawing-16T/ai-drawing/models/loras/runtime_anima_smoke_clean_20260706.safetensors

POST /api/lora-train/jobs/0b1c0988-83ad-469f-a5bf-6a8fd9273b4f/smoke-test
smoke_test_status=submitted
generation_job_id=b49d2e24-4389-42c9-a80c-6043b8279f6e
smoke_test_error=null
```

Earlier failed jobs `a6de8666-53ca-4708-ae0c-ad35a3aebef1`, `d3854dd0-8321-4dab-8664-c946c1a1debc`, and `569deb43-2a0a-4f00-8803-c5cb61b1f060` document the incremental fixes; final successful live verification is `0b1c0988-83ad-469f-a5bf-6a8fd9273b4f`.

## 3. Evidence and Cleanup

- [x] 3.1 Document the runtime preflight commands, bounded training command/API sequence, job id, log path, and smoke-test result.
- [x] 3.2 Verify generated models, logs, virtual environments, and local path configuration are not accidentally staged for commit.
- [x] 3.3 Run `openspec validate install-verify-kohya-sd-scripts-runtime --strict` after recording evidence.

Evidence (2026-07-06):

```text
$ git status --short --ignored | sed -n '1,120p'
?? .hermes/
?? .louise_pairwise_41f1s_watchdog_reported
!! .env
!! backend/.venv/
!! lora_train/
!! outputs/
```

The selected training venv (`lora_train/kohya-runtime-venv`), prepared dataset (`lora_train/runtime_kohya_smoke_20260706`), and local `.env` are ignored. No generated LoRA model or training log was produced because training did not start.

Validation output:

```text
$ openspec validate install-verify-kohya-sd-scripts-runtime --strict
Change 'install-verify-kohya-sd-scripts-runtime' is valid

$ openspec validate --all
Totals: 12 passed, 0 failed (12 items)

$ backend/.venv/bin/python -m pytest backend/tests/ -x -q
297 passed, 2 warnings in 0.70s

$ (cd mcp-server && .venv/bin/python -m pytest tests/ -x -q)
97 passed in 0.28s
```

Focused mixed precision fix validation (2026-07-06):

```text
$ backend/.venv/bin/python -m pytest backend/tests/test_lora_trainer.py backend/tests/test_lora_train_workflow_api.py -x -q
27 passed, 2 warnings in 0.16s

$ openspec validate install-verify-kohya-sd-scripts-runtime --strict
Change 'install-verify-kohya-sd-scripts-runtime' is valid

$ openspec validate --all
Totals: 12 passed, 0 failed (12 items)
```

Focused Anima runtime args fix validation (2026-07-06):

```text
$ backend/.venv/bin/python -m pytest backend/tests/test_lora_trainer.py backend/tests/test_lora_train_workflow_api.py -x -q
35 passed, 2 warnings in 0.21s

$ (cd mcp-server && .venv/bin/python -m pytest tests/test_lora_train_tools.py -x -q)
8 passed in 0.20s

$ backend/.venv/bin/python -m pytest backend/tests/ -x -q
297 passed, 2 warnings in 0.70s

$ (cd mcp-server && .venv/bin/python -m pytest tests/ -x -q)
97 passed in 0.28s

$ openspec validate install-verify-kohya-sd-scripts-runtime --strict
Change 'install-verify-kohya-sd-scripts-runtime' is valid

$ openspec validate --all
Totals: 12 passed, 0 failed (12 items)

$ git diff --check
# no output
```

Focused Anima network-module fix validation (2026-07-06):

```text
$ backend/.venv/bin/python -m pytest backend/tests/test_lora_trainer.py backend/tests/test_lora_train_workflow_api.py -x -q
37 passed, 2 warnings in 0.22s

$ (cd mcp-server && .venv/bin/python -m pytest tests/test_lora_train_tools.py -x -q)
8 passed in 0.20s

$ backend/.venv/bin/python -m pytest backend/tests/ -x -q
299 passed, 2 warnings in 0.67s

$ (cd mcp-server && .venv/bin/python -m pytest tests/ -x -q)
97 passed in 0.28s

$ openspec validate install-verify-kohya-sd-scripts-runtime --strict
Change 'install-verify-kohya-sd-scripts-runtime' is valid

$ openspec validate --all
Totals: 12 passed, 0 failed (12 items)

$ git diff --check
# no output
```
