---
preset_id: asagi-floral-pastel-anima
chinese_name: 淺蔥花境粉彩 Anima
catalog_path: style_presets/agent/presets/asagi-floral-pastel-anima.json
checkpoint:
lora:
source_url: https://civitai.com/images/130992277
---

# Toosaka Asagi Floral Pastel Anima

## 中文名稱

淺蔥花境粉彩 Anima

從 Civitai 單張圖片頁 `130992277` 建立的 Anima style preset。此頁沒有 LoRA；資源包含 Anima base-v1.0 和 RealESRGAN anime upscaler。

## Source

- Image URL: https://civitai.com/images/130992277
- Civitai image id: `130992277`
- Creator shown by API/page: `akizukirei608`
- Base model shown by image API: `Anima`
- Image dimensions on Civitai: `3328x4864`
- Badges shown near prompt: `External Generator`, `inpainting`

## Resources Used on Civitai

1. `Anima`
   - Resource type: `Checkpoint`
   - Version: `base-v1.0`
   - Model id: `2458426`
   - Model version id: `2945208`

2. `RealESRGAN_x4Plus Anime 6B`
   - Resource type: `Upscaler`
   - Version: `v1`
   - Model id: `147821`
   - Model version id: `164904`

## Local Resource Pairing

Civitai 把 Anima 顯示為 `Checkpoint`，但本機以 split-model workflow 處理：

- Template: `anima`
- Diffusion model / UNET: `anima_baseV10.safetensors`
- Text encoder: `anima_baseV10_txt.safetensors`
- VAE: `qwen_image_vae.safetensors`
- LoRA: none
- Upscaler: `realesrganX4plusAnime_v1.pt`（已下載；後續若用 MCP custom workflow 成功生圖，應保存對應 upscale workflow template）

Installed files and hashes:

```text
/Volumes/AI-Drawing-16T/ai-drawing/models/diffusion_models/anima_baseV10.safetensors
sha256=BD43B7CFFE1ED1153D9C41E7BEB2F18CB1273EAFBAA3AF3EDD6A173DC90A006E

/Volumes/AI-Drawing-16T/ai-drawing/models/text_encoders/anima_baseV10_txt.safetensors
sha256=CD2A512003E2F9F3CD3C32A9C3573F820BB28C940F73C57B1DDAA983D9223EBA

/Volumes/AI-Drawing-16T/ai-drawing/models/vae/qwen_image_vae.safetensors
sha256=A70580F0213E67967EE9C95F05BB400E8FB08307E017A924BF3441223E023D1F

/Volumes/AI-Drawing-16T/ai-drawing/models/upscale_models/realesrganX4plusAnime_v1.pt
sha256=F872D837D3C90ED2E05227BED711AF5671A6FD1C9F7D7E91C911A61F155E99DA
```

All hashes matched Civitai API.

## Extracted Source Prompt

```text
1girl, solo, masterpiece, best quality, score_7, safe, cinematic lighting, volumetric lighting, anime coloring, anime screenshot,
anime coloring, delicate, dreamy, natural shadow, serene atmosphere, cloud, blue sky, film grain,
soft and gentle colors, soft pastel colors, soft shading, detailed textures,
(floral background:1.5), (irregular border:1.5), outline,geometry, from below, dutch angle,
kaela kovalskia, long hair, twintail, smile, parted lips, hair ribbon, red ribbon,
(gown, burgundy dress, gossamer:1.4),
outdoors, swing, tree, reading book, sitting, on swing, falling petals,
@toosaka asagi
```

## Extracted Negative Prompt

```text
worst quality, low quality, score_1, score_2, score_3, artist name
```

## Extracted Generation Params

```text
cfgScale: 5
steps: 30
sampler: ER SDE
seed: 3797619011
width: 3328
height: 4864
eps_scaling_factor: present on page metadata
```

Mapped local sampler name:

```text
sampler_name: er_sde
```

Scheduler was not shown by the page; recipe leaves scheduler unspecified so the workflow default can apply.

## Current Prompt Design

依 CTY 規則，Civitai 來源圖的通用 profile 不再使用過度乾淨的 `neutral-*`。這一系列以 `source-color-style-neutral` 作為通用模板：保留來源圖的上色/光影/質感/完成度語彙，但移除角色、服裝、道具、姿勢、場景物件。

### Base prompt

```text
masterpiece, best quality, high-quality Anima anime illustration, cinematic lighting, volumetric lighting, anime coloring, anime screenshot, delicate, dreamy, natural shadow, serene atmosphere, film grain, soft pastel colors, soft shading, detailed textures, clean outline, subtle geometric design accents
```

### `source-color-style-neutral`

通用上色風格 profile。這是此系列預設通用 profile，用於「接近來源圖上色/質感，而不是復刻物件」。

```text
prompt_prefix: soft cinematic color grading, airy pastel palette, delicate shadow transitions
prompt_suffix: gentle film-grain finish, serene polished illustration look
negative: kaela kovalskia, hololive, gown, burgundy dress, gossamer, swing, reading book, book, floral border, irregular border, floral background, tree, sitting, on swing, falling petals, from below, dutch angle, hair ribbon, red ribbon
```

### `source-image-130992277`

來源圖復刻 profile，保留來源圖角色/服裝/道具/姿勢/構圖。

```text
prompt_prefix: score_7, safe, anime screenshot, cloud, blue sky, film grain, floral background, irregular border, outline, geometry, from below, dutch angle
prompt_suffix: kaela kovalskia, long hair, twintail, smile, parted lips, hair ribbon, red ribbon, gown, burgundy dress, gossamer, outdoors, swing, tree, reading book, sitting, on swing, falling petals, @toosaka asagi
```

## Source-Specific Elements

以下不應放進 `source-color-style-neutral` 的 positive prompt：

- `kaela kovalskia`
- `long hair`, `twintail`, `hair ribbon`, `red ribbon`
- `gown`, `burgundy dress`, `gossamer`
- `outdoors`, `swing`, `tree`, `reading book`, `sitting`, `on swing`, `falling petals`
- `floral background`, `irregular border`
- `from below`, `dutch angle`
- `cloud`, `blue sky` if the user asks for another setting
- `@toosaka asagi` unless explicitly requested

## Preset-Memory Rule Applied

1. `source-color-style-neutral` 是 Civitai-derived style preset 的通用 profile：保留上色/光影/質感，不保留物件要素。
2. `source-image-*` profile 保留來源圖角色、服裝、道具、姿勢、構圖與藝術家標籤，只用於復刻來源圖。
3. 修改服裝/場景/背景時，移除舊 positive token 後替換成新 token，不疊加矛盾詞，也不靠 negative 解決 positive 衝突。
4. 若來源頁列出後處理資源（例如 upscaler），需下載並嘗試用 MCP custom workflow 納入 graph；若成功生圖，使用 `save_workflow_template` 保存可複用模板。
