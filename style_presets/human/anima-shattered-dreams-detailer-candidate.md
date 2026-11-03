---
preset_id: anima-shattered-dreams-detailer-candidate
catalog_path: style_presets/agent/presets/anima-shattered-dreams-detailer-candidate.json
checkpoint:
lora:
source_url:
---

# [Anima] Shattered Dreams + Detailer Style (Candidate)

**Status: Needs re-verification.**

Intended style: warm, cinematic, dreamlike film-still illustration with atmospheric storytelling. This remains a candidate, not an observed or accepted style.

[Recipe](../agent/presets/anima-shattered-dreams-detailer-candidate.json) · [Shared operations and evidence rules](../README.md)

## Base graph and resources

No named profiles exist. Omit the profile for the [`__base__` saved graph](../agent/workflows/anima-shattered-dreams-detailer-candidate/__base__.api.json).

Uses `minijma_1.safetensors`, `anima_baseV10_txt.safetensors` with CLIP type `qwen_image`, and `qwen_image_vae.safetensors`. The ordered model-only LoRAs are `ShatteredDreams.safetensors` at 0.5, then `Detailer-AnimeBooster.safetensors` at 0.5. See the JSON for exact prompts and parameters.

## Limits

**Detailer-AnimeBooster is a LoRA, not a detailer stage.** The graph has one sampler and no face detection, face-detailer or inpaint stage. Encoder-family runtime compatibility remains untested. The note records no source/version/hash, sample or acceptance evidence.
