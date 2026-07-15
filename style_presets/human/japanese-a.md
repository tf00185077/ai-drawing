---
preset_id: japanese-a
alias: 日系a
alias_type: style
source_image_id: 82973952
registry_version: 3
---

# 日系a

## Source layers

- Exact Civitai Parent: image `82973952`, post `18428032`.
- Parent recipe SHA-256: `3d4b0b059deab7d9aba34b8ade337a399d528cb94dec8fb116df8926bfad8a08`.
- Checkpoint: `aMixIllustrious_aMix.safetensors`, exact file `1692152/1915059/1813499`.
- This is a style alias. Source character, clothing, pose, room, and camera are not preset defaults.

## Preserved style identity

The reusable identity combines Parent quality tags with visual evidence from the exact official source image: polished Japanese 2D anime illustration, clean thin lineart, hybrid cel shading and soft gradients, high-detail hair/eyes/fabric, warm natural light, soft luminous highlights, harmonious warm colors, crisp character rendering, shallow depth of field, and a softly rendered background.

## Removed source content

Removed character appearance (freckles, orange hair/eyes, ponytail, wink, body descriptors), outfit (sweater, pants, boots, choker), action/pose (blowing kiss, on stomach, lying, feet up), room elements (window, curtains), and dynamic-angle composition. These may only re-enter a variant when explicitly requested.

## Sampling evidence

Civitai API records the final image as `1072×1608`; embedded A1111 metadata records a `768×1152` base pass with 1.4× hires. Both are retained. The executable single-pass default is `1072×1608`, 20 steps, CFG 6, `euler_ancestral`, `normal`, random seed.

## Variant safety

Known school-age characters must remain age-appropriate, fully clothed, and non-suggestive unless a clearly adult alternate portrayal is explicitly requested. Any neutral safety/detail additions are reported as `agent_added`; they are not folded into the alias.

## First variant audit — Kousaka Honoka in a room, lying pose

- User-requested: `Kousaka Honoka (Love Live!)`, a room scene, and a lying pose.
- Necessary character anchors: orange hair, side ponytail, blue eyes.
- Agent-added neutral constraints: solo, bed as a support surface, fully clothed, modest casual clothes, wholesome non-suggestive pose.
- Removed rather than inherited from Parent: freckles, blowing kiss, wink, Parent ponytail identity, source orange/brown eyes conflict, sweater/black pants/boots/choker, breasts/body-size tags, on-stomach/feet-up pose details, window/curtains, and dynamic angle.
- Variant-only negative additions: `nsfw, nude, naked, cleavage, lingerie, underwear, suggestive pose, fetish clothing`.
- Job: `f2d70359-310d-4769-83f0-be5a46818422`; Gallery image `2427`; seed `5245869681136200769`.
- Result: recognizable orange-haired, blue-eyed side-ponytail Honoka, alone in a room and lying on a bed. The model concretized unspecified clothing as a top and short plaid skirt; this is output-specific and is not added to the alias or preset.
