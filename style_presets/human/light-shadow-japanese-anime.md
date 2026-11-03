---
preset_id: light-shadow-japanese-anime
catalog_path: style_presets/agent/presets/light-shadow-japanese-anime.json
checkpoint: oneObsession_v23.safetensors
lora:
source_url: https://civitai.com/images/136374992
source_alias: 光影日式動畫
---

# [Illustrious] Light and Shadow Japanese Anime

**Status: Needs re-verification.**

Intended style: hand-drawn Japanese anime, vibrant gradients, low-key chiaroscuro, soft overhead light, subtle impasto and controlled glossy accents. The 2D medium/negative guards are agent normalization of the alias, not verbatim source metadata.

[Recipe](../agent/presets/light-shadow-japanese-anime.json) · [Shared operations and evidence rules](../README.md)

## Profile and limits

[`portrait`](../agent/workflows/light-shadow-japanese-anime/portrait.api.json): base style with no profile prompt additions, using `oneObsession_v23.safetensors` and checkpoint CLIP/VAE, without LoRA. Canonical Parent size 1536×2304 was normalized to 1360×2040 for 8-alignment and the 2048 limit. Exact prompts and parameters remain in the JSON.

Do not reintroduce source camera, character or artist tokens as alias defaults.

## Historical source and sample evidence

Requested source [image `136374992`](https://civitai.com/images/136374992) and proxy Parent [image `136378559`](https://civitai.com/images/136378559) are distinct. The prior note reports that REST v1 did not index the requested image/post. The proxy audit combined same-author/model-version REST data with the requested image's embedded metadata. See the [preservation manifest](../agent/preservation_manifests/light-shadow-japanese-anime.json) for retained provenance/classifications.

Historical variant: gallery `2426`, seed `4011193838`, artifact `2026-07-14/ComfyUI_00006_6b1bafc7_0.png`. The request specified a black long-haired girl. Adult/solo, eye color, relaxed pose, a simple dark dress and detailed hair/silhouette were variant-only agent additions, not alias defaults or current acceptance.
