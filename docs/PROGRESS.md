# 進度追蹤

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 完整 task spec 見 `docs/task-specs/`。

---

## 目前聚焦

OpenClaw × ai-drawing 本地繪圖 / MCP 整合已建立交接計畫：`docs/openclaw-ai-drawing-mcp-handoff.md`。

目前執行位置：尚未開始 Phase 1；下一步是透過 ai-drawing backend 端點實際進行一次低負載繪圖驗證。

---

## 已完成

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

1. [ ] 透過 ai-drawing backend 端點進行低負載繪圖驗證
2. [ ] 整理 OpenClaw backend 繪圖 SOP
3. [ ] 將 ai-drawing 繪圖最小閉環做成 MCP tools
4. [ ] 透過 MCP 實際完成一次繪圖驗證
5. [ ] 整理 OpenClaw MCP 繪圖 SOP

詳細順序、狀態與驗證標準見 `docs/openclaw-ai-drawing-mcp-handoff.md`。

---

## 卡住 / 待決策

| 項目 | 原因 | 需要 |
|------|------|------|
| Skill 文件 | openclaw skill 格式未確認 | 確認工具名稱 / 框架後才能開始 |
