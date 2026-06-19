# AI Drawing MCP Server

AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

## Tools

> 共 24 個 tool，全部回傳 agent-friendly 結構化輸出（早期的純文字重複版 `get_job_status` / `get_available_resources` / `gallery_detail` 已移除）。

### 連線檢查

| Tool | 說明 |
|------|------|
| `mcp_ping` | 檢查 MCP 與 Backend 連線（打 `/health`） |

### 生圖

| Tool | 說明 |
|------|------|
| `generate_image` | 主要生圖入口；支援 character、style 語意（如「初音」「動漫」）與完整參數（checkpoint、lora、seed、steps、cfg、寬高、sampler、scheduler、lora_strength、denoise、batch_size 1–8、diffusion_model / text_encoder / vae）；可直接餵入 `compose_style_preset` 產出的 `generation` payload |
| `generate_image_from_description` | 依描述生圖（預存模板）；複雜需求由 AI 組 workflow 後呼叫 generate_image_custom_workflow |
| `suggest_workflow_from_description` | 預覽描述解析結果（不觸發生圖） |
| `generate_image_custom_workflow` | 使用自訂 workflow 生圖；支援 `image_pose`（ControlNet 姿勢參考圖） |
| `list_workflow_templates` | 列出可用 workflow 模板（default、default_lora 等） |
| `get_workflow_template` | 取得指定模板的 workflow JSON |
| `generate_queue_status` | 取得生圖佇列狀態（執行中／等候中） |
| `get_generation_status` | 查詢 job 狀態；完成時帶 image_id / image_path |
| `cancel_job` | 取消尚未開始（pending）的 job；執行中無法取消 |
| `list_available_resources` | 列出 checkpoints / LoRA / diffusion_models（UNET，如 Anima）/ text_encoders / vaes / workflows，含 default_checkpoint |

### LoRA 訓練

| Tool | 說明 |
|------|------|
| `caption_image` | 對訓練資料夾的圖呼叫 LLM 自動產生 caption，寫入同名 .txt |
| `lora_train_start` | 手動觸發 LoRA 訓練（folder 必填，可帶 epochs、resolution、network_dim 等） |
| `lora_train_status` | 取得 LoRA 訓練進度與佇列狀態 |

### 圖庫

| Tool | 說明 |
|------|------|
| `gallery_list` | 圖庫列表（可依 checkpoint / lora / 日期篩選） |
| `get_gallery_image` | 單張圖片，含 image_url、local_path 與完整 metadata |
| `gallery_rerun` | 一鍵重現該圖參數 |

### 角色／風格語意

| Tool | 說明 |
|------|------|
| `list_character_styles` | 列出可用的角色／風格別名 |
| `resolve_character_style_prompt` | 預覽角色+風格解析後的 prompt（不生圖） |

### 風格預設目錄（Style Preset Catalog）

創作者／風格「食譜」：記錄 checkpoint / LoRA / diffusion 元件、trigger words、base/negative prompt、profiles。
**兩種使用模式，共用同一條生圖路徑：**

- **Preset 模式**：使用者指名某個 preset → `list_style_presets` / `get_style_preset` →
  `compose_style_preset(preset_id, content_prompt[, profile])` 取得 `generation` payload →
  把該 payload 的欄位餵給 `generate_image`。
- **手動模式**：使用者直接指定 checkpoint / LoRA → 用 `list_available_resources` 驗證 → 直接呼叫 `generate_image`。

`compose_style_preset` 採「compose first, generate second」：先回傳完整 `generation`（含最終
prompt / 參數）供檢視，不會送出生圖；確認後再交給 `generate_image`。

| Tool | 說明 |
|------|------|
| `list_style_presets` | 列出所有 preset（id、name、profiles、資源摘要） |
| `get_style_preset` | 取得單一 preset 完整食譜 |
| `validate_style_presets` | 驗證每個 preset 參照的資源是否已安裝；invalid preset 以資料形式回傳，不隱藏 |
| `compose_style_preset` | 將 preset + 使用者 `content_prompt`（＋ profile / overrides）組成可餵給 `generate_image` 的 `generation` payload |

### ComfyUI 直連

| Tool | 說明 |
|------|------|
| `free_comfyui_memory` | 釋放 ComfyUI 顯存（直連 ComfyUI `/free`，生圖完成後應呼叫） |

## 安裝

```bash
cd mcp-server
uv sync
# 或 pip install -e .
```

## 執行

```bash
# stdio（供 Cursor 等 MCP 用戶端使用）
# 目前請優先使用
uv run ai-drawing-mcp
# 或 python -m mcp_server.server
```

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `MCP_BACKEND_API_URL` | ai-drawing 後端 Base URL | `http://127.0.0.1:8001` |
| `MCP_COMFYUI_API_URL` | ComfyUI API Base URL（釋放記憶體等） | `http://127.0.0.1:8188` |
| `MCP_GALLERY_DIR` | Backend gallery 實體檔案根目錄 | `/Users/tf00185088/Desktop/ai-drawing/outputs/gallery` |

> 本機 OpenClaw / ai-drawing 驗證路徑使用 backend `8001`。不要把 `8000` 當成 ai-drawing backend；本機 `8000` 可能是其他 LLM / MLX 服務。

## 依賴

- Python ≥ 3.10
- mcp
- httpx
