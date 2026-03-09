# img2img + LoRA + ControlNet 姿態

## 用途

**對已存在的圖片做動作調整**：輸入主體圖 + 姿態參考圖，以 Checkpoint + LoRA 控制風格，ControlNet 控制目標動作。

## 流程說明

1. **LoadImage (subject)**：主體圖片，作為 img2img 起點
2. **LoadImage (pose)**：姿態參考圖（目標動作）
3. **VAEEncode**：主體圖編碼為 latent
4. **DWPreprocessor**：從姿態圖萃取骨骼 pose map
5. **CheckpointLoaderSimple + LoraLoader**：模型與 LoRA
6. **ControlNetLoader + ControlNetApply**：將 pose 條件套用到生成
7. **KSampler (denoise 0.75)**：img2img 生成

## 可替換參數

- `checkpoint`、`lora`、`prompt`、`negative_prompt`
- `seed`、`steps`、`cfg`
- `image`：主體圖路徑（相對於 gallery_dir）
- `image_pose`：姿態參考圖路徑（相對於 gallery_dir）

## API 使用

```bash
POST /api/generate/custom
{
  "workflow": { ... },  # 或 GET /api/generate/workflow-templates/img2img_lora_pose
  "checkpoint": "v1-5-pruned-emaonly.safetensors",
  "lora": "my_character.safetensors",
  "prompt": "1girl, standing, smile",
  "image": "2026-03-08/subject.png",
  "image_pose": "2026-03-08/pose_ref.png"
}
```
