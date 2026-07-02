# Qwen Pose Routes 測試結論（2026-06-26）

## 總結

- **Route C 是主線**：已知 subject 圖 + pose reference / skeleton → 調整角色動作。控制力與任務目標最接近。
- **Route B 降級保留**：pose reference / DWPose + prompt → 生成新圖。可作粗略 pose-inspired generation，但不適合承諾精準 pose following。

## Route C：Qwen Image Edit 2511 + AnyPose

### 對應網路方法

- `lilylilith/AnyPose`
- `linoyts/Qwen-Image-Edit-2511-AnyPose` HF Space
- 概念：`Image 1 = subject`，`Image 2 = pose reference`，讓 subject 做 reference 的姿勢。

### 本地模型

- `qwen-image-edit-2511-Q5_K_M.gguf`（主用）
- `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`
- LoRAs:
  - `2511-AnyPose-base-000006250.safetensors`
  - `2511-AnyPose-helper-00006000.safetensors`
  - `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`

### MCP workflow template

```text
gen_img2img_qwen_image_edit_lora_model_only_multi_lora_pose_transfer_image_ref_pose_ref
```

### 結論

- pose photo reference：pose 控制較強，但背景/攝影感容易污染 subject。
- DWPose skeleton reference：subject 風格與背景保留較好，pose 精準度略弱。
- 建議主線：先用 pose photo；若污染嚴重，改用 skeleton。

## Route B：Qwen Image Union + DiffSynth OpenPose

### 對應網路方法

- `axiomgraph/ComfyUIWorkflow` 的 `Qwen Image Union Diffsynth Lora OpenPose.json`
- 概念：`prompt + pose reference / DWPose skeleton → 生成新圖`。

### 本地模型

- `qwen-image-Q5_K_M.gguf`（主用）
- `qwen_2.5_vl_7b_fp8_scaled.safetensors`
- `qwen_image_vae.safetensors`
- LoRAs:
  - `qwen_image_union_diffsynth_lora.safetensors`
  - `Qwen-Image-Lightning-8steps-V1.1.safetensors`

### MCP workflow template

```text
gen_txt2img_qwen_image_controlnet_pose_lora_model_only_multi_lora_image_ref
```

### 測試結果

- High-lunge pose photo → DWPose → Route B：腿部有時接近，但上半身/手臂常錯。
- 加強 prompt：可拉動手臂，但腿部又容易跑掉。
- 直接餵 DWPose skeleton：沒有改善，甚至可能變成半身構圖。
- 最終判斷：可作 pose-inspired generation；不適合作精準 OpenPose/ControlNet 級姿勢跟隨。

## 清理與模型策略

- `qwen_image_fp8_e4m3fn.safetensors` 已刪除：Route B FP8 實測 runtime memory pressure 過大，sampling 0/10 被 OS kill。
- `qwen_image_edit_2511_fp8mixed.safetensors` 仍保留：Route C 尚未正式棄用 FP8，但目前 Q5 GGUF 已可用。
- 量化策略：先 Q5，若壓力/速度不可接受再 Q4；Q2 僅保底證明路線通。
- 後續若路線棄用或模型跑不起來，刪除相關模型釋放空間。

## 重要檔案

Research/workflows:

```text
~/Desktop/ai-drawing/research/qwen-pose-routes/
```

Templates:

```text
~/Desktop/ai-drawing/backend/workflows/gen_img2img_qwen_image_edit_lora_model_only_multi_lora_pose_transfer_image_ref_pose_ref.json
~/Desktop/ai-drawing/backend/workflows/gen_txt2img_qwen_image_controlnet_pose_lora_model_only_multi_lora_image_ref.json
```

Public pose refs:

```text
~/Desktop/ai-drawing/research/qwen-pose-routes/pose_refs/
```

Gallery outputs:

```text
~/Desktop/ai-drawing/outputs/gallery/2026-06-26/
```
