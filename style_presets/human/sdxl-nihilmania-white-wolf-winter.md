---
preset_id: sdxl-nihilmania-white-wolf-winter
catalog_path: style_presets/agent/presets/sdxl-nihilmania-white-wolf-winter.json
checkpoint: sdxlUnstableDiffusers_nihilmania.safetensors
lora: 
source_url:
---

# [SDXL] NihilMania White Wolf Winter

**Status: Needs re-verification.**

Intended content/style: a white-haired girl and white wolf with bright blue eyes, snowy landscape and close-up framing in hyperreal cold light. **This is a fixed-content winter-fantasy recipe, not a neutral style.** UHD/8K are prompt tokens only.

[Recipe](../agent/presets/sdxl-nihilmania-white-wolf-winter.json) · [Shared operations and evidence rules](../README.md)

## Profile and execution identity

[`portrait`](../agent/workflows/sdxl-nihilmania-white-wolf-winter/portrait.api.json): fantasy portrait that reinforces snow, white wolf companion and blue eyes. Output is 768×1368, not 8K. Exact prompts and parameters remain in the JSON.

Uses `sdxlUnstableDiffusers_nihilmania.safetensors`, no LoRA, and **checkpoint/baked VAE** through `CheckpointLoaderSimple` output 2. No external VAE loader exists; recipe `vae=null` matches the graph. The earlier external `sdxl_vae.safetensors` intent was not this execution and needs separate re-verification.

For unrelated subjects, use the [cold-fantasy sibling](sdxl-nihilmania-hyperreal-cold-fantasy.md) or revise positive content. Adding negatives does not remove the white-wolf content lock.

## Historical execution evidence

The prior read-only `auto_draw.db` inspection found matching graph structure and non-prompt inputs in image `2975`, job `e97336a0-f6eb-42b1-a4b6-313a58238567`. Decode uses checkpoint VAE output despite metadata naming `sdxl_vae.safetensors`. Prompt text differs. Both NihilMania notes cite this same execution-settings evidence; it does not independently prove white-wolf output or acceptance. The note records no source/version/hash evidence.
