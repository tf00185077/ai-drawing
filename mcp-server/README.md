# AI Drawing MCP Server

AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

## Tools

> 共 32 個 tool，全部回傳 agent-friendly 結構化輸出（早期的純文字重複版 `get_job_status` / `get_available_resources` / `gallery_detail` 已移除；NLP 解析版 `generate_image_from_description` / `suggest_workflow_from_description` 已停用——agent 自行解析後直接呼叫 `generate_image`）。
>
> **建議的自組為主流程（agent）**：`list_template_capabilities`／`match_workflow_template` 先判斷有沒有現成模板能解決需求 → **命中**就用其 id 走 `generate_image(template=…)` 或取出影片模板後走 `generate_video_custom_workflow`；**未命中**就 `list_node_categories`／`search_nodes`／`get_node_schema` 認識本機節點後自組 workflow，經 `generate_image_custom_workflow` 或 `generate_video_custom_workflow` 送出（失敗時 `get_generation_status` 回結構化 `node_errors` 可自我修正）；成功且是可重用的新形狀，再 `save_workflow_template(job_id, …)` 晉升入庫，下次即可被 match 命中。

### 連線檢查

| Tool | 說明 |
|------|------|
| `mcp_ping` | 檢查 MCP 與 Backend 連線（打 `/health`） |

### 生圖

| Tool | 說明 |
|------|------|
| `generate_image` | 主要生圖入口；支援 character、style 語意（如「初音」「動漫」）與完整參數（checkpoint、lora、seed、steps、cfg、寬高、sampler、scheduler、lora_strength、denoise、batch_size 1–8、diffusion_model / text_encoder / vae）；可直接餵入 `compose_style_preset` 產出的 `generation` payload，或用 `match_workflow_template` 命中的模板 id |
| `generate_image_custom_workflow` | 使用自訂 workflow 生圖（自組為主路徑）；支援 `image`（img2img 主體）/`image_pose`（ControlNet 姿勢）/`mask`（inpaint）；成功後可 `save_workflow_template` 晉升 |
| `generate_video_custom_workflow` | 使用呼叫端提供的完整 ComfyUI video workflow JSON 送出影片 job；可選 `image` / `first_frame` / `last_frame` / `video_ref`，完成後用 `artifacts[]` + `get_gallery_artifact` 取影片 |
| `list_workflow_templates` | 列出可用 workflow 模板名稱（default、default_lora 等） |
| `get_workflow_template` | 取得指定模板的 workflow JSON（可當自組起手鷹架） |
| `generate_queue_status` | 取得生圖佇列狀態（執行中／等候中） |
| `get_generation_status` | 查詢 job 狀態；完成帶 `artifacts[]`，圖片 job 仍帶 image_id / image_path；**失敗（含執行期）回 `node_errors` 或 `recording_error`** 供自我修正 |
| `cancel_job` | 取消尚未開始（pending）的 job；執行中無法取消 |
| `list_available_resources` | 列出 checkpoints / LoRA / diffusion_models（UNET，如 Anima）/ text_encoders / vaes / workflows，含 default_checkpoint；影片資源類別目前只有本機可發現時才填入，否則回空陣列 |

### 影片 MCP MVP

影片 MVP 的責任邊界是「提交已知可用的本機 ComfyUI workflow、記錄輸出 artifact、讓 MCP 取回檔案」。它不會從自然語言合成完整影片 graph，也不會下載或安裝 ComfyUI custom nodes。

建議 derivation loop：

1. 從 CTY 提供的 known-good local ComfyUI video workflow 開始。
2. 用 `list_node_categories` / `search_nodes` / `get_node_schema` 檢查本機節點與可接受 input。
3. 只修改 schema-grounded 的 workflow JSON 欄位。
4. 用 `generate_video_custom_workflow(workflow=..., first_frame=..., last_frame=..., video_ref=...)` 送出。
5. 用 `get_generation_status(job_id)` 輪詢；若失敗，讀 `node_errors` / `recording_error` 修正後重送。
6. 完成時讀 `artifacts[]`，用 `get_gallery_artifact(artifact_id)` 取得 `local_path` / mime type / file size。
7. 只有已完成且成功 recorded 的 video workflow，才可用 `save_workflow_template(job_id, modality="txt2video" 或 "img2video", ...)` 回填。

Out of scope for this MVP：自動 node download/install、第三方 partner/API video nodes、frontend video browsing UI、backend prose-to-video-graph synthesis、未驗證 workflow 的 video template manifest。

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
| `get_gallery_artifact` | 單一 generated artifact，含影片 artifact 的 mime type、gallery_path、local_path、file_size、job_id 與 workflow metadata |
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

### ComfyUI 節點 Schema（自組 workflow 的 grounding）

讓 agent 認識「本機 ComfyUI 實際有哪些節點」才能組出合法 workflow。皆有 context 防護：
`search_nodes` 強制至少給 `query` 或 `category`、每頁上限、可 `offset` 翻頁；`get_object_info` 原始大檔不會回給 agent。

| Tool | 說明 |
|------|------|
| `list_node_categories` | 列出所有節點類別與數量（無參數探索入口，先瀏覽再縮小） |
| `search_nodes` | 依名稱／類別搜尋節點（`{name, category}`，須給 query 或 category，分頁） |
| `get_node_schema` | 取單一節點的 input/output 規格（COMBO 不展開可選值，可選值走 `list_available_resources`） |

### Workflow 模板能力目錄（自組／reuse／回填）

模板帶受控詞彙的能力標籤（modality 必填：`txt2img` / `img2img` / `inpaint` / `txt2video` / `img2video`，model_family 必填，conditioning、io），agent 不必展開
整份 workflow 即可二元判斷可用性；成功的自組 workflow 可回填成可重用模板，模板庫自我擴充。

| Tool | 說明 |
|------|------|
| `list_template_capabilities` | 列出模板能力標籤與 description（輕量，不含 workflow JSON） |
| `match_workflow_template` | 二元 reuse 匹配（模板 ⊇ 需求）；命中→`generate_image(template=…)`，miss→自組；deprecated 不列入 |
| `save_workflow_template` | 把已成功 job 的 workflow 晉升為模板（DB 成功閘門、剝 prompt/seed 存形狀、key 去重、家族歸檔、版本化） |
| `validate_template_capabilities` | 逐模板驗證能力 manifest（詞彙／id／檔案；invalid 以資料回報） |
| `consolidate_workflow_templates` | 清理已 deprecated 的模板（手動／週期家務整理） |

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
