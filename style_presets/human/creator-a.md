---
preset_id: creator-a
chinese_name: 柔光動漫創作者 A
catalog_path: style_presets/agent/catalog.json
checkpoint: novaAnimeXL_ilV190.safetensors
lora: creatorA_style_v2.safetensors
source_url:
---

# Creator A 柔光動漫

## 中文名稱

柔光動漫創作者 A

## Resource Pairing

- Checkpoint: novaAnimeXL_ilV190.safetensors
- LoRA: creatorA_style_v2.safetensors
- Trigger words: creatorA_style
- Suggested LoRA strength: 0.8
- Template: default_lora

## Prompt Base

Base prompt: masterpiece, best quality, 1girl, soft lighting

Negative prompt: lowres, bad anatomy, worst quality, jpeg artifacts

## Profiles

### default

Use for: 一般構圖，方形 1024x1024。

Prompt hints: 直接把要畫的內容當 content_prompt 傳入即可。

### portrait

Use for: 半身/特寫人像，896x1152。

Prompt hints: 已加上 close-up portrait 前綴與 detailed face 後綴；負面額外排除 full body。

### full-body

Use for: 全身、動態姿勢，832x1216。

Prompt hints: 已加上 full body 前綴與 dynamic pose 後綴。

## Source Notes

- Creator/source: （填入創作者或來源連結）
- License/usage notes: （填入授權與使用限制）
- Download location: （填入模型/LoRA 下載位置）

## Experiments

- Works well: 柔光、淺景深人像；cfg 6~7 表現穩定。
- Fails when: cfg > 8 容易過曝；手部仍需 inpaint 修。
- Example image ids: （填入 gallery 內代表作的 image id）
