---
preset_id: hoseki-lustrousmix-anima
chinese_name: 寶石抽象插畫 Anima
catalog_path: style_presets/agent/presets/hoseki-lustrousmix-anima.json
checkpoint:
lora:
source_url: https://civitai.com/images/132048670
---

# [Anima] Hoseki LustrousMix / Abstract Gem Illustration

**Status: Needs re-verification.**

Intended style: polished anime linework, abstract multicolored backgrounds and a calm illustrative mood. Gem props and uniforms are source-profile content.

[Recipe](../agent/presets/hoseki-lustrousmix-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`neutral-anime`](../agent/workflows/hoseki-lustrousmix-anima/neutral-anime.api.json): general characters without gem/Houseki props; still adds an abstract multicolored background and calm mood.
- [`source-image-132048670`](../agent/workflows/hoseki-lustrousmix-anima/source-image-132048670.api.json): approximate side-view, gem-holding figure with pale skin and uniform styling; not an exact source prompt/image match.
- [`anime-2d-default`](../agent/workflows/hoseki-lustrousmix-anima/anime-2d-default.api.json): hand-drawn 2D intent with abstract multicolor, translucent highlights and sharp silhouette; negatives suppress dark backgrounds and gemstone/jewelry focus.

## Resource and processing limits

Civitai labels LustrousMix a checkpoint; the local graphs use split `UNETLoader`, text encoder and VAE, not `CheckpointLoaderSimple`. Recipe size/scheduler are unspecified. Saved graphs use 1024×1024 and `simple`, unlike the reported source 832×1216. Full prompts and parameters remain in the JSON.

## Historical source and resource evidence

- [Civitai image `132048670`](https://civitai.com/images/132048670), creator `Hoseki`, API base model `Anima`, dimensions `832x1216`.
- Page resource: `Hoseki - LustrousMix [Anima v1.0]`, Civitai type `Checkpoint`, version `Anima v1.0`, model `941345`, version ID `2982979`, file `2862545`, filename `hosekiLustrousmixAnima_animaV10.safetensors`.
- Historical path: `/Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/hosekiLustrousmixAnima_animaV10.safetensors`.
- Recorded size: `4182230672` bytes; SHA-256: `19147601CFC165D8851222505B5CD2B99C11874F6B2BEE0CF00612E77D7CBCAB`.
- Text-encoder/VAE source hashes are missing.
