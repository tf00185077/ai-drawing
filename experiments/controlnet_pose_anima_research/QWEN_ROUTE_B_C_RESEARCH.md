# Route B/C research — Qwen pose control and Qwen Edit AnyPose

Date: 2026-06-26

CTY requested abandoning Anima legacy pose and Anima any-test testing, then researching how others do:

- Route B: Qwen Image Union Control / DiffSynth Union pose
- Route C: Qwen Image Edit / AnyPose / pose transfer

No visual judgement is included.

---

## Local inventory

### Relevant local ComfyUI nodes present

```text
QwenImageDiffsynthControlnet        Apply Qwen Image DiffSynth ControlNet      model/patch/qwen
TextEncodeQwenImageEdit             model/conditioning/qwen image
TextEncodeQwenImageEditPlus         model/conditioning/qwen image
EmptyQwenImageLayeredLatentImage    model/latent/qwen
ModelMergeQwenImage                 model/merging/model specific
ModelPatchLoader                    model/loaders
LoraLoaderModelOnly                 model/loaders
ControlNetLoader / ControlNetApplyAdvanced / SetUnionControlNetType
SDPoseKeypointExtractor / SDPoseDrawKeypoints
```

### Important schemas

`QwenImageDiffsynthControlnet`:

```text
inputs:
  model: MODEL
  model_patch: MODEL_PATCH
  vae: VAE
  image: IMAGE
  strength: FLOAT
optional:
  mask: MASK
output:
  MODEL
```

`ModelPatchLoader`:

```text
input:
  name: COMBO
output:
  MODEL_PATCH
```

`TextEncodeQwenImageEditPlus`:

```text
required:
  clip: CLIP
  prompt: STRING
optional:
  vae: VAE
  image1: IMAGE
  image2: IMAGE
  image3: IMAGE
output:
  CONDITIONING
```

This confirms the local ComfyUI build has native Qwen edit/multi-image conditioning nodes.

### Local models currently missing for Qwen routes

Local model inventory found only:

```text
/Volumes/AI-Drawing-16T/ai-drawing/models/text_encoders/qwen_3_06b_base.safetensors
/Volumes/AI-Drawing-16T/ai-drawing/models/vae/qwen_image_vae.safetensors
```

Missing for Route B Qwen-Image Union/DiffSynth:

```text
models/diffusion_models/qwen_image_fp8_e4m3fn.safetensors or equivalent
models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
models/loras/qwen_image_union_diffsynth_lora.safetensors
optional: Qwen-Image-Lightning-8steps-V1.1.safetensors
optional: InstantX/Qwen-Image-ControlNet-Union model in models/controlnet
```

Missing for Route C Qwen Edit 2511 AnyPose:

```text
Qwen-Image-Edit-2511 diffusion model or AIO equivalent
AnyPose base LoRA
AnyPose helper LoRA
Qwen-Image-Edit-2511 Lightning LoRA
```

---

## Route B1 — Qwen Image Union DiffSynth LoRA OpenPose

### Source examples

- ComfyUI Qwen tutorial: `docs.comfy.org/tutorials/image/qwen/qwen-image`
- Comfy blog: `Qwen Image ControlNet & LoRA, EasyCache and Context Window in ComfyUI`
- AxiomGraph workflow: `Qwen Image Union Diffsynth Lora OpenPose.json`

### What others do

The most concrete workflow found is AxiomGraph's:

```text
Qwen Image Union Diffsynth Lora OpenPose.json
```

It uses:

```text
UNETLoader: qwen_image_fp8_e4m3fn.safetensors
CLIPLoader: qwen_2.5_vl_7b_fp8_scaled.safetensors, type=qwen_image
VAELoader: qwen_image_vae.safetensors
LoraLoaderModelOnly: qwen_image_union_diffsynth_lora.safetensors @ 1
LoraLoaderModelOnly: Qwen-Image-Lightning-8steps-V1.1.safetensors @ 1
DWPreprocessor: generate OpenPose/DWPose-style pose map from reference image
ImageScaleToTotalPixels
VAEEncode(reference latent)
ReferenceLatent nodes for positive/negative conditioning
KSampler: 10 steps, cfg 1, euler/simple, denoise 1
VAEDecode
SaveImage
```

The workflow prompt example is simple:

```text
a man standing on a tip of boat
```

Key point: this route uses the Qwen Image **Union DiffSynth LoRA** as a model-only LoRA, not a standard `ControlNetLoader` apply. It is a Qwen-Image generation route.

### Model files from Qwen docs / workflow

```text
Comfy-Org/Qwen-Image_ComfyUI/split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors
Comfy-Org/Qwen-Image_ComfyUI/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
Comfy-Org/Qwen-Image_ComfyUI/split_files/vae/qwen_image_vae.safetensors
Comfy-Org/Qwen-Image-DiffSynth-ControlNets/split_files/loras/qwen_image_union_diffsynth_lora.safetensors
lightx2v/Qwen-Image-Lightning/Qwen-Image-Lightning-8steps-V1.1.safetensors
```

### Supported controls according to Comfy docs

`qwen_image_union_diffsynth_lora.safetensors` supports:

```text
canny
Depth
Pose
Lineart
Softedge
Normal
OpenPose
```

### Practical interpretation

For pose, this is probably the more concrete Route B subroute because it has a real shared ComfyUI workflow JSON and includes `DWPreprocessor`.

---

## Route B2 — InstantX/Qwen-Image-ControlNet-Union

### Source

```text
InstantX/Qwen-Image-ControlNet-Union
```

### What it is

A unified ControlNet for `Qwen/Qwen-Image` supporting:

```text
canny
soft edge
depth
pose
```

Model card details:

```text
5 double blocks copied from pretrained transformer layers
trained from scratch for 50K steps
10M general/human images
1328x1328 training resolution
bf16
```

The diffusers sample uses:

```python
QwenImageControlNetModel.from_pretrained("InstantX/Qwen-Image-ControlNet-Union")
QwenImageControlNetPipeline.from_pretrained("Qwen/Qwen-Image", controlnet=controlnet)
controlnet_conditioning_scale = 1.0
```

### Practical interpretation

This is a standard ControlNet-style route for Qwen-Image, but local ComfyUI workflow details are less concrete than the AxiomGraph DiffSynth LoRA workflow. It may require a newer ComfyUI native workflow/template or correct controlnet resource installation.

---

## Route C — Qwen Image Edit 2511 + AnyPose

### Sources

- `lilylilith/AnyPose`
- `linoyts/Qwen-Image-Edit-2511-AnyPose` HF Space
- MyAIForce article: `Pose Transfer in ComfyUI with Qwen Edit 2511`
- Qwen blog: `Qwen-Image-Edit-2511: Improve Consistency`

### What others do

The core workflow is not OpenPose ControlNet. It is **edit-based pose transfer**:

Inputs:

```text
Image 1: subject / character image whose identity should be preserved
Image 2: pose reference image
optional Image 3: DWPose skeleton generated from pose reference
```

Base model:

```text
Qwen-Image-Edit-2511
```

LoRAs:

```text
lilylilith/AnyPose:
  2511-AnyPose-base-000006250.safetensors
  2511-AnyPose-helper-00006000.safetensors

lightx2v/Qwen-Image-Edit-2511-Lightning:
  Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
  or 8steps variant
```

Recommended LoRA strengths from AnyPose model card / article:

```text
AnyPose base: 0.7
AnyPose helper: 0.7
Lightning: 4-step for fast inference
```

Main prompt from AnyPose:

```text
Make the person in image 1 do the exact same pose of the person in image 2. Changing the style and background of the image of the person in image 1 is undesirable, so don't do it. The new pose should be pixel accurate to the pose we are trying to copy. The position of the arms and head and legs should be the same as the pose we are trying to copy. Change the field of view and angle to match exactly image 2. Head tilt and eye gaze pose should match the person in image 2.
```

MyAIForce's higher-success variant uses three images:

```text
Image 1: portrait/character to edit
Image 2: cleaned pose reference image
Image 3: DWPose skeleton from pose reference
```

Prompt should refer to both Image 2 and Image 3 for pose guidance.

### Cleaning pose reference

The article recommends cleaning Image 2:

```text
mask/remove the pose-reference head
remove background
avoid copying pose-reference face/hair/background
```

Reason: the model may otherwise copy unwanted identity, hair, props, or background from the pose reference.

### Qwen Edit 2511 capabilities

Qwen's blog says 2511 improves:

```text
character consistency
multi-person consistency
geometric reasoning
integrated selected LoRA capabilities
```

This fits pose-transfer editing better than pure txt2img pose control.

### Practical interpretation

Route C is likely the best candidate when the goal is:

```text
make this specific existing character/image adopt that pose
```

It is not Anima-native, but can produce a posed character image that can later be passed into Anima img2img/style transfer if needed.

---

## Qwen Image Edit + OpenPose ControlNet combination status

Found both Comfy-Org and ZHO-ZHO-ZHO issues asking whether Qwen Image Edit can be combined with OpenPose ControlNet. The public issues did not provide a confirmed official solution.

Implication:

```text
Do not assume Qwen Image Edit + OpenPose ControlNet is a solved native combo.
For edit-based pose transfer, use Qwen Edit 2511 + AnyPose LoRAs instead.
For controlnet-based pose generation, use Qwen Image Union/DiffSynth route instead.
```

---

## Comparison for next test

### Route B — Qwen Image Union/DiffSynth OpenPose

Best for:

```text
pose-controlled generation from prompt/reference pose
```

Concrete workflow exists:

```text
AxiomGraph Qwen Image Union Diffsynth Lora OpenPose.json
```

Local blockers:

```text
large Qwen Image diffusion model missing
qwen_2.5_vl_7b_fp8_scaled missing
qwen_image_union_diffsynth_lora missing
Qwen Image Lightning LoRA missing
DWPose dependencies may need model download
```

### Route C — Qwen Edit 2511 AnyPose

Best for:

```text
pose transfer onto an existing subject/image
```

Concrete resources exist:

```text
Qwen-Image-Edit-2511
lilylilith/AnyPose base/helper LoRAs
Qwen-Image-Edit-2511-Lightning
TextEncodeQwenImageEditPlus supports image1/image2/image3 locally
```

Local blockers:

```text
Qwen Edit 2511 model missing
AnyPose base/helper missing
Lightning LoRA missing
need concrete ComfyUI workflow JSON or construct from TextEncodeQwenImageEditPlus schema
```

### Current recommendation

If CTY wants to test **copy a pose onto an existing character**, Route C is more aligned.

If CTY wants to test **prompt-to-image with a pose skeleton**, Route B is more aligned.

Both are Qwen-family first-stage routes, not direct Anima. The likely practical pipeline for Anima-style output remains:

```text
Qwen pose/control stage
→ Anima img2img or masked img2img refinement/style transfer
```
