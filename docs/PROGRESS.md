# 進度追蹤

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 完整 task spec 見 `docs/task-specs/`。

---

## 目前聚焦

OpenClaw × ai-drawing 本地繪圖 / MCP 整合已建立交接計畫：`docs/openclaw-ai-drawing-mcp-handoff.md`。

目前執行位置：Phase 1~5 文件化流程已完成。最小 MCP 閉環已通過單元測試與本機實測，且 OpenClaw MCP 繪圖 SOP 已整理完成。

---

## 已完成

### 修復
- [x] `list_resources` tool 回傳 `{}`（2026-06-17）：tool 名稱與 MCP 協定內建的 `resources` primitive（`resources/list`）撞名，agent 端被路由到沒掛任何 resource 的 `resources/list` → 空 `{}`，而非真正的 tool。backend 與 tool 邏輯本身正常。改名為 `list_available_resources`（與 backend `available-resources` 端點同名、避開 primitive），同步更新 `generate.py`、tests、`mcp-server/README.md`、`docs/mcp-setup.md`、`docs/openclaw-mcp-drawing-sop.md`。歷史規劃/SOP 記錄文件保留原名不動。`uv run pytest tests/ -q` → `43 passed`。
- [x] MCP tool 呼叫時 `McpSettings` 驗證錯誤（`Extra inputs are not permitted`，2026-06-17）：root cause 是 `config.py` 用了 pydantic 核心的 `ConfigDict` + 相對路徑 `env_file=".env"`，Hermes 從 `~/.hermes` 啟動時把 `~/.hermes/.env` 整包當成 extra 欄位吃進來。改為 `SettingsConfigDict(env_prefix="MCP_", extra="ignore")` 並移除 `env_file`，只讀 `MCP_*` 真實環境變數。已在汙染 CWD `.env` + process env 下驗證初始化正常。

### OpenClaw × ai-drawing 本地繪圖 / MCP 整合
- [x] Phase 1 backend 低負載繪圖驗證（2026-06-11）：backend `8001` → ComfyUI `8188` → gallery 閉環成功，job `27920202-569f-4880-abc2-7a9f477d0094`，輸出 PNG 512×512。
- [x] Phase 2 OpenClaw backend 繪圖 SOP（2026-06-11）：建立 `docs/openclaw-backend-drawing-sop.md`，包含可用 curl/HTTP 範例、成功/失敗判斷、資源限制與 busy 處理規則。
- [x] Phase 3 Step 1 MCP config / URL（2026-06-11）：`config.py` 預設 `8001`，新增 `test_config.py`，`uv run python -m pytest tests/ -q` → 通過。
- [x] Phase 3 Step 2 `list_resources`（2026-06-11）：agent-friendly JSON，`5 passed`。
- [x] Phase 3 Step 3 `generate_image`（2026-06-11）：回傳含 `job_id/status/submitted/next`，`4 passed`。
- [x] Phase 3 Step 4 `get_generation_status`（2026-06-12）：queued/running/completed/error 四種狀態，`10 passed`，完整回歸 `42 passed`。
- [x] Phase 3 Step 5 `get_gallery_image`（2026-06-12）：回傳 `image_url`、`local_path`、metadata 與 JSON 錯誤結構，`uv run pytest tests/test_tools.py -k 'gallery_image or gallery_detail' -q` → `4 passed`。
- [x] Phase 3 Step 6 `free_comfyui_memory`（2026-06-12）：新增 ComfyUI `/free` wrapper，`uv run pytest tests/ -k 'free_comfyui_memory or comfyui' -q` → `3 passed`。
- [x] Phase 3 Step 7 registration / docs（2026-06-12）：MCP server 載入新 tools，`docs/mcp-setup.md` 與 `mcp-server/README.md` 已同步最小閉環 tool 清單，`uv run pytest tests/test_server.py -q` → `3 passed`。
- [x] Phase 3 Step 8 完整單元測試（2026-06-12）：`uv run pytest tests/ -q` → `50 passed`。
- [x] Phase 3 Step 9 本機 backend / ComfyUI MCP smoke test（2026-06-12）：以 MCP tools 完成 `list_resources → generate_image → get_generation_status → get_gallery_image → free_comfyui_memory` 閉環；job `c99167aa-4370-47e1-ae09-2b97d5f18978`、image `2`、輸出 `outputs/gallery/2026-06-12/ComfyUI_00008__c99167aa_0.png`、PNG 512×512，測試後 queue 為空。
- [x] Phase 4 Hermes / agent MCP 實際驗證（2026-06-12）：已由 Hermes 實際透過 MCP tools 完成一次生圖與查詢，不再依賴 curl/HTTP 手動操作。
- [x] Phase 5 OpenClaw MCP 繪圖 SOP（2026-06-15）：建立 `docs/openclaw-mcp-drawing-sop.md`，根據本機 `openclaw mcp show` 設定與真 stdio MCP 驗證整理 OpenClaw agent 使用規則、`openclaw mcp set` 範例與最小閉環操作順序；當日再次實測 job `3a18d370-3726-4fcf-b91b-b838fb6e4b87`、image `6`、輸出 `outputs/gallery/2026-06-15/ComfyUI_00012__3a18d370_0.png`。
- [x] 記錄 Anima 元件以支援重生（2026-06-17）：`GeneratedImage` 新增 `template` / `diffusion_model` / `text_encoder` / `vae` 四欄。`workflow.py` 加 `extract_model_files_from_workflow`，並讓 `apply_params` 支援注入 `UNETLoader.unet_name`（diffusion_model，退回 checkpoint）/ `CLIPLoader.clip_name`（text_encoder）/ `VAELoader.vae_name`（vae）。`queue.py` 於送出後反解實際 workflow 的模型檔並寫回 job 參數 → `recording.save()` 一併記錄。`gallery_rerun` 帶回 template + 三個元件，確保 Anima 等非傳統 checkpoint 可正確重生；gallery 列表/詳情/CSV 匯出與 MCP `get_gallery_image` metadata 也補上這些欄位。`scripts/init_db.py` 加 idempotent `ensure_columns()`（ALTER TABLE ADD COLUMN），已對既有 `auto_draw.db` 補欄位（保留原 5 筆）。backend `113 passed`、mcp-server `43 passed`（4 既有失敗無關），並以單元模擬驗證「生圖→記錄→重生」模型檔一致。
- [x] diffusion-model 元件目錄與資源列舉（2026-06-17）：新增 `comfyui_diffusion_models_dir` / `comfyui_text_encoders_dir` / `comfyui_vae_dir` 三個設定（`config.py` 預設 + `.env` / `.env.example`，本機指向 `/Users/tf00185088/comfyui/models/{diffusion_models,text_encoders,vae}`）。`resources.py` 加 `list_diffusion_models` / `list_text_encoders` / `list_vaes`，`/api/generate/available-resources` 與 MCP `list_resources` 一併回傳 `diffusion_models` / `text_encoders` / `vaes`。實測抓到 `anima_preview3Base.safetensors`、`qwen_3_06b_base.safetensors`、`qwen_image_vae.safetensors`。
- [x] 多 workflow 模板切換（Anima 支援，2026-06-17）：`generate_image` 新增 `template` 參數，可在不另開 tool 的情況下切換模板（如 `anima`）。後端 `apply_params` 支援 diffusion-model 家族節點（`UNETLoader.unet_name`、`EmptySD3LatentImage` 寬高/batch）；`queue.py` 改為「自訂 workflow > 指定 template > 依 lora 推斷預設」優先序，且僅含 `CheckpointLoaderSimple` 的傳統 workflow 才套用預設 checkpoint，避免把傳統 checkpoint 名稱注入 Anima 的 UNETLoader。動到 `mcp-server/.../generate.py`、`backend/app/schemas/generate.py`、`backend/app/api/generate.py`、`backend/app/core/queue.py`、`backend/app/core/workflow.py`。backend `113 passed`、mcp-server `50 passed`（4 個既有失敗與本次無關）。
- [x] 移除重複的純文字 tool（2026-06-17）：刪掉 `get_job_status`、`get_available_resources`、`gallery_detail` 三個早期純文字版，只保留對應的 agent-friendly 結構化版（`get_generation_status`、`list_resources`、`get_gallery_image`）。一併清掉相關測試與 README 條目；server 註冊 tool 由 23 → **20**，skill 未參照這三者故不受影響。mcp-server `43 passed`。
- [x] MCP README tool 清單同步（2026-06-17）：`mcp-server/README.md` 更新為完整 23 個 tool（分組並標示與純文字版重疊的 JSON 版），補上先前漏列的 `get_generation_status`、`get_job_status`、`cancel_job`、`list_resources`、`get_available_resources`、`caption_image`、`get_gallery_image`、`free_comfyui_memory`。
- [x] `add-style-preset-catalog`（openspec change，2026-06-19）：新增風格預設目錄（創作者／風格食譜）。後端 `backend/app/core/style_presets.py` 以 JSON（`backend/style_presets/catalog.json`，sample-safe 空清單）為執行期來源，提供 `list_presets`/`get_preset`/`validate_presets`/`compose`，prompt 依固定順序組裝（base → profile prefix → content_prompt → profile suffix），負面 prompt 兩層合併，參數優先序 default_params < profile params < overrides；`validate_presets` 會同時檢查模型/template 資源、`note_path` 是否存在、Markdown frontmatter `preset_id` 是否與 catalog `id` 一致。新增 `GET/POST /api/style-presets`（list / `{id}` / validate / `{id}/compose`）與 schemas；`compose` 採 compose-first-generate-second，回傳可直接餵 `generate_image` 的 `generation` payload。一般生圖 `GenerateRequest` + `trigger_generate` 補上 `diffusion_model`/`text_encoder`/`vae`，讓 Anima 等 diffusion-family preset 不必改走 `/custom`。MCP 新增 `list_style_presets`/`get_style_preset`/`validate_style_presets`/`compose_style_preset` 四個 agent-friendly tool（`ok`/`tool`/`next`/結構化錯誤），`generate_image` 同步補三個 diffusion 元件參數。文件：`mcp-server/README.md`（20→24 tool + 新章節）、`docs/api-contract.md`（5c 風格預設模組 + 生圖新欄位）、`docs/openclaw-mcp-drawing-sop.md`（preset 模式／手動模式分流，僅在無對應 preset 時才問是否新增）。測試：backend 新增 `test_style_presets.py`（18）+ `test_style_presets_api.py`（10）；mcp-server 新增 `test_style_presets.py`（10）+ e2e dry path `test_style_preset_e2e.py`（1，compose→generate_image 轉送）。backend `149 passed`、mcp-server `56 passed`（4 個 backend 既有失敗與本次無關：config-path cwd、兩個 lora_trainer mock、缺檔 `honoka_pose_controlnet` 模板）。
- [x] `enhance-custom-workflow-tool`（openspec change，2026-06-18）：`generate_image_custom_workflow` 補上 `image`（img2img 主體）、`mask`（inpaint）、`batch_size`、`diffusion_model`/`text_encoder`/`vae` 參數通道。**Breaking（僅 custom 路徑）**：`apply_params` 改為「僅在呼叫端明確提供時才覆寫」`steps`/`cfg`/`seed`，省略時保留提交 workflow JSON 原值（解決 hires-fix / 多 KSampler 被強制覆寫的問題）；預設值（20/7.0）與隨機 seed 的職責從 `apply_params` 移到 `queue.py` 的 template 分支，`generate_image`（template 路徑）行為不變。新增 `LoadImageMask` 注入（獨立 class_type，與 subject/pose 的位置式注入無衝突）與 `backend/workflows/inpaint.json` 模板。動到 `backend/app/core/{workflow,queue}.py`、`backend/app/schemas/generate.py`、`backend/app/api/generate.py`、`mcp-server/mcp_server/tools/generate.py`。backend `121 passed`（4 個既有失敗與本次無關：`test_relative_defaults_are_project_root_based_from_any_cwd`、兩個 `test_lora_trainer` mock 案例、`honoka_pose_controlnet` 缺檔模板）、mcp-server `45 passed`。

### 路徑正規化修正（2026-06-09）
- [x] `backend/app/config.py` 將 DB / output / gallery / lora_train / sd-scripts / watch_dirs 的相對路徑統一正規化為 **project root 基準**
- [x] 修正 `DATABASE_URL` 為 sqlite 相對路徑時會隨啟動 cwd 漂移的問題
- [x] 新增 `backend/tests/test_config_paths.py`，驗證 defaults 與 env override 在不同 cwd 下都解析到同一位置
- [x] 實測 `POST /api/generate/` 成功，輸出與 DB 記錄固定落在 `backend/` 路徑下

### F-F：LLM 自動產生 Caption (2026-06-07)
- [x] 後端 LLM caption API：`POST /api/lora-docs/caption-llm/{image_path}`
- [x] MCP tool：`caption_image(image_path)`
- [x] 新增 `llm_caption_url` 環境變數（`.env`）
- [x] 支援外部 LLM API（如 BLIP2 service）
- [x] 完成驗證：呼叫 MCP tool → LLM 產生 → 寫入 .txt

### 系統基礎建置
- [x] ComfyUI API 串接（`backend/app/core/comfyui.py`）
- [x] Workflow JSON 模板管理（`backend/app/core/workflow.py`）
- [x] 批次生圖排程器（`backend/app/core/queue.py`）
- [x] 資料庫設計（`backend/app/db/models.py`）
- [x] 自動記錄 Pipeline（`backend/app/core/recording.py`）
- [x] Gallery 瀏覽器 + 一鍵重現（`backend/app/api/gallery.py`）
- [x] LoRA 文件工具（watcher、caption editor、zip download）
- [x] LoRA 訓練執行器（`backend/app/services/lora_trainer.py`）
- [x] MCP Server 基礎建置（`mcp-server/`）
- [x] MCP Tools 初版（generate、lora_train、gallery）
- [x] Docker 部署
- [x] F-B Job 狀態查詢（DB job_id + API endpoint + MCP tool）
- [x] F-C Job 取消（`queue.cancel()` + `DELETE /api/generate/queue/{job_id}` + MCP tool，PR #4，2026-06-07）
- [x] F-D 查詢可用資源（純 MCP tool，API 已有）
- [x] F-A 生圖完整參數（lora_strength、denoise、width/height、sampler_name、scheduler 暴露至 MCP，2026-06-07）
- [x] F-E LoRA 訓練完整參數（移除 generate_after + MCP 補齊參數，PR #5，2026-06-07）

### Phase 0：Slack 清理（PR #1，2026-06-04）
- [x] 刪除 Slack service 檔案
- [x] 移除 main.py Slack 啟動邏輯
- [x] 移除 config Slack token 欄位
- [x] 移除 schema slack_channel_id / slack_thread_ts
- [x] 更新 README / AGENTS 移除 Slack 相關章節

---

## 進行中

- [ ] `add-agent-workflow-authoring`（openspec change，2026-06-19 起）：把重心從「人供給固定模板」轉成「供給 agent 能力＋護欄」，讓 agent 自組 workflow 為主路徑、模板庫自我擴充。6 個階段，**一次做一階段、階段間 review**。
  - [x] #1 ComfyUI 節點 schema grounding（單點查）：`ComfyUIClient.get_object_info`（以 base_url 為 key 的程序內 TTL 快取，新增 `comfyui_object_info_ttl` 設定，可 `force_refresh`／`clear_object_info_cache` 失效）＋純函式 `search_node_types`（名稱＋類別雙條件 AND，回 `{name, category}`）／`list_node_categories`／`extract_node_schema`；新增 `GET /api/comfyui/nodes`（依 query/category 搜尋）、`/api/comfyui/node-categories`（列類別＋數量）、`/api/comfyui/nodes/{node_type}`（單節點 input/output 規格，缺則 404），於 `main.py` 註冊；MCP 新增 `search_nodes`（query＋category）／`list_node_categories`／`get_node_schema` 三個 agent-friendly tool（404→`not_found`）。測試：backend `test_comfyui_nodes.py`（15）、mcp-server `test_comfyui_tools.py`（6）。**真機驗證**：對 live ComfyUI（8188, 747 節點）實測名稱搜尋、類別搜尋（`category=loaders` 找到 CLIPLoader/DualCLIPLoader/UNETLoader/VAELoader 等 text-encoder 載入器）、query+category 組合、單節點 schema、未知節點 404/not_found、TTL 快取命中（0ms 同物件）vs `force_refresh` 重抓；MCP→backend→ComfyUI 全鏈路通。backend 在本機新建 `backend/.venv`（py3.11，本機原僅 3.9 系統＋3.10 bare），4 個既有失敗與本次無關（config-path cwd、兩個 lora_trainer mock、workflow bbox detector）。
  - **Context 防護**（2026-06-19）：雙重把關——(1) `search_nodes` 的 `query`/`category` **至少要給一個，皆空回 400**（backend 端，連 `/object_info` 都不抓；MCP 端同步先擋回 `missing_filter` 不打 backend），擋「完全不篩」；(2) 每頁**上限**（預設 50、上限 200），擋「篩了但範圍太寬」；(3) 加 `offset` **分頁**（命中按名稱排序、回 `offset`/`next_offset`/`truncated`），讓超過上限的尾巴仍可翻頁取得（避免「永遠拿不到後面」），但 `next` 仍引導優先縮小條件、翻頁為退路。真機驗證 `category=model` 274 個 → 6 頁全取回。`list_node_categories` 維持**無參數**作為探索入口（先瀏覽 144 類再 `search_nodes(category=…)`）。`get_object_info` 原始 1.2MB 僅 backend 內部用、永不回給 agent。COMBO 維持壓成 `"COMBO"` 不回可選值（定案，可選值走 `list_available_resources`）。真機驗證：無參數→400、`category=loaders`→35 筆、`node-categories`→144 類。spec 新增「依名稱/類別搜尋」與「搜尋有界以保護 context（強制給參數＋上限）」requirement，`openspec validate` 通過。
  - [ ] #2 模板能力 manifest＋索引（受控詞彙二元標籤）
  - [ ] #3 二元 reuse 匹配（superset 測試）
  - [ ] #4 custom workflow 轉發 ComfyUI 驗證錯誤
  - [ ] #5 回填／自我擴充模板庫（成功閘門＋key 去重＋家族歸檔＋版本化不就地改）
  - [ ] #6 agent 指引＋consolidation
  - artifacts：`openspec/changes/add-agent-workflow-authoring/`（proposal/design/specs/tasks，已 `openspec validate` 通過）。

---

## 待做

OpenClaw × ai-drawing 本地繪圖 / MCP 整合：

1. [x] 透過 ai-drawing backend 端點進行低負載繪圖驗證
2. [x] 整理 OpenClaw backend 繪圖 SOP
3. [x] 將 ai-drawing 繪圖最小閉環做成 MCP tools
4. [x] 透過 MCP 實際完成一次繪圖驗證
5. [x] 整理 OpenClaw MCP 繪圖 SOP

詳細順序、狀態與驗證標準見 `docs/openclaw-ai-drawing-mcp-handoff.md`。

---

## 卡住 / 待決策

| 項目 | 原因 | 需要 |
|------|------|------|
| backend 生圖 queue 隊首阻塞（2026-06-16） | `backend/app/core/queue.py` 在 submit failure 時會把 job 插回隊首，可能造成壞 job 無限重試並堵住後續任務 | 修 queue failure-handling（retry_count / last_error / retry 上限 / failed 狀態）；詳見 `docs/backend-generate-queue-head-blocking-2026-06-16.md` |
| Skill 文件 | openclaw skill 格式未確認 | 確認工具名稱 / 框架後才能開始 |
