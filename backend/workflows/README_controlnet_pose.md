# ControlNet 姿勢 Workflow

## 用途

**給圖片，透過 ControlNet 改變動作**：輸入人物圖片，以 OpenPose 姿態控制生成新圖。

## 流程說明

1. **LoadImage (subject)**：主體圖片，作為 img2img 起點
2. **LoadImage (pose)**：姿態參考圖，可與主體同一張
3. **DWPreprocessor**：從姿態圖萃取骨骼 pose map
4. **ControlNetLoader**：載入 OpenPose 模型
5. **ControlNetApply**：將 pose 條件套用到生成
6. **VAEEncode + KSampler + VAEDecode**：img2img 生成

## 使用情境

| 情境 | subject 圖 | pose 圖 | 結果 |
|------|------------|---------|------|
| 同圖保姿 | 人物照 A | 人物照 A | 依 prompt 變化，保留原 pose |
| 姿態遷移 | 人物照 A | 姿態參考 B | 人物 A 以姿態 B 重新生成 |

## 前置需求

- **ComfyUI ControlNet Aux**：需安裝 [ComfyUI's ControlNet Auxiliary Preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux)，提供 `DWPreprocessor`
- **OpenPose ControlNet 模型**：`control_v11p_sd15_openpose_fp16.safetensors` 放入 `ComfyUI/models/controlnet/`

## 參數替換

透過 `workflow.apply_params()` 可替換：

- `image`：主體圖檔名（上傳後填入）
- `image_pose`：姿態參考圖檔名（若不設則用 `image`）
- `checkpoint`、`prompt`、`negative_prompt`、`seed`、`steps`、`cfg`、`denoise`

## API 使用範例

```python
from app.core.workflow import load_template, apply_params

wf = load_template("controlnet_pose")
wf = apply_params(
    wf,
    image="uploaded_subject.png",
    image_pose="uploaded_pose_ref.png",  # 可省略，預設同 image
    prompt="1girl, standing, smile",
    denoise=0.75,
)
# 提交 wf 至 ComfyUI /prompt
```
