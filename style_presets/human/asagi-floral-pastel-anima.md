---
preset_id: asagi-floral-pastel-anima
chinese_name: 淺蔥花境粉彩 Anima
catalog_path: style_presets/agent/presets/asagi-floral-pastel-anima.json
checkpoint:
lora:
source_url: https://civitai.com/images/130992277
---

# [Anima] Toosaka Asagi Floral Pastel

**Status: Needs re-verification.**

Intended style: airy pastel anime coloring, cinematic/volumetric light, soft shadows and gentle film grain. Floral borders and source-character content belong to the source profile.

[Recipe](../agent/presets/asagi-floral-pastel-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`source-color-style-neutral`](../agent/workflows/asagi-floral-pastel-anima/source-color-style-neutral.api.json): pastel color/material intent without the source subject; negatives block its character, clothing, book, swing and floral scene, which may conflict with new content.
- [`source-image-130992277`](../agent/workflows/asagi-floral-pastel-anima/source-image-130992277.api.json): Kaela Kovalskia reading on a swing, burgundy gown, floral border/petals, low/Dutch-angle framing and Asagi artist token. Reconstruction intent only.
- [`anime-2d-default`](../agent/workflows/asagi-floral-pastel-anima/anime-2d-default.api.json): airy pastel, film grain and matte hand-drawn 2D intent; negatives suppress dark/gloomy backgrounds.

## Processing limits

Source metadata reported External Generator/inpainting badges and RealESRGAN post-processing. **The saved graphs have no upscale, image input, mask or inpaint nodes.** They use single-pass txt2img at 1024×1024 with scheduler `simple`; recipe size/scheduler are unspecified. They do not reproduce the source's 3328×4864 processing chain. Exact prompts and parameters remain in the JSON.

## Historical source and resource evidence

- [Civitai image `130992277`](https://civitai.com/images/130992277), creator `akizukirei608`, API base model `Anima`, dimensions `3328x4864`, badges `External Generator` and `inpainting`.
- Source resource `Anima`: Civitai type `Checkpoint`, version `base-v1.0`, model `2458426`, version ID `2945208`.
- Source upscaler `RealESRGAN_x4Plus Anime 6B`: version `v1`, model `147821`, version ID `164904`. This is not a saved-graph stage.

The prior note reported these paths and SHA-256 values as matching the Civitai API; no current hash check:

| Historical path | SHA-256 |
|---|---|
| `/Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/anima_baseV10.safetensors` | `BD43B7CFFE1ED1153D9C41E7BEB2F18CB1273EAFBAA3AF3EDD6A173DC90A006E` |
| `/Volumes/AI-Drawing-16T/ai-drawing/models/text_encoders/anima_baseV10_txt.safetensors` | `CD2A512003E2F9F3CD3C32A9C3573F820BB28C940F73C57B1DDAA983D9223EBA` |
| `/Volumes/AI-Drawing-16T/ai-drawing/models/vae/qwen_image_vae.safetensors` | `A70580F0213E67967EE9C95F05BB400E8FB08307E017A924BF3441223E023D1F` |
| `/Volumes/AI-Drawing-16T/ai-drawing/models/upscale_models/realesrganX4plusAnime_v1.pt` | `F872D837D3C90ED2E05227BED711AF5671A6FD1C9F7D7E91C911A61F155E99DA` |
