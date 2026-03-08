---
name: comfyui-workflow
description: ComfyUI workflow JSON 組裝注意事項 - API 格式、ControlNet 新舊版節點差異、模型檔名、prompt 替換邏輯。Use when building or modifying ComfyUI workflow JSON for the auto-draw project.
---

# ComfyUI Workflow 組裝注意事項

AI 依使用者描述組 workflow 時，須注意下列要點。專案 `backend/app/core/workflow.py` 的 `apply_params` 會根據 workflow 結構替換參數。

## 1. API Workflow 格式

- **僅指定 inputs**：JSON 中只寫 `class_type` 與 `inputs`，節點 output 依型別隱含存在，無需也無法寫入。
- **連線格式**：`["node_id", output_index]`，如 `["3", 0]` 表示引用節點 3 的 output 0。
- **節點 ID**：可非連續（如 3, 4, 5, 11, 13）；連續 ID 有時可避免驗證問題。

## 2. ControlNet 節點版本差異（重要）

ComfyUI 有 **新版** 與 **舊版** ControlNetApply，輸入/輸出結構不同，依錯誤訊息判斷：

| 版本 | ControlNetApply inputs | KSampler 連線 |
|------|------------------------|---------------|
| **新版** | `positive`, `negative`, `control_net`, `image`, `strength` | positive/negative 皆來自 ControlNetApply output |
| **舊版** | `conditioning`, `control_net`, `image`, `strength` | positive 來自 ControlNetApply，**negative 直接接 CLIPTextEncode** |

**錯誤「Required input is missing: conditioning」** → 表示環境為舊版，須改用 `conditioning` 且 KSampler.negative 直接連 CLIPTextEncode。

```json
// 舊版 ControlNetApply
"8": {
  "class_type": "ControlNetApply",
  "inputs": {
    "conditioning": ["3", 0],
    "control_net": ["7", 0],
    "image": ["6", 0],
    "strength": 1.0
  }
},
"9": {
  "class_type": "KSampler",
  "inputs": {
    "positive": ["8", 0],
    "negative": ["4", 0]
  }
}
```

## 3. ControlNet 模型檔名

`control_net_name` **必須與 ComfyUI 已安裝的檔名一致**。可透過 `GET /object_info` 查詢可用清單。

| 錯誤 | 解法 |
|------|------|
| `'controlnet-openpose-sdxl-1.0.safetensors' not in [...]` | 改用錯誤訊息中列出的檔名，例如 `OpenPoseXL2.safetensors` |

常見 SDXL OpenPose：`OpenPoseXL2.safetensors`、`controlnet-openpose-sdxl-1.0.safetensors`。

## 4. apply_params 與 prompt/negative_prompt 替換

- **直接接 KSampler**：若 positive/negative 直接來自 CLIPTextEncode，會替換該 CLIPTextEncode 的 `text`。
- **經 ControlNetApply**：會從 KSampler 追蹤至 ControlNetApply，再從其 `positive`/`conditioning` 上游找 CLIPTextEncode 做替換。
- **negative_prompt=None**：不替換，保留 workflow 內建負向提示詞。

## 5. LoadImage 與輸入圖片路徑

- LoadImage 從 ComfyUI 的 `input` 資料夾讀取。
- `image` 為檔名或 `subfolder/filename`；若圖片在其他目錄，需先複製至 input 或使用相對 path。
- **使用 gallery 圖片作為姿態參考**：傳入 `image_pose`（相對於 `gallery_dir`，如 `2026-03-08/ComfyUI_xxx.png`）。後端會從 `Path(gallery_dir).resolve() / image_pose` 讀取、上傳至 ComfyUI，取得檔名後替換 LoadImage；若 path traversal 會 blocked 並 log warning。

## 6. DWPreprocessor 與 bbox_detector

使用 ControlNet 時，**DWPreprocessor 的 bbox_detector 預設為 `yolo_nas_s_fp16.onnx`**。

- 專案 workflow 模板已內建此預設
- `apply_params` 支援 `bbox_detector` 參數（預設 `yolo_nas_s_fp16.onnx`）
- ComfyUI ControlNet Aux 常見選項：`yolo_nas_s_fp16.onnx`、`yolo_nas_m_fp16.onnx`、`yolo_nas_l_fp16.onnx`、`yolox_l.onnx`

```json
"6": {
  "class_type": "DWPreprocessor",
  "inputs": {
    "bbox_detector": "yolo_nas_s_fp16.onnx",
    "image": ["5", 0],
    "resolution": 1024
  }
}
```

## 7. 前置需求

- **DWPreprocessor**：需安裝 [ComfyUI ControlNet Aux](https://github.com/Fannovel16/comfyui_controlnet_aux)。
- **SDXL**：checkpoint 與 ControlNet 須皆為 SDXL 相容（如 incursiosMemeDiffusion_v16PDXL + OpenPoseXL2）。

## 8. KSampler 採樣器

- **預設採樣器**：`dpmpp_2m`（專案 workflow 模板與 apply_params 未指定時使用）
- 常見選項：`euler`、`dpmpp_2m`、`ddim`、`euler_ancestral`、`heun` 等

## 9. 常見節點快速參考

| 節點 | 重要 inputs |
|------|-------------|
| CheckpointLoaderSimple | ckpt_name |
| CLIPTextEncode | clip, text |
| EmptyLatentImage | width, height, batch_size |
| LoadImage | image |
| DWPreprocessor | bbox_detector（預設 yolo_nas_s_fp16.onnx）, image, resolution |
| ControlNetLoader | control_net_name |
| ControlNetApply（新版） | positive, negative, control_net, image, strength |
| ControlNetApply（舊版） | conditioning, control_net, image, strength |
| KSampler | model, positive, negative, latent_image, seed, steps, cfg, **sampler_name**（預設 `dpmpp_2m`）, scheduler |
| VAEDecode | samples, vae |
| SaveImage | images, filename_prefix |

## See Also

- `comfyui-api-client` - REST/WebSocket API、提交與取圖流程
- `mcp-workflow-generation` rule - MCP 依描述生圖流程
