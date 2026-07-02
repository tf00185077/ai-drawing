# Qwen pose/action control — two task lines

## Goal

CTY wants both directions tested independently, with the same discipline:

1. find successful cases / reproducible workflow
2. faithful smoke test first
3. only after a successful baseline, run single-factor tests

Do not mix the two routes when evaluating results.

---

## Route B — Qwen Image Union / DiffSynth OpenPose

### Direction

`prompt + pose/OpenPose control image -> new Qwen-Image output`

This is pose-conditioned generation. It does not primarily preserve a specific source character identity.

### Current best success case

Primary faithful-copy workflow:

- `axiomgraph/ComfyUIWorkflow`: `Qwen Image Union Diffsynth Lora OpenPose.json`
- local copy: `research/qwen-pose-routes/route-b-axiomgraph-qwen-union-openpose.json`
- raw source: `https://raw.githubusercontent.com/axiomgraph/ComfyUIWorkflow/main/Qwen%20Image%20Union%20Diffsynth%20Lora%20OpenPose.json`

Secondary official confirmation/template:

- ComfyUI docs: `https://docs.comfy.org/tutorials/image/qwen/qwen-image`
- official template local copy: `research/qwen-pose-routes/official-qwen-union-control-lora.json`
- official blog confirms Union LoRA supports OpenPose.

### Faithful baseline resources

Install into ComfyUI:

```text
models/diffusion_models/qwen_image_fp8_e4m3fn.safetensors
models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
models/vae/qwen_image_vae.safetensors
models/loras/qwen_image_union_diffsynth_lora.safetensors
models/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors
```

Custom nodes / preprocessors:

```text
comfyui_controlnet_aux / DWPreprocessor
rgthree-comfy
SetNode/GetNode support if required by imported workflow
```

### Baseline params from axiomgraph

```text
DWPreprocessor:
  detect_body: enable
  detect_hand: enable
  detect_face: enable
  resolution: 1024
  bbox_detector: yolox_l.onnx
  pose_estimator: dw-ll_ucoco_384_bs5.torchscript.pt

KSampler:
  steps: 10
  cfg: 1
  sampler: euler
  scheduler: simple
  denoise: 1

LoRAs:
  qwen_image_union_diffsynth_lora: 1.0
  Qwen-Image-Lightning-8steps-V1.1: 1.0
```

### Single-factor sequence after baseline succeeds

Keep prompt, input pose image, seed, resolution, and all non-target params fixed.

1. `control LoRA strength`: 1.0 -> 0.75 -> 1.25
2. `DWPose resolution`: 1024 -> 768 -> 1216
3. `hand/face detection`: body+hand+face -> body only -> body+hand
4. `Lightning steps`: 10 -> 8 -> 12 with 8-step Lightning
5. Optional: swap to official 4-step Lightning template only after the above baseline is stable.

---

## Route C — Qwen Image Edit 2511 + AnyPose

### Direction

`image 1 subject/character + image 2 pose reference (+ optional image 3 DWPose skeleton) -> edited image`

This is pose-transfer editing. It is the route for “make this existing character do this pose”.

### Current best success cases

Primary author/model card:

- `lilylilith/AnyPose`: `https://huggingface.co/lilylilith/AnyPose`
- LoRAs: `2511-AnyPose-base-000006250.safetensors`, `2511-AnyPose-helper-00006000.safetensors`

Working demo / reproducible diffusers success case:

- `linoyts/Qwen-Image-Edit-2511-AnyPose`: `https://huggingface.co/spaces/linoyts/Qwen-Image-Edit-2511-AnyPose`
- uses Qwen-Image-Edit-2511 + AnyPose + Qwen-Image-Edit-2511 Lightning for 4-step pose transfer.

Official ComfyUI Qwen Edit 2511 baseline:

- docs: `https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511`
- local copy: `research/qwen-pose-routes/official-qwen-image-edit-2511.json`

### Faithful baseline resources

Install into ComfyUI:

```text
models/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors
models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
models/vae/qwen_image_vae.safetensors
models/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
models/loras/2511-AnyPose-base-000006250.safetensors
models/loras/2511-AnyPose-helper-00006000.safetensors
```

Note: official docs list `qwen_image_edit_2511_bf16.safetensors`; for this Mac the fp8mixed 2511 file is the practical first baseline because BF16 is ~40.9 GB and fp8mixed is ~20.5 GB.

### Baseline prompt from AnyPose

```text
Make the person in image 1 do the exact same pose of the person in image 2. Changing the style and background of the image of the person in image 1 is undesirable, so don't do it. The new pose should be pixel accurate to the pose we are trying to copy. The position of the arms and head and legs should be the same as the pose we are trying to copy. Change the field of view and angle to match exactly image 2. Head tilt and eye gaze pose should match the person in image 2.
```

If background leaks from image 2, append:

```text
Remove the background of image 2, and replace it with the background of image 1.
```

### Faithful baseline params

```text
Qwen Edit 2511 model: qwen_image_edit_2511_fp8mixed.safetensors
Lightning LoRA: Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
AnyPose base strength: 0.7
AnyPose helper strength: 0.7
steps: 4
cfg: low/lightning-style baseline, start from official workflow value
input images: image1 full-body subject if possible; image2 pose reference
optional image3: DWPose skeleton from image2 via TextEncodeQwenImageEditPlus image3 input
```

### Single-factor sequence after baseline succeeds

Keep image1, image2, prompt, seed, resolution, and all non-target params fixed.

1. `AnyPose strength`: base/helper 0.7 -> 0.5 -> 0.9
2. `helper only effect`: base 0.7/helper 0.0; base 0.0/helper 0.7
3. `Lightning steps`: 4 -> 8, using matching Lightning if installed
4. `background instruction`: baseline prompt -> append background-preservation sentence
5. `image3 skeleton`: two-image input -> three-image input with generated DWPose skeleton

---

## Current local state recorded

- `qwen_image_vae.safetensors` already existed locally.
- `rgthree-comfy` already existed locally.
- `comfyui_controlnet_aux` was cloned; `onnxruntime-gpu` failed on macOS, so dependencies were installed with CPU `onnxruntime` instead.
- Required Qwen/AnyPose model downloads are running via `~/qwen_pose_resource_download.sh`.
- Current free disk before download: ~329 GiB.

## Next verification gate

After downloads finish:

1. restart ComfyUI so new custom nodes/resources are visible
2. verify `DWPreprocessor` appears in node search
3. verify resource inventory lists the Qwen/AnyPose files
4. convert/import baseline workflows to API form
5. submit one Route B smoke test and one Route C smoke test
6. only if each baseline completes, run its single-factor matrix
