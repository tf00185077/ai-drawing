---
preset_id: niji-daylight-2d-anime-anima
catalog_path: style_presets/agent/presets/niji-daylight-2d-anime-anima.json
checkpoint:
lora: anima-highres-aesthetic-boost.safetensors
source_url:
---

# [Anima] Niji Daylight 2D Anime

**Status: Needs re-verification.**

Intended style: bright daylight Niji-like colors, cool rim light and matte 2D cel shading. Negative tokens target realistic, glossy, 3D and night rendering; they do not demonstrate prevention.

[Recipe](../agent/presets/niji-daylight-2d-anime-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles and campus limits

- [`daylight-campus-2d`](../agent/workflows/niji-daylight-2d-anime-anima/daylight-campus-2d.api.json): cheerful daylight school campus with explicit LoveLive-style setting vocabulary.
- [`neutral-daylight-2d`](../agent/workflows/niji-daylight-2d-anime-anima/neutral-daylight-2d.api.json): recipe prefix omits campus, but retains blue sky/daylight and a bright clean background.
- [`anime-2d-default`](../agent/workflows/niji-daylight-2d-anime-anima/anime-2d-default.api.json): matte hand-drawn 2D intent with an explicit bright school campus.

**Saved graphs retain an expanded historical base with school-campus-friendly vocabulary. Even `neutral-daylight-2d` replay is not campus-neutral.** The current recipe base is shorter; composition and replay text differ. The inherited moonlit filename prefix does not describe prompt intent.

## Resource distinctions and provenance

Uses the same ordered three-LoRA stack as [High Contrast Color](high-contrast-color-anima.md): `anima-highres-aesthetic-boost.safetensors` at 0.7, `Niji Reol v1 EP11.safetensors` at 0.8, then `AnimaNSS4RE.safetensors` at 0.65. Exact prompts and parameters remain in the JSON.

Related lineage: [Civitai image `131966887`](https://civitai.com/images/131966887), recorded for High Contrast Color, not an independently proven source for every Niji profile. Base Anima version `2945208`; LoRA versions: Highres/Aesthetic Boost `2855073`, Niji Reol `2960729`, Niji Sweet Spot `2964538`. Sweet Spot's 0.65 is a local choice because the source weight was hidden. Resource SHA-256 and complete license evidence are missing.
