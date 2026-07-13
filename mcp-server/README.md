# AI Drawing MCP Server

AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

## Tools

> 共 51 個 server-side registered tool。`dict` 代表 MCP tool 直接回 JSON-compatible dict；`json_string` 是相容期 JSON 字串（內容仍含 `ok`/`tool` 或可解析 JSON）；`plain_text` 是 legacy human-readable helper。
>
> 如果 Hermes/Cursor 目前 session 看不到這裡列出的 tool（例如 `generate_video_custom_workflow`），先重啟 MCP client 或重新載入 tool catalog；server-side `mcp.list_tools()` 會由測試驗證與下列 catalog 一致。
>
> **Civitai recipe 匯入 bytes contract**：`civitai_recipe_import(embedded_image=...)` 對 MCP caller 保持 bytes 介面，但在 HTTP JSON 邊界一律轉為標準 base64 的 `embedded_image_base64`；backend 只接受嚴格 base64，解碼失敗會拒絕 request。這避免把 Python `bytes` 放進 `httpx json=`，而 metadata 合併仍完全委派 CIV-B。
> `civitai_recipe_import` 可選 `remember_alias` 會原樣隨同一次 import POST 交給 backend；以 `civitai_source_alias_resolve(alias=...)` 精確取得既有、不可變且可稽核的來源綁定。MCP 不正規化、建議或持久化 alias。
>
> **建議的自組為主流程（agent）**：`list_template_capabilities`／`match_workflow_template` 先判斷有沒有現成模板能解決需求 → **命中**就用其 id 走 `generate_image(template=…)` 或取出影片模板後走 `generate_video_custom_workflow`；**未命中**就 `list_node_categories`／`search_nodes`／`get_node_schema` 認識本機節點後自組 workflow，經 `generate_image_custom_workflow` 或 `generate_video_custom_workflow` 送出（失敗時 `get_generation_status` 回結構化 `node_errors` 可自我修正）；成功且是可重用的新形狀，再 `save_workflow_template(job_id, …)` 晉升入庫，下次即可被 match 命中。

<!-- MCP-CATALOG:START -->
| Tool | Response | Backend/API |
|------|----------|-------------|
| `mcp_ping` | `plain_text` | GET /health |
| `list_character_styles` | `plain_text` | local helper |
| `resolve_character_style_prompt` | `plain_text` | local helper |
| `free_comfyui_memory` | `json_string` | POST <ComfyUI>/free |
| `search_nodes` | `json_string` | GET /api/comfyui/nodes |
| `list_node_categories` | `json_string` | GET /api/comfyui/node-categories |
| `get_node_schema` | `json_string` | GET /api/comfyui/nodes/{node_type} |
| `gallery_list` | `plain_text` | GET /api/gallery/ |
| `get_gallery_image` | `json_string` | GET /api/gallery/{image_id} |
| `get_gallery_artifact` | `json_string` | GET /api/gallery/artifacts/{artifact_id} |
| `gallery_rerun` | `plain_text` | POST /api/gallery/{image_id}/rerun |
| `civitai_resource_inspect` | `dict` | POST /api/civitai-recipes/resource-inspect |
| `civitai_resource_select` | `dict` | POST /api/civitai-recipes/resource-select |
| `civitai_resource_install` | `dict` | POST /api/civitai-recipes/resource-install |
| `civitai_recipe_import` | `dict` | POST /api/civitai-recipes/import |
| `civitai_source_alias_resolve` | `dict` | POST /api/civitai-recipes/source-aliases/resolve |
| `civitai_recipe_inspect` | `dict` | POST /api/civitai-recipes/inspect |
| `civitai_recipe_resolve` | `dict` | POST /api/civitai-recipes/resolve |
| `civitai_recipe_compatibility` | `dict` | POST /api/civitai-recipes/compatibility |
| `civitai_recipe_build` | `dict` | POST /api/civitai-recipes/build |
| `civitai_recipe_run` | `dict` | POST /api/civitai-recipes/run |
| `civitai_recipe_variant_generate` | `dict` | POST /api/civitai-recipes/variants/generate-one |
| `civitai_recipe_variation_set_generate` | `dict` | POST /api/civitai-recipes/variation-sets |
| `civitai_recipe_variation_set_status` | `dict` | GET /api/civitai-recipes/variation-sets/{variation_set_id} |
| `civitai_recipe_variation_set_cancel` | `dict` | POST /api/civitai-recipes/variation-sets/{variation_set_id}/cancel |
| `civitai_recipe_variation_set_export` | `dict` | GET /api/civitai-recipes/variation-sets/{variation_set_id}/export |
| `civitai_recipe_export` | `dict` | GET /api/gallery/{image_id}/export?format=recipe |
| `generate_image` | `json_string` | POST /api/generate/ |
| `list_workflow_templates` | `plain_text` | GET /api/generate/workflow-templates |
| `get_workflow_template` | `json_string` | GET /api/generate/workflow-templates/{name} |
| `generate_image_custom_workflow` | `json_string` | POST /api/generate/custom |
| `generate_video_custom_workflow` | `json_string` | POST /api/generate/video/custom |
| `generate_video_wan_keyframes` | `json_string` | POST /api/generate/video/wan-keyframes |
| `generate_queue_status` | `plain_text` | GET /api/generate/queue |
| `get_generation_status` | `json_string` | GET /api/generate/job/{job_id} |
| `cancel_job` | `plain_text` | DELETE /api/generate/queue/{job_id} |
| `list_available_resources` | `json_string` | GET /api/generate/available-resources |
| `caption_image` | `dict` | POST /api/lora-docs/caption-llm/{image_path} |
| `lora_dataset_list` | `dict` | GET /api/lora-train/datasets |
| `lora_dataset_inspect` | `dict` | GET /api/lora-train/datasets/{folder} |
| `lora_dataset_metadata_get` | `dict` | GET /api/lora-train/datasets/{folder}/metadata |
| `lora_dataset_metadata_update` | `dict` | PUT /api/lora-train/datasets/{folder}/metadata |
| `lora_dataset_metadata_validate` | `dict` | POST /api/lora-train/datasets/{folder}/metadata/validate |
| `lora_dataset_agent_inspect` | `dict` | GET /api/lora-train/datasets/{folder}/agent-inspect |
| `lora_dataset_prepare` | `dict` | POST /api/lora-train/datasets/prepare |
| `lora_dataset_validate` | `dict` | POST /api/lora-train/datasets/validate |
| `lora_dataset_caption_assess` | `dict` | POST /api/lora-train/datasets/caption-assessment |
| `lora_dataset_curate` | `dict` | POST /api/lora-train/datasets/curate |
| `lora_training_decision_preflight` | `dict` | POST /api/lora-train/datasets/training-decision-preflight |
| `lora_train_start` | `dict` | POST /api/lora-train/start |
| `lora_train_status` | `dict` | GET /api/lora-train/status |
| `lora_train_job_status` | `dict` | GET /api/lora-train/jobs/{job_id} |
| `lora_train_logs` | `dict` | GET /api/lora-train/jobs/{job_id}/logs |
| `lora_train_cancel` | `dict` | POST /api/lora-train/jobs/{job_id}/cancel |
| `lora_train_smoke_test` | `dict` | POST /api/lora-train/jobs/{job_id}/smoke-test |
| `create_style_preset` | `json_string` | POST /api/style-presets/ |
| `reindex_style_presets` | `json_string` | POST /api/style-presets/reindex |
| `list_style_presets` | `json_string` | GET /api/style-presets/ |
| `get_style_preset` | `json_string` | GET /api/style-presets/{preset_id} |
| `validate_style_presets` | `json_string` | GET /api/style-presets/validate |
| `compose_style_preset` | `json_string` | POST /api/style-presets/{preset_id}/compose |
| `list_template_capabilities` | `json_string` | GET /api/workflow-catalog/ |
| `match_workflow_template` | `json_string` | GET /api/workflow-catalog/match |
| `save_workflow_template` | `json_string` | POST /api/workflow-catalog/backfill |
| `consolidate_workflow_templates` | `json_string` | POST /api/workflow-catalog/consolidate |
| `validate_template_capabilities` | `json_string` | GET /api/workflow-catalog/validate |
<!-- MCP-CATALOG:END -->

<!-- MCP-OMISSIONS:START -->
| Omitted name | Replacement | Reason |
|--------------|-------------|--------|
| `list_resources` | `list_available_resources` | Removed because the name collided with the MCP resources/list primitive. |
| `get_available_resources` | `list_available_resources` | Removed legacy human-readable duplicate. |
| `get_job_status` | `get_generation_status` | Removed legacy human-readable duplicate. |
| `gallery_detail` | `get_gallery_image` | Removed legacy human-readable duplicate. |
| `generate_image_from_description` | `generate_image` | Disabled regex/NLP fallback; LLM agents should submit structured generation fields directly. |
| `suggest_workflow_from_description` | `list_template_capabilities` | Disabled regex/NLP fallback; agents should inspect catalog/schema tools directly. |
<!-- MCP-OMISSIONS:END -->

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
| `lora_dataset_metadata_get` | 讀取 dataset-local `.lora-dataset.json` normalized metadata profile 與 `profile_hash` |
| `lora_dataset_metadata_validate` | 驗證 proposed metadata profile；不寫入檔案 |
| `lora_dataset_metadata_update` | 以 expected `profile_hash` 更新 metadata profile；stale hash 回 structured conflict |
| `lora_dataset_agent_inspect` | 組合 dataset/profile/caption suitability/validation signals；不啟動訓練 |
| `lora_dataset_caption_assess` | 評估 dataset caption 覆蓋率、trigger token 覆蓋、常見/稀有 tags 與 coherence verdict；不會啟動訓練 |
| `lora_dataset_curate` | deterministic caption curation：dry-run 預覽 trigger/tag cleanup/outlier/manual blocks；apply 需 expected hashes 並建立 backup；rollback 依 backup id 還原 |
| `lora_training_decision_preflight` | deterministic training decision：回 `train` / `needs_review` / `do_not_train`、reasons、hashes、next actions 與 advisory suggested params；不啟動訓練 |
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

## LoRA training MCP workflow

LoRA training tools now return structured JSON dictionaries with `ok`, `tool`, payload fields, and a structured `error` object on failure.

Recommended agent flow:

1. `lora_dataset_list()` — list folders under the backend `lora_train_dir`, including image/caption counts and dataset hash.
2. `lora_dataset_inspect(folder, trigger_token?)` — inspect image/caption pairs and trigger-token candidates.
3. `lora_dataset_prepare(folder, trigger_token, dry_run=True)` — preview caption rewrites without writing files.
4. `lora_dataset_prepare(folder, trigger_token, dry_run=False, expected_dataset_hash=...)` — apply trigger-token normalization with backup.
5. `lora_dataset_validate(folder, trigger_token, expected_dataset_hash=...)` — preflight dataset readiness before training.
6. `lora_train_start(folder, trigger_token, expected_dataset_hash, checkpoint?, epochs?, model_family?, network_module?, anima_qwen3?, anima_vae?, ...)` — create a durable training job only after runtime preflight passes.
7. `lora_train_job_status(job_id)` / `lora_train_logs(job_id)` — poll progress, stage, epoch fields, output, errors, and bounded logs.
8. `lora_train_cancel(job_id)` — cancel queued/running jobs; terminal jobs are idempotent.
9. `lora_train_smoke_test(job_id, prompt?)` — after successful registration, submit a generation smoke test with the registered LoRA.

Training runtime preflight checks `sd_scripts_path` before enqueueing. If Kohya `sd-scripts` or the expected train script is missing, `lora_train_start` returns `ok=false` immediately instead of creating a job that instantly fails. For `model_family="anima"`, pass `anima_qwen3` or configure `LORA_ANIMA_QWEN3`; missing qwen3 returns structured `anima_qwen3_missing` before job creation. Anima defaults `network_module` to `networks.lora_anima`; SD1.x/SDXL default to `networks.lora`, and callers may override the field explicitly.

## 依賴

- Python ≥ 3.10
- mcp
- httpx
