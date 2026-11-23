---
preset_id: high-contrast-color-anima
chinese_name: 高對比用色
catalog_path: style_presets/agent/presets/high-contrast-color-anima.json
checkpoint:
lora: anima-highres-aesthetic-boost.safetensors
source_url: https://civitai.com/images/131966887
---

# [Anima] High Contrast Color

**Status: Needs re-verification.**

Intended style: vivid Niji-like color separation, cool rim light and crisp 2D anime linework. Base intent does not require a source character, background or time of day.

[Recipe](../agent/presets/high-contrast-color-anima.json) · [Shared operations and evidence rules](../README.md)

## Profiles

- [`source-color-style-neutral`](../agent/workflows/high-contrast-color-anima/source-color-style-neutral.api.json): color/material transfer intent; negatives also block woman, black hair, armor and sword, so check new-content conflicts.
- [`source-image-131966887`](../agent/workflows/high-contrast-color-anima/source-image-131966887.api.json): despite its name, now retains color-reference language rather than the original scene/character.
- [`anime-2d-default`](../agent/workflows/high-contrast-color-anima/anime-2d-default.api.json): matte hand-drawn 2D intent with an explicit **bright school campus**; not scene-neutral.

## Resource distinctions and limits

Uses an ordered three-LoRA stack: `anima-highres-aesthetic-boost.safetensors` at 0.7, `Niji Reol v1 EP11.safetensors` at 0.8, then `AnimaNSS4RE.safetensors` at 0.65. The legacy first-LoRA field alone is insufficient. Sweet Spot's 0.65 is a local conservative choice; the source page hid its weight.

The inherited `niji_moonlit_honoka_multilora` output prefix does not require moonlight or Honoka. See the linked JSON for full resources, prompts and parameters.

## Historical source evidence

[Civitai image `131966887`](https://civitai.com/images/131966887) is the recorded High Contrast Color lineage, not an independently proven source for every Niji profile. Base Anima version `2945208`; LoRA versions: Highres/Aesthetic Boost `2855073`, Niji Reol `2960729`, Niji Sweet Spot `2964538`. Resource SHA-256 and complete license evidence are missing.
