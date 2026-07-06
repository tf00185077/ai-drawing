---
preset_id: tactile-verism-city-noir-anima
chinese_name: 厚塗油彩城市夜景 Anima
catalog_path: style_presets/agent/presets/tactile-verism-city-noir-anima.json
checkpoint:
lora: Tactile_Verism-Anima-tcl-vrs-style.safetensors
source_url: https://civitai.com/images/133592240
---

# Tactile Verism City Noir Anima

## 中文名稱

厚塗油彩城市夜景 Anima

來源圖：<https://civitai.com/images/133592240>

這個 preset 捕捉來源圖的「表現主義油畫 / 厚塗觸感 / 暗青綠與金色夜景 / noir 城市氛圍」風格。來源圖是 Anima txt2img，且 External Generator metadata 額外標出一個 LoRA alias：`tactile_paint_3.5k_cl_1.0.safetensors : str_1`。該 alias 經 Civitai model search 對應到 `Tactile Verism` Anima LoRA 的實際檔案 `Tactile_Verism-Anima-tcl-vrs-style.safetensors`。

## Source generation data

- Tool: ComfyUI
- Technique: txt2img
- Base model: Anima
- Image size: `832x1280`
- CFG scale: `2.5`
- Steps: `35`
- Sampler: `Euler` → backend sampler name `euler`
- Seed: `344596877060857`
- Negative prompt: not shown on page

## Required resources

### Split Anima base

- Civitai resource: `Anima — base-v1.0`
- Model version ID: `2945208`
- Diffusion model: `anima_baseV10.safetensors`
- Text encoder: `anima_baseV10_txt.safetensors`
- VAE: `qwen_image_vae.safetensors`

### LoRA stack

| Resource | External metadata alias | Installed file | Version ID | Strength | SHA256 |
|---|---|---|---:|---:|---|
| Tactile Verism | `tactile_paint_3.5k_cl_1.0.safetensors` | `Tactile_Verism-Anima-tcl-vrs-style.safetensors` | `2938169` | `1.0` | `63CB6E25EB5CDBC1879B90B00DA05B7EB3CE66C08100FD3478D9B2DB8C29E084` |

Installed local path:

```text
/Volumes/AI-Drawing-16T/ai-drawing/models/loras/Tactile_Verism-Anima-tcl-vrs-style.safetensors
```

## Workflow requirement

The normal `anima` workflow is insufficient because it has no LoRA loader node. This preset requires an Anima txt2img workflow with `LoraLoaderModelOnly`.

Matching reusable workflow:

```text
gen_txt2img_anima_lora_model_only
```

Capability shape:

```text
modality = txt2img
model_family = anima
conditioning = ["lora_model_only"]
io = ["text"]
```

## Source prompt

```text
Expressionist oil painting, heavy impasto, visible thick brushstrokes, dark teal and gold color palette. A sprawling, industrial city skyline at night, arched bridge over a shimmering river, glowing yellow moon, hazy smog, dense skyscrapers with scattered lights. Steam rises from buildings, wet streets reflecting city gold. No visible people, focus on vast urban scale. Moody, noir, atmospheric, mysterious.
```

## Profiles

### source-color-style-neutral

Reusable style profile. Keeps:

- expressionist oil painting
- heavy impasto
- visible thick brushstrokes
- tactile paint texture
- dark teal and gold palette
- moody noir atmosphere
- hazy/smoggy atmospheric depth
- wet reflective surfaces
- glowing gold highlights
- mysterious cinematic nocturne lighting

Removes source-specific composition locks such as exact arched bridge, exact skyline, exact yellow moon, and the no-visible-people constraint.

### source-image-133592240

Source reconstruction profile. Keeps source content and composition:

- sprawling industrial city skyline at night
- arched bridge over shimmering river
- glowing yellow moon
- hazy smog
- dense skyscrapers with scattered lights
- steam rising from buildings
- wet streets reflecting city gold
- no visible people
- vast urban scale

Use this profile only when trying to reproduce the source image composition, not for general character/content generation.

## CTY-approved anime oil color-safe profile

Profile id:

```text
anime-oil-color-safe
```

This profile was added after CTY confirmed that image `391` / job `50a309e5-e4f4-44b5-80d5-071dd412f853` had the desired color direction. Use it for normal anime-character portraits instead of the raw `source-color-style-neutral` profile.

### Intent

Keep the Civitai source's dark teal / amber-gold noir oil-paint atmosphere, but preserve anime character readability:

- anime face proportions stay clean and readable
- face uses warm natural key light and healthy soft peach skin
- teal is constrained to the background and shadows
- amber-gold is constrained to rim light / hair edge / background accents
- oil/impasto texture is applied as brushwork on hair, clothing, and background, not as metallic or ghostly skin material

### Prompt shape

```text
anime oil painting hybrid, preserved anime character design, clean anime facial proportions, expressive anime eyes, soft anime face, warm natural key light on face, healthy soft peach skin, natural blush, non-metallic matte skin, oil painting brushwork visible on hair, clothes, and background, controlled impasto texture, dark teal noir background, teal shadows only in the background, restrained amber-gold rim light behind the character, subtle gold edge light on hair, <character/content>, wet reflective background surfaces, smoggy atmospheric depth, high quality anime portrait with painterly oil finish, keep the character face anime and readable, oil paint texture on rendering not on skin material
```

### Default profile params

```text
lora_strength: 0.5
cfg: 3.2
steps: 35
sampler_name: euler
scheduler: simple
width: 832
height: 1280
```

### Material blockers

```text
photorealistic face, realistic old face, uncanny face, corpse-like skin, ghostly skin, green skin, blue skin, gray skin, sickly pale skin, metallic skin, golden skin, gold face, bronze face, statue, mask, robot, armor, chrome, reflective face, gold paint on skin, face covered in paint, heavy paint blobs on face, harsh teal light on face
```

### Usage note

For CTY's anime-character requests, start from `anime-oil-color-safe`, then add detailed character identity, hair/eye/accessory/clothing tokens. Do not revert to broad unscoped `dark teal and gold color palette` near character tokens; that caused metallic/ghostly face contamination.

## CTY-approved character-preserving oil correction

Profile id:

```text
anime-oil-character-preserving
```

This profile records CTY's approved third correction result:

```text
image_id: 399
job_id: 2542d05a-af63-420f-82f2-68cc638dcf69
seed: 3833842405
```

### What this correction actually means

The important correction is **not** “record the yellow ribbon fix.” The yellow/body-binding issue was only one visible symptom of the larger problem: the Tactile Verism / teal-gold noir style could take over the whole character and cover the face/body with strange material or color.

The accepted direction is:

- keep the character recognizable and anime-shaped
- keep the face warm, natural, matte, and readable
- keep eyes / facial proportions / identity details crisp
- apply oil-paint feeling as brushwork and rendering texture, not as skin material
- move the strong teal / gold / noir palette mostly to background, atmosphere, rim light, edge light, hair, clothing folds, and silhouette texture
- prevent the whole character from being washed over by teal, gold, metallic, ghostly, gray, or corpse-like color
- use reduced LoRA strength and moderate CFG so the style supports the character instead of replacing it

### Durable prompt method

```text
anime oil painting hybrid,
preserved anime character design,
recognizable character identity,
clean anime facial proportions,
expressive anime eyes,
soft anime face,
readable character features,
warm natural key light on face,
healthy peach anime skin with subtle painterly shading,
natural blush,
non-metallic matte skin,
avoid global color wash on face,
painterly but readable anime portrait,
oil brushwork as surface rendering rather than skin material,
visible oil brush strokes on hair locks,
painterly edges on hairstyle silhouette,
visible oil brush texture on clothing fabric,
broad oil-paint strokes on clothing folds and sleeve shadows,
painterly strokes on collar and neck accessory,
controlled impasto texture in the background,
textured painterly background with visible canvas-like brush grain,
teal and amber color grading constrained to background, atmosphere, rim light, and edge light,
warm natural face color separated from the background palette,
<character/content>,
bust portrait, chest-up portrait, cropped above waist, upper body only,
hands out of frame,
wet reflective background surfaces,
smoggy atmospheric depth,
high quality anime character portrait with stronger painterly oil finish,
anime face preserved while hair, clothing, background, and silhouette edges carry the oil-paint texture,
character details remain crisp and recognizable under the painterly finish
```

### Negative blockers

Use blockers that target **global style contamination of the character**, especially the face/skin:

```text
photorealistic face, realistic old face, uncanny face,
distorted character identity, lost character identity,
face obscured, face covered in paint, heavy paint blobs on face,
overpainted face, color wash over face,
teal face, blue face, green face, gray face,
corpse-like skin, ghostly skin, sickly pale skin,
metallic skin, golden skin, gold face, bronze face,
chrome skin, reflective face,
statue, mask, robot, armor,
gold paint on skin, harsh teal light on face,
excessive rim light on face, muddy facial details
```

Body-accessory blockers can remain as secondary cleanup when the image is waist-visible, but they are not the main lesson.

### Default params from the accepted correction

```text
lora_strength: 0.5
cfg: 3.2
steps: 35
sampler_name: euler
scheduler: simple
width: 832
height: 1280
```

### Usage note

Use `anime-oil-character-preserving` when applying this preset to a named anime/game character. It is the safer default than the raw source-style profile because it separates character identity from background/style color: the oil/noir look should enhance hair, clothing, edges, and atmosphere while leaving the character's face and key traits intact.

