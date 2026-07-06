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

這個 preset 來源於 131966887 的 Niji/Anima 多 LoRA 配方；目前只保留冷藍 Niji 上色、乾淨色彩分離、cool rim light 與受控 anime 對比，不再預設夜晚、月亮、暗背景、半寫實或 glossy/立體高光。來源圖內容線索也已從一般 prompt 中移除。

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

Reusable style profile. Keeps the usable color identity only: cool blue Niji anime palette, clean color separation, cool rim light, controlled anime contrast, refined 2D anime finish, and crisp anime hair detail. It intentionally removes night/moon/dark-background defaults and semi-real/glossy/specular positive terms; do not rely on negative prompts alone to suppress those effects.

### source-image-131966887

Former source reconstruction profile. It no longer keeps source content tokens such as black hair, armor, moon, night, or dark fantasy portrait; it now preserves only the reusable Niji color reference and cool-blue anime color separation.
