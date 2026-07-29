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

> MCP tools 只包裝 backend HTTP API，不直接操作 ComfyUI workflow / DB / gallery 檔案。共 36 個 server-side registered tool。
>
> 舊版 source-alias catalog 為 53 個 server-side registered tool；新增 `civitai_source_alias_repoint` 後曾為 54 個 server-side registered tool，新增 `civitai_source_alias_resolve_explicit_version` 後為 55 個 server-side registered tool。保留 registry 在新增 `civitai_source_alias_backfill_gallery` 前已為 74 個 server-side registered tool；新增 `civitai_source_alias_backfill_gallery` 後以本頁的 75 為準。
>
> `dict` 代表 MCP tool 直接回 JSON-compatible dict；`json_string` 是相容期 JSON 字串；`plain_text` 是 legacy human-readable helper。若 Cursor/Hermes 看不到下列工具，請完整重啟 MCP client 或重新載入 tool catalog。
>
> `civitai_recipe_import` 的 optional `embedded_image` 在 MCP 端會以標準 base64 JSON 欄位 `embedded_image_base64` 傳給 backend；backend 嚴格驗證／解碼，不能傳 raw Python bytes 到 HTTP JSON body。
> `civitai_recipe_import` 的 optional `remember_alias` 會原樣併入同一次 import POST；`civitai_source_alias_resolve(alias=...)` 只做 exact resolve，原樣回傳 backend 的 immutable audited binding，不在 MCP 正規化、搜尋或寫入 alias。
> `civitai_source_alias_resolve_explicit_version(alias, registry_version)` 只以一次 POST 解析 caller 明確指定的目前或歷史 immutable audited binding；MCP 不正規化、選版、搜尋、重建 evidence，且不自動 build/queue。
> `civitai_source_alias_backfill_gallery(gallery_image_id, primary_alias=None)` 只以一次 POST 將 eligible Gallery 來源委派給 backend backfill；`pending_name` 只回候選，不自動 remember、resolve、build 或 queue。
> `civitai_source_alias_list(limit=50, offset=0)` 僅以一次 GET 列出 backend 稽核記錄；`civitai_source_alias_search(query, limit=50, offset=0)` 僅以一次 POST 回傳 backend 排名 candidates。兩者不在 MCP 端搜尋、計分、選定或 exact resolve。
> `civitai_source_alias_rename(current_primary_alias, new_primary_alias, expected_registry_version)` 只以一次 POST 轉送 caller intent；改名的稽核 lifecycle evidence 由 backend 建立並原樣回傳，MCP 不正規化、補寫或重建它。
> `civitai_source_alias_archive(current_primary_alias, expected_registry_version)` 只以一次 POST 轉送 caller intent；terminal audited archive evidence 由 backend 建立並原樣回傳，MCP 不正規化、補寫、重建、unarchive 或改綁它。
> `civitai_source_alias_repoint(current_primary_alias, expected_registry_version, replacement)` 只以一次 POST 轉送 typed immutable replacement；explicit repoint 的 audited transition evidence 由 backend 建立並原樣回傳。bare alias 後續使用仍必須提供 explicit registry version，MCP 不自動 resolve、build 或 queue。

<!-- MCP-CATALOG:START -->
| Tool | Response | Backend/API |
|------|----------|-------------|
| `prompt_library_search` | `dict` | GET /api/prompt-library/catalog, categories, search |
| `prompt_library_save` | `dict` | PUT /api/prompt-library/categories, entries, combinations |
| `prompt_library_compose` | `dict` | POST /api/prompt-library/compose |
| `prompt_library_archive` | `dict` | POST /api/prompt-library/archive |
| `prompt_library_restore` | `dict` | POST /api/prompt-library/restore |
| `mcp_ping` | `plain_text` | GET /health |
| `civitai_source_info` | `dict` | GET /api/civitai/source-info |
| `civitai_generate_like` | `dict` | POST /api/civitai/generate-like |
| `civitai_resource_acquire` | `dict` | POST /api/civitai/resources/acquire |
| `civitai_resource_status` | `dict` | GET /api/civitai/resources/status |
| `generate_image` | `json_string` | POST /api/generate/ |
| `generate_image_custom_workflow` | `json_string` | POST /api/generate/custom |
| `generate_video_wan_keyframes` | `json_string` | POST /api/generate/video/wan-keyframes |
| `generate_video_custom_workflow` | `json_string` | POST /api/generate/video/custom |
| `get_generation_status` | `json_string` | GET /api/generate/job/{job_id} |
| `cancel_job` | `json_string` | DELETE /api/generate/queue/{job_id} |
| `list_available_resources` | `json_string` | GET /api/generate/available-resources |
| `gallery_list` | `plain_text` | GET /api/gallery/ |
| `get_gallery_image` | `json_string` | GET /api/gallery/{image_id} |
| `get_gallery_artifact` | `json_string` | GET /api/gallery/artifacts/{artifact_id} |
| `gallery_rerun` | `plain_text` | POST /api/gallery/{image_id}/rerun |
| `free_comfyui_memory` | `json_string` | POST <ComfyUI>/free |
| `comfyui_node_provision` | `json_string` | GET/POST <ComfyUI>/customnode/getmappings, /manager/queue/install, /manager/queue/start, /manager/queue/status |
| `comfyui_restart` | `json_string` | POST <ComfyUI>/manager/reboot |
| `create_style_preset` | `json_string` | POST /api/style-presets/ |
| `list_style_presets` | `json_string` | GET /api/style-presets/ |
| `get_style_preset` | `json_string` | GET /api/style-presets/{preset_id} |
| `compose_style_preset` | `json_string` | POST /api/style-presets/{preset_id}/compose |
| `save_successful_workflow_as_style_preset` | `json_string` | POST /api/style-presets/{preset_id}/workflow/save |
| `test_saved_style_preset_workflow` | `json_string` | POST /api/style-presets/{preset_id}/workflow/test |
| `caption_image` | `dict` | POST /api/lora-docs/caption-llm/{image_path} |
| `lora_training_decision_preflight` | `dict` | POST /api/lora-train/datasets/training-decision-preflight |
| `lora_train_start` | `dict` | POST /api/lora-train/start |
| `lora_train_job_status` | `dict` | GET /api/lora-train/jobs/{job_id} |
| `lora_train_logs` | `dict` | GET /api/lora-train/jobs/{job_id}/logs |
| `lora_train_cancel` | `dict` | POST /api/lora-train/jobs/{job_id}/cancel |
| `lora_dataset_list` | `dict` | GET /api/lora-train/datasets |
| `lora_dataset_inspect` | `dict` | GET /api/lora-train/datasets/{folder}/agent-inspect |
| `lora_train_smoke_test` | `dict` | POST /api/lora-train/jobs/{job_id}/smoke-test |
<!-- MCP-CATALOG:END -->

`save_successful_workflow_as_style_preset` 僅能在使用者明確要求保存某次已成功結果後呼叫；
agent 只傳短 source locator 與精簡正／負關鍵字，workflow graph 由 backend 解析、清理與保存，
不經 MCP 傳輸。保存後用 `test_saved_style_preset_workflow` 原樣排入 server-owned graph，並以
`get_generation_status` 輪詢 job。

<!-- MCP-OMISSIONS:START -->
2026-07 工具大幅收斂後，現由 36 個意圖級工具組成。低階 Civitai recipe/資源/alias 工具、
style preset 維護、workflow catalog、ComfyUI node 查詢等已從 MCP 移除；
對應功能仍在 backend HTTP API（見 docs/api-contract.md），Civitai 流程改用
`civitai_source_info` / `civitai_generate_like` / `civitai_resource_acquire` / `civitai_resource_status`。
<!-- MCP-OMISSIONS:END -->

### LoRA recipe：寬進、嚴出

`lora_training_decision_preflight` 的 `recipe` 是選填；`lora_train_start` 的
`recipe` 是必填。兩者都接受 JSON object 或 JSON-object string，也接受只描述使用者意圖的
partial recipe。`decision="train"` 時，Backend 會回傳保留 caller omissions 的
canonical partial `requested_recipe`、完整 `effective_recipe`、`field_sources`、
`step_plan`、`component_identities`、`capability`、`execution_evidence` 與
`recipe_hash`；review/blocking 結果的 recipe 或 evidence 欄位可能是 `null`。

Start 的 public top-level 固定只有四個必要欄位：

```json
{
  "folder": "my_char",
  "expected_dataset_hash": "<preflight dataset_hash>",
  "expected_profile_hash": "<preflight profile_hash>",
  "recipe": {
    "schema_version": "lora-training-recipe/v1",
    "expected_recipe_hash": "<preflight recipe_hash>",
    "optimization": {
      "seed": {
        "mode": "random",
        "value": 123456789,
        "source": "preflight_policy"
      }
    }
  }
}
```

`recipe` 的 canonical container 是 `schema_version`、`expected_recipe_hash` 與
`model` / `scope` / `dataset` / `optimization` / `caching` / `execution`。
呼叫者不必補齊空白 section；上例只是顯示完整容器。`expected_recipe_hash` 是 preflight
產生的 optimistic-concurrency 證據，不應由 agent 自行計算或改寫。

輸入端允許常見別名與無損 coercion：

| 類別 | 可接受形式（節錄） | Canonical 位置 |
|------|--------------------|----------------|
| 版本 | `schemaVersion`、`version=1/"1"/"v1"` | `schema_version` |
| Model | `family`、`model_family`、`modelFamily`、`networkDim`、`animaQwen3`、`animaVae` | `model.*` |
| Scope | `trainTextEncoder`、`trainable_scope=denoiser_only/denoiser_and_text_encoder` | `scope.train_text_encoder` |
| Dataset | `triggerToken`、`class_tokens`、`instance_token`、`batch`、`batchSize`、bucket camelCase 欄位 | `dataset.*` |
| Optimization | `learningRate`、`unet_lr`、`dit_lr`、`text_encoder_lr`、`gradientAccumulation`、`optimizer`、`scheduler`、warmup aliases、`precision` | `optimization.*` |
| Caching | `cacheLatents`、`cacheTextEncoderOutputs`、`cacheToDisk` | `caching.*` |
| Execution | `workers`、`persistentWorkers`、`save_cadence`、`saveCadence` | `execution.*` |

整數與 boolean 可用型別正確的值或無損字串（例如 `"4"`、`"true"`、`"0"`）；
learning rate 接受正數或可正規化的數字字串；Text Encoder learning rate 接受 scalar
或 list；optimizer/scheduler args 接受 mapping、`key=value` list 或空白分隔的
`key=value` 字串，raw `--flags`、重複 key 與非 `key=value` token 會被拒絕。
Warmup 接受整數 steps shorthand、`{mode: "steps" | "ratio", value: N}`，或
`lr_warmup_steps` / `warmup_ratio` aliases；不接受 bare `"steps"` / `"ratio"`。
Seed 可用固定整數、`"random"` / `null` 或 `{mode, value}`；`fp32` 會正規化為
`mixed_precision="no"`。

同一 canonical 欄位若由多個 alias 給出衝突值，回
`recipe_field_conflict`；未知欄位、拼字錯誤或有損 coercion 回
`recipe_validation_failed`。Agent 應依 `error.details.issues[]` 的安全 location、
accepted forms 與 suggestion 修正，不得猜測或覆寫衝突意圖。

MCP 回傳採穩定 envelope。成功只保留該工具白名單中的欄位：

```json
{
  "ok": true,
  "tool": "lora_training_decision_preflight",
  "decision": "train",
  "recipe_hash": "<sha256>",
  "start_payload": {
    "folder": "my_char",
    "expected_dataset_hash": "<sha256>",
    "expected_profile_hash": "<sha256>",
    "recipe": {
      "schema_version": "lora-training-recipe/v1",
      "expected_recipe_hash": "<same recipe_hash>",
      "optimization": {
        "seed": {
          "mode": "random",
          "value": 123456789,
          "source": "preflight_policy"
        }
      }
    }
  }
}
```

失敗固定為修復指南；HTTP/protocol 失敗可能另有 `status_code`：

```json
{
  "ok": false,
  "tool": "lora_train_start",
  "error": {
    "code": "recipe_validation_failed",
    "message": "Backend rejected the LoRA request",
    "hint": "correct the referenced fields and rerun decision preflight",
    "details": {
      "issues": []
    }
  }
}
```

錯誤清理會移除 submitted values、URL、環境內容與任意 exception context。若舊 client
仍把 `checkpoint`、`model_family`、`epochs`、`batch_size`、`learning_rate`、
`network_*`、`anima_*`、`sdxl` 等 flat training fields 傳給 Start，protocol wrapper
回 `legacy_training_fields_removed`：只列出欄位名稱、不列值，也不會呼叫 Start。
正確修復是重跑 preflight，不能把舊 payload 暗中翻譯成 recipe。

可執行的 preflight → Start handoff：

```python
preflight = lora_training_decision_preflight(
    folder="my_char",
    recipe={"modelFamily": "anima", "batchSize": "1"},  # optional broad hints
)

if (
    preflight["ok"]
    and preflight["decision"] == "train"
    and preflight["start_payload"]
):
    payload = preflight["start_payload"]
    result = lora_train_start(
        folder=payload["folder"],
        expected_dataset_hash=payload["expected_dataset_hash"],
        expected_profile_hash=payload["expected_profile_hash"],
        recipe=payload["recipe"],
    )
```

Start 只能提交 preflight 回傳的完整 `start_payload`。不要重建、merge、補 default、
重抽 seed 或覆寫其中欄位；若使用者改了任何 hint，重跑 preflight 並改用新的
`start_payload`。

```json lora-recipe-contract
{
  "schema_version": "lora-training-recipe/v1",
  "start_required_top_level": [
    "folder",
    "expected_dataset_hash",
    "expected_profile_hash",
    "recipe"
  ],
  "recipe_input_forms": [
    "object",
    "JSON-object string"
  ],
  "canonical_recipe_fields": [
    "schema_version",
    "expected_recipe_hash",
    "model",
    "scope",
    "dataset",
    "optimization",
    "caching",
    "execution"
  ],
  "strict_error_envelope": {
    "ok": false,
    "tool": "lora_train_start",
    "error_fields": [
      "code",
      "message",
      "hint",
      "details"
    ]
  },
  "migration_error": {
    "code": "legacy_training_fields_removed",
    "invokes_start": false,
    "returns_field_names_only": true
  },
  "handoff": {
    "source": "preflight.start_payload",
    "submit_exact": true,
    "allow_rebuild_or_override": false
  }
}
```

### 影片 MCP MVP 邊界

影片生成目前是 MCP-first 的 artifact lifecycle：agent 從 CTY 提供的 known-good 本機 ComfyUI video workflow 開始，用 `search_nodes` / `get_node_schema` 檢查本機節點，修改 schema-valid 欄位後呼叫 `generate_video_custom_workflow`，再用 `get_generation_status` 的 `artifacts[]` 和 `get_gallery_artifact` 取回影片檔。

此 MVP 不包含：自動安裝 / 下載 ComfyUI nodes、第三方 partner/API video nodes、frontend video gallery UI、backend 從自然語言合成完整 video graph。未經本機成功驗證的 video workflow 不應寫成模板 manifest。

---

## 七、自然語言範例

在 Composer 中可直接說：

- **「產生初音、動漫風格的圖」** → 呼叫 `generate_image(character="初音", style="動漫")`
- **「用 default 模板產生穿和服的初音」** → 呼叫 `list_workflow_templates` → `get_workflow_template("default")` → `generate_image_custom_workflow(workflow=..., character="初音", prompt="1girl, kimono")`
- **「開始訓練 my_char 資料夾的 LoRA」** → 先呼叫 `lora_training_decision_preflight(folder="my_char")`；只有 `decision="train"` 且 `start_payload` 存在時，才把該 payload 的四個欄位原樣交給 `lora_train_start`
- **「用 Anima 訓練 my_char」** → 把 `recipe={"modelFamily": "anima", "animaQwen3": "...", "animaVae": "..."}` 作為 preflight hint；取得 `decision="train"` 後只提交其完整 `start_payload`
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
