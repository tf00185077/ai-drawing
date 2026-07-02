# ControlNet / Mask Inpaint workflow template research

查詢時間：2026-06-26

## 來源優先級

1. **Comfy 官方 docs / Comfy-Org workflow_templates**：優先，因為節點和模型命名跟新版 ComfyUI 較一致。
2. **ComfyUI_examples / Comfy-Org example_workflows**：可用，但很多是 PNG 內嵌 workflow metadata，不是裸 JSON。
3. **Stable Diffusion Art 教學 JSON**：實務性強，尤其 inpaint / ControlNet inpaint，但第三方範本需檢查節點和模型。
4. **社群 GitHub collections**：只當找靈感，不直接信任；需先做 dependency check。

## 本機 ComfyUI 節點狀態

已確認存在：

- `ControlNetLoader`
- `ControlNetApplyAdvanced`
- `ControlNetApplySD3`
- `DiffControlNetLoader`
- `Canny`
- `VAEEncode`
- `VAEEncodeForInpaint`
- `InpaintModelConditioning`
- `SetLatentNoiseMask`
- `ImageCompositeMasked`
- `FeatherMask`
- `GrowMask`
- `MaskComposite`
- `ControlNetInpaintingAliMamaApply`
- `QwenImageDiffsynthControlnet`
- `ResizeImageMaskNode`

未確認/目前不存在：

- `CLIPSeg`
- `DepthAnythingV2Preprocessor`
- `MiDaS-DepthMapPreprocessor`
- `OpenposePreprocessor`
- `Apply Anima ControlNet-LLLite` / Anima-LLLite custom node

本機 `models/controlnet` 目前沒有實際 ControlNet model，只有 placeholder。也就是：**ControlNet 節點多數可用，但 ControlNet 模型檔要下載；Anima 專用 ControlNet node/weights 尚未安裝。**

## Anima 本機資源狀態

已確認本機有 Anima split-model 基礎資源：

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
  - `AnimaNSS4RE.safetensors`
  - `Niji Reol v1 EP11.safetensors`
  - etc.

現有 ai-drawing Anima templates：

- `anima.json`
- `gen_txt2img_anima_lora_model_only.json`
- `gen_txt2img_anima_lora_model_only_multi_lora.json`

它們都是 **txt2img split-model Anima**：

```text
UNETLoader
CLIPLoader(type=qwen_image)
VAELoader(qwen_image_vae)
EmptySD3LatentImage
CLIPTextEncode positive/negative
optional LoraLoaderModelOnly chain
KSampler
VAEDecode
SaveImage
```

## Anima txt2img / img2img 實測

測試腳本：

`/Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_inpaint_template_research/test_anima_txt_img2img.py`

結果檔：

`/Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_inpaint_template_research/anima_smoke/results.json`

### txt2img smoke test

- workflow: `gen_txt2img_anima_lora_model_only.json` 低步數改版
- prompt_id: `f0c7c184-b350-4b13-9e1f-a430f3154034`
- status: `success`
- elapsed: `10.2s`
- output: `/Users/tf00185088/comfyui/output/anima_smoke_txt2img_00001_.png`
- size: `512×512 RGB`

結論：**Anima txt2img 在本機可跑。**

### img2img smoke test

自建 Anima img2img workflow：在 txt2img template 上將 `EmptySD3LatentImage` 替換成：

```text
LoadImage
→ VAEEncode(pixels=input_image, vae=qwen_image_vae)
→ KSampler(latent_image=VAEEncode output, denoise=0.35)
```

其他 Anima loader / prompt / LoRA / decode 流程不變。

- prompt_id: `0acfae6f-92f4-42e3-821a-a8b711b2a6fd`
- status: `success`
- elapsed: `20.2s`
- output: `/Users/tf00185088/comfyui/output/anima_smoke_img2img_00001_.png`
- size: `832×1216 RGB`（跟輸入圖尺寸一致）

結論：**Anima img2img 在本機可跑，但目前 ai-drawing 還沒有正式 Anima img2img template；需要新增模板。**

## txt2img vs img2img 模板差異（Anima）

### txt2img

核心差異：latent 來源是空 latent。

```text
EmptySD3LatentImage(width, height, batch_size)
→ KSampler.latent_image
```

可控參數：

- width / height
- seed
- steps
- cfg
- sampler / scheduler
- denoise 通常 `1.0`

### img2img

核心差異：latent 來源是輸入圖經 VAE encode。

```text
LoadImage(image)
→ VAEEncode(pixels, qwen_image_vae)
→ KSampler.latent_image
```

可控參數：

- input image
- denoise，通常 `0.2–0.7`
- seed
- steps/cfg/sampler/scheduler

不需要 `EmptySD3LatentImage`，尺寸由輸入圖 latent 決定；如需固定尺寸，應在 `LoadImage` 後加 resize/crop 節點。

### inpaint / mask img2img

標準 masked repaint 邏輯會在 img2img latent 上再加：

```text
mask
→ SetLatentNoiseMask(samples=VAEEncode output, mask=mask)
→ KSampler.latent_image
```

或 dedicated inpaint model/flow 才用：

```text
VAEEncodeForInpaint
```

對 Anima 而言，一般 masked img2img 應先用 `VAEEncode + SetLatentNoiseMask` 做 smoke test；不要直接假設 `VAEEncodeForInpaint` 品質/語義正確。

## Anima + ControlNet 結論

### 不能直接套 SD1.5 / SDXL / SD3 ControlNet 模板

雖然節點 schema 上 `ControlNetApplyAdvanced` 接的是通用：

```text
positive: CONDITIONING
negative: CONDITIONING
control_net: CONTROL_NET
image: IMAGE
optional vae: VAE
```

但 ControlNet 權重必須跟 base model family 相容。Anima 是 DiT / Qwen-image text-encoder/vae 的 split-model，不是 SD1.5/SDXL checkpoint。

因此：

```text
SD1.5 ControlNet 不應接 Anima
SDXL ControlNet 不應接 Anima
SD3.5 ControlNet 不應接 Anima
```

這些模板只適合各自模型族。

### Anima 專用 ControlNet 路線：Anima-LLLite

查到 Anima 專用控制路線：

- HF: `kohya-ss/Anima-LLLite`
- custom node: `kohya-ss/ComfyUI-Anima-LLLite`

它不是標準 `ControlNetLoader + ControlNetApplyAdvanced`，而是專用節點：

```text
Apply Anima ControlNet-LLLite
```

節點輸入概念：

```text
model: MODEL
lllite_name: models/controlnet/*.safetensors
image: IMAGE
strength: FLOAT
start_percent: FLOAT
end_percent: FLOAT
mask: optional MASK, inpaint 4-channel weights required
```

輸出：

```text
patched MODEL
```

也就是它應插在 Anima model chain 裡：

```text
UNETLoader
→ optional LoraLoaderModelOnly chain
→ Apply Anima ControlNet-LLLite(control image / optional mask)
→ KSampler.model
```

目前本機未安裝此 custom node，也沒有 `anima-lllite-*.safetensors` 權重，所以 **Anima ControlNet 目前不能跑**。

### Qwen-Image ControlNet 路線不等於 Anima ControlNet

本機有 Qwen Image 相關節點：

- `QwenImageDiffsynthControlnet`
- `ControlNetInpaintingAliMamaApply`

官方 Qwen-Image docs 提到 DiffSynth / InstantX ControlNet，包括 canny/depth/inpaint。但這些是 **Qwen-Image base model** 控制路線，不等於 Anima base model。

Anima 使用 Qwen text encoder / VAE，但 diffusion model 是 Anima；不能因此假設 Qwen-Image ControlNet 權重能接到 Anima。

## 已下載官方候選範本

保存在：

`/Users/tf00185088/Desktop/ai-drawing/experiments/controlnet_inpaint_template_research/`

### ControlNet 候選

#### 1. `sd3.5_large_canny_controlnet_example.json`

來源：
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/sd3.5_large_canny_controlnet_example.json

用途：Canny ControlNet。

模型需求：

- checkpoint: `sd3.5_large_fp8_scaled.safetensors`
- controlnet: `sd3.5_large_controlnet_canny.safetensors`

判斷：**結構清楚，適合作為 SD3.5 ControlNet API template。** 但不是 Anima ControlNet template。

#### 2. `sd3.5_large_depth.json`

來源：
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/sd3.5_large_depth.json

用途：Depth ControlNet。

判斷：**結構可行，但 depth map 來源/預處理要另外處理。** 不是 Anima ControlNet template。

#### 3. `flux_canny_model_example.json`

來源：
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/flux_canny_model_example.json

用途：Flux Canny model，不是傳統 ControlNetLoader。

判斷：**可行但偏 Flux 專用。** 不是 Anima ControlNet template。

### 遮罩修圖 / inpaint 候選

#### 4. `basic_mask_operations_and_compositing.json`

來源：
https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/basic_mask_operations_and_compositing.json

用途：mask 操作、mask composite、feather、invert、threshold 等。

判斷：**非常適合抽節點邏輯**，但它不是完整生成式 inpaint；比較像遮罩處理工具箱。適合作為 ai-drawing 的 mask utility template 或前處理模板。

#### 5. `flux_fill_outpaint_example.json` / `flux_fill_inpaint_example.json`

用途：Flux Fill outpaint / inpaint 類流程。

判斷：**高品質路線，但資源較重。** 適合未來做高品質遮罩修圖，但不是 Anima template。

#### 6. `image_qwen_image_instantx_inpainting_controlnet.json`

用途：Qwen Image + InstantX inpainting ControlNet。

判斷：**功能很貼近「遮罩 + ControlNet 修圖」，但屬 Qwen-Image ControlNet，不是已證明的 Anima ControlNet。**

## 推薦落地順序（修正版）

### A. 先正式化 Anima img2img template

因為已實測成功，應先新增：

```text
gen_img2img_anima_lora_model_only
```

核心差異：

```text
LoadImage + VAEEncode(qwen_image_vae)
取代 EmptySD3LatentImage
```

### B. 再做 Anima masked img2img / inpaint smoke

先用：

```text
VAEEncode + SetLatentNoiseMask
```

不要先用專用 ControlNet。

### C. 若 CTY 要 Anima ControlNet

需要安裝/驗證：

1. `kohya-ss/ComfyUI-Anima-LLLite` custom node
2. `kohya-ss/Anima-LLLite` 權重，例如：
   - `anima-lllite-inpainting-v2.safetensors`
   - `anima-lllite-any-test-like-v2.safetensors`
   - Preview3-era lineart/depth/pose/scribble 權重（品質可能較差）
3. 建立 Anima-LLLite API template：

```text
UNETLoader
→ LoraLoaderModelOnly optional
→ Apply Anima ControlNet-LLLite
→ KSampler
```

4. 實測 canny/lineart/inpaint 類控制圖。

### D. 若只是要一般 ControlNet

那就不要叫 Anima ControlNet；應另做 SD/SDXL/SD3/Flux/Qwen 專用模板，並用對應模型族的 ControlNet 權重。

## 最終結論

- **Anima txt2img：已實測可跑。**
- **Anima img2img：已自建模板實測可跑。**
- **Anima masked img2img：理論上可用 `SetLatentNoiseMask`，尚待實測。**
- **Anima ControlNet：目前本機不能跑，因為缺 Anima-LLLite custom node + Anima-LLLite 權重。**
- **SD/SDXL/SD3/Flux/Qwen 的 ControlNet 模板不能直接當作 Anima ControlNet 模板。**
