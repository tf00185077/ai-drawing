# 進度追蹤

> **唯一來源**。完成的任務要同步修改這個文件（`docs/PROGRESS.md`），且不需同步改 README.md 或 AGENTS.md。
> 完整 task spec 見 `docs/task-specs/`。

---

## 目前聚焦

F-F（LLM 自動 caption）已完成並合併。無待辦任務。

---

## 已完成

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

目前無待辦任務。

---

## 卡住 / 待決策

| 項目 | 原因 | 需要 |
|------|------|------|
| Skill 文件 | openclaw skill 格式未確認 | 確認工具名稱 / 框架後才能開始 |
