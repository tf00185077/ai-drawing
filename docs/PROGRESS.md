# 進度追蹤

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 完整 task spec 見 `docs/task-specs/`。

---

## 目前聚焦

OpenClaw × ai-drawing 本地繪圖 / MCP 整合已建立交接計畫：`docs/openclaw-ai-drawing-mcp-handoff.md`。

目前執行位置：Phase 1~5 文件化流程已完成。最小 MCP 閉環已通過單元測試與本機實測，且 OpenClaw MCP 繪圖 SOP 已整理完成。

---

## 已完成

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
- [x] 多 workflow 模板切換（Anima 支援，2026-06-17）：`generate_image` 新增 `template` 參數，可在不另開 tool 的情況下切換模板（如 `anima`）。後端 `apply_params` 支援 diffusion-model 家族節點（`UNETLoader.unet_name`、`EmptySD3LatentImage` 寬高/batch）；`queue.py` 改為「自訂 workflow > 指定 template > 依 lora 推斷預設」優先序，且僅含 `CheckpointLoaderSimple` 的傳統 workflow 才套用預設 checkpoint，避免把傳統 checkpoint 名稱注入 Anima 的 UNETLoader。動到 `mcp-server/.../generate.py`、`backend/app/schemas/generate.py`、`backend/app/api/generate.py`、`backend/app/core/queue.py`、`backend/app/core/workflow.py`。backend `113 passed`、mcp-server `50 passed`（4 個既有失敗與本次無關）。
- [x] MCP README tool 清單同步（2026-06-17）：`mcp-server/README.md` 更新為完整 23 個 tool（分組並標示與純文字版重疊的 JSON 版），補上先前漏列的 `get_generation_status`、`get_job_status`、`cancel_job`、`list_resources`、`get_available_resources`、`caption_image`、`get_gallery_image`、`free_comfyui_memory`。

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

（目前無）

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
