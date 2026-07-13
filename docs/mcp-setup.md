# MCP 整合文件與 Cursor 配置

> AI 自動化出圖系統的 MCP（Model Context Protocol）介面，讓 Cursor / Claude 等 AI 透過自然語言觸發生圖、LoRA 訓練、圖庫查詢。

---

## 一、前置需求

| 項目 | 說明 |
|------|------|
| **ai-drawing Backend** | 必須先啟動，MCP Server 會呼叫其 API |
| **Python ≥ 3.10** | MCP Server 執行環境 |
| **uv** | 建議使用（或 `pip install -e mcp-server`） |
| **Cursor IDE** | v0.40 以上 |

**啟動順序**：先啟動 Backend → 再讓 Cursor 連線 MCP Server

---

## 二、安裝 MCP Server

```bash
cd mcp-server
uv sync
```

或使用 pip：

```bash
cd mcp-server
pip install -e .
```

---

## 三、Cursor 配置

### 方式 A：專案級配置（建議，可 commit 給團隊）

在專案根目錄建立 `.cursor/mcp.json`。

**Windows**（將 `D:\AI\ai-drawing` 改為你的專案路徑）：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "D:\\AI\\ai-drawing\\scripts\\run-mcp-server.bat",
      "args": []
    }
  }
}
```

**macOS / Linux**：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "/path/to/ai-drawing/scripts/run-mcp-server.sh",
      "args": []
    }
  }
}
```

> 路徑需為**絕對路徑**，或確保 Cursor 的 working directory 為專案根目錄時使用 `scripts/run-mcp-server.bat`（Windows）／`scripts/run-mcp-server.sh`（Unix）。

### 方式 B：使用 uv 直接執行（需指定工作目錄）

若你的 Cursor 支援 `cwd` 或類似設定：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "uv",
      "args": ["run", "ai-drawing-mcp"],
      "cwd": "D:\\AI\\ai-drawing\\mcp-server"
    }
  }
}
```

> **注意**：部分版本可能不支援 `cwd`，建議優先使用方式 A 的啟動腳本。

### 方式 C：全域配置（個人用）

編輯 `~/.cursor/mcp.json`（Windows：`%USERPROFILE%\.cursor\mcp.json`），加入同上結構。

---

## 四、環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `MCP_BACKEND_API_URL` | ai-drawing 後端 Base URL | `http://127.0.0.1:8001` |
| `MCP_COMFYUI_API_URL` | ComfyUI API Base URL（釋放記憶體等） | `http://127.0.0.1:8188` |
| `MCP_GALLERY_DIR` | Backend gallery 實體檔案根目錄 | `/Users/tf00185088/Desktop/ai-drawing/outputs/gallery` |

> 本機 OpenClaw / ai-drawing 驗證路徑使用 backend `8001`。不要把 `8000` 當成 ai-drawing backend；本機 `8000` 可能是其他 LLM / MLX 服務。

若 Backend、ComfyUI 或 Gallery 不在上述位置，在 `mcp.json` 的 `env` 中設定：

```json
{
  "mcpServers": {
    "ai-drawing": {
      "command": "D:\\AI\\ai-drawing\\scripts\\run-mcp-server.bat",
      "args": [],
      "env": {
        "MCP_BACKEND_API_URL": "http://127.0.0.1:8001",
        "MCP_COMFYUI_API_URL": "http://127.0.0.1:8188",
        "MCP_GALLERY_DIR": "/Users/tf00185088/Desktop/ai-drawing/outputs/gallery"
      }
    }
  }
}
```

---

## 五、驗證

### 1. 重啟 Cursor

修改 `mcp.json` 後需**完整重啟** Cursor。

### 2. 確認 MCP Server 已載入

- 開啟 **Settings**（Ctrl+Shift+J / Cmd+Shift+J）→ **Tools & MCP**
- 檢查 `ai-drawing` 是否出現且為開啟狀態

### 3. 在 Composer（Agent 模式）中測試

對 AI 說：

> 請呼叫 mcp_ping 檢查 ai-drawing 連線

預期回傳：`ok: Backend 連線正常`（若 Backend 已啟動）

### 4. 若失敗

- 查看 **Output** 面板（Ctrl+Shift+U）→ 選擇 **MCP Logs**
- 確認 Backend 是否已啟動：`uvicorn app.main:app --reload`（在 `backend/` 目錄）
- 確認 `MCP_BACKEND_API_URL` 與 Backend 位址一致

---

## 六、可用 Tools

> MCP tools 只包裝 backend HTTP API，不直接操作 ComfyUI workflow / DB / gallery 檔案。共 51 個 server-side registered tool。
>
> `dict` 代表 MCP tool 直接回 JSON-compatible dict；`json_string` 是相容期 JSON 字串；`plain_text` 是 legacy human-readable helper。若 Cursor/Hermes 看不到下列工具，請完整重啟 MCP client 或重新載入 tool catalog。
>
> `civitai_recipe_import` 的 optional `embedded_image` 在 MCP 端會以標準 base64 JSON 欄位 `embedded_image_base64` 傳給 backend；backend 嚴格驗證／解碼，不能傳 raw Python bytes 到 HTTP JSON body。
> `civitai_recipe_import` 的 optional `remember_alias` 會原樣併入同一次 import POST；`civitai_source_alias_resolve(alias=...)` 只做 exact resolve，原樣回傳 backend 的 immutable audited binding，不在 MCP 正規化、搜尋或寫入 alias。

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

### 影片 MCP MVP 邊界

影片生成目前是 MCP-first 的 artifact lifecycle：agent 從 CTY 提供的 known-good 本機 ComfyUI video workflow 開始，用 `search_nodes` / `get_node_schema` 檢查本機節點，修改 schema-valid 欄位後呼叫 `generate_video_custom_workflow`，再用 `get_generation_status` 的 `artifacts[]` 和 `get_gallery_artifact` 取回影片檔。

此 MVP 不包含：自動安裝 / 下載 ComfyUI nodes、第三方 partner/API video nodes、frontend video gallery UI、backend 從自然語言合成完整 video graph。未經本機成功驗證的 video workflow 不應寫成模板 manifest。

---

## 七、自然語言範例

在 Composer 中可直接說：

- **「產生初音、動漫風格的圖」** → 呼叫 `generate_image(character="初音", style="動漫")`
- **「用 default 模板產生穿和服的初音」** → 呼叫 `list_workflow_templates` → `get_workflow_template("default")` → `generate_image_custom_workflow(workflow=..., character="初音", prompt="1girl, kimono")`
- **「開始訓練 my_char 資料夾的 LoRA」** → 呼叫 `lora_train_start(folder="my_char")`
- **「用 Anima 訓練 my_char」** → 呼叫 `lora_train_start(folder="my_char", model_family="anima", anima_qwen3="...", anima_vae="...")`，或先在 backend `.env` 設定 `LORA_ANIMA_QWEN3` / `LORA_ANIMA_VAE`；未指定 `network_module` 時會使用 `networks.lora_anima`
- **「列出最近 5 張圖」** → 呼叫 `gallery_list(limit=5)`
- **「用第 3 張的參數再產一張」** → 呼叫 `gallery_rerun(image_id=3)`

---

## 八、範例配置檔

專案內含 `.cursor/mcp.json.example`，複製後重新命名為 `mcp.json` 並修改路徑：

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
# 編輯 .cursor/mcp.json，將 command 路徑改為你的專案絕對路徑
```

---

## 九、相關文件

- [setup-guide.md](./setup-guide.md) - Backend 完整運行設定
- [mcp-server/README.md](../mcp-server/README.md) - MCP Server 技術說明
- [api-contract.md](./api-contract.md) - REST API 契約
