---
preset_id: soft-mist-skin-anima
catalog_path: style_presets/agent/presets/soft-mist-skin-anima.json
checkpoint:
lora:
source_url:
---

# [Anima] Soft Mist Skin

**Status: Needs re-verification.**

Intended style: matte anime skin, diffused blush, translucent warmth, gentle bloom and high-key backlight with fine lineart. Negative tokens target oily, plastic or waxy skin; they do not prove prevention.

[Recipe](../agent/presets/soft-mist-skin-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`default`](../agent/workflows/soft-mist-skin-anima/default.api.json): base style; supply the subject and scene when composing.
- [`portrait`](../agent/workflows/soft-mist-skin-anima/portrait.api.json): facial-plane/detail vocabulary and face-asymmetry negatives. No face-detailer stage.

## Resource and parameter differences

Uses the `miaomiaoRealskin_anima11.safetensors` diffusion model and matching `miaomiaoRealskin_anima11_txt.safetensors` encoder, with `qwen_image_vae.safetensors` and no LoRA.

Recipe composition requests **batch 4**; both saved graphs use **batch 1** at 920×1560. These paths do not share validation. See the linked JSON for prompts and remaining parameters.

## Historical execution evidence

The prior read-only `auto_draw.db` inspection found the same graph structure and non-prompt inputs in image `2981`, job `b3310b2d-3d2f-47e7-8b33-ed549ecec86c`, as in both saved profiles, including batch 1. Prompt text differs. This supports single-image execution settings, not batch-4 composition or current aesthetic acceptance. The note records no source/version/hash evidence.
