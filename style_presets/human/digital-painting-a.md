---
preset_id: digital-painting-a
chinese_name: 暖粉日系電繪 Anima
catalog_path: style_presets/agent/presets/digital-painting-a.json
checkpoint:
lora: anima-base-1-masterpiece-v51.safetensors
source_url: https://civitai.com/models/929497/aesthetic-quality-modifiers-masterpiece
---

# 電繪A / Anima Masterpiece Digital Painting

## 中文名稱

暖粉日系電繪 Anima

以 Civitai「Aesthetic Quality Modifiers - Masterpiece」的 Anima Base 1 LoRA 建立的電繪風格 preset。

## Resource Pairing

- Model family: Anima split-model workflow
- Template: `anima`
- Diffusion model: `anima_baseV10.safetensors`
- Text encoder: `qwen_3_06b_base.safetensors`
- VAE: `qwen_image_vae.safetensors`
- LoRA: `anima-base-1-masterpiece-v51.safetensors`
- LoRA strength: `1.0`

> 注意：Anima 不是傳統 checkpoint-only 流程；主模型應放在 `models/diffusion_models`，不是 `models/checkpoints`。本 preset 的 `checkpoint` 留空，改用 `diffusion_model` / `text_encoder` / `vae` 三元件。

## 來源與安裝位置

- Civitai model: `Aesthetic Quality Modifiers - Masterpiece`
- Civitai model id: `929497`
- Selected version: `v5.1 [anima-base-1]`
- Version id: `2961717`
- File id: `2841058`
- Downloaded file: `/Users/tf00185088/comfyui/models/loras/anima-base-1-masterpiece-v51.safetensors`
- SHA256: `B330B46DF1C71E4409D7B60ECF45DF4EE26310FA914C398226C7800CC2912936`

## 從使用者 prompt 提煉出的風格元素

原 prompt 中排除角色、服裝、道具、作品名、具體場景後，保留以下風格向量：

- Quality tags: `masterpiece`, `very aesthetic`, `absurdres`
- Artist blend: `@[yoneyama mai|kuga huna|diyokama]`
- 視覺類型：高完成度日系電繪、商業 key visual、精緻角色插畫
- 線條：乾淨、細緻、帶繪畫感的 refined linework
- 光線：soft warm lighting、柔和暖光、低刺激對比
- 色彩：pastel color palette、柔粉色系、溫暖低飽和調性
- 構圖：medium-shot / cinematic character framing，角色為中心但背景裝飾感完整
- 材質/動勢：flowing fabric accents、柔軟布料流動感、空氣感
- 背景語彙：traditional decorative background elements，可放中式燈籠、窗框、布幔等裝飾，但不強綁特定題材

## Prompt 組裝規則

機器 recipe 會把風格分成：

1. `base_prompt`：品質、artist blend、電繪完成度與主風格
2. `warm-pastel.prompt_prefix`：柔暖光、粉彩、氛圍光
3. 使用者 content prompt：角色/主題/場景
4. `warm-pastel.prompt_suffix`：布料流動、傳統裝飾背景、中景構圖、乾淨細節

推薦使用：

```text
compose_style_preset(
  preset_id="digital-painting-a",
  profile="warm-pastel",
  content_prompt="<角色與場景內容>"
)
```

## Negative Prompt

基礎 negative：

```text
worst quality, low quality, blurry, jpeg artifacts, sepia, signature, artist name, bad anatomy, deformed
```

`warm-pastel` 額外避免：

```text
harsh contrast, muddy colors, flat lighting
```
