---
preset_id: digital-painting-a
chinese_name: 暖粉日系電繪 Anima
catalog_path: style_presets/agent/presets/digital-painting-a.json
checkpoint:
lora:
source_url: https://civitai.com/models/929497/aesthetic-quality-modifiers-masterpiece
---

# [Anima] Masterpiece Digital Painting

**Status: Needs re-verification.**

Intended style: warm pastel Japanese digital illustration, painterly linework and decorative commercial key-visual framing. Artist-blend tokens express prompt intent, not observed fidelity.

[Recipe](../agent/presets/digital-painting-a.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`warm-pastel`](../agent/workflows/digital-painting-a/warm-pastel.api.json): decorative character/key-visual work with flowing fabric, traditional background elements and medium-shot framing.
- [`anime-2d-default`](../agent/workflows/digital-painting-a/anime-2d-default.api.json): hand-drawn 2D intent with matte cel colors, painterly background and warm pastel light.

## Execution identity and limits

The saved graphs have **no LoRA loader**. The recipe now has no LoRA; the former Masterpiece LoRA declaration at strength 1.0 described an intended pairing, not these executions. A LoRA-wired variant needs separate re-verification. Exact resources, prompts and sampler settings remain in the linked JSON.

## Historical evidence

The prior note records the following downloaded resource; it is not part of the saved graphs:

- Civitai model `Aesthetic Quality Modifiers - Masterpiece`, model `929497`.
- Selected version `v5.1 [anima-base-1]`, version `2961717`, file `2841058`.
- Path: `/Volumes/AI-Drawing-16T/ai-drawing/models/loras/anima-base-1-masterpiece-v51.safetensors`.
- SHA-256: `B330B46DF1C71E4409D7B60ECF45DF4EE26310FA914C398226C7800CC2912936`.

The prior read-only `auto_draw.db` inspection found the same graph structure and non-prompt inputs in image `2879`, job `70e01bd2-5db9-4c8e-b1ac-c66f871638ce`, as in both saved profiles. The recorded graph has no LoRA loader despite image metadata naming the old LoRA. Prompt text differs. This supports execution identity, not either profile's current effect or CTY acceptance.
