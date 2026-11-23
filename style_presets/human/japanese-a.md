---
preset_id: japanese-a
alias: 日系a
alias_type: style
source_image_id: 82973952
registry_version: 3
catalog_path: style_presets/agent/presets/japanese-a.json
---

# [Illustrious] Japanese A

**Status: Needs re-verification.**

Intended style: polished Japanese anime illustration, thin lineart, cel shading with controlled gradients, warm daylight and soft backgrounds. Manifest visual-evidence classifications are historical, not a fresh inspection.

[Recipe](../agent/presets/japanese-a.json) · [Shared operations and evidence rules](../README.md)

## Profile and processing limits

[`portrait`](../agent/workflows/japanese-a/portrait.api.json): base style at 1072×1608, with no additional profile prompt. Uses `aMixIllustrious_aMix.safetensors` and its checkpoint CLIP/VAE, without LoRA.

Source API final size was 1072×1608. Embedded A1111 metadata recorded a 768×1152 base, 1.4× hires, 10 hires steps and denoise 0.1. The saved graph uses **one pass** at final size, not that hires chain. Recipe seed is unspecified and the manifest describes randomization; exact replay fixes seed `2667468589`. Other exact settings remain in the JSON.

Character, clothing, room, camera and source pose are not alias defaults. Keep school-age characters age-appropriate and non-suggestive; identify variant-only agent additions separately.

## Historical source and sample evidence

The [preservation manifest](../agent/preservation_manifests/japanese-a.json) retains the source/resource locks, acquisition/prompt/media hashes and classifications. Source: [Civitai image `82973952`](https://civitai.com/images/82973952), post `18428032`. Checkpoint lock: model `1692152`, version `1915059`, file `1813499`, size `7105348060` bytes, SHA-256 `b199b92ee9fadbd84b926e8f2592a8ea04503ec0953b50d62d40169264fb69d4`.

Historical variant: gallery `2427`, job `f2d70359-310d-4769-83f0-be5a46818422`, seed `5245869681136200769`. The request specified Honoka, a room and a lying pose; the agent added modest clothing and bed support. The original note described recognizable Honoka on a bed, with a top and short plaid skirt. That is a historical description, not current validation; those clothes are not alias defaults.
