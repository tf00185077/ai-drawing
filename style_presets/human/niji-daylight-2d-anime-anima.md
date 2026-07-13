---
preset_id: niji-daylight-2d-anime-anima
chinese_name: 白天日系手繪2D Niji Anima
catalog_path: style_presets/agent/presets/niji-daylight-2d-anime-anima.json
checkpoint:
lora: anima-highres-aesthetic-boost.safetensors
source_preset: high-contrast-color-anima
---

# Niji Daylight 2D Anime Anima

## 中文名稱

白天日系手繪2D Niji Anima

## 目的

這是從 `high-contrast-color-anima` 分出的白天 2D 動畫版。

CTY 的結論：原高對比用色 preset 的 glossy / semi-realistic 不是「日式 2D 動畫感」必需；若背景要 LoveLive 校園或白天校園，來源情境預設會拉錯方向。因此本 preset 保留 Anima/Niji 多 LoRA recipe，但把預設 prompt 改成：

- 純日系手繪 2D 動畫
- 白天 / 清亮校園背景
- flat matte cel colors
- clean ink line
- simple cel shadow shapes
- cool clean rim light / clean Niji color separation
- 不預設黑夜、月光、暗背景、半寫實或 glossy 3D 質感

## Prompt core

```text
pure hand-drawn 2D Japanese TV anime cel style,
daylight niji lock: clear blue sky, cool clean rim light, soft crisp anime shadows, bright school campus;
anime only on face, eyes, lineart,
flat matte color fills,
clean ink line,
simple cel shadow shapes,
no 3D lighting
```

## Profiles

### daylight-campus-2d

預設給 LoveLive / 校園 / 白天背景：清亮藍天、乾淨校園、手繪 2D 動畫背景，不走暗色月光。

### neutral-daylight-2d

泛用白天 2D 動畫版；適合非校園場景但仍要清亮背景。

## Required resources

沿用 `high-contrast-color-anima` 的 Anima split model 與多 LoRA stack：

| Resource | File | Weight |
|---|---|---:|
| Anima Highres/Aesthetic Boost | `anima-highres-aesthetic-boost.safetensors` | 0.7 |
| NijiReol | `Niji Reol v1 EP11.safetensors` | 0.8 |
| Niji Sweet Spot | `AnimaNSS4RE.safetensors` | 0.65 |

## 注意

不要把來源 preset 的 `semi-realistic`, `glossy highlight rendering`, `dark cinematic color grading`, `deep shadow contrast` 當成此 preset 的預設 positive。這些詞不適合 CTY 要的白天日式手繪 2D 動畫。
