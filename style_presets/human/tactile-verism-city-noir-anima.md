---
preset_id: tactile-verism-city-noir-anima
chinese_name: 厚塗油彩城市夜景 Anima
catalog_path: style_presets/agent/presets/tactile-verism-city-noir-anima.json
checkpoint:
lora: Tactile_Verism-Anima-tcl-vrs-style.safetensors
source_url: https://civitai.com/images/133592240
---

# [Anima] Tactile Verism City Noir

**Status: Needs re-verification.**

Intended style: tactile oil brushwork and impasto, with teal/gold city-noir atmosphere in source-oriented profiles. Character profiles aim to localize texture/color to hair, clothes, edges and background while keeping a warm readable anime face. These are prompt targets, not observed current effects.

[Recipe](../agent/presets/tactile-verism-city-noir-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles and parameter differences

All graphs use 35 steps, Euler/simple, 832×1280. Source/neutral/2D profiles use LoRA 1.0 and CFG 2.5; both character-oil profiles use LoRA 0.5 and CFG 3.2. Full prompts and wiring remain in the JSON.

- [`source-color-style-neutral`](../agent/workflows/tactile-verism-city-noir-anima/source-color-style-neutral.api.json): heavy impasto, dark teal/gold noir, wet reflections and haze, without the exact bridge/skyline/moon composition lock.
- [`source-image-133592240`](../agent/workflows/tactile-verism-city-noir-anima/source-image-133592240.api.json): industrial city at night, arched bridge, river, yellow moon, steam and no visible people.
- [`anime-oil-color-safe`](../agent/workflows/tactile-verism-city-noir-anima/anime-oil-color-safe.api.json): warm matte anime face with brushwork on hair/clothes/background and restrained teal/amber background/rim light. “Safe” names mitigation intent, not a verified outcome.
- [`anime-oil-character-preserving`](../agent/workflows/tactile-verism-city-noir-anima/anime-oil-character-preserving.api.json): recognizable named-character bust, chest-up crop and hands out of frame; stronger localized brushwork. Negatives also block smile/grin, v-sign and torso bindings, which may conflict with new content.
- [`anime-2d-default`](../agent/workflows/tactile-verism-city-noir-anima/anime-2d-default.api.json): matte hand-drawn anime face, painterly hair/clothes/background and warm rim light; suppresses dark noir/black backgrounds.

Historical reports of metallic, ghostly or teal/gold face contamination motivated warm-face and localized-brushwork constraints. These are not a proven current fix.

## Historical source and resource evidence

- [Civitai image `133592240`](https://civitai.com/images/133592240): ComfyUI txt2img, base Anima version `2945208`, 832×1280, CFG 2.5, 35 steps, Euler (`euler`), seed `344596877060857`; page did not show a negative prompt.
- Historical external alias `tactile_paint_3.5k_cl_1.0.safetensors : str_1` mapped to `Tactile_Verism-Anima-tcl-vrs-style.safetensors`, model `2616851`, version `2938169`.
- SHA-256: `63CB6E25EB5CDBC1879B90B00DA05B7EB3CE66C08100FD3478D9B2DB8C29E084`.
- Historical path: `/Volumes/AI-Drawing-16T/ai-drawing/models/loras/Tactile_Verism-Anima-tcl-vrs-style.safetensors`.
- Recipe `required_resources` retains source prompt/process/cache hash; the temporary cache path may no longer exist.

## Historical CTY feedback, not current acceptance

- `cty-approved-color-2026-06-20`: image `391`, job `50a309e5-e4f4-44b5-80d5-071dd412f853`, profile `anime-oil-color-safe`, LoRA 0.5, seed `344596877060861`. The recorded report says CTY confirmed the color direction and recommended starting future character portraits from this profile with character-detail tokens.
- `cty-approved-character-preserving-oil-2026-06-20`: image `399`, job `2542d05a-af63-420f-82f2-68cc638dcf69`, profile `anime-oil-character-preserving`, LoRA 0.5, seed `3833842405`. The recorded report says CTY approved recognizable character identity, warm natural anime skin and crisp face details, with oil texture/color on hair, clothes, background and rim/edge light rather than a global color wash.

The saved oil-profile seed `2782265067` matches neither sample. Those reports concern specific historical images, not acceptance of current replay, other profiles, seeds or modified graphs.
