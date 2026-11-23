---
preset_id: posing-dynamics-watercolor-silhouette-anima
chinese_name: 水彩剪影動態姿勢 Anima
catalog_path: style_presets/agent/presets/posing-dynamics-watercolor-silhouette-anima.json
checkpoint: 
lora: posing-dynamics-anima.safetensors
source_url:
---

# [Anima] Posing Dynamics Watercolor Silhouette

**Status: Needs re-verification.**

Intended style: airy watercolor anime silhouettes, luminous backlight, cyan/pink wash, warm foreground glow, wet-on-wet bleeding and broad white negative space. Even the neutral profile retains petals/flower accents.

[Recipe](../agent/presets/posing-dynamics-watercolor-silhouette-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`source-color-style-neutral`](../agent/workflows/posing-dynamics-watercolor-silhouette-anima/source-color-style-neutral.api.json): watercolor palette, splatter, petals and flower-field color accents; LoRA 0.65.
- [`source-image-130172482`](../agent/workflows/posing-dynamics-watercolor-silhouette-anima/source-image-130172482.api.json): solitary side-view figure in a flower field, head/hair dissolving into paint splashes, white central glow and floral foreground; LoRA 0.75. Suppresses sharp facial detail, so unsuitable for detailed likeness intent.
- [`anime-2d-default`](../agent/workflows/posing-dynamics-watercolor-silhouette-anima/anime-2d-default.api.json): matte hand-drawn character with a watercolor background, speckles/petals and white space; LoRA 0.7.

## Resource distinctions and provenance

Uses **`anima_preview3Base.safetensors`**, not Anima base v1.0, with `qwen_3_06b_base.safetensors`, `qwen_image_vae.safetensors` and the single model-only `posing-dynamics-anima.safetensors` LoRA. Trigger: `PosingDynamicsDaal`. Base strength is 0.7; profile differences are above. Full prompts and remaining parameters stay in the JSON.

Source-profile locator: [Civitai image `130172482`](https://civitai.com/images/130172482). Existing records do not establish model/LoRA version IDs, file hashes, creator or license.
