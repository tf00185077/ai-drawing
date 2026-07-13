---
preset_id: high-contrast-color-anima
chinese_name: 高對比用色
catalog_path: style_presets/agent/presets/high-contrast-color-anima.json
checkpoint:
lora: anima-highres-aesthetic-boost.safetensors
source_url: https://civitai.com/images/131966887
---

# 高對比用色

## 中文名稱

高對比用色

來源圖：<https://civitai.com/images/131966887>

這個 preset 來源於 131966887 的 Niji/Anima 多 LoRA 配方；只保留可重用的高對比用色、乾淨色彩分離、cool rim light、受控 anime 對比與 2D anime 線條清晰度。

明確不代表特定時間、來源場景、背景情境、半寫實或 glossy/立體高光。來源圖內容線索也不應進入一般生成 prompt。

## Required resources

### Split Anima base

- Diffusion model: `anima_baseV10.safetensors`
- Text encoder: `anima_baseV10_txt.safetensors`
- VAE: `qwen_image_vae.safetensors`
- Civitai model version: `2945208` (`Anima — base-v1.0`)

### LoRA stack from source image

The source image uses multiple LoRAs. A generation workflow must actually wire all of them into the graph; recording only the first `lora` field is not enough.

| Resource | File | Version ID | Source weight |
|---|---|---:|---:|
| Anima Highres/Aesthetic Boost | `anima-highres-aesthetic-boost.safetensors` | `2855073` | `0.7` |
| NijiReol / Niji Style | `Niji Reol v1 EP11.safetensors` | `2960729` | `0.8` |
| Niji Sweet Spot | `AnimaNSS4RE.safetensors` | `2964538` | source page hidden; use conservative `0.65` unless tuned |

## Workflow requirement

The normal `anima` workflow is insufficient because it has no LoRA loader nodes. This preset requires an Anima txt2img workflow with chained `LoraLoaderModelOnly` nodes, one per LoRA.

Suggested capability shape:

```text
modality = txt2img
model_family = anima
conditioning = ["lora_model_only", "multi_lora"]
io = ["text"]
```

## Profiles

### source-color-style-neutral

Reusable style profile. Keeps the usable color identity only: high-contrast Niji anime palette, clean color separation, cool rim light, controlled anime contrast, refined 2D anime finish, and crisp anime hair detail. It intentionally removes source-scene defaults and semi-real/glossy/specular positive terms; do not rely on negative prompts alone to suppress those effects.

### source-image-131966887

Former source reconstruction profile. It preserves only the reusable Niji color reference and high-contrast anime color separation.

### anime-2d-default

Default CTY anime profile: bright/non-gloomy scene, high-contrast Niji color separation, clean rim light, pure hand-drawn 2D Japanese anime, flat matte cel colors, clean ink line, and no 3D lighting.
