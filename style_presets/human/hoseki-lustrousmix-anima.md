---
preset_id: hoseki-lustrousmix-anima
chinese_name: 寶石抽象插畫 Anima
catalog_path: style_presets/agent/presets/hoseki-lustrousmix-anima.json
checkpoint:
lora:
source_url: https://civitai.com/images/132048670
---

# Hoseki LustrousMix Anima / Abstract Gem Illustration

## 中文名稱

寶石抽象插畫 Anima

從 Civitai 單張圖片頁 `132048670` 建立的 Anima checkpoint / diffusion-model style preset。

## Source

- Image URL: https://civitai.com/images/132048670
- Civitai image id: `132048670`
- Creator shown on image API: `Hoseki`
- Base model shown by image API: `Anima`
- Image dimensions on Civitai: `832x1216`

## Resources Used on Civitai

頁面 `Generation data → Resources used` 顯示：

- `Hoseki - LustrousMix [Anima v1.0]`
  - Resource type on Civitai: `Checkpoint`
  - Version: `Anima v1.0`
  - Model id: `941345`
  - Model version id: `2982979`
  - File id: `2862545`
  - File: `hosekiLustrousmixAnima_animaV10.safetensors`

## Local Resource Pairing

雖然 Civitai 顯示 resource type 為 `Checkpoint`，但 base model 是 `Anima`，在本機 ai-drawing / ComfyUI 中用 split-model workflow 處理，不放傳統 checkpoints 目錄。

- Template: `anima`
- Diffusion model / UNET: `hosekiLustrousmixAnima_animaV10.safetensors`
- Text encoder: `qwen_3_06b_base.safetensors`
- VAE: `qwen_image_vae.safetensors`
- LoRA: none

Installed file:

```text
/Users/tf00185088/comfyui/models/diffusion_models/hosekiLustrousmixAnima_animaV10.safetensors
```

Verification:

```text
size_bytes=4182230672
sha256=19147601CFC165D8851222505B5CD2B99C11874F6B2BEE0CF00612E77D7CBCAB
```

## Extracted Source Prompt

```text
masterpiece, best quality, 1other, diamond \(houseki no kuni\), pale skin, elbow gloves, from side, pensive, holding gem, holding diamond, text "To be or not to be?", abstract background, hand on own chin, looking at object, gem uniform \(houseki no kuni\), abstract, multicolored background
```

## Extracted Negative Prompt

```text
worst quality, low quality, bad anatomy, jpeg artifacts, signature, sepia, fewer digits, extra digits, bad hands, bad anatomy, watermark, score_1, score_2, score_3, censored
```

## Extracted Generation Params

```text
cfgScale: 4
steps: 24
sampler: Euler a
seed: 2374630006
```

Mapped local sampler name:

```text
sampler_name: euler_ancestral
```

## Reusable Style Signals

通用 profile 只保留這些可重用風格元素：

- `masterpiece`, `best quality`
- Anima-based polished anime illustration
- abstract / multicolored background
- refined character linework
- clean polished digital rendering
- contemplative / calm atmosphere
- sharp silhouette
- soft dramatic lighting

## Source-Specific Elements

以下屬於來源圖題材或服裝/道具/角色，不應放進通用 profile：

- `diamond \(houseki no kuni\)`
- `gem uniform \(houseki no kuni\)`
- `elbow gloves`
- `holding gem`
- `holding diamond`
- `hand on own chin`
- `looking at object`
- text: `"To be or not to be?"`
- gem / diamond / crystal motif

## Profiles

### `neutral-anime`

通用風格 profile。用於一般角色圖，例如 Love Live 穗乃果、逛街、休閒服、回眸。這個 profile 已移除：

- gem / diamond / crystal / holding gem
- Houseki no Kuni 題材
- gem uniform / elbow gloves 等來源服裝
- looking at object / hand on chin 等來源姿勢

並在 profile negative 中排除：

```text
gem, diamond, crystal, holding gem, holding diamond, gemstone, jewelry focus, houseki no kuni
```

Recommended use:

```text
compose_style_preset(
  preset_id="hoseki-lustrousmix-anima",
  profile="neutral-anime",
  content_prompt="<角色、服裝、姿勢、場景>"
)
```

### `source-image-132048670`

來源圖復刻 profile。只有在 CTY 明確要接近原 Civitai 圖、寶石/鑽石/Houseki 題材時使用。

這個 profile 會保留：

- jewel-like color accents
- gem motif
- holding gem
- from side / looking at object
- elegant uniform styling

不適合一般角色圖；如果用它畫休閒服角色，模型會傾向產生寶石、制服感或同源服裝。

## Preset-Memory Rule Learned

從 Civitai image 建 style preset 時必須拆分：

1. `source-image-*` profile：保留來源圖的角色、服裝、道具、姿勢、構圖，用於復刻來源圖。
2. `neutral-*` profile：只保留可重用畫風；移除角色/作品/服裝/道具/姿勢，並把會污染一般生成的元素加入 negative。

一般 Discord 選單若使用者只選 style 而沒有指定 profile，應優先使用 neutral profile；source-image profile 只能在使用者明確要「照來源圖感」時使用。
