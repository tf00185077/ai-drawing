# Anima ControlNet / Pose research — txt2img vs img2img

查詢時間：2026-06-26

## 目標

針對 CTY 指定的「先以 Anima 為主」查找 pose/control 路線，分成：

1. `txt2img + pose`：文字生圖，但用 pose/reference skeleton 控制姿勢。
2. `img2img + pose`：已有 input image/style/reference，再用 pose/control 引導重繪。

核心原則：**不要把 SD1.5/SDXL/SD3 的 ControlNet 直接套到 Anima。** Anima 是 DiT / Qwen text encoder / Qwen VAE split-model 架構，pose/control 必須用 Anima-compatible adapter。

---

## 本機現況

### 已有 Anima 基礎資源

`list_available_resources` 顯示本機有：

- diffusion models:
  - `anima_baseV10.safetensors`
  - `anima_preview3Base.safetensors`
  - `hosekiLustrousmixAnima_animaV10.safetensors`
- text encoders:
  - `anima_baseV10_txt.safetensors`
  - `qwen_3_06b_base.safetensors`
- VAE:
  - `qwen_image_vae.safetensors`
- Anima LoRAs:
  - `anima-base-1-masterpiece-v51.safetensors`
  - `anima-highres-aesthetic-boost.safetensors`
  - `Niji Reol v1 EP11.safetensors`
  - `AnimaNSS4RE.safetensors`
  - `posing-dynamics-anima.safetensors`
  - etc.

### 已有 Anima workflows/templates

- `anima`
- `gen_txt2img_anima_lora_model_only`
- `gen_txt2img_anima_lora_model_only_multi_lora`
- `gen_img2img_anima_lora_model_only_image_ref`
- `gen_inpaint_anima_lora_model_only_multi_lora_image_ref_mask`

### 本機缺口

目前缺：

```text
ComfyUI/custom_nodes/ComfyUI-Anima-LLLite
ComfyUI/models/controlnet/anima-lllite-pose-1.safetensors
```

本機 `~/comfyui/models/controlnet/` 只有 placeholder：

```text
put_controlnets_and_t2i_here
```

ComfyUI node catalog 也沒有：

```text
Apply Anima ControlNet-LLLite
```

所以 **Anima pose control 目前不能立即跑**；需要先安裝 custom node + 權重。

---

## 查到的 Anima 專用 ControlNet 路線

### 正確主線：Anima-LLLite

來源：

- HF: `kohya-ss/Anima-LLLite`
- ComfyUI node: `kohya-ss/ComfyUI-Anima-LLLite`
- 訓練/推論文件：`kohya-ss/sd-scripts/docs/anima_train_control_net_lllite.md`

定位：

```text
ControlNet-LLLite is a lightweight, LoRA-like conditional control module ported to Anima's DiT / MiniTrainDIT architecture.
```

它不是標準：

```text
ControlNetLoader -> ControlNetApplyAdvanced
```

而是 Anima 專用：

```text
Apply Anima ControlNet-LLLite
```

### ComfyUI-Anima-LLLite node

Node name:

```text
Apply Anima ControlNet-LLLite
```

Inputs:

```text
model: MODEL
lllite_name: filename from ComfyUI/models/controlnet/
image: IMAGE
strength: FLOAT
start_percent: FLOAT
end_percent: FLOAT
preserve_wrapper: BOOLEAN
mask: optional MASK
```

Output:

```text
MODEL
```

也就是它是 **patch MODEL**，不是修改 conditioning：

```text
UNETLoader / LoraLoaderModelOnly chain
→ Apply Anima ControlNet-LLLite(control image)
→ KSampler.model
```

### Multiple controls 可串接

ComfyUI-Anima-LLLite README 說多個 LLLite node 可以串接，例如：

```text
pose LLLite + depth LLLite
```

每個 node 有自己的：

```text
strength
start_percent
end_percent
```

並透過 `preserve_wrapper=True` 避免 wrapper 互相覆蓋。

---

## 權重清單

HF `kohya-ss/Anima-LLLite` 檔案清單：

```text
anima-lllite-any-test-like-1-step1000.safetensors
anima-lllite-any-test-like-1-step2000.safetensors
anima-lllite-any-test-like-v2-beta-epoch-03.safetensors
anima-lllite-any-test-like-v2.safetensors
anima-lllite-depth-1.safetensors
anima-lllite-inpainting-v1.safetensors
anima-lllite-inpainting-v2.safetensors
anima-lllite-lineart-1.safetensors
anima-lllite-pose-1.safetensors
anima-lllite-scribble-1.safetensors
```

重點：

- `v2` 權重是 Anima-Base v1.0 新版：
  - `anima-lllite-inpainting-v2.safetensors`
  - `anima-lllite-any-test-like-v2.safetensors`
- `pose` 權重只有 Preview3 legacy：
  - `anima-lllite-pose-1.safetensors`

官方說明：

```text
lineart / depth / pose / scribble only published in Preview3 form.
They can work on Anima-Base v1.0 with somewhat reduced quality.
Pose model in particular has noticeably weaker control.
```

因此 pose control 可測，但預期不要太高：它是 reference/sample weight，不是強 production-grade ControlNet。

---

## Pose conditioning 格式

`anima-lllite-pose-1.safetensors` 的 conditioning source：

```text
DWPose standard: colored skeleton + face/hand keypoints
```

也就是需要一張類似 OpenPose/DWPose 的彩色骨架圖。

本機已有一些 pose/keypoint 相關節點：

```text
SDPoseKeypointExtractor
SDPoseDrawKeypoints
FaceMaskFromPoseKeypoints
```

Schema:

```text
SDPoseKeypointExtractor:
  inputs: model, vae, image, batch_size, optional bboxes
  output: POSE_KEYPOINT

SDPoseDrawKeypoints:
  input: POSE_KEYPOINT + draw flags
  output: IMAGE
```

但這些是否能產生完全符合 `anima-lllite-pose-1` 訓練時的 DWPose colored skeleton，仍需 smoke test。若不符合，應安裝/使用標準 DWPose/OpenPose preprocessor 產 control image。

---

# A. Anima txt2img + pose control

## 用途

從文字 prompt 生圖，但用 pose image 控制人物姿勢。

不是 pure txt2img；實際 IO 是：

```text
text + pose_ref_image -> image
```

## Graph shape

基於現有 Anima txt2img graph：

```text
UNETLoader(anima_baseV10 or anima_preview3Base)
CLIPLoader(qwen/anima text encoder)
VAELoader(qwen_image_vae)
EmptySD3LatentImage
CLIPTextEncode positive/negative
optional LoraLoaderModelOnly chain
Apply Anima ControlNet-LLLite(image=pose_ref, lllite=anima-lllite-pose-1)
KSampler(model=patched_model, latent=EmptySD3LatentImage)
VAEDecode
SaveImage
```

## Key parameters

```text
lllite_name: anima-lllite-pose-1.safetensors
strength: start 0.8–1.2
start_percent: 0.0
end_percent: 0.8–1.0
preserve_wrapper: True
```

Because pose weight is known weak, test strengths:

```text
0.8, 1.0, 1.3, 1.6
```

但高 strength 可能造成 anatomy/texture artifacts。

## Recommended first smoke test

1. Use `anima_preview3Base.safetensors` first because pose weight is Preview3-era.
2. Generate/choose one DWPose/OpenPose skeleton image at `832×1216`.
3. Use simple prompt:

```text
1girl, solo, full body, red plugsuit, orange hair, standing pose, clean anime illustration
```

4. No img2img init latent; use `EmptySD3LatentImage`.
5. Compare no-control vs pose-control output.

## Expected result

- Should influence rough pose if node/weight/control image format are correct.
- Pose adherence may be weak.
- If output ignores pose entirely, likely causes:
  - wrong pose map format
  - pose LLLite too weak
  - Preview3 weight mismatch on Anima Base v1.0
  - node not correctly installed/loaded

---

# B. Anima img2img + pose control

## 用途

有 input image / style image / base composition，再用 pose image 引導重繪。

實際 IO：

```text
text + image_ref + pose_ref_image -> image
```

## Graph shape

基於已記錄的 Anima img2img template：

```text
LoadImage(input image)
VAEEncode(qwen_image_vae)
UNETLoader
CLIPLoader
VAELoader
CLIPTextEncode positive/negative
optional LoraLoaderModelOnly chain
Apply Anima ControlNet-LLLite(image=pose_ref, lllite=anima-lllite-pose-1)
KSampler(model=patched_model, latent=VAEEncode output, denoise=...)
VAEDecode
SaveImage
```

## Key parameters

```text
denoise: 0.55–0.75 for style/pose nudging
         0.80–0.95 for stronger pose change, but identity may drift
lllite strength: 1.0–1.6
```

Important tradeoff:

- Low denoise: input image dominates; pose control may not change much.
- High denoise: pose can influence more, but image identity/character stability drops.

## Recommended first smoke test

Use the already-verified image #4 or Niji img2img output as input.

Test matrix:

```text
B0: img2img no LLLite, denoise 0.65
B1: img2img + pose LLLite, denoise 0.65, strength 1.0
B2: img2img + pose LLLite, denoise 0.80, strength 1.0
B3: img2img + pose LLLite, denoise 0.80, strength 1.4
```

This separates:

- img2img anchor strength
- LLLite pose influence
- high strength artifact risk

## Expected result

Because pose LLLite is weak and img2img latent anchors pose strongly, **img2img + pose may be less convincing than txt2img + pose** unless denoise is high.

If goal is precise pose transfer, this Anima-LLLite pose route may not be enough; may need a stronger future Anima pose weight or another model family.

---

# C. Why not use existing SDXL `controlnet_pose` template?

Existing catalog has:

```text
controlnet_pose
img2img_lora_pose
txt2img_lora_pose
```

But they are tagged:

```text
model_family: sdxl
conditioning: [controlnet_pose]
```

They rely on SDXL/standard ControlNet concepts:

```text
ControlNetLoader
ControlNetApplyAdvanced
```

Anima should not use those directly, because Anima's model family is not SDXL. Anima needs:

```text
Apply Anima ControlNet-LLLite
```

and Anima-compatible `.safetensors` weights.

---

# D. Install / enable requirements

Needed before smoke test:

## 1. Install custom node

```bash
cd /Users/tf00185088/comfyui/custom_nodes
git clone https://github.com/kohya-ss/ComfyUI-Anima-LLLite.git
```

Restart ComfyUI and verify node appears:

```text
Apply Anima ControlNet-LLLite
```

## 2. Download pose weight

```text
https://huggingface.co/kohya-ss/Anima-LLLite/resolve/main/anima-lllite-pose-1.safetensors
```

Destination:

```text
/Volumes/AI-Drawing-16T/ai-drawing/models/controlnet/anima-lllite-pose-1.safetensors
```

Optional related weights:

```text
anima-lllite-depth-1.safetensors
anima-lllite-lineart-1.safetensors
anima-lllite-scribble-1.safetensors
anima-lllite-any-test-like-v2.safetensors
anima-lllite-inpainting-v2.safetensors
```

For immediate pose work, only `pose-1` is required.

## 3. Pose preprocessor/control image

Need one of:

- external DWPose/OpenPose skeleton PNG supplied by user;
- install a DWPose/OpenPose preprocessor node;
- use existing `SDPoseKeypointExtractor + SDPoseDrawKeypoints` if it produces compatible colored keypoint image.

Best first smoke test: use a known DWPose/OpenPose skeleton PNG rather than relying on uncertain extractor output.

---

# E. Proposed smoke-test order

## Phase 1 — install/preflight only

1. Install `ComfyUI-Anima-LLLite`.
2. Download `anima-lllite-pose-1.safetensors`.
3. Restart ComfyUI.
4. Verify node schema for `Apply Anima ControlNet-LLLite`.
5. Verify weight appears in node combo / `models/controlnet`.

No generation yet.

## Phase 2 — txt2img + pose

Start with txt2img because no input latent fights pose.

```text
T0: Anima txt2img no pose control
T1: Anima txt2img + pose LLLite strength 1.0
T2: Anima txt2img + pose LLLite strength 1.4
```

Use same seed/prompt/latent size. Deliver contact sheet and judge pose adherence.

## Phase 3 — img2img + pose

Only after txt2img proves the pose weight does something.

```text
I0: img2img no pose, denoise 0.65
I1: img2img + pose, denoise 0.65, strength 1.0
I2: img2img + pose, denoise 0.80, strength 1.0
I3: img2img + pose, denoise 0.80, strength 1.4
```

If pose effect is weak, try `anima_preview3Base` before blaming graph wiring, since the pose weight is Preview3-era.

---

# F. Template catalog plan after success

If txt2img pose succeeds:

```text
modality: txt2img
model_family: anima
conditioning: [lora_model_only, anima_lllite_pose]
io: [text, image_ref]
```

`image_ref` here means pose control image, not img2img init.

Possible template id:

```text
gen_txt2img_anima_lllite_pose_image_ref
```

If img2img pose succeeds:

```text
modality: img2img
model_family: anima
conditioning: [lora_model_only, anima_lllite_pose]
io: [text, image_ref, pose_ref]
```

Current controlled vocabulary may not have `pose_ref` or `anima_lllite_pose`; if backend rejects tags, use nearest accepted tags temporarily and extend vocabulary later. Do not collapse Anima-LLLite pose into generic `controlnet_pose` without documenting the distinction.

---

## Bottom line

- **Anima pose control exists, but via Anima-LLLite, not standard ControlNet.**
- **txt2img + pose** is the cleaner first test because pose is not fighting an input latent.
- **img2img + pose** is possible but likely needs higher denoise and may be weaker/less stable.
- Current machine lacks the required custom node and `anima-lllite-pose-1.safetensors`.
- Pose weight is Preview3 legacy and officially described as weaker than other controls; expectation should be “smoke-test and characterize,” not assume production-grade pose fidelity.
