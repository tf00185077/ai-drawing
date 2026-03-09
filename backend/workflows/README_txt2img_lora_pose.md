# txt2img + LoRA + ControlNet 姿態

## 用途

**不傳入主體圖，以 Checkpoint + LoRA 控制風格與角色，以 ControlNet 控制動作**：純文字生圖 + 姿態參考。

## 流程說明

1. **EmptyLatentImage**：空白 latent，從頭生成
2. **CheckpointLoaderSimple**：基礎模型
3. **LoraLoader**：LoRA 風格/角色
4. **LoadImage (pose)**：姿態參考圖
5. **DWPreprocessor**：從姿態圖萃取骨骼 pose map
6. **ControlNetLoader + ControlNetApply**：將 pose 條件套用到生成
7. **KSampler + VAEDecode + SaveImage**：txt2img 生成

## 可替換參數

- `checkpoint`、`lora`、`prompt`、`negative_prompt`
- `seed`、`steps`、`cfg`、`width`、`height`、`batch_size`
- `sampler_name`、`scheduler`
- `image_pose`：姿態參考圖路徑（必填，相對於 gallery_dir）

## API 使用

```bash
POST /api/generate/custom
{
  "workflow": { ... },  # 或 GET /api/generate/workflow-templates/txt2img_lora_pose
  "checkpoint": "v1-5-pruned-emaonly.safetensors",
  "lora": "my_character.safetensors",
  "prompt": "1girl, standing, smile",
  "image_pose": "2026-03-08/ComfyUI_xxx.png"
}
```
