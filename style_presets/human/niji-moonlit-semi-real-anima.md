---
preset_id: niji-moonlit-semi-real-anima
chinese_name: 月光半寫實 Niji Anima
catalog_path: style_presets/agent/presets/niji-moonlit-semi-real-anima.json
checkpoint:
lora: anima-highres-aesthetic-boost.safetensors
source_url: https://civitai.com/images/131966887
---

# Niji Moonlit Semi-real Anima

## 中文名稱

月光半寫實 Niji Anima

來源圖：<https://civitai.com/images/131966887>

這個 preset 捕捉 131966887 的暗色月光、半寫實 Niji anime、強對比高光與 polished high-resolution 質感。

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
| NijiReol / Semi-realistic Niji Style | `Niji Reol v1 EP11.safetensors` | `2960729` | `0.8` |
| Niji Sweet Spot | `AnimaNSS4RE.safetensors` | `2964538` | source page hidden; use conservative `0.65` unless tuned |

## Workflow requirement

The normal `anima` workflow is insufficient because it has no LoRA loader nodes. This preset requires an Anima txt2img workflow with chained `LoraLoaderModelOnly` nodes, one per LoRA.

If no existing workflow template matches this condition, self-author it with MCP `generate_image_custom_workflow`. After a correct generation succeeds, persist the graph with MCP `save_workflow_template`.

Suggested capability shape:

```text
modality = txt2img
model_family = anima
conditioning = ["lora_model_only", "multi_lora"]
io = ["text"]
```

## Profiles

### source-color-style-neutral

Reusable style profile. Keeps dark cinematic color grading, semi-realistic Niji rendering, cool rim light, glossy highlights, sharp details, high contrast, and polished finish. Excludes source subject objects such as black armor, moon, exact night sky, and original character composition.

### source-image-131966887

Source reconstruction profile. Keeps source content tokens such as black hair, armor, moon, night, dark fantasy portrait, and upper-body composition.
