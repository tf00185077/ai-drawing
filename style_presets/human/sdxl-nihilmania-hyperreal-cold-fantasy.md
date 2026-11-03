---
preset_id: sdxl-nihilmania-hyperreal-cold-fantasy
catalog_path: style_presets/agent/presets/sdxl-nihilmania-hyperreal-cold-fantasy.json
checkpoint: sdxlUnstableDiffusers_nihilmania.safetensors
lora: 
source_url:
---

# [SDXL] NihilMania Hyperreal Cold Fantasy

**Status: Needs re-verification.**

Intended style: hyperreal stylized fantasy, cold blue cinematic grading, fine texture, dramatic depth of field and concept-art detail. UHD/8K are prompt tokens, not output dimensions.

[Recipe](../agent/presets/sdxl-nihilmania-hyperreal-cold-fantasy.json) · [Shared operations and evidence rules](../README.md)

## Profile and execution identity

[`portrait`](../agent/workflows/sdxl-nihilmania-hyperreal-cold-fantasy/portrait.api.json): cold-blue fantasy portrait with skin/hair texture and depth-of-field intent. Single-pass output is 768×1368; no upscaler. Exact prompts and parameters remain in the JSON.

Uses `sdxlUnstableDiffusers_nihilmania.safetensors`, no LoRA, and **checkpoint/baked VAE**: `VAEDecode` connects to `CheckpointLoaderSimple` output 2; no `VAELoader` exists. Recipe `vae=null` matches that wiring. The former external `sdxl_vae.safetensors` pairing was intent only; a variant using it needs separate re-verification.

## Historical execution evidence

The prior read-only `auto_draw.db` inspection found matching graph structure and non-prompt inputs in image `2975`, job `e97336a0-f6eb-42b1-a4b6-313a58238567`. Its decoder uses checkpoint VAE output despite metadata naming `sdxl_vae.safetensors`. Prompt text differs. This supports execution configuration, not independent profile acceptance. The note records no source/version/hash evidence.
