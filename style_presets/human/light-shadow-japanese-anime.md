---
preset_id: light-shadow-japanese-anime
catalog_path: style_presets/agent/presets/light-shadow-japanese-anime.json
checkpoint: oneObsession_v23.safetensors
lora:
source_url: https://civitai.com/images/136374992
source_alias: 光影日式動畫
---

# 光影日式動畫

從 Civitai 來源圖抽取的**風格型** preset。它只保存可跨角色與場景複用的色彩、材質、光影、線條與渲染語彙；角色、服裝、姿勢、背景與鏡位留給每次生成的 content prompt。

## 來源與稽核限制

- 使用者指定來源圖：Civitai image `136374992`。
- 該圖片頁面與官方 CDN 原圖可取得，但 Civitai REST v1 未索引該 image/post。
- Source Alias registry 因此以同作者、同模型版本且 REST 可解析的 image `136378559` 作代理稽核 Parent，並結合指定原圖的 embedded metadata；不可宣稱 registry identity 就是 `136374992`。
- Checkpoint：`oneObsession_v23.safetensors`
- Civitai model/version/file：`1318945` / `3118448` / `2998810`
- SHA-256：`71b1a14c2e4dbf3d43d5a8226a6bfe6a8a6f6a2bce97920b2e15a5f0203f06f2`
- Template：`default`

## Prompt 抽取結果

### 保留並正規化

- 品質／媒材：`masterpiece`, `best quality`, `very aesthetic`, `high detail`, `digital art`。
- 色彩：`vibrant colors`, `smooth gradients`, `colorful depth`。
- 光影：`cinematic lighting`, `soft shadow`, `soft lighting`, `lighting from above`, `light and shadow gradients`, `high contrast`, `chiaroscuro`, `low key`。
- 質感／渲染：`impasto`, `smooth shading`, `glossy surfaces`；正規化成較不會污染皮膚的 `subtle impasto texture`, `controlled glossy accents`。
- 氛圍：`mystical aura` 正規化為 `mystical atmosphere`。

### 依別名語意新增

別名是「光影日式動畫」，因此加入媒材鎖：

- `pure hand-drawn 2D Japanese TV anime style`
- `crisp anime lineart`
- `refined cel shading with controlled gradients`

這些不是冒充原 Parent prompt，而是由別名意圖導出的明示正規化層。

### 移除

- 原角色／作品：`hina (dress) (blue archive)` 與其他角色身份 token。
- 人物外觀：原髮色、眼睛、身形、表情、服裝與飾品。
- 動作／姿勢：`dynamic pose` 等主體動作。
- 場景／背景：原圖特定環境與背景內容。
- 構圖／鏡位：`high angle`, `dutch angle`, `foreshortening`, `depth of field`, `shallow depth of field`, `dynamic angle`；風格 preset 不應鎖死下一張圖的鏡頭。
- 作者 token：`artist:dino`, `artist:mika pikazo`；避免把作者身份當成泛用風格控制。
- Parser／模板雜訊：`lnewest`, `lazypos`, `lazyup`, `dak depth`, `low kye`、拼字錯誤與重複詞。

### Negative prompt 處理

- 保留並合併：解剖、手足、多指、低品質、壓縮、浮水印、文字、簽名等一般失敗模式。
- 移除：`simple background`（不應強迫每次都做複雜背景）、重複或低資訊詞。
- 新增日式 2D 媒材防護：`photorealistic`, `realistic skin`, `3d`, `cgi`, `semi-realistic`, `western comic style`, `plastic skin`, `glossy skin`。

## 預設生成參數

- Steps：20
- CFG：5.0
- Sampler：`euler`
- Scheduler：`karras`
- Size：1536×2304

這些沿用 Parent 的 canonical sampling；生成時可由明確需求覆寫。
